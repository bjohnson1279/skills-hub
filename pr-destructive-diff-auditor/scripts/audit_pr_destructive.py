#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys

# Force UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRATCH_PATTERNS = [
    r'^(test(_.*)?\.(ts|js|cjs|mjs|sh|bash|py|php)|test.*\.cjs)$',
    r'^(fix_.*\.(php|cjs|js|ts|sh)|update_.*\.(php|cjs|js|ts|sh))$',
    r'^(scratch_.*|temp_.*|test_reduce\.cjs|plan\.md)$'
]

CRITICAL_PATHS = [
    "schema.prisma",
    "index.ts",
    "index.php",
    "init.sql",
    "schema.sql",
    "routes.php",
    "composer.json",
    "package.json",
    "graphql.ts",
    "api.ts",
    "client.ts",
    "endpoints.ts",
    "server.ts",
    "app.ts",
    "main.py"
]

def run_cmd(cmd, cwd=None):
    try:
        is_shell = isinstance(cmd, str)
        res = subprocess.run(cmd, shell=is_shell, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=cwd)
        return res.stdout.strip(), res.stderr.strip(), res.returncode
    except Exception as e:
        return "", str(e), 1

def find_local_repo(base_dir, repo_name):
    search_dirs = [base_dir] if base_dir else []
    dev_default = "C:/Users/johns/DEV"
    if dev_default not in search_dirs and os.path.exists(dev_default):
        search_dirs.append(dev_default)

    repo_basename = repo_name.split("/")[-1]
    for b in search_dirs:
        candidates = [
            os.path.join(b, repo_basename),
            os.path.join(b, repo_name),
            b if os.path.basename(os.path.abspath(b)) == repo_basename else None
        ]
        for c in candidates:
            if c and os.path.exists(os.path.join(c, ".git")):
                return os.path.abspath(c)
        if os.path.exists(b):
            for root, dirs, _ in os.walk(b):
                if os.path.basename(root) == repo_basename and os.path.exists(os.path.join(root, ".git")):
                    return os.path.abspath(root)
    return None

def audit_pr(repo, pr_num):
    out, err, code = run_cmd(f"gh pr view {pr_num} -R {repo} --json number,title,files,headRefName,baseRefName,state")
    if code != 0 or not out:
        return {"error": f"Failed to view PR {repo}#{pr_num}: {err}"}

    pr_data = json.loads(out)
    files = pr_data.get("files", [])
    head_branch = pr_data.get("headRefName", "")
    base_branch = pr_data.get("baseRefName", "main")
    
    findings = []
    is_destructive = False
    is_scratch_polluted = False
    is_zero_diff = False
    collateral_files = []

    # 1. Scratch & verification file detection
    scratch_files = []
    for f in files:
        path_str = f.get("path", "")
        norm_path = path_str.replace('\\', '/').strip('/')
        parts = norm_path.split('/')
        if any(p in ['tests', '__tests__', 'test'] for p in parts[:-1]):
            continue
        base_filename = os.path.basename(path_str).lower()
        if any(re.match(pat, base_filename) for pat in SCRATCH_PATTERNS):
            scratch_files.append(path_str)

    if scratch_files:
        is_scratch_polluted = True
        findings.append(f"Contains uncleaned scratch/benchmark files: {', '.join(scratch_files)}")

    # 2. Critical file destructive deletions
    for f in files:
        path_str = f.get("path", "").lower()
        dels = f.get("deletions", 0)
        adds = f.get("additions", 0)
        if any(cp in path_str for cp in CRITICAL_PATHS):
            if dels > 15 and adds < 5:
                is_destructive = True
                collateral_files.append(f.get("path", ""))
                findings.append(f"Destructive line deletions in critical file '{f.get('path')}' (-{dels} / +{adds})")

    # 3. Lockfile deletion
    for f in files:
        path_str = f.get("path", "")
        if path_str in ["pnpm-lock.yaml", "package-lock.json", "composer.lock", "mix.lock"]:
            if f.get("changeType") == "DELETED" or (f.get("deletions", 0) > 100 and f.get("additions", 0) == 0):
                is_destructive = True
                findings.append(f"Unexpected deletion of lockfile: {path_str}")

    # 4. Zero functional diffs & salvageable assessment
    valid_changes = [
        f for f in files
        if not f.get("path", "").lower().startswith(".jules/")
        and not f.get("path", "").lower().startswith(".github/")
        and f.get("path", "") not in ["package.json", "package-lock.json", "composer.lock", "pnpm-lock.yaml"]
        and f.get("path", "") not in scratch_files
        and f.get("path", "") not in collateral_files
    ]
    if len(valid_changes) == 0 and len(collateral_files) == 0:
        is_zero_diff = True
        findings.append("Zero functional code diffs outside metadata/scratch files")

    is_salvageable = bool(valid_changes and (collateral_files or scratch_files))

    # 5. Unresolved Git merge conflict markers
    is_conflict_polluted = False
    diff_out, _, _ = run_cmd(f"gh pr diff {pr_num} -R {repo}")
    if diff_out:
        conflict_matches = re.findall(r'^\+([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))', diff_out, re.MULTILINE)
        if conflict_matches:
            is_conflict_polluted = True
            findings.append(f"Contains {len(conflict_matches)} unresolved Git merge conflict marker(s) in added lines")

    classification = "SAFE"
    if is_destructive or is_scratch_polluted or is_zero_diff or is_conflict_polluted:
        classification = "SALVAGEABLE" if is_salvageable else "REJECT_OR_CLOSE"

    return {
        "repo": repo,
        "number": pr_num,
        "title": pr_data.get("title"),
        "head_branch": head_branch,
        "base_branch": base_branch,
        "classification": classification,
        "is_destructive": is_destructive,
        "is_scratch_polluted": is_scratch_polluted,
        "is_conflict_polluted": is_conflict_polluted,
        "is_zero_diff": is_zero_diff,
        "is_salvageable": is_salvageable,
        "collateral_files": collateral_files,
        "scratch_files": scratch_files,
        "valid_change_count": len(valid_changes),
        "findings": findings,
        "total_files": len(files)
    }

def repair_pr(repo, pr_num, base_dir=None):
    audit = audit_pr(repo, pr_num)
    if "error" in audit:
        print(f"[ERROR] {audit['error']}")
        return False

    if not audit.get("is_salvageable"):
        print(f"[SKIP] PR {repo}#{pr_num} is not salvageable. Classification: {audit.get('classification')}")
        return False

    local_dir = find_local_repo(base_dir, repo)
    if not local_dir:
        print(f"[ERROR] Local repository for {repo} not found in {base_dir or 'C:/Users/johns/DEV'}")
        return False

    head_b = audit["head_branch"]
    base_b = audit["base_branch"]
    collateral = audit.get("collateral_files", [])
    scratches = audit.get("scratch_files", [])

    print(f"🔧 Repairing PR {repo}#{pr_num} on local repo {local_dir}...")
    run_cmd(f"git fetch origin {head_b}", cwd=local_dir)
    run_cmd(f"git checkout {head_b}", cwd=local_dir)

    actions = []
    for c_file in collateral:
        print(f"  Restoring collateral file from {base_b}: {c_file}")
        run_cmd(f'git checkout origin/{base_b} -- "{c_file}"', cwd=local_dir)
        run_cmd(f'git add "{c_file}"', cwd=local_dir)
        actions.append(f"restored {c_file}")

    for s_file in scratches:
        print(f"  Removing scratch file: {s_file}")
        run_cmd(f'git rm -f "{s_file}"', cwd=local_dir)
        actions.append(f"removed scratch {s_file}")

    if actions:
        c_msg = "chore(guardrail): repair collateral destructive deletions and remove scratch files"
        out_c, err_c, code_c = run_cmd(f'git commit -m "{c_msg}"', cwd=local_dir)
        if code_c == 0:
            print("  Pushed repaired branch to origin...")
            out_p, err_p, code_p = run_cmd(f'git push origin "{head_b}" --force', cwd=local_dir)
            if code_p == 0:
                print(f"✅ Successfully repaired PR {repo}#{pr_num}!")
                return True
            else:
                print(f"❌ Failed to push repaired branch: {err_p}")
                return False
        else:
            print(f"  No staged changes to commit or commit failed: {err_c}")

    return True

def main():
    parser = argparse.ArgumentParser(description="PR Destructive Diff & Scratch Auditor / Auto-Repair")
    parser.add_argument("--repo", required=True, help="GitHub repository (owner/repo)")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--repair", action="store_true", help="Auto-repair collateral destructive diffs and scratch pollution")
    parser.add_argument("--prune-scratch", action="store_true", help="Prune detected scratch files and push repaired branch")
    parser.add_argument("--base-dir", default="C:/Users/johns/DEV", help="Base directory containing local repos")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    if args.repair or args.prune_scratch:
        success = repair_pr(args.repo, args.pr, args.base_dir)
        sys.exit(0 if success else 1)

    result = audit_pr(args.repo, args.pr)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        cls = result.get("classification", "UNKNOWN")
        if cls == "SAFE":
            status_icon = "[SAFE]"
        elif cls == "SALVAGEABLE":
            status_icon = "[SALVAGEABLE via --repair]"
        else:
            status_icon = "[REJECT/CLOSE]"

        title = result.get("title", "")
        print(f"Audit Report for {args.repo}#{args.pr}: {title}")
        print(f"Status: {status_icon}")
        if result.get("findings"):
            print("Findings:")
            for f in result["findings"]:
                print(f"  - {f}")
        else:
            print("  - No destructive diffs or scratch artifacts found.")

        if result.get("is_salvageable"):
            print("  💡 PR contains valid functional changes alongside collateral damage. Run with --repair to auto-fix.")

if __name__ == "__main__":
    main()
