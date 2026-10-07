#!/usr/bin/env python3
"""
Submodule Parent Tree Syncer CLI
Standardizes and automates submodule pointer fast-forwarding, detached HEAD reconciliation,
dirty worktree cleanup, and atomic parent repository tree synchronization.
"""

import argparse
import json
import os
import subprocess
import sys

# Force UTF-8 encoding across Windows console streams
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
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""
    return env

def log(msg):
    print(msg, flush=True)

def run_command(cmd, cwd=None, timeout=30):
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
    except subprocess.TimeoutExpired:
        return None, f"Command timed out after {timeout}s"
    except Exception as e:
        return None, str(e)

def get_submodule_list(base_dir):
    """Parses .gitmodules and git submodule status to get all submodules."""
    out, err = run_command("git submodule status", cwd=base_dir)
    submodules = []
    if not out:
        return submodules

    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        
        status_char = line[0] if line[0] in ['-', '+', 'U'] else ' '
        clean_line = line[1:].strip() if status_char != ' ' else line
        parts = clean_line.split()
        
        if len(parts) >= 2:
            commit_sha = parts[0]
            sub_path = parts[1]
            branch_info = parts[2] if len(parts) > 2 else ""
            
            submodules.append({
                "path": sub_path,
                "commit": commit_sha,
                "status": "uninitialized" if status_char == '-' else ("modified_pointer" if status_char == '+' else ("merge_conflict" if status_char == 'U' else "synced")),
                "branch_info": branch_info,
                "full_path": os.path.abspath(os.path.join(base_dir, sub_path))
            })
    return submodules

def detect_default_branch(submodule_dir):
    """Detects whether main or master is the default tracking branch."""
    head_ref, _ = run_command("git symbolic-ref refs/remotes/origin/HEAD", cwd=submodule_dir)
    if head_ref:
        return head_ref.replace("refs/remotes/origin/", "").strip()

    # Fallback to gh repo view
    gh_out, _ = run_command("gh repo view --json defaultBranchRef --jq .defaultBranchRef.name", cwd=submodule_dir, timeout=5)
    if gh_out and gh_out.strip():
        return gh_out.strip()

    branches_out, _ = run_command("git branch -r", cwd=submodule_dir)
    if branches_out:
        if "origin/master" in branches_out and "origin/main" not in branches_out:
            return "master"
        if "origin/main" in branches_out:
            return "main"

    out, _ = run_command("git remote show origin", cwd=submodule_dir, timeout=5)
    if out:
        for line in out.splitlines():
            if "HEAD branch:" in line:
                return line.split(":")[-1].strip()
    return "main"

def cmd_status(args):
    base_dir = os.path.abspath(args.base_dir)
    log(f"Auditing submodules in parent repository: {base_dir}")
    submodules = get_submodule_list(base_dir)
    
    if not submodules:
        log("ℹ️ No git submodules detected in this repository.")
        return

    results = []
    log(f"\nFound {len(submodules)} submodules:")
    for sub in submodules:
        sub_dir = sub["full_path"]
        if not os.path.exists(sub_dir):
            sub["state"] = "DIRECTORY_MISSING"
            results.append(sub)
            continue
        
        branch_out, _ = run_command("git branch --show-current", cwd=sub_dir)
        current_branch = branch_out.strip() if branch_out else "(detached HEAD)"
        
        default_branch = detect_default_branch(sub_dir)
        
        dirty_out, _ = run_command("git status --porcelain", cwd=sub_dir)
        is_dirty = bool(dirty_out and len(dirty_out.strip()) > 0)
        
        head_sha_out, _ = run_command("git rev-parse HEAD", cwd=sub_dir)
        head_sha = head_sha_out.strip() if head_sha_out else sub["commit"]
        sub["current_branch"] = current_branch
        sub["default_branch"] = default_branch
        sub["is_dirty"] = is_dirty
        sub["head_sha"] = head_sha

        remote_sha = None
        drift_tag = ""
        if getattr(args, 'check_remote', False):
            r_out, _ = run_command(f"git ls-remote origin refs/heads/{default_branch}", cwd=sub_dir, timeout=10)
            if r_out:
                remote_sha = r_out.split()[0] if r_out.split() else None
                if remote_sha and remote_sha != sub["head_sha"]:
                    drift_tag = f" ⚠️ [REMOTE DRIFT: {remote_sha[:8]}]"
                    sub["remote_sha"] = remote_sha
                    sub["has_drift"] = True
                else:
                    sub["has_drift"] = False

        results.append(sub)
        
        dirty_tag = " [DIRTY]" if is_dirty else ""
        log(f"  • {sub['path']} -> Branch: {current_branch} (Default: {default_branch}) | Pointer: {sub['head_sha'][:8]}{dirty_tag}{drift_tag}")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        log(f"\n✅ Status report written to: {args.output}")

def cmd_sync(args):
    base_dir = os.path.abspath(args.base_dir)
    log(f"🔄 Synchronizing all submodule trees in: {base_dir}...")
    submodules = get_submodule_list(base_dir)
    
    if not submodules:
        log("ℹ️ No git submodules found to sync.")
        return

    updated_submodules = []
    for sub in submodules:
        sub_dir = sub["full_path"]
        sub_path = sub["path"]
        
        if not os.path.exists(sub_dir):
            log(f"  Initializing missing submodule {sub_path}...")
            run_command(f"git submodule update --init --recursive {sub_path}", cwd=base_dir)
        
        default_branch = detect_default_branch(sub_dir)
        log(f"\n📂 [{sub_path}] Updating to {default_branch}...")
        
        if args.clean:
            run_command("git checkout .", cwd=sub_dir)
            run_command("git clean -fd", cwd=sub_dir)
            transient_dirs = ["infra/db/backups", ".pytest_cache", "coverage", "tmp", "var/log"]
            for td in transient_dirs:
                full_td = os.path.join(sub_dir, td)
                if os.path.exists(full_td):
                    run_command(f'git clean -fd "{td}"', cwd=sub_dir)
        
        run_command("git fetch origin", cwd=sub_dir, timeout=15)
        run_command(f"git checkout {default_branch} -f", cwd=sub_dir)
        pull_out, pull_err = run_command(f"git pull origin {default_branch}", cwd=sub_dir, timeout=15)
        
        new_sha, _ = run_command("git rev-parse HEAD", cwd=sub_dir)
        updated_submodules.append({
            "path": sub_path,
            "branch": default_branch,
            "sha": new_sha
        })
        log(f"  ✅ [{sub_path}] At commit {new_sha[:8] if new_sha else 'UNKNOWN'} on {default_branch}")

    # Check parent repo git diff on submodules
    parent_diff, _ = run_command("git status --porcelain", cwd=base_dir)
    candidate_submodules = []
    if parent_diff:
        for line in parent_diff.splitlines():
            if len(line) > 3:
                p = line[3:].strip()
                if any(p == s["path"] for s in submodules):
                    candidate_submodules.append(p)

    log(f"\n==================================================")
    if candidate_submodules:
        log(f"📌 {len(candidate_submodules)} submodule(s) detected with changes/updates in parent tree:")
        
        # Verify that candidate submodule commits actually exist on remote origin
        safe_candidates = []
        for cg in candidate_submodules:
            sub_info = next((s for s in submodules if s["path"] == cg), None)
            if not sub_info:
                safe_candidates.append(cg)
                continue
            
            sub_dir = sub_info["full_path"]
            head_sha, _ = run_command("git rev-parse HEAD", cwd=sub_dir)
            if not head_sha:
                safe_candidates.append(cg)
                continue
                
            # Check if remote branch or remote tracking branch contains this commit
            r_branches, _ = run_command(f"git branch -r --contains {head_sha}", cwd=sub_dir)
            if not r_branches or "origin/" not in r_branches:
                # Also check remote directly via ls-remote if local tracking ref is not updated
                def_branch = detect_default_branch(sub_dir)
                ls_out, _ = run_command(f"git ls-remote origin refs/heads/{def_branch}", cwd=sub_dir, timeout=10)
                if ls_out and head_sha in ls_out:
                    is_pushed = True
                else:
                    is_pushed = False
            else:
                is_pushed = True
                
            if not is_pushed:
                log(f"   ⚠️ SKIPPING {cg} (Commit {head_sha[:8]} is NOT pushed to remote origin! Push child submodule first to prevent 'upload-pack: not our ref' CI errors)")
            else:
                log(f"   • {cg} (Commit {head_sha[:8]} verified on remote)")
                safe_candidates.append(cg)

        candidate_submodules = safe_candidates
        
        if not candidate_submodules:
            log("⚠️ No candidate submodules have commits pushed to remote origin. Aborting parent pointer stage.")
        elif args.commit:
            log(f"\n💾 Staging verified submodule gitlinks in parent repository...")
            run_command(f"git add {' '.join(candidate_submodules)}", cwd=base_dir)
            
            staged_out, _ = run_command("git diff --cached --name-only", cwd=base_dir)
            staged_files = [f.strip() for f in staged_out.splitlines() if f.strip()] if staged_out else []
            
            if staged_files:
                commit_msg = args.message or f"chore(submodules): update submodule pointers ({', '.join(staged_files)})"
                c_out, c_err = run_command(f'git commit -m "{commit_msg}"', cwd=base_dir)
                if c_out is not None:
                    log(f"✅ Parent commit created: {commit_msg}")
                    if args.push:
                        log("⬆️ Pushing parent repository to origin...")
                        p_out, p_err = run_command("git push origin HEAD", cwd=base_dir)
                        if p_out is not None:
                            log("✅ Parent commit pushed successfully.")
                        else:
                            log(f"❌ Failed to push parent repo: {p_err}")
                else:
                    log(f"❌ Failed to commit in parent repository: {c_err}")
            else:
                log("ℹ️ No commit SHA pointer changes to stage in parent tree.")
    else:
        log("✨ All submodule pointers in parent repository are already up to date.")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({
                "updatedSubmodules": updated_submodules,
                "changedGitlinks": candidate_submodules
            }, f, indent=2)
        log(f"📄 Sync summary written to: {args.output}")

def main():
    parser = argparse.ArgumentParser(description="Submodule Parent Tree Syncer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: status
    p_status = subparsers.add_parser("status", help="Audit submodule pointers, branches, and dirty statuses")
    p_status.add_argument("--base-dir", default=".", help="Parent repository base directory (default: current dir)")
    p_status.add_argument("--check-remote", action="store_true", help="Check for remote branch HEAD drift via ls-remote")
    p_status.add_argument("--output", help="Optional output JSON filepath")
    p_status.set_defaults(func=cmd_status)

    # Subcommand: sync
    p_sync = subparsers.add_parser("sync", help="Fast-forward submodules and update parent tree pointers")
    p_sync.add_argument("--base-dir", default=".", help="Parent repository base directory (default: current dir)")
    p_sync.add_argument("--clean", action="store_true", help="Discard untracked/dirty files before syncing")
    p_sync.add_argument("--commit", action="store_true", help="Automatically commit changed gitlink pointers in parent repo")
    p_sync.add_argument("--push", action="store_true", help="Push parent repo commit after committing")
    p_sync.add_argument("--message", help="Custom commit message for parent repo")
    p_sync.add_argument("--output", help="Optional output JSON filepath")
    p_sync.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
