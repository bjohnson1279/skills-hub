#!/usr/bin/env python3
"""
Polyglot PR Batch Merger CLI
Automates triage, sequential base synchronization, lockfile conflict auto-resolution, and admin merging across multi-technology DDD repositories.
"""

import argparse
import json
import os
import re
import sys
import subprocess

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_cmd(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, encoding='utf-8', errors='replace')
    return res.returncode, res.stdout, res.stderr

def resolve_jules_conflict(filepath):
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if "<<<<<<<" in content:
            lines = content.splitlines()
            cleaned = [l for l in lines if not (l.startswith("<<<<<<<") or l.startswith("=======") or l.startswith(">>>>>>>"))]
            merged_text = "\n".join(cleaned)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(merged_text.strip() + "\n")
    except Exception as e:
        print(f"    Warning resolving jules conflict for {filepath}: {e}", file=sys.stderr)

def cmd_triage(args):
    print(f"Fetching open PRs for owner '{args.owner}' across target repositories...")
    cmd = f"gh search prs --owner {args.owner} --state open --limit {args.limit} --json number,title,repository,author"
    code, stdout, stderr = run_cmd(cmd)
    if code != 0:
        print(f"Error fetching PRs: {stderr}", file=sys.stderr)
        sys.exit(1)

    prs = json.loads(stdout)
    triaged = []

    for pr in prs:
        repo_name = pr.get("repository", {}).get("nameWithOwner", "")
        num = pr.get("number")
        
        view_cmd = f"gh pr view {num} -R {repo_name} --json files,statusCheckRollup"
        v_code, v_out, _ = run_cmd(view_cmd)
        
        files_info = []
        status_checks = []
        if v_code == 0:
            details = json.loads(v_out)
            files_info = details.get("files", [])
            status_checks = details.get("statusCheckRollup", [])
            
        changed_paths = [f.get("path", "") for f in files_info]
        code_paths = [p for p in changed_paths if not p.lower().startswith(".jules/")]
        
        # Critical deletions check
        critical_deletions = sum(f.get("deletions", 0) for f in files_info if any(k in f.get("path", "") for k in ["schema.prisma", "src/index.ts", "public/index.php"]))
        
        # Check diff for conflict markers
        _, pr_diff, _ = run_cmd(f"gh pr diff {num} -R {repo_name}")
        has_conflicts = bool(re.search(r'^\+([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))', pr_diff, re.MULTILINE)) if pr_diff else False

        if len(code_paths) == 0:
            group = "Group C: Zero-Diff"
            reason = "Documentation log update only"
        elif has_conflicts:
            group = "Group B: Destructive"
            reason = "Contains unresolved Git merge conflict markers"
        elif critical_deletions > 15:
            group = "Group B: Destructive"
            reason = f"Destructive line deletions in schema/entrypoint ({critical_deletions} lines)"
        else:
            group = "Group A: Safe & High Value"
            reason = "Clean code improvement or test addition"
            
        triaged.append({
            "repo": repo_name,
            "number": num,
            "title": pr.get("title"),
            "head": pr.get("headRefName"),
            "base": pr.get("baseRefName"),
            "group": group,
            "reason": reason
        })

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(triaged, f, indent=2)

    print(f"Triage completed for {len(triaged)} PRs. Saved to: {args.output}")

def cmd_execute(args):
    if not os.path.exists(args.input_file):
        print(f"Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.input_file, "r", encoding="utf-8") as f:
        triaged = json.load(f)

    # 1. Close Group B / C PRs
    for p in triaged:
        if p["group"].startswith("Group B") or p["group"].startswith("Group C"):
            repo = p["repo"]
            num = p["number"]
            reason = p["reason"]
            print(f"Closing {p['group']} PR #{num} in {repo}...")
            close_cmd = f'gh pr close {num} -R {repo} --comment "Closing PR during automated polyglot triage: {reason}"'
            if not args.dry_run:
                run_cmd(close_cmd)

    # 2. Merge Group A PRs with sequential base sync
    group_a_prs = [p for p in triaged if p["group"].startswith("Group A")]
    print(f"\nProcessing {len(group_a_prs)} Group A PRs...")

    for p in group_a_prs:
        repo = p["repo"]
        num = p["number"]
        head = p.get("head")
        base = p.get("base")
        if not head or not base:
            c, out, _ = run_cmd(f"gh pr view {num} -R {repo} --json headRefName,baseRefName")
            if c == 0:
                view_data = json.loads(out)
                head = view_data.get("headRefName")
                base = view_data.get("baseRefName")
            base = base or "main"
        repo_name = repo.split("/")[-1]

        local_dir = os.path.join(args.base_dir, repo_name) if args.base_dir else None

        if local_dir and os.path.exists(local_dir):
            print(f"\nSyncing base for {repo} #{num} ({head})...")
            run_cmd(f"git restore .", cwd=local_dir)
            run_cmd(f"git checkout {base} -f", cwd=local_dir)
            run_cmd(f"git pull origin {base}", cwd=local_dir)
            run_cmd("git merge --abort", cwd=local_dir)
            run_cmd(f"git fetch origin {head}:{head}", cwd=local_dir)
            run_cmd(f"git checkout \"{head}\" -f", cwd=local_dir)
            c_code, _, _ = run_cmd(f"git merge origin/{base} --no-edit", cwd=local_dir)
            if c_code != 0:
                print(f"  Resolving conflicts with origin/{base}...")
                _, status_out, _ = run_cmd("git status --porcelain", cwd=local_dir)
                conflict_files = [line[3:].strip() for line in status_out.splitlines() if len(line) > 3]
                auto_resolvable = all(
                    any(cf.endswith(ext) for ext in ["package-lock.json", "composer.lock", "package.json", "pnpm-lock.yaml", "mix.lock"])
                    or ".jules" in cf.lower()
                    for cf in conflict_files
                )
                if not auto_resolvable:
                    print(f"  ❌ Unresolvable merge conflicts in non-lockfile code ({', '.join(conflict_files)}). Aborting merge for {repo}#{num}.")
                    run_cmd("git merge --abort", cwd=local_dir)
                    continue

                for cf in conflict_files:
                    full_cf = os.path.join(local_dir, cf)
                    if ".jules" in cf.lower():
                        resolve_jules_conflict(full_cf)
                        run_cmd(f'git add "{cf}"', cwd=local_dir)
                    else:
                        run_cmd(f'git checkout origin/{base} -- "{cf}"', cwd=local_dir)
                        run_cmd(f'git add "{cf}"', cwd=local_dir)
                run_cmd(f'git commit -m "fix(merge): sync latest {base} and union jules logs"', cwd=local_dir)

            # Check for conflict markers in diff before push
            _, post_diff, _ = run_cmd(f"git diff origin/{base}...HEAD", cwd=local_dir)
            if re.search(r'^\+([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))', post_diff, re.MULTILINE):
                print(f"  ❌ GUARD BLOCKED: Synced branch contains merge conflict markers! Aborting push.")
                continue

            run_cmd(f"git push origin \"{head}\" -f", cwd=local_dir)

        # Pre-merge check on PR diff
        _, pr_diff_check, _ = run_cmd(f"gh pr diff {num} -R {repo}")
        if re.search(r'^\+([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))', pr_diff_check, re.MULTILINE):
            print(f"  ❌ GUARD BLOCKED: PR {repo}#{num} introduces unresolved Git merge conflict markers! Refusing to merge.")
            continue

        merge_cmd = f"gh pr merge {num} -R {repo} --admin --merge --delete-branch"
        print(f"Merging: {merge_cmd}")
        if not args.dry_run:
            m_code, m_out, m_err = run_cmd(merge_cmd)
            if m_code == 0:
                print(f"  [SUCCESS] Merged {repo} #{num}")
            else:
                print(f"  [ERROR] Failed {repo} #{num}: {m_err.strip()}")

def main():
    parser = argparse.ArgumentParser(description="Polyglot PR Batch Merger CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_triage = subparsers.add_parser("triage", help="Triage open PRs into Group A/B/C")
    p_triage.add_argument("--owner", required=True, help="GitHub owner or org")
    p_triage.add_argument("--limit", type=int, default=100, help="Max PRs to fetch")
    p_triage.add_argument("--output", required=True, help="Output JSON file path")
    p_triage.set_defaults(func=cmd_triage)

    p_exec = subparsers.add_parser("execute", help="Execute batch closures and sequential base-synced merges")
    p_exec.add_argument("--input-file", required=True, help="Input triaged JSON file")
    p_exec.add_argument("--base-dir", help="Parent directory containing local repositories")
    p_exec.add_argument("--dry-run", action="store_true", help="Print actions without executing")
    p_exec.set_defaults(func=cmd_execute)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
