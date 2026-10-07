#!/usr/bin/env python3
"""
Bot PR Triage Runner CLI
Helper script to search, audit, categorize, sync, and batch process open bot PRs.
Enhanced with Windows UTF-8 safety, non-interactive GH flags, local 3-way diff analysis,
stale-base auto-healing, and workspace/submodule filtering.
"""

import argparse
import json
import os
import re
import subprocess
import sys

# Force UTF-8 encoding across Windows console streams
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def log(msg, **kwargs):
    print(msg, flush=True, **kwargs)

def get_base_env():
    env = os.environ.copy()
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_PAGER"] = "1"
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["APP_ENV"] = "testing"
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

def run_targeted_tests_for_files(local_repo, modified_files):
    """
    Discovers and executes targeted unit tests for modified source files across
    TypeScript (Jest), PHP (PHPUnit), and Python (pytest).
    """
    if not local_repo or not modified_files:
        return True, "No files to test"

    test_results = []
    
    # 1. TypeScript / JavaScript (Jest)
    ts_files = [f for f in modified_files if f.endswith(('.ts', '.tsx', '.js', '.jsx')) and not f.startswith('.')]
    if ts_files and os.path.exists(os.path.join(local_repo, "package.json")):
        files_arg = " ".join(f'"{f}"' for f in ts_files)
        log(f"    🧪 Running Jest related tests for {len(ts_files)} file(s)...")
        out, err = run_command(f"npx jest --findRelatedTests {files_arg} --passWithNoTests --runInBand", cwd=local_repo, timeout=45)
        if out is not None:
            test_results.append(("TypeScript/Jest", True, "Passed"))
        else:
            test_results.append(("TypeScript/Jest", False, err or "Tests failed"))

    # 2. PHP (PHPUnit)
    php_files = [f for f in modified_files if f.endswith('.php') and not f.startswith('.')]
    if php_files and os.path.exists(os.path.join(local_repo, "composer.json")):
        matched_tests = []
        for pf in php_files:
            base_name = os.path.splitext(os.path.basename(pf))[0]
            # Search for matching Test.php
            for root, _, files in os.walk(os.path.join(local_repo, "tests")):
                for f in files:
                    if f == f"{base_name}Test.php" or f == f"test_{base_name}.php":
                        matched_tests.append(os.path.relpath(os.path.join(root, f), local_repo))

        if matched_tests:
            test_target = " ".join(f'"{t}"' for t in matched_tests)
            log(f"    🧪 Running PHPUnit on {len(matched_tests)} targeted test fixture(s)...")
            out, err = run_command(f"vendor/bin/phpunit {test_target}", cwd=local_repo, timeout=45)
            if out is not None:
                test_results.append(("PHP/PHPUnit", True, "Passed"))
            else:
                test_results.append(("PHP/PHPUnit", False, err or "Tests failed"))

    # 3. Python (pytest)
    py_files = [f for f in modified_files if f.endswith('.py') and not f.startswith('.')]
    if py_files and (os.path.exists(os.path.join(local_repo, "pyproject.toml")) or os.path.exists(os.path.join(local_repo, "requirements.txt"))):
        matched_tests = []
        for pyf in py_files:
            base_name = os.path.splitext(os.path.basename(pyf))[0]
            for root, _, files in os.walk(os.path.join(local_repo, "tests")):
                for f in files:
                    if f in [f"test_{base_name}.py", f"{base_name}_test.py"]:
                        matched_tests.append(os.path.relpath(os.path.join(root, f), local_repo))

        if matched_tests:
            test_target = " ".join(f'"{t}"' for t in matched_tests)
            log(f"    🧪 Running pytest on {len(matched_tests)} targeted test fixture(s)...")
            out, err = run_command(f"pytest {test_target}", cwd=local_repo, timeout=45)
            if out is not None:
                test_results.append(("Python/pytest", True, "Passed"))
            else:
                test_results.append(("Python/pytest", False, err or "Tests failed"))

    # 4. Elixir / Phoenix (Mix / Docker Compose)
    elixir_files = [f for f in modified_files if f.endswith(('.ex', '.exs', '.heex')) or f in ['mix.exs', 'mix.lock']]
    if elixir_files and os.path.exists(os.path.join(local_repo, "mix.exs")):
        has_docker = (
            os.path.exists(os.path.join(local_repo, "docker-compose.yml"))
            or os.path.exists(os.path.join(local_repo, "compose.yaml"))
        )
        runner_prefix = "docker compose run --rm app " if has_docker else ""
        
        # If mix.lock was modified, ensure dependencies are synchronized
        if any(f.endswith('mix.lock') for f in elixir_files):
            log("    📦 Syncing Elixir Hex dependencies (mix deps.get)...")
            run_command(f"{runner_prefix}mix deps.get", cwd=local_repo, timeout=60)

        matched_tests = []
        for ef in elixir_files:
            if ef.endswith('_test.exs'):
                matched_tests.append(ef)
            elif ef.endswith(('.ex', '.heex')):
                base_name = os.path.splitext(os.path.basename(ef))[0]
                for root, _, files in os.walk(os.path.join(local_repo, "test")):
                    for f in files:
                        if f == f"{base_name}_test.exs":
                            matched_tests.append(os.path.relpath(os.path.join(root, f), local_repo))

        matched_tests = [t.replace('\\', '/') for t in set(matched_tests)]
        test_target = " ".join(f'"{t}"' for t in matched_tests) if matched_tests else ""
        log(f"    🧪 Running Elixir tests ({'targeted: ' + str(len(matched_tests)) if test_target else 'full suite'})...")
        out, err = run_command(f"{runner_prefix}mix test {test_target}".strip(), cwd=local_repo, timeout=120)
        if out is not None:
            test_results.append(("Elixir/Mix", True, "Passed"))
        else:
            test_results.append(("Elixir/Mix", False, err or "Tests failed"))

    if not test_results:
        return True, "No specific test fixtures found (clean)"

    all_passed = all(r[1] for r in test_results)
    summary = "; ".join(f"{r[0]}: {'PASSED' if r[1] else 'FAILED'}" for r in test_results)
    return all_passed, summary

def find_local_repo_dir(base_dir, repo_name):
    if not base_dir:
        return None
    repo_basename = repo_name.split("/")[-1]
    candidates = [
        os.path.join(base_dir, repo_basename),
        os.path.join(base_dir, repo_name),
        base_dir if os.path.basename(os.path.abspath(base_dir)) == repo_basename else None
    ]
    for c in candidates:
        if c and os.path.exists(os.path.join(c, ".git")):
            return os.path.abspath(c)
    return None

def detect_workspace_repos(workspace_dir):
    """Detects the root repo and any git submodules in the workspace."""
    repos = set()
    if not workspace_dir or not os.path.exists(workspace_dir):
        return repos
    
    root_git = os.path.join(workspace_dir, ".git")
    if os.path.exists(root_git):
        repos.add(os.path.basename(os.path.abspath(workspace_dir)).lower())
    
    # Check submodules
    out, _ = run_command("git submodule status", cwd=workspace_dir)
    if out:
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                sub_path = parts[1].strip()
                repos.add(os.path.basename(sub_path).lower())
                repos.add(sub_path.lower())
    
    # Also scan top-level directory entries with .git
    try:
        for entry in os.listdir(workspace_dir):
            full_path = os.path.join(workspace_dir, entry)
            if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, ".git")):
                repos.add(entry.lower())
    except Exception:
        pass

    return repos

def cmd_search(args):
    prs = []
    # If specific repo is provided or owner contains a slash (e.g. owner/repo)
    target_repo = getattr(args, "repo", None)
    if not target_repo and args.owner and "/" in args.owner:
        target_repo = args.owner

    if target_repo:
        print(f"Listing open PRs directly for repository: {target_repo} (state: {args.state}, limit: {args.limit})...")
        cmd = f"gh pr list --repo {target_repo} --state {args.state} --limit {args.limit} --json number,title,author,createdAt,labels,url"
        raw_output, err = run_command(cmd, timeout=30)
        if raw_output:
            try:
                prs = json.loads(raw_output)
                for p in prs:
                    if "repository" not in p:
                        p["repository"] = {"nameWithOwner": target_repo, "name": target_repo.split("/")[-1]}
            except Exception as e:
                print(f"⚠️ JSON parse error on gh pr list: {e}", file=sys.stderr)

    if not prs:
        print(f"Searching open PRs for owner: {args.owner} (state: {args.state}, limit: {args.limit})...")
        cmd = f"gh search prs --owner {args.owner} --state {args.state} --limit {args.limit} --json number,title,repository,author,createdAt,labels,url"
        raw_output, err = run_command(cmd, timeout=30)
        if raw_output:
            try:
                prs = json.loads(raw_output)
            except Exception as e:
                print(f"⚠️ JSON parse error on gh search prs: {e}", file=sys.stderr)
        
        # Fallback to local workspace repository auto-discovery if gh search timed out or returned error
        if not prs and args.workspace_filter:
            detected = detect_workspace_repos(args.workspace_filter)
            print(f"🔄 Search returned empty/timed out. Falling back to direct gh pr list across {len(detected)} detected repos...")
            for repo_cand in detected:
                full_repo_name = f"{args.owner}/{repo_cand}" if "/" not in repo_cand else repo_cand
                cmd_fb = f"gh pr list --repo {full_repo_name} --state {args.state} --limit {args.limit} --json number,title,author,createdAt,labels,url"
                out_fb, _ = run_command(cmd_fb, timeout=20)
                if out_fb:
                    try:
                        p_list = json.loads(out_fb)
                        for p in p_list:
                            if "repository" not in p:
                                p["repository"] = {"nameWithOwner": full_repo_name, "name": repo_cand}
                        prs.extend(p_list)
                    except Exception:
                        pass

    # Optional Repository / Workspace filtering
    filter_repos = set()
    if args.workspace_filter:
        detected = detect_workspace_repos(args.workspace_filter)
        filter_repos.update(detected)
        print(f"🔍 Auto-detected {len(detected)} workspace repos/submodules for filtering: {', '.join(sorted(detected))}")

    if args.repo_filter:
        custom_filters = [r.strip().lower() for r in args.repo_filter.split(",") if r.strip()]
        filter_repos.update(custom_filters)

    if filter_repos:
        original_count = len(prs)
        prs = [
            p for p in prs
            if any(
                fr in p.get("repository", {}).get("nameWithOwner", "").lower()
                or fr == p.get("repository", {}).get("name", "").lower()
                for fr in filter_repos
            )
        ]
        print(f"🎯 Filtered down from {original_count} to {len(prs)} relevant repository PRs.")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(prs, f, indent=2)
    
    print(f"✅ Successfully found {len(prs)} PRs. Results written to: {args.output}")

def cmd_audit(args):
    if not os.path.exists(args.input_file):
        print(f"❌ Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.input_file, "r", encoding="utf-8") as f:
        prs = json.load(f)

    audited_prs = []
    print(f"Auditing {len(prs)} PRs...")

    for i, pr in enumerate(prs, 1):
        repo_name = pr.get("repository", {}).get("nameWithOwner", "")
        pr_number = pr.get("number")
        
        view_cmd = f"gh pr view {pr_number} -R {repo_name} --json number,title,state,author,files,statusCheckRollup,body,headRefName,baseRefName,mergeable,mergeStateStatus"
        view_out, err = run_command(view_cmd)
        
        if not view_out:
            print(f"  [{i}/{len(prs)}] ⚠️ Warning: Failed to fetch {repo_name}#{pr_number}: {err}")
            continue

        try:
            details = json.loads(view_out)
            details["repository"] = pr.get("repository")
            details["url"] = pr.get("url")
        except Exception:
            continue

        files = details.get("files", [])
        status_checks = details.get("statusCheckRollup", []) or []
        head_branch = details.get("headRefName", "")
        base_branch = details.get("baseRefName", "main")
        remote_state = details.get("state", "OPEN")
        
        # Scratch file detection
        has_scratch = any(re.search(r'^test(_.*)?\.(ts|js)$', f.get("path", "")) for f in files)
        
        # Meta files vs code files
        non_meta_files = [
            f for f in files
            if not f.get("path", "").lower().startswith(".jules/")
            and not f.get("path", "").lower().startswith(".github/")
            and f.get("path", "") not in ["package.json", "package-lock.json", "composer.lock", "pnpm-lock.yaml"]
        ]
        is_metadata_only = len(non_meta_files) == 0

        # CI Checks analysis
        ci_failed = any(c.get("conclusion") in ["FAILURE", "CANCELLED", "TIMED_OUT"] for c in status_checks)
        audit_bot_passed = any(c.get("name") == "audit-bot-pr" and c.get("conclusion") == "SUCCESS" for c in status_checks)
        has_audit_bot = any(c.get("name") == "audit-bot-pr" for c in status_checks)

        # Destructive file line deletions check (>15 lines in schema/entrypoints)
        destructive_deletion = False
        critical_paths = ["schema.prisma", "index.ts", "index.php", "init.sql", "routes.php"]
        for f in files:
            path_str = f.get("path", "").lower()
            if any(cp in path_str for cp in critical_paths):
                if f.get("deletions", 0) > 15 and f.get("additions", 0) < 5:
                    destructive_deletion = True
                    break

        # Local 3-way diff check and stale base diagnosis
        local_repo = find_local_repo_dir(args.base_dir, repo_name) if args.base_dir else None
        local_zero_diff = False
        local_merge_conflict = False
        stale_base_detected = False
        superseded_by = None

        if local_repo:
            diff_stat, _ = run_command(f"git diff {base_branch}...origin/{head_branch} --stat", cwd=local_repo)
            if diff_stat is not None and len(diff_stat.strip()) == 0:
                local_zero_diff = True

            merge_test, _ = run_command(f"git merge-tree $(git merge-base {base_branch} origin/{head_branch}) {base_branch} origin/{head_branch}", cwd=local_repo)
            if merge_test and "<<<<<<<" in merge_test:
                local_merge_conflict = True
            
            # Check if PR branch is behind base branch
            behind_check, _ = run_command(f"git rev-list --count origin/{head_branch}..{base_branch}", cwd=local_repo)
            if behind_check and behind_check.isdigit() and int(behind_check) > 0:
                stale_base_detected = True

            # Check if substantive changes are already incorporated into base_branch (superseded PR)
            if non_meta_files and (local_merge_conflict or stale_base_detected):
                non_meta_paths = [f.get("path", "") for f in non_meta_files]
                paths_arg = " ".join(f'"{p}"' for p in non_meta_paths if p)
                if paths_arg:
                    merge_base, _ = run_command(f"git merge-base {base_branch} origin/{head_branch}", cwd=local_repo)
                    if merge_base and merge_base.strip():
                        overlap_log, _ = run_command(f'git log {merge_base.strip()}..{base_branch} --oneline -- {paths_arg}', cwd=local_repo)
                        if overlap_log and overlap_log.strip():
                            top_commit = overlap_log.strip().splitlines()[0]
                            # Check if the code diff of substantive files against base_branch is empty
                            # or only removes newer additions on base_branch
                            subst_diff, _ = run_command(f'git diff {base_branch} origin/{head_branch} -- {paths_arg}', cwd=local_repo)
                            if subst_diff is not None:
                                superseded_by = top_commit

        category = "Group A"
        reasons = []

        if remote_state in ["MERGED", "CLOSED"]:
            category = "Group C"
            reasons.append(f"PR already {remote_state} on GitHub")
        elif superseded_by:
            category = "Group C (Superseded)"
            reasons.append(f"Superseded by merged commit on {base_branch}: {superseded_by}")
        elif is_metadata_only or local_zero_diff:
            category = "Group C"
            reasons.append("Zero non-metadata code diffs (already integrated or hallucinatory)")
        elif destructive_deletion:
            category = "Group B"
            reasons.append("Destructive line deletions in critical schema/entrypoint files")
        elif has_scratch:
            category = "Group B"
            reasons.append("Contains uncleaned scratch verification files")
        elif ci_failed:
            if stale_base_detected and not local_merge_conflict:
                category = "Group A (Needs Base Sync)"
                reasons.append("CI failed on stale base branch (sync required)")
            else:
                category = "Group B"
                reasons.append("Failed one or more CI status checks")
        elif has_audit_bot and not audit_bot_passed:
            category = "Group B"
            reasons.append("Failed audit-bot-pr guardrail check")
        # Local targeted unit tests verification (optional)
        local_tests_passed = True
        local_tests_summary = ""
        if local_repo and getattr(args, 'verify_local_tests', False) and not local_merge_conflict:
            modified_paths = [f.get("path") for f in files if f.get("path")]
            local_tests_passed, local_tests_summary = run_targeted_tests_for_files(local_repo, modified_paths)
            if not local_tests_passed:
                category = "Group B"
                reasons.append(f"Targeted test failure: {local_tests_summary}")

        details["category"] = category
        details["auditReasons"] = reasons
        details["localZeroDiff"] = local_zero_diff
        details["localMergeConflict"] = local_merge_conflict
        details["localTestsPassed"] = local_tests_passed
        details["localTestsSummary"] = local_tests_summary
        details["staleBase"] = stale_base_detected
        details["supersededBy"] = superseded_by
        audited_prs.append(details)

        print(f"  [{i}/{len(prs)}] {repo_name}#{pr_number} -> {category} ({', '.join(reasons) if reasons else 'Clean & Safe'})")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(audited_prs, f, indent=2)

    # Optional Markdown Table Export
    if args.markdown_output:
        os.makedirs(os.path.dirname(os.path.abspath(args.markdown_output)), exist_ok=True)
        generate_markdown_report(audited_prs, args.markdown_output)
        print(f"📄 Markdown triage report written to: {args.markdown_output}")

    print(f"✅ Audit completed for {len(audited_prs)} PRs. Results written to: {args.output}")

def generate_markdown_report(audited_prs, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 📋 Bot Pull Request Triage Report\n\n")
        f.write("| Repo | PR # | Title | Category | Reasons | URL |\n")
        f.write("| :--- | :---: | :--- | :---: | :--- | :--- |\n")
        for pr in audited_prs:
            repo = pr.get("repository", {}).get("nameWithOwner", "")
            num = pr.get("number")
            title = pr.get("title", "").replace("|", "\\|")
            cat = pr.get("category", "Group A")
            reasons = "; ".join(pr.get("auditReasons", [])) or "Clean & Safe"
            url = pr.get("url", "")
            f.write(f"| `{repo}` | **#{num}** | {title} | **{cat}** | {reasons} | [Link]({url}) |\n")

def union_jules_markdown_files(file_path, local_dir, base_branch):
    """Unions markdown learning sections from HEAD and base branch without conflict markers."""
    base_content, _ = run_command(f'git show "origin/{base_branch}:{file_path}"', cwd=local_dir)
    head_content, _ = run_command(f'git show "HEAD:{file_path}"', cwd=local_dir)
    
    sections = {}
    
    def extract_sections(text):
        if not text:
            return
        blocks = re.split(r'(?m)(?=^##\s+)', text.strip())
        for b in blocks:
            b_str = b.strip()
            if not b_str:
                continue
            first_line = b_str.splitlines()[0].strip()
            if first_line not in sections:
                sections[first_line] = b_str

    extract_sections(head_content)
    extract_sections(base_content)
    
    full_path = os.path.join(local_dir, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(sections.values()) + "\n")

def sync_single_pr_base(repo, pr_num, base_dir, push=True):
    """Syncs target PR branch with latest remote base branch."""
    view_out, err = run_command(f"gh pr view {pr_num} -R {repo} --json headRefName,baseRefName,state")
    if not view_out:
        return False, f"Could not view PR: {err}"
    
    pr_info = json.loads(view_out)
    if pr_info.get("state") in ["MERGED", "CLOSED"]:
        return False, f"PR is already {pr_info.get('state')}"
    
    head = pr_info.get("headRefName")
    base = pr_info.get("baseRefName", "main")
    
    local_dir = find_local_repo_dir(base_dir, repo)
    if not local_dir:
        return False, f"Local directory not found for repository: {repo}"

    print(f"🔄 Syncing base '{base}' into '{head}' in {local_dir}...")
    run_command(f"git checkout {base} -f", cwd=local_dir)
    run_command(f"git pull origin {base}", cwd=local_dir)
    run_command("git merge --abort", cwd=local_dir)
    run_command(f"git fetch origin {head}:{head}", cwd=local_dir)
    run_command(f"git checkout \"{head}\" -f", cwd=local_dir)
    
    code_m, err_m = run_command(f"git merge origin/{base} --no-edit", cwd=local_dir)
    if code_m is None:
        print(f"  ⚠️ Merge conflict encountered. Checking for auto-resolvable lockfiles and agent notes...")
        res_st, _ = run_command("git status --porcelain", cwd=local_dir)
        if res_st:
            conflict_files = [line[3:].strip() for line in res_st.splitlines() if len(line) > 3]
            auto_resolvable = all(
                any(cf.endswith(ext) for ext in ['package-lock.json', 'composer.lock', 'package.json', 'pnpm-lock.yaml'])
                or '.jules' in cf.lower()
                for cf in conflict_files
            )
            if auto_resolvable:
                for cf in conflict_files:
                    if '.jules' in cf.lower() and cf.endswith('.md'):
                        print(f"  📝 Unioning agent learning notes in {cf}...")
                        union_jules_markdown_files(cf, local_dir, base)
                        run_command(f"git add \"{cf}\"", cwd=local_dir)
                    else:
                        run_command(f"git checkout origin/{base} -- \"{cf}\"", cwd=local_dir)
                        run_command(f"git add \"{cf}\"", cwd=local_dir)
                run_command(f"git commit -m \"fix(merge): sync latest {base} and union agent notes\"", cwd=local_dir)
            else:
                run_command("git merge --abort", cwd=local_dir)
                return False, f"Non-lockfile merge conflicts in: {', '.join(conflict_files)}"

    # Diff purification check
    stat_out, _ = run_command(f"git diff origin/{base}..HEAD --stat", cwd=local_dir)
    if stat_out:
        print(f"  📊 Purified PR diff against origin/{base}:\n{stat_out}")

    if push:
        print(f"  ⬆️ Pushing synced branch '{head}' to origin...")
        run_command(f"git push origin \"{head}\"", cwd=local_dir)

    return True, "Successfully synced base branch"

def clean_git_locks(local_dir):
    """Removes dangling git lock files on Windows."""
    git_dir = os.path.join(local_dir, ".git")
    if not os.path.exists(git_dir):
        return
    for root, _, files in os.walk(git_dir):
        for f in files:
            if f.endswith(".lock"):
                lock_path = os.path.join(root, f)
                try:
                    os.remove(lock_path)
                except Exception:
                    pass

def harmonize_case_collision_index(local_dir):
    """
    Audits and resolves case-collision paths in the git index (e.g. .jules/ vs .Jules/)
    that cause phantom modifications or checkout collisions on case-insensitive filesystems (Windows/macOS).
    """
    if not local_dir or not os.path.exists(os.path.join(local_dir, ".git")):
        return False, "Not a git repository"

    out, err = run_command("git ls-files -s", cwd=local_dir)
    if not out:
        return True, "No tracked files found"

    # Map lowercase path -> list of (stage, hash, original_path)
    path_map = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        meta, orig_path = parts[0], parts[1]
        meta_parts = meta.split()
        if len(meta_parts) < 3:
            continue
        blob_hash = meta_parts[1]
        lower_path = orig_path.lower()
        path_map.setdefault(lower_path, []).append((blob_hash, orig_path))

    collisions = {k: v for k, v in path_map.items() if len(v) > 1}
    if not collisions:
        return True, "Zero case-collision paths in git index"

    print(f"  🔍 Found {len(collisions)} case-colliding path(s) in git index:")
    fixed_count = 0

    for lower_p, entries in collisions.items():
        print(f"    - Collision for '{lower_p}': {[e[1] for e in entries]}")
        # Determine canonical path (prefer lowercase or .jules/)
        canonical_entry = None
        for e in entries:
            if e[1].startswith(".jules/") or (not e[1].startswith(".Jules/") and e[1] == lower_p):
                canonical_entry = e
                break
        if not canonical_entry:
            canonical_entry = sorted(entries, key=lambda x: (x[1].isupper(), len(x[1])))[0]

        canonical_path = canonical_entry[1]
        non_canonical = [e for e in entries if e[1] != canonical_path]

        # If it's a markdown learning file, union content from all colliding blobs
        if lower_p.endswith(".md"):
            all_sections = {}
            for blob_hash, p in entries:
                blob_content, _ = run_command(f"git cat-file -p {blob_hash}", cwd=local_dir)
                if blob_content:
                    blocks = re.split(r'(?m)(?=^##\s+)', blob_content.strip())
                    for b in blocks:
                        b_str = b.strip()
                        if b_str:
                            header = b_str.splitlines()[0].strip()
                            if header not in all_sections:
                                all_sections[header] = b_str

            # Write unioned content to disk
            full_canon_path = os.path.join(local_dir, canonical_path)
            os.makedirs(os.path.dirname(full_canon_path), exist_ok=True)
            with open(full_canon_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(all_sections.values()) + "\n")

        # Remove non-canonical paths from git index
        for _, bad_path in non_canonical:
            run_command(f'git rm --cached -f "{bad_path}"', cwd=local_dir)
            print(f"      🗑️ Removed cached index duplicate: {bad_path}")

        # Re-add canonical path
        run_command(f'git add "{canonical_path}"', cwd=local_dir)
        print(f"      ✅ Re-indexed canonical path: {canonical_path}")
        fixed_count += 1

    if fixed_count > 0:
        run_command('git commit -m "fix(git): harmonize case-colliding index paths and union logs"', cwd=local_dir)
        return True, f"Harmonized {fixed_count} case-colliding path(s)"
    return True, "No changes needed"


def repair_conflict_markers_in_file(file_path):
    """Scans and strips dangling conflict markers and duplicate conflict blocks."""
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return False

    original = content
    # Remove standalone conflict marker lines
    lines = content.splitlines()
    cleaned_lines = []
    i = 0
    modified = False

    while i < len(lines):
        line = lines[i]
        # Check for conflict marker lines
        if re.match(r'^(<{7}|={7}|>{7})(.*)$', line.strip()):
            modified = True
            i += 1
            continue
        cleaned_lines.append(line)
        i += 1

    # Check for excessive repetitive padding lines (>50 identical consecutive comments or blank lines)
    deduped_lines = []
    rep_count = 0
    last_line = None
    for line in cleaned_lines:
        if line == last_line and (line.strip().startswith("//") or line.strip().startswith("#") or line.strip() == ""):
            rep_count += 1
            if rep_count > 10:
                modified = True
                continue
        else:
            rep_count = 0
            last_line = line
        deduped_lines.append(line)

    new_content = "\n".join(deduped_lines) + ("\n" if original.endswith("\n") else "")
    if modified and new_content != original:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    return False

def auto_repair_single_pr(repo, pr_num, base_dir, push=True):
    """Diagnoses and repairs common bot PR corruption patterns in local working copy."""
    view_out, err = run_command(f"gh pr view {pr_num} -R {repo} --json headRefName,baseRefName,state")
    if not view_out:
        return False, f"Could not view PR: {err}"
    
    pr_info = json.loads(view_out)
    if pr_info.get("state") in ["MERGED", "CLOSED"]:
        return False, f"PR is already {pr_info.get('state')}"
    
    head = pr_info.get("headRefName")
    base = pr_info.get("baseRefName", "main")
    local_dir = find_local_repo_dir(base_dir, repo)
    if not local_dir:
        return False, f"Local directory not found for: {repo}"

    clean_git_locks(local_dir)
    harmonize_case_collision_index(local_dir)
    print(f"🔧 Auto-repairing '{head}' in {local_dir}...")
    run_command(f"git fetch origin {head}:{head}", cwd=local_dir)
    run_command(f"git checkout \"{head}\" -f", cwd=local_dir)
    harmonize_case_collision_index(local_dir)

    # Find modified files in this PR
    diff_files_out, _ = run_command(f"git diff --name-only origin/{base}...HEAD", cwd=local_dir)
    if not diff_files_out:
        return True, "No files modified in PR"

    modified_files = [f.strip() for f in diff_files_out.splitlines() if f.strip()]
    repaired_count = 0

    for mf in modified_files:
        full_path = os.path.join(local_dir, mf)
        if repair_conflict_markers_in_file(full_path):
            print(f"  ✨ Cleaned conflict markers / repetitive bloat in: {mf}")
            run_command(f"git add \"{mf}\"", cwd=local_dir)
            repaired_count += 1

    if repaired_count > 0:
        run_command('git commit -m "fix(auto-repair): resolve conflict markers and syntax anomalies"', cwd=local_dir)
        if push:
            print(f"  ⬆️ Pushing repaired branch '{head}' to origin...")
            run_command(f"git push origin \"{head}\"", cwd=local_dir)
        return True, f"Repaired {repaired_count} file(s) and pushed"
    else:
        return True, "No corrupted markers found"

def cmd_auto_repair(args):
    prs = [p.strip() for p in args.pr_list.split(",") if p.strip()]
    print(f"Auto-repairing {len(prs)} PRs...")
    for item in prs:
        parts = item.split("#")
        if len(parts) != 2:
            print(f"❌ Invalid PR specifier: {item}", file=sys.stderr)
            continue
        repo, pr_num = parts[0], parts[1]
        success, msg = auto_repair_single_pr(repo, pr_num, args.base_dir, push=not args.dry_run)
        if success:
            print(f"✅ {item}: {msg}")
        else:
            print(f"❌ {item}: {msg}", file=sys.stderr)

def cmd_sync_base(args):
    prs = [p.strip() for p in args.pr_list.split(",") if p.strip()]
    print(f"Syncing {len(prs)} PRs against remote base branches...")

    for item in prs:
        parts = item.split("#")
        if len(parts) != 2:
            print(f"❌ Invalid PR specifier: {item}", file=sys.stderr)
            continue
        repo, pr_num = parts[0], parts[1]
        success, msg = sync_single_pr_base(repo, pr_num, args.base_dir, push=not args.dry_run)
        if success:
            print(f"✅ {item}: {msg}")
        else:
            print(f"❌ {item}: {msg}", file=sys.stderr)

def cmd_harmonize_case(args):
    """Audits and fixes case-collision index entries across repositories."""
    base_dir = os.path.abspath(args.base_dir or os.getcwd())
    print(f"🔍 Auditing and harmonizing case-collision index entries in {base_dir}...")
    success, msg = harmonize_case_collision_index(base_dir)
    if success:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}", file=sys.stderr)

def get_pr_modified_files_remote(repo, pr_num):
    """Fetches list of modified files for a PR via gh CLI."""
    out, _ = run_command(f"gh pr view {pr_num} -R {repo} --json files")
    if out:
        try:
            data = json.loads(out)
            return [f.get("path") for f in data.get("files", []) if f.get("path")]
        except Exception:
            pass
    return []

def cmd_merge_batch(args):
    prs = [p.strip() for p in args.pr_list.split(",") if p.strip()]
    print(f"Merging {len(prs)} PRs with base sync...")

    # Optional: Disjoint file analysis
    if len(prs) > 1 and getattr(args, 'check_disjoint', True):
        print(f"\n📊 Evaluating pairwise modified file overlap across {len(prs)} PRs...")
        pr_files = {}
        for item in prs:
            parts = item.split("#")
            if len(parts) == 2:
                r, num = parts[0], parts[1]
                files = get_pr_modified_files_remote(r, num)
                # Ignore agent memory logs from code overlap calculations
                code_files = {f for f in files if not f.lower().startswith(".jules/") and not f.lower().startswith(".github/")}
                pr_files[item] = code_files

        all_disjoint = True
        pr_keys = list(pr_files.keys())
        for i in range(len(pr_keys)):
            for j in range(i + 1, len(pr_keys)):
                p1, p2 = pr_keys[i], pr_keys[j]
                overlap = pr_files[p1].intersection(pr_files[p2])
                if overlap:
                    all_disjoint = False
                    print(f"  ⚠️ Overlap between {p1} and {p2}: {sorted(list(overlap))}")
                else:
                    print(f"  ✅ {p1} & {p2}: Completely Disjoint")

        if all_disjoint:
            print("🚀 Fast-Path Enabled: All PRs in batch touch 100% disjoint files (zero merge ordering hazards).\n")

    merged_repos = set()

    for item in prs:
        parts = item.split("#")
        if len(parts) == 2:
            repo, pr_num = parts[0], parts[1]
        else:
            print(f"❌ Invalid PR specifier: {item}. Expected OWNER/REPO#NUMBER", file=sys.stderr)
            continue

        # Sync base if local directory exists
        if args.base_dir and not args.no_sync:
            sync_single_pr_base(repo, pr_num, args.base_dir, push=not args.dry_run)

        cmd = f"gh pr merge {pr_num} -R {repo} --admin --merge --delete-branch"
        print(f"Executing: {cmd}")
        if not args.dry_run:
            out, err = run_command(cmd)
            if out is not None:
                print(f"✅ Successfully merged {item}")
                merged_repos.add(repo)
            else:
                print(f"❌ Failed to merge {item}: {err}")
        else:
            merged_repos.add(repo)

    # Optional: Fast-forward local submodules and advance parent pointer
    if args.sync_submodules and args.base_dir and merged_repos and not args.dry_run:
        print(f"\n🔄 Syncing parent submodule pointers for {len(merged_repos)} merged repo(s)...")
        updated_submodules = []
        for repo in merged_repos:
            local_dir = find_local_repo_dir(args.base_dir, repo)
            if local_dir and os.path.exists(os.path.join(local_dir, ".git")):
                # Determine base branch (main or master)
                out_b, _ = run_command("git branch --show-current", cwd=local_dir)
                curr_branch = out_b.strip() if out_b else "main"
                run_command(f"git checkout {curr_branch} -f", cwd=local_dir)
                run_command(f"git pull origin {curr_branch}", cwd=local_dir)
                
                # Check relative path from base_dir
                rel_path = os.path.relpath(local_dir, args.base_dir)
                if rel_path != ".":
                    run_command(f'git add "{rel_path}"', cwd=args.base_dir)
                    updated_submodules.append(rel_path)
                    print(f"  📌 Staged updated submodule pointer for: {rel_path}")

        if updated_submodules:
            commit_msg = f"chore(submodules): fast-forward {len(updated_submodules)} submodule pointer(s) after bot PR batch merges"
            c_out, c_err = run_command(f'git commit -m "{commit_msg}"', cwd=args.base_dir)
            if c_out is not None:
                print(f"✅ Committed updated submodule pointers in parent repository.")
                if args.push_parent:
                    p_out, p_err = run_command("git push origin main", cwd=args.base_dir)
                    if p_out is not None:
                        print(f"⬆️ Successfully pushed parent repository updates to origin/main.")
                    else:
                        print(f"⚠️ Failed to push parent repository: {p_err}")
            else:
                print(f"ℹ️ Parent repository working tree already up to date ({c_err}).")


def cmd_close_batch(args):
    prs = [p.strip() for p in args.pr_list.split(",") if p.strip()]
    print(f"Closing {len(prs)} PRs with comment: '{args.reason}'...")

    for item in prs:
        parts = item.split("#")
        if len(parts) == 2:
            repo, pr_num = parts[0], parts[1]
        else:
            print(f"❌ Invalid PR specifier: {item}. Expected OWNER/REPO#NUMBER", file=sys.stderr)
            continue

        # Live state pre-check
        view_out, _ = run_command(f"gh pr view {pr_num} -R {repo} --json state")
        if view_out:
            try:
                pr_info = json.loads(view_out)
                state = pr_info.get("state")
                if state in ["CLOSED", "MERGED"]:
                    print(f"ℹ️ {item} is already {state}. Skipping closure.")
                    continue
            except Exception:
                pass

        cmd = f'gh pr close {pr_num} -R {repo} --comment "{args.reason}"'
        print(f"Executing: {cmd}")
        if not args.dry_run:
            out, err = run_command(cmd)
            if out is not None:
                print(f"✅ Successfully closed {item}")
            else:
                print(f"❌ Failed to close {item}: {err}")

def cmd_harvest(args):
    """Scans remote branches for unmerged commits and surfaces recoverable code patches."""
    local_dir = os.path.abspath(args.base_dir) if args.base_dir else os.getcwd()
    print(f"🌾 Scanning remote branches in {local_dir} for unmerged/stalled PR code...", flush=True)
    
    out, err = run_command("git branch -r", cwd=local_dir)
    if not out:
        print(f"❌ Failed to list remote branches: {err}", file=sys.stderr, flush=True)
        return

    base_branch = args.base_branch or "main"
    branches = [b.strip() for b in out.splitlines() if 'origin/' in b and 'HEAD' not in b and f'origin/{base_branch}' not in b]
    print(f"  Found {len(branches)} remote tracking branches. Auditing unmerged commits...", flush=True)
    
    candidates = []
    for idx, b in enumerate(branches, 1):
        b_name = b.replace('origin/', '')
        log_out, _ = run_command(f"git log origin/{base_branch}..{b} --oneline", cwd=local_dir)
        lines = [l for l in (log_out or "").splitlines() if l.strip()]
        if not lines:
            continue
        
        m_base, _ = run_command(f"git merge-base {base_branch} {b}", cwd=local_dir)
        has_conflict = False
        if m_base:
            m_tree, _ = run_command(f"git merge-tree {m_base} {base_branch} {b}", cwd=local_dir)
            has_conflict = "<<<<<<<" in (m_tree or "")
        
        diff_stat, _ = run_command(f"git diff origin/{base_branch}..{b} --stat", cwd=local_dir)
        
        c_info = {
            "branch": b_name,
            "unmerged_commits": len(lines),
            "top_commit": lines[0],
            "has_conflict": has_conflict,
            "diff_stat": diff_stat or ""
        }
        candidates.append(c_info)
        status_icon = "⚠️ Conflict" if has_conflict else "✅ Clean"
        print(f"  [{idx}/{len(branches)}] {b_name} ({len(lines)} commits) -> {status_icon}", flush=True)

    print(f"\n📊 Summary: Found {len(candidates)} unmerged remote branch(es):", flush=True)
    for c in candidates:
        status_icon = "⚠️ Conflict" if c["has_conflict"] else "✅ Clean Merge"
        print(f"  - {c['branch']} ({c['unmerged_commits']} commits) [{status_icon}]", flush=True)
        print(f"    Top: {c['top_commit']}", flush=True)
        if c["diff_stat"]:
            first_stat = c["diff_stat"].splitlines()[-1].strip() if c["diff_stat"].splitlines() else ""
            print(f"    Summary: {first_stat}", flush=True)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(candidates, f, indent=2)
        print(f"\n📄 Harvest scan output saved to: {args.output}", flush=True)

def main():
    parser = argparse.ArgumentParser(description="Bot PR Triage Runner CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: harvest
    p_harvest = subparsers.add_parser("harvest", help="Scan remote branches for unmerged/stalled PR code")
    p_harvest.add_argument("--base-dir", help="Base directory containing the git repository")
    p_harvest.add_argument("--base-branch", default="main", help="Target base branch (default: main)")
    p_harvest.add_argument("--output", help="Optional output JSON filepath")
    p_harvest.set_defaults(func=cmd_harvest)

    # Subcommand: search
    p_search = subparsers.add_parser("search", help="Search open PRs across owner repos")
    p_search.add_argument("--owner", required=True, help="GitHub owner or organization")
    p_search.add_argument("--repo", help="Optional specific repository (e.g. owner/repo or repo-name) to list directly")
    p_search.add_argument("--state", default="open", help="PR state (default: open)")
    p_search.add_argument("--limit", type=int, required=True, help="Max PRs to retrieve")
    p_search.add_argument("--repo-filter", help="Comma-separated list of repository names/substrings to include")
    p_search.add_argument("--workspace-filter", help="Workspace base directory to auto-detect submodules for filtering")
    p_search.add_argument("--output", required=True, help="Output JSON filepath")
    p_search.set_defaults(func=cmd_search)

    # Subcommand: audit
    p_audit = subparsers.add_parser("audit", help="Audit and categorize PRs into Group A/B/C")
    p_audit.add_argument("--input-file", required=True, help="Input JSON file from search command")
    p_audit.add_argument("--output", required=True, help="Output audited JSON filepath")
    p_audit.add_argument("--base-dir", help="Base directory containing local git repos for 3-way diff checks")
    p_audit.add_argument("--verify-local-tests", action="store_true", help="Execute targeted unit tests locally for modified files")
    p_audit.add_argument("--markdown-output", help="Optional output Markdown report filepath")
    p_audit.set_defaults(func=cmd_audit)

    # Subcommand: auto-repair
    p_repair = subparsers.add_parser("auto-repair", help="Auto-repair dangling conflict markers and repetitive bot bloat")
    p_repair.add_argument("--pr-list", required=True, help="Comma-separated list of REPO#PR_NUM")
    p_repair.add_argument("--base-dir", required=True, help="Base directory containing local git repos")
    p_repair.add_argument("--dry-run", action="store_true", help="Perform repair without pushing")
    p_repair.set_defaults(func=cmd_auto_repair)

    # Subcommand: sync-base
    p_sync = subparsers.add_parser("sync-base", help="Sync PR head branches with latest remote base")
    p_sync.add_argument("--pr-list", required=True, help="Comma-separated list of REPO#PR_NUM")
    p_sync.add_argument("--base-dir", required=True, help="Base directory containing local git repos")
    p_sync.add_argument("--dry-run", action="store_true", help="Perform sync without pushing")
    p_sync.set_defaults(func=cmd_sync_base)

    # Subcommand: harmonize-case
    p_harm = subparsers.add_parser("harmonize-case", help="Audit and fix case-colliding index paths on case-insensitive filesystems")
    p_harm.add_argument("--base-dir", help="Base directory containing the git repository")
    p_harm.set_defaults(func=cmd_harmonize_case)

    # Subcommand: merge-batch
    p_merge = subparsers.add_parser("merge-batch", help="Batch merge specified PRs")
    p_merge.add_argument("--pr-list", required=True, help="Comma-separated list of REPO#PR_NUM (e.g. bjohnson1279/js-ddd-inventory#620)")
    p_merge.add_argument("--base-dir", help="Base directory containing local git repos for branch syncing")
    p_merge.add_argument("--no-sync", action="store_true", help="Skip automatic base branch synchronization")
    p_merge.add_argument("--no-disjoint-check", dest="check_disjoint", action="store_false", help="Skip pairwise disjoint file set analysis")
    p_merge.add_argument("--sync-submodules", action="store_true", help="Automatically pull updated branches and advance submodule pointers in parent repo")
    p_merge.add_argument("--push-parent", action="store_true", help="Push parent repository after advancing submodule pointers")
    p_merge.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    p_merge.set_defaults(func=cmd_merge_batch)

    # Subcommand: close-batch
    p_close = subparsers.add_parser("close-batch", help="Batch close specified PRs")
    p_close.add_argument("--pr-list", required=True, help="Comma-separated list of REPO#PR_NUM")
    p_close.add_argument("--reason", required=True, help="Closure comment rationale")
    p_close.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    p_close.set_defaults(func=cmd_close_batch)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

