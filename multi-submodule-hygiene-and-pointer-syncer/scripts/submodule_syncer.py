#!/usr/bin/env python3
"""
Multi-Submodule Hygiene & Pointer Syncer CLI
Audits submodule status, detects untracked/modified content anomalies,
harmonizes gitignore patterns, and performs atomic parent tree synchronization.
"""

import argparse
import json
import os
import re
import subprocess
import sys

# Force UTF-8 encoding and unbuffered output across Windows console streams
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

def get_base_env():
    env = os.environ.copy()
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_PAGER"] = "1"
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env

def run_command(cmd, cwd=None, timeout=60):
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
        m_section = re.match(r'^\[submodule\s+"([^"]+)"\]$', line)
        if m_section:
            if current and "path" in current:
                submodules.append(current)
            current = {"name": m_section.group(1)}
            continue
        
        m_path = re.match(r'^path\s*=\s*(.+)$', line)
        if m_path and current:
            current["path"] = m_path.group(1).strip()
            continue

        m_url = re.match(r'^url\s*=\s*(.+)$', line)
        if m_url and current:
            current["url"] = m_url.group(1).strip()
            continue

    if current and "path" in current:
        submodules.append(current)

    return submodules

def clean_git_locks(local_dir):
    git_dir = os.path.join(local_dir, ".git")
    if not os.path.exists(git_dir):
        return 0
    removed = 0
    for root, _, files in os.walk(git_dir):
        for f in files:
            if f.endswith(".lock"):
                lock_path = os.path.join(root, f)
                try:
                    os.remove(lock_path)
                    removed += 1
                except Exception:
                    pass
    return removed

def cmd_scan(args):
    workspace_dir = os.path.abspath(args.workspace_dir)
    print(f"🔍 Scanning submodules in: {workspace_dir}")

    submodules = parse_gitmodules(workspace_dir)
    if not submodules:
        print(f"⚠️ No submodules found in .gitmodules under {workspace_dir}")
        sys.exit(0)

    print(f"Found {len(submodules)} registered submodule(s). Evaluating hygiene...")
    status_tree = []

    for sub in submodules:
        sub_name = sub.get("name")
        sub_rel_path = sub.get("path")
        sub_full_path = os.path.join(workspace_dir, sub_rel_path)
        sub_url = sub.get("url", "")

        info = {
            "name": sub_name,
            "path": sub_rel_path,
            "url": sub_url,
            "exists": os.path.exists(sub_full_path),
            "is_git": os.path.exists(os.path.join(sub_full_path, ".git")),
            "branch": "unknown",
            "head_commit": "unknown",
            "pointer_commit": "unknown",
            "status": "CLEAN",
            "untracked_files": [],
            "modified_files": [],
            "is_behind_origin": False,
            "behind_count": 0
        }

        if not info["exists"] or not info["is_git"]:
            info["status"] = "MISSING_OR_UNINITIALIZED"
            status_tree.append(info)
            continue

        b_out, _ = run_command("git branch --show-current", cwd=sub_full_path)
        info["branch"] = b_out.strip() if b_out else "DETACHED_HEAD"

        c_out, _ = run_command("git rev-parse HEAD", cwd=sub_full_path)
        info["head_commit"] = (c_out or "").strip()

        p_out, _ = run_command(f'git ls-tree HEAD "{sub_rel_path}"', cwd=workspace_dir)
        if p_out:
            parts = p_out.split()
            if len(parts) >= 3:
                info["pointer_commit"] = parts[2]

        st_out, _ = run_command("git status --porcelain", cwd=sub_full_path)
        if st_out:
            for line in st_out.splitlines():
                if len(line) < 3:
                    continue
                code = line[:2]
                file_path = line[3:].strip()
                if "??" in code:
                    info["untracked_files"].append(file_path)
                else:
                    info["modified_files"].append(file_path)

        if info["untracked_files"] and info["modified_files"]:
            info["status"] = "MODIFIED_AND_UNTRACKED_CONTENT"
        elif info["untracked_files"]:
            info["status"] = "UNTRACKED_CONTENT"
        elif info["modified_files"]:
            info["status"] = "MODIFIED_CONTENT"

        if info["branch"] != "DETACHED_HEAD":
            run_command(f"git fetch origin {info['branch']}", cwd=sub_full_path)
            behind_out, _ = run_command(f"git rev-list --count HEAD..origin/{info['branch']}", cwd=sub_full_path)
            if behind_out and behind_out.isdigit() and int(behind_out) > 0:
                info["is_behind_origin"] = True
                info["behind_count"] = int(behind_out)

        status_tree.append(info)
        status_icon = "✅" if info["status"] == "CLEAN" and not info["is_behind_origin"] else "⚠️"
        print(f"  [{status_icon}] {sub_rel_path} ({info['branch']}): {info['status']}" + 
              (f" (Behind remote by {info['behind_count']} commits)" if info["is_behind_origin"] else ""))

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(status_tree, f, indent=2)
        print(f"\n📊 JSON hygiene report written to: {args.output}")

    if args.markdown_output:
        os.makedirs(os.path.dirname(os.path.abspath(args.markdown_output)), exist_ok=True)
        with open(args.markdown_output, "w", encoding="utf-8") as f:
            f.write("# 📋 Multi-Submodule Hygiene & Pointer Status\n\n")
            f.write("| Submodule | Branch | Status | Untracked Files | Modified Files | Remote Drift |\n")
            f.write("| :--- | :---: | :---: | :---: | :---: | :---: |\n")
            for item in status_tree:
                untracked_count = len(item.get("untracked_files", []))
                mod_count = len(item.get("modified_files", []))
                drift = f"{item['behind_count']} commits behind" if item.get("is_behind_origin") else "In sync"
                f.write(f"| `{item['path']}` | `{item['branch']}` | **{item['status']}** | {untracked_count} | {mod_count} | {drift} |\n")
        print(f"📄 Markdown report written to: {args.markdown_output}")

def cmd_clean(args):
    workspace_dir = os.path.abspath(args.workspace_dir)
    print(f"🧹 Running submodule hygiene cleanup in: {workspace_dir}")
    submodules = parse_gitmodules(workspace_dir)

    for sub in submodules:
        sub_path = os.path.join(workspace_dir, sub.get("path"))
        if not os.path.exists(os.path.join(sub_path, ".git")):
            continue

        locks = clean_git_locks(sub_path)
        if locks > 0:
            print(f"  🔓 Cleared {locks} orphaned .git/*.lock files in {sub.get('path')}")

        if args.restore_tracked:
            run_command("git restore .", cwd=sub_path)
            print(f"  ♻️ Restored tracked modifications in {sub.get('path')}")

        if getattr(args, 'clean_transient', False):
            # Target known transient directories without touching uncommitted source files
            transient_dirs = ["infra/db/backups", ".pytest_cache", "coverage", ".nyc_output", "var/log", "tmp"]
            for td in transient_dirs:
                full_td = os.path.join(sub_path, td)
                if os.path.exists(full_td):
                    out, _ = run_command(f'git clean -fd "{td}"', cwd=sub_path)
                    if out:
                        print(f"  🧹 Cleaned transient artifacts in {sub.get('path')}/{td}")

def cmd_sync(args):
    workspace_dir = os.path.abspath(args.workspace_dir)
    print(f"🔄 Synchronizing all submodules with remote base in: {workspace_dir}")
    submodules = parse_gitmodules(workspace_dir)

    updated_submodules = []

    for sub in submodules:
        sub_path = os.path.join(workspace_dir, sub.get("path"))
        if not os.path.exists(os.path.join(sub_path, ".git")):
            continue

        clean_git_locks(sub_path)
        b_out, _ = run_command("git branch --show-current", cwd=sub_path)
        curr_b = b_out.strip() if b_out else None

        if not curr_b or curr_b == "HEAD":
            for candidate in ["main", "master"]:
                r_out, _ = run_command(f"git rev-parse --verify origin/{candidate}", cwd=sub_path)
                if r_out:
                    curr_b = candidate
                    break
            curr_b = curr_b or "main"

        # Clean transient artifacts before branch checkout
        transient_dirs = ["infra/db/backups", ".pytest_cache", "coverage", ".nyc_output", "var/log", "tmp"]
        for td in transient_dirs:
            full_td = os.path.join(sub_path, td)
            if os.path.exists(full_td):
                run_command(f'git clean -fd "{td}"', cwd=sub_path)

        print(f"  ⬇️ Pulling origin/{curr_b} in {sub.get('path')}...")
        run_command(f"git checkout {curr_b} -f", cwd=sub_path)
        pull_out, pull_err = run_command(f"git pull origin {curr_b}", cwd=sub_path)

        run_command(f'git add "{sub.get("path")}"', cwd=workspace_dir)
        updated_submodules.append(sub.get("path"))

    if updated_submodules and not args.dry_run:
        commit_msg = f"chore(submodules): sync latest main/master branches across {len(updated_submodules)} submodule(s)"
        c_out, c_err = run_command(f'git commit -m "{commit_msg}"', cwd=workspace_dir)
        if c_out is not None:
            print(f"✅ Committed updated submodule pointers in parent repository.")
            if args.push:
                print(f"⬆️ Pushing parent repository to origin/main...")
                p_out, p_err = run_command("git push origin main", cwd=workspace_dir)
                if p_out is not None:
                    print(f"🎉 Successfully pushed parent repository updates!")
                else:
                    print(f"⚠️ Failed to push parent repository: {p_err}")
        else:
            print(f"ℹ️ Parent repository submodule pointers are already up to date ({c_err}).")

def main():
    parser = argparse.ArgumentParser(description="Multi-Submodule Hygiene & Pointer Syncer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_scan = subparsers.add_parser("scan", help="Audit submodules for untracked/modified content and remote drift")
    p_scan.add_argument("--workspace-dir", default=".", help="Workspace parent directory containing .gitmodules")
    p_scan.add_argument("--output", help="Optional output JSON file")
    p_scan.add_argument("--markdown-output", help="Optional output Markdown report file")
    p_scan.set_defaults(func=cmd_scan)

    p_clean = subparsers.add_parser("clean", help="Clean orphaned git locks and optionally restore tracked modifications")
    p_clean.add_argument("--workspace-dir", default=".", help="Workspace parent directory")
    p_clean.add_argument("--restore-tracked", action="store_true", help="Discard local tracked modifications in submodules")
    p_clean.add_argument("--clean-transient", action="store_true", help="Clean known transient untracked artifacts (e.g. db backups, test caches, logs)")
    p_clean.set_defaults(func=cmd_clean)

    p_sync = subparsers.add_parser("sync", help="Pull latest default branch in all submodules and advance parent pointers")
    p_sync.add_argument("--workspace-dir", default=".", help="Workspace parent directory")
    p_sync.add_argument("--push", action="store_true", help="Push parent repository after committing updated pointers")
    p_sync.add_argument("--dry-run", action="store_true", help="Simulate synchronization without committing or pushing")
    p_sync.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
