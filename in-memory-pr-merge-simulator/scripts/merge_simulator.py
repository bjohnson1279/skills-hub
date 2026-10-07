#!/usr/bin/env python3
"""
In-Memory PR Merge Simulator CLI
Simulates 3-way merges and pairwise branch compatibility in-memory using `git merge-tree`
without checking out branches or modifying the local working tree.
"""

import argparse
import json
import os
import re
import subprocess
import sys

# Force UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def run_cmd(cmd, cwd=None, timeout=30):
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
            timeout=timeout
        )
        return res.stdout.strip(), res.stderr.strip(), res.returncode
    except Exception as e:
        return "", str(e), 1

def resolve_ref(ref, repo_dir):
    """Resolves branch name or PR ref into a valid git object commit hash."""
    # Try direct ref, origin/ref, or PR ref
    candidates = [ref, f"origin/{ref}", f"refs/pull/{ref}/head", f"refs/heads/{ref}"]
    for c in candidates:
        out, _, code = run_cmd(f"git rev-parse --verify {c}^{{commit}}", cwd=repo_dir)
        if code == 0 and out:
            return out, c
    return None, None

def get_modified_files(base_branch, branch_ref, repo_dir):
    """Returns list of modified files between base_branch and branch_ref."""
    out, _, code = run_cmd(f"git diff --name-only {base_branch}...{branch_ref}", cwd=repo_dir)
    if code == 0 and out:
        return [line.strip() for line in out.splitlines() if line.strip()]
    return []

def simulate_single_merge(base_branch, branch_ref, repo_dir):
    """Runs in-memory git merge-tree to test 3-way mergeability."""
    # Find merge base
    base_commit, _, code1 = run_cmd(f"git merge-base {base_branch} {branch_ref}", cwd=repo_dir)
    if code1 != 0 or not base_commit:
        return {
            "branch": branch_ref,
            "mergeable": False,
            "error": f"Could not determine merge-base between {base_branch} and {branch_ref}"
        }

    # Run git merge-tree (modern 3-way syntax supported across Git 2.x)
    merge_out, merge_err, code2 = run_cmd(f"git merge-tree {base_commit} {base_branch} {branch_ref}", cwd=repo_dir)
    has_conflict = "<<<<<<<" in merge_out or "CONFLICT" in merge_err or code2 != 0

    modified_files = get_modified_files(base_branch, branch_ref, repo_dir)

    return {
        "branch": branch_ref,
        "merge_base": base_commit,
        "mergeable": not has_conflict,
        "has_conflicts": has_conflict,
        "conflict_snippets": [l for l in merge_out.splitlines() if "<<<<<<<" in l or ">>>>>>>" in l][:5],
        "modified_files": modified_files,
        "file_count": len(modified_files)
    }

def cmd_simulate(args):
    repo_dir = os.path.abspath(args.repo_dir or os.getcwd())
    if not os.path.exists(os.path.join(repo_dir, ".git")):
        print(f"❌ Error: {repo_dir} is not a valid git repository", file=sys.stderr)
        sys.exit(1)

    branches = [b.strip() for b in args.branches.split(",") if b.strip()]
    if not branches:
        print("❌ Error: No branches specified via --branches", file=sys.stderr)
        sys.exit(1)

    base = args.base
    print(f"🔍 Simulating in-memory merges against base: '{base}' in {repo_dir}...")

    # Ensure remote branches are fetched locally, otherwise git merge-tree will spuriously fail
    print("   Fetching origin to ensure PR refs are available locally...")
    run_cmd("git fetch origin", cwd=repo_dir)

    results = []
    for b in branches:
        _, valid_ref = resolve_ref(b, repo_dir)
        target_ref = valid_ref or b
        sim = simulate_single_merge(base, target_ref, repo_dir)
        sim["input_name"] = b
        results.append(sim)

    # Pairwise file intersection analysis
    pairwise = []
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            b1 = results[i]
            b2 = results[j]
            files1 = set(b1.get("modified_files", []))
            files2 = set(b2.get("modified_files", []))
            # Ignore agent learning notes like .jules/*.md from conflict intersection warnings
            code_files1 = {f for f in files1 if not f.startswith(".jules/") and not f.startswith(".Jules/")}
            code_files2 = {f for f in files2 if not f.startswith(".jules/") and not f.startswith(".Jules/")}
            overlap = code_files1.intersection(code_files2)
            pairwise.append({
                "branch_a": b1["input_name"],
                "branch_b": b2["input_name"],
                "disjoint": len(overlap) == 0,
                "overlapping_files": sorted(list(overlap))
            })

    # Disjoint Cluster Analysis (Graph Connected Components)
    clusters = []
    visited = set()
    branch_names = [r["input_name"] for r in results]
    branch_files = {r["input_name"]: {f for f in r.get("modified_files", []) if not f.startswith(".jules/") and not f.startswith(".Jules/")} for r in results}

    for b in branch_names:
        if b not in visited:
            cluster = []
            queue = [b]
            visited.add(b)
            while queue:
                curr = queue.pop(0)
                cluster.append(curr)
                for other in branch_names:
                    if other not in visited:
                        if not branch_files[curr].isdisjoint(branch_files[other]):
                            visited.add(other)
                            queue.append(other)
            clusters.append(cluster)

    output_data = {
        "base_branch": base,
        "repository": repo_dir,
        "simulations": results,
        "pairwise_intersections": pairwise,
        "disjoint_clusters": clusters,
        "all_clean": all(r.get("mergeable", False) for r in results),
        "all_disjoint": all(p.get("disjoint", False) for p in pairwise)
    }

    # Print human summary
    print("\n" + "=" * 65)
    print("IN-MEMORY MERGE SIMULATION REPORT")
    print("=" * 65)
    for r in results:
        status = "✅ CLEAN" if r.get("mergeable") else "❌ CONFLICTS"
        print(f"[{status}] {r['input_name']} ({r.get('file_count', 0)} files modified)")
        if not r.get("mergeable") and r.get("conflict_snippets"):
            print(f"       Conflicts detected in: {r.get('conflict_snippets')}")

    print("\nPairwise Disjoint File Sets:")
    for p in pairwise:
        if p["disjoint"]:
            print(f"  ✅ {p['branch_a']} & {p['branch_b']}: Completely Disjoint")
        else:
            print(f"  ⚠️ {p['branch_a']} & {p['branch_b']}: Shared modified files -> {', '.join(p['overlapping_files'])}")

    print(f"\n🧩 Disjoint PR Clusters ({len(clusters)} independent group(s)):")
    for idx, c in enumerate(clusters, 1):
        print(f"  Cluster {idx} (Independent Batch): {', '.join(c)}")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"\n📄 Full JSON output saved to: {args.output}")

def main():
    parser = argparse.ArgumentParser(description="In-Memory PR Merge Simulator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_sim = subparsers.add_parser("simulate", help="Simulate in-memory merges for branches")
    p_sim.add_argument("--base", default="main", help="Target base branch (default: main)")
    p_sim.add_argument("--branches", required=True, help="Comma-separated branch or PR names")
    p_sim.add_argument("--repo-dir", help="Path to local git repository directory")
    p_sim.add_argument("--output", help="Optional JSON output filepath")
    p_sim.set_defaults(func=cmd_simulate)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

