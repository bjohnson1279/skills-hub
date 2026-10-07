#!/usr/bin/env python3
"""
Bot PR Zero-Diff & Scratch Cleaner CLI
Audits and batch-closes zero-diff (already merged/superseded) and scratch-only
automated bot Pull Requests with polite audit comments and remote branch deletion.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Force UTF-8 console output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def get_base_env():
    env = os.environ.copy()
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_PAGER"] = "1"
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env

def run_cmd(cmd, cwd=None, timeout=45):
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            encoding='utf-8',
            errors='replace',
            stdin=subprocess.DEVNULL,
            env=get_base_env(),
            timeout=timeout
        )
        if res.returncode != 0:
            return None, res.stderr.strip()
        return res.stdout.strip(), None
    except Exception as e:
        return None, str(e)

def parse_gitmodules(workspace_dir):
    gitmodules_path = os.path.join(workspace_dir, ".gitmodules")
    submodules = []
    if not os.path.exists(gitmodules_path):
        return submodules
    try:
        with open(gitmodules_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return submodules

    current = {}
    for line in content.splitlines():
        line = line.strip()
        m_sec = re.match(r'^\[submodule\s+"([^"]+)"\]$', line)
        if m_sec:
            if current and "path" in current:
                submodules.append(current)
            current = {"name": m_sec.group(1)}
            continue
        m_path = re.match(r'^path\s*=\s*(.+)$', line)
        if m_path and current:
            current["path"] = m_path.group(1).strip()
            continue
        m_url = re.match(r'^url\s*=\s*(.+)$', line)
        if m_url and current:
            current["url"] = m_url.group(1).strip()
    if current and "path" in current:
        submodules.append(current)
    return submodules

def is_scratch_file(filepath):
    norm_path = filepath.replace('\\', '/').strip('/')
    parts = norm_path.split('/')
    # If the file is inside recognized test directories, it's a legitimate test suite, not a scratch script
    if any(p in ['tests', '__tests__', 'test'] for p in parts[:-1]):
        return False
    fname = os.path.basename(filepath)
    scratch_patterns = [
        r'^test[-_].*\.(c?js|ts|py|php|sh|bash)$',
        r'^fix_.*\.(php|ts|js|py|sh)$',
        r'^update_.*\.(php|ts|js|py|sh)$',
        r'.*scratch.*',
        r'^temp[-_].*',
        r'^plan\.md$'
    ]
    return any(re.match(pat, fname, re.IGNORECASE) for pat in scratch_patterns)

def audit_single_pr(repo, pr_num, local_repo_dir=None):
    """Audits an open PR to determine if it is ZERO_DIFF, SCRATCH_ONLY, or VALID."""
    out, _ = run_cmd(f"gh pr view {pr_num} -R {repo} --json number,title,headRefName,baseRefName,author,state")
    if not out:
        return None

    try:
        pr_info = json.loads(out)
    except Exception:
        return None

    if pr_info.get("state") != "OPEN":
        return None

    head = pr_info.get("headRefName")
    base = pr_info.get("baseRefName", "main")
    title = pr_info.get("title", "")

    # Get file list from diff
    diff_files_out, _ = run_cmd(f"gh pr diff {pr_num} -R {repo} --name-only")
    files = [f.strip() for f in diff_files_out.splitlines() if f.strip()] if diff_files_out else []

    # Filter out jules files for code comparison
    code_files = [f for f in files if not (f.replace('\\', '/').lower().startswith(".jules/") and f.endswith(".md"))]

    # Check scratch only
    scratch_files = [f for f in code_files if is_scratch_file(f)]
    is_scratch_only = bool(code_files and len(scratch_files) == len(code_files))

    # Check net zero-diff if local repo is available
    is_net_zero_diff = False
    if local_repo_dir and os.path.exists(os.path.join(local_repo_dir, ".git")):
        # Fetch latest base and head
        run_cmd(f"git fetch origin {base} {head}", cwd=local_repo_dir, timeout=15)
        nd_out, _ = run_cmd(f"git diff origin/{base}...origin/{head} --name-only", cwd=local_repo_dir)
        if nd_out is not None:
            nd_files = [f.strip() for f in nd_out.splitlines() if f.strip()]
            nd_code = [f for f in nd_files if not (f.replace('\\', '/').lower().startswith(".jules/") and f.endswith(".md"))]
            if len(nd_code) == 0:
                is_net_zero_diff = True
    elif len(code_files) == 0:
        is_net_zero_diff = True

    if is_net_zero_diff:
        category = "ZERO_DIFF"
        reason = "All functional code changes are already incorporated into the upstream default branch or superseded."
    elif is_scratch_only:
        category = "SCRATCH_ONLY"
        reason = f"PR only contains root scratch/verification script(s): {', '.join(scratch_files)}. Fails repository guardrails."
    else:
        category = "VALID"
        reason = f"Contains {len(code_files)} functional code change file(s)."

    return {
        "repo": repo,
        "number": pr_info.get("number"),
        "title": title,
        "head": head,
        "base": base,
        "category": category,
        "reason": reason,
        "files": files,
        "scratch_files": scratch_files
    }

def get_open_prs(repo):
    out, _ = run_cmd(f"gh pr list -R {repo} --state open --json number")
    if not out:
        return []
    try:
        prs = json.loads(out)
        return [p.get("number") for p in prs]
    except Exception:
        return []

def cmd_audit(args):
    targets = []
    if args.repo:
        targets.append((args.repo, args.local_dir))
    elif args.workspace:
        ws_dir = os.path.abspath(args.workspace)
        submodules = parse_gitmodules(ws_dir)
        for sub in submodules:
            url = sub.get("url", "")
            m = re.search(r'github\.com[:/]([^/]+/[^/.]+)', url)
            if m:
                r_name = m.group(1)
                s_dir = os.path.join(ws_dir, sub.get("path"))
                targets.append((r_name, s_dir))

    if not targets:
        print("❌ No repository or workspace specified. Use --repo or --workspace.", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 Auditing open PRs across {len(targets)} repository/submodule target(s)...")
    results = []

    for repo, l_dir in targets:
        pr_numbers = get_open_prs(repo)
        if not pr_numbers:
            continue
        print(f"\n📂 [{repo}] Scanning {len(pr_numbers)} open PR(s)...")
        for num in pr_numbers:
            res = audit_single_pr(repo, num, local_repo_dir=l_dir)
            if res:
                results.append(res)
                icon = "🧹" if res["category"] in ["ZERO_DIFF", "SCRATCH_ONLY"] else "✅"
                print(f"  [{icon} {res['category']}] #{res['number']} - {res['title']}: {res['reason']}")

    if not results:
        print("\n✅ No open PRs found across inspected repositories.")
        return

    cleanable = [r for r in results if r["category"] in ["ZERO_DIFF", "SCRATCH_ONLY"]]
    print(f"\n==================================================")
    print(f"📊 Summary: {len(results)} open PR(s) evaluated. {len(cleanable)} candidate(s) for cleanup.")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"📄 Audit report written to: {args.output}")

def cmd_close(args):
    targets = []
    if args.repo:
        targets.append((args.repo, args.local_dir))
    elif args.workspace:
        ws_dir = os.path.abspath(args.workspace)
        submodules = parse_gitmodules(ws_dir)
        for sub in submodules:
            url = sub.get("url", "")
            m = re.search(r'github\.com[:/]([^/]+/[^/.]+)', url)
            if m:
                r_name = m.group(1)
                s_dir = os.path.join(ws_dir, sub.get("path"))
                targets.append((r_name, s_dir))

    results = []
    for repo, l_dir in targets:
        pr_numbers = get_open_prs(repo)
        for num in pr_numbers:
            res = audit_single_pr(repo, num, local_repo_dir=l_dir)
            if res and res["category"] in ["ZERO_DIFF", "SCRATCH_ONLY"]:
                results.append(res)

    if not results:
        print("✅ No zero-diff or scratch-only PRs detected for closure.")
        return

    print(f"🧹 Closing {len(results)} detected PR candidate(s)...")
    for r in results:
        comment = (
            f"Closing automatically as {r['category'].lower()}: {r['reason']} "
            "Branch deleted to maintain repository hygiene."
        )
        if args.dry_run:
            print(f"  [DRY-RUN] Would close {r['repo']}#{r['number']} ({r['category']}): {r['title']}")
        else:
            close_cmd = f'gh pr close {r["number"]} -R {r["repo"]} --comment "{comment}" --delete-branch'
            out, err = run_cmd(close_cmd)
            if out is not None:
                print(f"  ✅ Closed {r['repo']}#{r['number']} ({r['category']}) and deleted branch {r['head']}")
            else:
                print(f"  ❌ Failed to close {r['repo']}#{r['number']}: {err}")

    print("\nBatch closure completed.")

def main():
    parser = argparse.ArgumentParser(description="Bot PR Zero-Diff & Scratch Cleaner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_audit = subparsers.add_parser("audit", help="Audit open PRs for zero-diff or scratch files")
    p_audit.add_argument("--repo", help="Target GitHub repository (OWNER/REPO)")
    p_audit.add_argument("--workspace", help="Target monorepo/workspace containing submodules")
    p_audit.add_argument("--local-dir", help="Local directory for git diff inspection")
    p_audit.add_argument("--output", help="Optional output JSON file")
    p_audit.set_defaults(func=cmd_audit)

    p_close = subparsers.add_parser("close", help="Batch close zero-diff and scratch PRs")
    p_close.add_argument("--repo", help="Target GitHub repository (OWNER/REPO)")
    p_close.add_argument("--workspace", help="Target monorepo/workspace containing submodules")
    p_close.add_argument("--local-dir", help="Local directory for git diff inspection")
    p_close.add_argument("--dry-run", action="store_true", help="Preview closures without modifying GitHub PRs")
    p_close.set_defaults(func=cmd_close)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
