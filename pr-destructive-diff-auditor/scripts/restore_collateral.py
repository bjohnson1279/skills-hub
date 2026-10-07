#!/usr/bin/env python3
"""
restore_collateral.py

Standalone CLI utility to restore collateral files damaged or deleted by bot PR branches
without affecting the PR's valid changes.
"""

import argparse
import os
import subprocess
import sys

# Force UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

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

def main():
    parser = argparse.ArgumentParser(description="Restore collateral files on a PR branch from target base branch")
    parser.add_argument("--repo", required=True, help="GitHub repository (owner/repo)")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--files", nargs="+", required=True, help="List of collateral file paths to restore")
    parser.add_argument("--base-dir", default="C:/Users/johns/DEV", help="Base directory containing local repos")
    args = parser.parse_args()

    local_dir = find_local_repo(args.base_dir, args.repo)
    if not local_dir:
        print(f"[ERROR] Could not find local clone for {args.repo} in {args.base_dir}")
        sys.exit(1)

    import json
    out, err, code = run_cmd(f"gh pr view {args.pr} -R {args.repo} --json headRefName,baseRefName")
    if code != 0 or not out:
        print(f"[ERROR] Could not query PR metadata: {err}")
        sys.exit(1)

    data = json.loads(out)
    head_b = data["headRefName"]
    base_b = data["baseRefName"]

    print(f"🔧 Restoring collateral files on {args.repo}#{args.pr} ({head_b})...")
    run_cmd(f"git fetch origin {head_b}", cwd=local_dir)
    run_cmd(f"git checkout {head_b}", cwd=local_dir)
    run_cmd(f"git fetch origin {base_b}", cwd=local_dir)

    for f_path in args.files:
        print(f"  Restoring: {f_path} from origin/{base_b}")
        out_r, err_r, code_r = run_cmd(f'git checkout origin/{base_b} -- "{f_path}"', cwd=local_dir)
        if code_r != 0:
            print(f"  ⚠️ Warning restoring {f_path}: {err_r}")
        run_cmd(f'git add "{f_path}"', cwd=local_dir)

    c_msg = f"chore: restore collateral file(s) {', '.join(args.files)} from {base_b}"
    out_c, err_c, code_c = run_cmd(f'git commit -m "{c_msg}"', cwd=local_dir)
    if code_c == 0:
        print("  Pushing repaired branch...")
        out_p, err_p, code_p = run_cmd(f'git push origin "{head_b}" --force', cwd=local_dir)
        if code_p == 0:
            print(f"✅ Successfully restored collateral files on {args.repo}#{args.pr}!")
        else:
            print(f"❌ Failed to push: {err_p}")
            sys.exit(1)
    else:
        print(f"  No diff found after restoration: {err_c}")

if __name__ == "__main__":
    main()
