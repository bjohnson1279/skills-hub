#!/usr/bin/env python3
"""
Cross-Repo PR Auditor
Bypasses GitHub CLI limits to scan all open PRs across a user's repositories for merge conflicts and test failures.
"""
import subprocess
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Audit all open PRs for a specific owner.")
    parser.add_argument("--owner", required=True, help="GitHub owner/organization name")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of PRs to query")
    args = parser.parse_args()

    cmd = ["gh", "search", "prs", "--owner", args.owner, "--state", "open", "--limit", str(args.limit), "--json", "number,repository,title,createdAt"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        print(f"Failed to query PRs: {res.stderr}")
        sys.exit(1)
        
    prs = json.loads(res.stdout)
    print(f"Total open PRs found for {args.owner}: {len(prs)}\n")
    
    conflicts = []
    failures_list = []

    for pr in prs:
        repo = pr["repository"]["nameWithOwner"]
        num = pr["number"]
        title = pr["title"]
        
        d_res = subprocess.run(["gh", "pr", "view", str(num), "--repo", repo, "--json", "mergeable,statusCheckRollup,author,headRefName"], capture_output=True, text=True, encoding="utf-8")
        if d_res.returncode == 0:
            data = json.loads(d_res.stdout)
            m = data.get("mergeable")
            checks = data.get("statusCheckRollup") or []
            failures = [c.get("name") for c in checks if c.get("conclusion") in ("FAILURE", "ACTION_REQUIRED", "TIMED_OUT")]
            
            if m == "CONFLICTING":
                conflicts.append((repo, num, title, data.get("headRefName")))
                print(f"CONFLICT: {repo}#{num} [{title}]")
            if failures:
                failures_list.append((repo, num, title, failures))
                print(f"FAILURES: {repo}#{num} [{title}] -> {failures}")
        else:
            print(f"WARNING: Could not fetch details for {repo}#{num}")

    print("\n--- SUMMARY OF ISSUES ---")
    print(f"Conflicts ({len(conflicts)}):")
    for c in conflicts:
        print(f"  {c[0]}#{c[1]}: {c[2]} (branch: {c[3]})")
    print(f"\nFailures ({len(failures_list)}):")
    for f in failures_list:
        print(f"  {f[0]}#{f[1]}: {f[2]} -> {f[3]}")

if __name__ == "__main__":
    main()
