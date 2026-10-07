#!/usr/bin/env python3
"""
PR Supersession Detector CLI
Detects and closes superseded, zero-diff, and redundant bot PRs across repositories.
"""

import argparse
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def run_cmd(cmd, cwd=None, timeout=60):
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )
        if res.returncode != 0:
            return None, res.stderr.strip()
        return res.stdout.strip(), None
    except Exception as e:
        return None, str(e)

def find_local_repo(base_dir, repo_name):
    if not base_dir:
        return None
    repo_basename = repo_name.split("/")[-1]
    candidates = [
        os.path.join(base_dir, repo_basename),
        os.path.join(base_dir, repo_name),
        base_dir if os.path.basename(os.path.abspath(base_dir)) == repo_basename else None
    ]
    for c in candidates:
        if c and os.path.exists(os.path.join(c, ".git")):
            return os.path.abspath(c)
    # Search one level deeper for submodules
    if os.path.exists(base_dir):
        for root, dirs, _ in os.walk(base_dir):
            if os.path.basename(root) == repo_basename and os.path.exists(os.path.join(root, ".git")):
                return os.path.abspath(root)
    return None

def fetch_open_prs(repo):
    out, err = run_cmd(f"gh pr list -R {repo} --state open --json number,title,author,headRefName,baseRefName,files --limit 100")
    if not out:
        return []
    try:
        return json.loads(out)
    except Exception:
        return []

def check_zero_diff(repo, pr_num, base_ref):
    out, _ = run_cmd(f"gh pr diff {pr_num} -R {repo}")
    if not out:
        return True, "Zero diff output returned from GitHub"
    
    # Filter out agent memory files
    code_diff_lines = []
    in_jules_file = False
    for line in out.splitlines():
        if line.startswith("diff --git"):
            in_jules_file = ".jules/" in line or ".github/" in line
        if not in_jules_file:
            if line.startswith("+") or line.startswith("-"):
                if not line.startswith("+++") and not line.startswith("---"):
                    code_diff_lines.append(line)
    
    if not code_diff_lines:
        return True, "PR diff modifies only agent memory / log files with zero functional code changes"
    return False, None

def check_gemfile_superseded(repo, pr, local_repo):
    if not local_repo:
        return False, None
    title = pr.get("title", "")
    match = re.search(r'(?:bump|update)\s+([a-zA-Z0-9_\-]+)\s+(?:from\s+[0-9\.]+\s+)?to\s+([0-9\.]+)', title, re.IGNORECASE)
    if not match:
        return False, None
    
    gem_name, target_version = match.group(1), match.group(2)
    gemfile_lock = os.path.join(local_repo, "Gemfile.lock")
    if not os.path.exists(gemfile_lock):
        return False, None
    
    try:
        with open(gemfile_lock, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        spec_match = re.search(rf'^\s+{re.escape(gem_name)}\s+\(([0-9\.]+)\)', content, re.MULTILINE)
        if spec_match:
            current_version = spec_match.group(1)
            if current_version == target_version:
                return True, f"Target version {gem_name} ({target_version}) is already satisfied on base branch"
    except Exception:
        pass
    return False, None

def check_directive_violations(repo, pr_num):
    diff_out, _ = run_cmd(f"gh pr diff {pr_num} -R {repo}")
    if not diff_out:
        return False, None
    
    # Check for conflict markers
    if re.search(r'^\+([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))', diff_out, re.MULTILINE):
        return True, "PR introduces unresolved Git merge conflict markers"
    
    # Check for scratch verification files
    if re.search(r'diff --git a/test(_.*)?\.(js|ts)', diff_out):
        return True, "PR commits temporary scratch verification files contrary to repository directives"
        
    return False, None

def is_bot_pr(pr):
    author = pr.get("author", {}).get("login", "").lower() if isinstance(pr.get("author"), dict) else ""
    head = pr.get("headRefName", "").lower()
    title = pr.get("title", "").lower()
    return any(b in author for b in ["jules", "sentinel", "bolt", "palette", "dependabot"]) or \
           any(b in head for b in ["jules", "sentinel", "bolt", "palette", "dependabot", "optimize-"]) or \
           any(b in title for b in ["⚡ bolt:", "jules:", "sentinel:", "palette:"])

def check_journal_only(pr):
    files = [f.get("path", "") for f in pr.get("files", [])]
    if not files:
        return False, None
    non_meta_files = [f for f in files if not f.startswith(".jules/") and not f.startswith(".Jules/") and not f.startswith(".github/")]
    if not non_meta_files:
        return True, "PR contains only .jules/ journal notes or workflow files without functional code changes"
    return False, None

def check_pairwise_supersession(prs):
    superseded = {}
    bot_prs = [pr for pr in prs if is_bot_pr(pr)]
    for i in range(len(bot_prs)):
        pr_a = bot_prs[i]
        num_a = pr_a.get("number")
        files_a = {f["path"] for f in pr_a.get("files", []) if not f["path"].startswith(".jules/")}
        if not files_a:
            continue
        for j in range(len(bot_prs)):
            if i == j:
                continue
            pr_b = bot_prs[j]
            num_b = pr_b.get("number")
            if num_b <= num_a:
                continue
            files_b = {f["path"] for f in pr_b.get("files", []) if not f["path"].startswith(".jules/")}
            if files_a and files_a.issubset(files_b):
                superseded[num_a] = f"Superseded by PR #{num_b} ({pr_b.get('title')}) covering overlapping target files: {', '.join(sorted(files_a))}"
    return superseded

def analyze_repo_prs(repo, local_base_dir):
    prs = fetch_open_prs(repo)
    if not prs:
        return []

    local_dir = find_local_repo(local_base_dir, repo) if local_base_dir else None
    results = []
    processed_pr_nums = set()

    # 1. Pairwise Supersession Check across open bot PRs
    pairwise_map = check_pairwise_supersession(prs)
    for pr in prs:
        pr_num = pr.get("number")
        if pr_num in pairwise_map:
            results.append({
                "repo": repo,
                "number": pr_num,
                "title": pr.get("title"),
                "status": "SUPERSEDED",
                "reason": pairwise_map[pr_num],
                "action": "close"
            })
            processed_pr_nums.add(pr_num)

    for pr in prs:
        pr_num = pr.get("number")
        if pr_num in processed_pr_nums:
            continue
        base = pr.get("baseRefName", "main")
        
        # 2. Journal-only Check
        is_journal, journal_reason = check_journal_only(pr)
        if is_journal:
            results.append({
                "repo": repo,
                "number": pr_num,
                "title": pr.get("title"),
                "status": "INVALID",
                "reason": journal_reason,
                "action": "close"
            })
            continue

        # 3. Zero Diff Check
        is_zero, zero_reason = check_zero_diff(repo, pr_num, base)
        if is_zero:
            results.append({
                "repo": repo,
                "number": pr_num,
                "title": pr.get("title"),
                "status": "SUPERSEDED",
                "reason": zero_reason,
                "action": "close"
            })
            continue

        # 4. Dependency Already Satisfied Check
        is_dep_sat, dep_reason = check_gemfile_superseded(repo, pr, local_dir)
        if is_dep_sat:
            results.append({
                "repo": repo,
                "number": pr_num,
                "title": pr.get("title"),
                "status": "SUPERSEDED",
                "reason": dep_reason,
                "action": "close"
            })
            continue

        # 5. Directive Violation Check
        is_viol, viol_reason = check_directive_violations(repo, pr_num)
        if is_viol:
            results.append({
                "repo": repo,
                "number": pr_num,
                "title": pr.get("title"),
                "status": "INVALID",
                "reason": viol_reason,
                "action": "close"
            })
            continue

    return results

def main():
    parser = argparse.ArgumentParser(description="PR Supersession Detector")
    parser.add_argument("--repo", help="Target GitHub repository (e.g. bjohnson1279/ruby-crm)")
    parser.add_argument("--owner", help="GitHub owner to scan all repositories")
    parser.add_argument("--base-dir", default="C:/Users/johns/DEV", help="Base directory of local git repositories")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without modifying PRs")
    parser.add_argument("--execute", action="store_true", help="Execute automated PR closures")
    args = parser.parse_args()

    repos = []
    if args.repo:
        repos.append(args.repo)
    elif args.owner:
        out, _ = run_cmd(f"gh repo list {args.owner} --limit 100 --json nameWithOwner")
        if out:
            try:
                data = json.loads(out)
                repos = [r["nameWithOwner"] for r in data]
            except Exception:
                pass

    if not repos:
        print("[ERROR] No repositories specified or found.")
        sys.exit(1)

    print(f"Scanning {len(repos)} repository(ies) for superseded or invalid PRs...")
    all_findings = []
    for r in repos:
        findings = analyze_repo_prs(r, args.base_dir)
        if findings:
            all_findings.extend(findings)
            for f in findings:
                print(f"  [FOUND] {f['repo']}#{f['number']}: {f['status']} - {f['reason']}")

    if not all_findings:
        print("[OK] No superseded or invalid open PRs detected.")
        return

    print(f"\nTotal action items identified: {len(all_findings)}")
    if args.execute and not args.dry_run:
        print("Executing automated closures...")
        for f in all_findings:
            cmd = f'gh pr close {f["number"]} -R {f["repo"]} --comment "Closing as {f["status"].lower()}: {f["reason"]}."'
            print(f"  Closing {f['repo']}#{f['number']}...")
            out, err = run_cmd(cmd)
            if out is not None:
                print(f"  ✅ Closed {f['repo']}#{f['number']}")
            else:
                print(f"  ❌ Failed to close {f['repo']}#{f['number']}: {err}")
    else:
        print("Dry run complete. Use --execute to automatically close detected PRs.")

if __name__ == "__main__":
    main()
