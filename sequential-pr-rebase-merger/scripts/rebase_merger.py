#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

# Force UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def run_cmd(cmd, cwd=None, timeout=60):
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            encoding='utf-8',
            errors='replace',
            timeout=timeout
        )
        if res.returncode != 0:
            return None, res.stderr.strip()
        return res.stdout.strip(), None
    except Exception as e:
        return None, str(e)

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
        # Check subdirectories
        if os.path.exists(b):
            for root, dirs, _ in os.walk(b):
                if os.path.basename(root) == repo_basename and os.path.exists(os.path.join(root, ".git")):
                    return os.path.abspath(root)
    return None

def rebuild_lockfile_with_docker(local_dir, lockfile_path, package_name=None):
    """
    Rebuilds lockfile using isolated Docker containers when host runtimes are absent.
    """
    filename = os.path.basename(lockfile_path)
    print(f"  🐳 Rebuilding lockfile '{filename}' via Docker runtime...", flush=True)

    abs_path = os.path.abspath(local_dir)
    vol_path = abs_path.replace("\\", "/")

    if filename == "Gemfile.lock":
        pkg_arg = f"--update {package_name}" if package_name else ""
        cmd = f'docker run --rm -v "{vol_path}:/rails" -w /rails ruby:3.3.8-slim bundle lock {pkg_arg}'
        out, err = run_cmd(cmd, timeout=120)
        if out is not None:
            print("  ✅ Successfully rebuilt Gemfile.lock via ruby:3.3.8-slim", flush=True)
            return True
        print(f"  ⚠️ Docker Gemfile.lock rebuild warning: {err}", flush=True)

    elif filename == "composer.lock":
        pkg_arg = f"{package_name}" if package_name else ""
        cmd = f'docker run --rm -v "{vol_path}:/app" -w /app composer:2 composer update --lock {pkg_arg} --no-install'
        out, err = run_cmd(cmd, timeout=120)
        if out is not None:
            print("  ✅ Successfully rebuilt composer.lock via composer:2", flush=True)
            return True
        print(f"  ⚠️ Docker composer.lock rebuild warning: {err}", flush=True)

    elif filename == "package-lock.json":
        cmd = f'docker run --rm -v "{vol_path}:/app" -w /app node:20-alpine npm install --package-lock-only'
        out, err = run_cmd(cmd, timeout=120)
        if out is not None:
            print("  ✅ Successfully rebuilt package-lock.json via node:20-alpine", flush=True)
            return True
        print(f"  ⚠️ Docker package-lock.json rebuild warning: {err}", flush=True)

    elif filename == "pnpm-lock.yaml":
        cmd = f'docker run --rm -v "{vol_path}:/app" -w /app node:20-alpine npx pnpm install --lockfile-only'
        out, err = run_cmd(cmd, timeout=120)
        if out is not None:
            print("  ✅ Successfully rebuilt pnpm-lock.yaml via node:20-alpine", flush=True)
            return True
        print(f"  ⚠️ Docker pnpm-lock.yaml rebuild warning: {err}", flush=True)

    return False

def parse_jules_sections(content):
    lines = content.splitlines(keepends=True)
    header_lines = []
    sections = []
    current_section = None
    section_header_regex = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*-\s*(.+)$")

    for line in lines:
        match = section_header_regex.match(line)
        if match:
            if current_section:
                sections.append(current_section)
            current_section = {
                "date": match.group(1).strip(),
                "title": match.group(2).strip(),
                "full_header": line.strip(),
                "body_lines": [],
            }
        else:
            if current_section is None:
                header_lines.append(line)
            else:
                current_section["body_lines"].append(line)

    if current_section:
        sections.append(current_section)

    return "".join(header_lines), sections

def union_jules_content(base_content, feature_content):
    base_preamble, base_sections = parse_jules_sections(base_content or "")
    _, feat_sections = parse_jules_sections(feature_content or "")

    existing_keys = set()
    for s in base_sections:
        key = f"{s['date']}:{re.sub(r'[^a-zA-Z0-9]', '', s['title'].lower())}"
        existing_keys.add(key)

    new_sections = []
    for s in feat_sections:
        key = f"{s['date']}:{re.sub(r'[^a-zA-Z0-9]', '', s['title'].lower())}"
        if key not in existing_keys:
            new_sections.append(s)
            existing_keys.add(key)

    combined_lines = [base_preamble.rstrip("\n")]
    if combined_lines and combined_lines[0]:
        combined_lines.append("\n\n")

    for s in base_sections:
        combined_lines.append(s["full_header"] + "\n")
        combined_lines.append("".join(s["body_lines"]).rstrip("\n") + "\n\n")

    for s in new_sections:
        combined_lines.append(s["full_header"] + "\n")
        combined_lines.append("".join(s["body_lines"]).rstrip("\n") + "\n\n")

    return "".join(combined_lines).rstrip() + "\n"

def wait_for_mergeable_settling(repo, pr_num, max_attempts=6, initial_wait=3):
    """
    Adaptive settling latch: Polls GitHub API with progressive backoff until the PR's
    asynchronous mergeability calculation settles to MERGEABLE.
    Prevents transient 'GraphQL: Pull Request is not mergeable' errors after force-pushes.
    """
    wait = initial_wait
    for attempt in range(1, max_attempts + 1):
        print(f"  ⏳ [Settling Latch] Waiting {wait}s for GitHub mergeability check to settle (attempt {attempt}/{max_attempts})...", flush=True)
        time.sleep(wait)
        out, _ = run_cmd(f"gh pr view {pr_num} -R {repo} --json mergeable,state,mergeStateStatus")
        if out:
            try:
                data = json.loads(out)
                state = data.get("state")
                if state != "OPEN":
                    return True
                mergeable = data.get("mergeable")
                merge_state = data.get("mergeStateStatus")
                if mergeable == "MERGEABLE" or merge_state in ["CLEAN", "UNSTABLE", "HAS_HOOKS"]:
                    print(f"  ✅ GitHub merge state settled to {mergeable} ({merge_state})!", flush=True)
                    return True
                elif mergeable == "CONFLICTING":
                    print(f"  ⚠️ GitHub reports branch is CONFLICTING.", flush=True)
                    return False
            except Exception:
                pass
        wait += 2
    return True

def merge_with_rebase(repo, pr_num, base_dir, use_admin=True):
    # HARD PRE-MERGE GUARDRAIL: Check PR diff for conflict markers
    pr_diff, _ = run_cmd(f"gh pr diff {pr_num} -R {repo}")
    if pr_diff and re.search(r'^\+([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))', pr_diff, re.MULTILINE):
        print(f"  ❌ GUARD BLOCKED: PR {repo}#{pr_num} contains unresolved Git merge conflict markers! Refusing to merge.", flush=True)
        return False

    admin_flag = "--admin " if use_admin else ""
    cmd = f"gh pr merge {pr_num} -R {repo} {admin_flag}--rebase --delete-branch"
    print(f"Attempting merge: {cmd}", flush=True)
    out, err = run_cmd(cmd)
    if out is not None:
        print(f"  [OK] Successfully merged {repo}#{pr_num}", flush=True)
        return True

    print(f"  [RETRY] Initial merge failed ({err}). Executing sequential re-sync and isolated feature rebase...", flush=True)
    local_dir = find_local_repo(base_dir, repo)
    if not local_dir:
        print(f"  [ERROR] Local repo directory not found for {repo}", flush=True)
        return False

    view_out, _ = run_cmd(f"gh pr view {pr_num} -R {repo} --json headRefName,baseRefName,title")
    if not view_out:
        print(f"  [ERROR] Could not fetch PR metadata for {repo}#{pr_num}", flush=True)
        return False

    v_data = json.loads(view_out)
    head = v_data.get("headRefName")
    base = v_data.get("baseRefName", "main")
    title = v_data.get("title", "")

    pkg_match = re.search(r'(?:bump|update)\s+([a-zA-Z0-9_\-]+)', title, re.IGNORECASE)
    package_name = pkg_match.group(1) if pkg_match else None

    # Step 1: Fetch and setup Worktree
    run_cmd(f"git fetch origin {base}:{base}", cwd=local_dir)
    run_cmd(f"git fetch origin {head}:{head}", cwd=local_dir)
    
    wt_base = os.path.dirname(local_dir) if os.path.basename(local_dir) != ".wts" else base_dir
    wt_dir = os.path.join(wt_base, ".wts", f"{repo.split('/')[-1]}-rebase-{pr_num}")
    if os.path.exists(wt_dir):
        run_cmd(f"git worktree remove {wt_dir} --force", cwd=local_dir)
        shutil.rmtree(wt_dir, ignore_errors=True)
    os.makedirs(os.path.dirname(wt_dir), exist_ok=True)
    run_cmd(f"git worktree add {wt_dir} {head}", cwd=local_dir)
    
    rebuilt_pushed = False
    try:
        # Step 2: Attempt clean merge of origin/<base> inside worktree
        m_out, m_err = run_cmd(f"git merge origin/{base} --no-edit", cwd=wt_dir)
        if m_out is not None:
            post_merge_diff, _ = run_cmd(f"git diff origin/{base}...HEAD", cwd=wt_dir)
            if post_merge_diff and re.search(r'^\+([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))', post_merge_diff, re.MULTILINE):
                print(f"  ❌ GUARD BLOCKED: Merge produced conflict markers! Aborting.", flush=True)
                return False
            run_cmd(f'git push origin "{head}" --force', cwd=wt_dir)
            rebuilt_pushed = True
        else:
            # Check unmerged paths
            stat_out, _ = run_cmd("git diff --name-only --diff-filter=U", cwd=wt_dir)
            unmerged = [u.strip() for u in stat_out.splitlines()] if stat_out else []
            lockfile_types = ['Gemfile.lock', 'composer.lock', 'package-lock.json', 'pnpm-lock.yaml']
            is_jules_file = lambda u: u.replace("\\", "/").lower().startswith(".jules/") and u.endswith(".md")
            is_lockfile = lambda u: any(u.endswith(ext) for ext in lockfile_types)

            has_code_conflict = any(not (is_lockfile(u) or is_jules_file(u)) for u in unmerged)

            if has_code_conflict:
                print(f"  [CONFLICT] PR {repo}#{pr_num} has code conflicts outside lockfiles/documentation: {unmerged}", flush=True)
                return False

            print(f"  [AUTO-RESOLVE] PR {repo}#{pr_num} has isolated lockfile/docs conflicts: {unmerged}. Resolving...", flush=True)

            # Resolve .jules/*.md conflicts via additive union
            for u in unmerged:
                if is_jules_file(u):
                    full_jules_path = os.path.join(wt_dir, u)
                    base_content, _ = run_cmd(f'git show origin/{base}:"{u}"', cwd=wt_dir)
                    feat_content, _ = run_cmd(f'git show origin/{head}:"{u}"', cwd=wt_dir)
                    unioned = union_jules_content(base_content or "", feat_content or "")
                    os.makedirs(os.path.dirname(full_jules_path), exist_ok=True)
                    with open(full_jules_path, "w", encoding="utf-8") as jf:
                        jf.write(unioned)
                    run_cmd(f'git add "{u}"', cwd=wt_dir)
                    print(f"  📝 Additively unioned documentation notes in {u}", flush=True)

            # Check out PR's version of conflicting lockfiles to get exact dependencies
            diff_paths, _ = run_cmd(f"gh pr diff {pr_num} -R {repo} --name-only")
            if diff_paths:
                lockfiles_to_rebuild = []
                for p in diff_paths.splitlines():
                    p_str = p.strip()
                    if not p_str:
                        continue
                    if any(p_str.endswith(ext) for ext in lockfile_types):
                        lockfiles_to_rebuild.append(p_str)
                    elif not is_jules_file(p_str):
                        run_cmd(f'git checkout origin/{head} -- "{p_str}"', cwd=wt_dir)
                
                for lf in lockfiles_to_rebuild:
                    full_lf = os.path.join(wt_dir, lf)
                    rebuilt = rebuild_lockfile_with_docker(wt_dir, full_lf, package_name)
                    if rebuilt:
                        run_cmd(f'git add "{lf}"', cwd=wt_dir)

                run_cmd("git add -A", cwd=wt_dir)
                staged_diff, _ = run_cmd("git diff --cached", cwd=wt_dir)
                if staged_diff and re.search(r'^\+([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))', staged_diff, re.MULTILINE):
                    print(f"  ❌ GUARD BLOCKED: Rebased branch contains conflict markers! Aborting push.", flush=True)
                    return False
                run_cmd(f'git commit -m "chore: sequential rebase {head} onto updated {base}"', cwd=wt_dir)
                run_cmd(f'git push origin "{head}" --force', cwd=wt_dir)
                rebuilt_pushed = True
    finally:
        run_cmd(f"git worktree remove {wt_dir} --force", cwd=local_dir)
        shutil.rmtree(wt_dir, ignore_errors=True)

    if rebuilt_pushed:
        wait_for_mergeable_settling(repo, pr_num)

    retry_out, retry_err = run_cmd(cmd)
    if retry_out is not None:
        print(f"  [OK] Successfully merged {repo}#{pr_num} on rebase retry!", flush=True)
        return True
    else:
        cmd_std = f"gh pr merge {pr_num} -R {repo} {admin_flag}--merge --delete-branch"
        retry_std_out, retry_std_err = run_cmd(cmd_std)
        if retry_std_out is not None:
            print(f"  [OK] Successfully merged {repo}#{pr_num} on standard merge retry!", flush=True)
            return True
        print(f"  [FAIL] Rebase retry failed for {repo}#{pr_num}: {retry_err or retry_std_err}", flush=True)
        return False

def main():
    parser = argparse.ArgumentParser(description="Sequential PR Rebase Merger with Adaptive Settling Latch")
    parser.add_argument("--pr-list", required=True, help="Comma-separated list of REPO#PR_NUM")
    parser.add_argument("--base-dir", default="C:/Users/johns/DEV", help="Base directory containing local repos")
    parser.add_argument("--no-admin", action="store_true", help="Do not use --admin flag during gh pr merge")
    parser.add_argument("--sync-submodules", action="store_true", help="Sync submodule pointers in parent repository")
    parser.add_argument("--push-parent", action="store_true", help="Push parent repository updates")
    args = parser.parse_args()

    prs = [p.strip() for p in args.pr_list.split(",") if p.strip()]
    print(f"Merging {len(prs)} PR(s) with sequential rebase recovery & adaptive settling...")

    use_admin = not args.no_admin
    merged_repos = set()
    for pr_item in prs:
        parts = pr_item.split("#")
        if len(parts) != 2:
            print(f"[ERROR] Invalid PR specifier: {pr_item}")
            continue
        repo, num = parts[0], parts[1]
        success = merge_with_rebase(repo, num, args.base_dir, use_admin=use_admin)
        if success:
            merged_repos.add(repo)

    if args.sync_submodules and args.base_dir and merged_repos:
        print(f"\nAdvancing submodule pointers for {len(merged_repos)} repo(s)...")
        updated = []
        for repo in merged_repos:
            loc = find_local_repo(args.base_dir, repo)
            if loc and os.path.exists(os.path.join(loc, ".git")):
                out_b, _ = run_cmd("git branch --show-current", cwd=loc)
                curr_b = out_b.strip() if out_b else "main"
                run_cmd(f"git checkout {curr_b} -f", cwd=loc)
                run_cmd(f"git pull origin {curr_b}", cwd=loc)
                rel_path = os.path.relpath(loc, args.base_dir)
                if rel_path != ".":
                    run_cmd(f'git add "{rel_path}"', cwd=args.base_dir)
                    updated.append(rel_path)
        if updated:
            c_msg = f"chore(submodules): advance {len(updated)} submodule pointer(s) after sequential PR merges"
            run_cmd(f'git commit -m "{c_msg}"', cwd=args.base_dir)
            if args.push_parent:
                run_cmd("git push origin main", cwd=args.base_dir)
                print("Pushed updated submodule pointers to origin/main.")

    print("\nSequential PR rebase merge workflow completed.")

if __name__ == "__main__":
    main()
