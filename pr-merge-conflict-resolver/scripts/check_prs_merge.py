#!/usr/bin/env python3
import subprocess
import json
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    return res.returncode, res.stdout, res.stderr

def get_git_root():
    code, stdout, _ = run("git rev-parse --show-toplevel")
    if code == 0:
        return stdout.strip()
    return os.getcwd()

def main():
    repo_dir = get_git_root()
    base_branch = sys.argv[1] if len(sys.argv) > 1 else "master"

    # Verify base branch existence (master or main)
    c_m, _, _ = run(f"git rev-parse --verify {base_branch}", cwd=repo_dir)
    if c_m != 0 and base_branch == "master":
        c_main, _, _ = run("git rev-parse --verify main", cwd=repo_dir)
        if c_main == 0:
            base_branch = "main"

    print(f"Checking open PRs against target branch: '{base_branch}' in {repo_dir}...")
    run("git fetch origin", cwd=repo_dir)

    code, stdout, stderr = run("gh pr list --state open --json number,title,headRefName", cwd=repo_dir)
    if code != 0:
        print("Error fetching PRs via gh CLI:", stderr)
        sys.exit(1)

    prs = json.loads(stdout)
    if not prs:
        print("No open PRs found.")
        sys.exit(0)

    conflicts = []
    clean = []

    for pr in prs:
        branch = pr["headRefName"]
        num = pr["number"]
        title = pr["title"]

        code_m, out_m, _ = run(f"git merge-tree origin/{base_branch} origin/{branch}", cwd=repo_dir)

        if code_m != 0 or "CONFLICT" in out_m or "conflict" in out_m.lower():
            conflicts.append({
                "number": num,
                "branch": branch,
                "title": title
            })
        else:
            clean.append({
                "number": num,
                "branch": branch,
                "title": title
            })

    print("\n================ SUMMARY ================")
    print(f"Total PRs: {len(prs)}")
    print(f"Clean merges ({len(clean)}):")
    for cl in clean:
        print(f"  PR #{cl['number']} ({cl['branch']}): {cl['title']}")

    print(f"\nConflicts ({len(conflicts)}):")
    for c in conflicts:
        print(f"  PR #{c['number']} ({c['branch']}): {c['title']}")

if __name__ == "__main__":
    main()
