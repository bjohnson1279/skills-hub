#!/usr/bin/env python3
"""
Polyglot Targeted PR Verifier CLI
Rapidly maps modified PR files to test fixtures, executes targeted tests across
TypeScript (Jest / Vitest), PHP (PHPUnit), and Python (pytest), and verifies pairwise disjointness.
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
    env["NODE_ENV"] = "test"
    env["GIT_TERMINAL_PROMPT"] = "0"
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
            return None, res.stderr.strip() or res.stdout.strip()
        return res.stdout.strip(), None
    except subprocess.TimeoutExpired:
        return None, f"Command timed out after {timeout}s"
    except Exception as e:
        return None, str(e)

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

def get_pr_diff_files(repo_name, pr_number, local_repo=None, base_branch="main"):
    """Fetches modified files either from local git or GitHub CLI."""
    files = []
    if local_repo:
        head_ref = f"origin/refs/pull/{pr_number}/head"
        out, _ = run_command(f"git diff --name-only origin/{base_branch}...{head_ref}", cwd=local_repo)
        if not out:
            out, _ = run_command(f"git diff --name-only {base_branch}...HEAD", cwd=local_repo)
        if out:
            files = [f.strip() for f in out.splitlines() if f.strip()]

    if not files and repo_name and pr_number:
        out, _ = run_command(f"gh pr view {pr_number} -R {repo_name} --json files")
        if out:
            try:
                data = json.loads(out)
                files = [f.get("path") for f in data.get("files", []) if f.get("path")]
            except Exception:
                pass
    return files

def map_related_tests(local_repo, modified_files):
    """
    Given a list of modified files, returns a structured mapping of test runners -> list of test targets.
    """
    mapped = {
        "typescript_jest": [],
        "typescript_vitest": [],
        "php_phpunit": [],
        "python_pytest": []
    }
    if not local_repo or not modified_files:
        return mapped

    is_vitest = os.path.exists(os.path.join(local_repo, "vitest.config.ts")) or os.path.exists(os.path.join(local_repo, "vite.config.ts"))

    for f_path in modified_files:
        norm_path = f_path.replace("\\", "/")
        base_name = os.path.splitext(os.path.basename(norm_path))[0]
        ext = os.path.splitext(norm_path)[1].lower()

        # TypeScript / JavaScript
        if ext in ['.ts', '.tsx', '.js', '.jsx']:
            if not norm_path.startswith('.'):
                if is_vitest:
                    mapped["typescript_vitest"].append(norm_path)
                else:
                    mapped["typescript_jest"].append(norm_path)

        # PHP
        elif ext == '.php':
            found_test = False
            tests_dir = os.path.join(local_repo, "tests")
            if os.path.exists(tests_dir):
                for root, _, f_list in os.walk(tests_dir):
                    for f in f_list:
                        if f in [f"{base_name}Test.php", f"test_{base_name}.php", f"{base_name}.test.php"]:
                            rel_t = os.path.relpath(os.path.join(root, f), local_repo).replace("\\", "/")
                            if rel_t not in mapped["php_phpunit"]:
                                mapped["php_phpunit"].append(rel_t)
                                found_test = True
            if not found_test and ("tests/" in norm_path or "Test.php" in norm_path):
                if norm_path not in mapped["php_phpunit"]:
                    mapped["php_phpunit"].append(norm_path)

        # Python
        elif ext == '.py':
            found_py = False
            tests_dir = os.path.join(local_repo, "tests")
            if os.path.exists(tests_dir):
                for root, _, f_list in os.walk(tests_dir):
                    for f in f_list:
                        if f in [f"test_{base_name}.py", f"{base_name}_test.py"]:
                            rel_t = os.path.relpath(os.path.join(root, f), local_repo).replace("\\", "/")
                            if rel_t not in mapped["python_pytest"]:
                                mapped["python_pytest"].append(rel_t)
                                found_py = True
            if not found_py and ("tests/" in norm_path or "test_" in norm_path):
                if norm_path not in mapped["python_pytest"]:
                    mapped["python_pytest"].append(norm_path)

    return mapped

def execute_targeted_tests(local_repo, mapped_tests, timeout=60):
    """Executes the mapped test suites with fast targeted runner flags."""
    results = []

    # 1. TypeScript / Vitest
    vitest_files = mapped_tests.get("typescript_vitest", [])
    if vitest_files and os.path.exists(os.path.join(local_repo, "package.json")):
        test_only_files = [f for f in vitest_files if "test" in f.lower() or "spec" in f.lower()]
        target_str = " ".join(f'"{f}"' for f in (test_only_files or vitest_files))
        log(f"  🧪 [Vitest] Running targeted test fixture(s)...")
        cmd = f"npx vitest run --pool=forks {target_str}"
        out, err = run_command(cmd, cwd=local_repo, timeout=timeout)
        passed = out is not None
        results.append({
            "framework": "Vitest",
            "targets": test_only_files or vitest_files,
            "passed": passed,
            "output": out if passed else err
        })

    # 2. TypeScript / Jest
    ts_files = mapped_tests.get("typescript_jest", [])
    if ts_files and os.path.exists(os.path.join(local_repo, "package.json")):
        test_only_files = [f for f in ts_files if "test" in f.lower() or "spec" in f.lower()]
        if test_only_files:
            target_str = " ".join(f'"{f}"' for f in test_only_files)
            cmd = f"npx jest {target_str} --runInBand --passWithNoTests"
        else:
            files_arg = " ".join(f'"{f}"' for f in ts_files)
            cmd = f"npx jest --findRelatedTests {files_arg} --passWithNoTests --runInBand"
        
        log(f"  🧪 [TS/Jest] Running targeted test fixture(s)...")
        out, err = run_command(cmd, cwd=local_repo, timeout=timeout)
        passed = out is not None
        results.append({
            "framework": "Jest",
            "targets": ts_files,
            "passed": passed,
            "output": out if passed else err
        })

    # 3. PHP / PHPUnit
    php_tests = mapped_tests.get("php_phpunit", [])
    if php_tests and os.path.exists(os.path.join(local_repo, "composer.json")):
        files_arg = " ".join(f'"{f}"' for f in php_tests)
        log(f"  🧪 [PHP/PHPUnit] Running {len(php_tests)} test fixture(s)...")
        win_runner = r"C:\Users\johns\.gemini\config\skills\win-php-extension-test-runner\scripts\run_phpunit_win.py"
        if os.path.exists(win_runner) and os.name == 'nt':
            cmd = f'python "{win_runner}" --cwd "{local_repo}" --no-coverage {files_arg}'
        else:
            cmd = f"vendor/bin/phpunit {files_arg}"
        out, err = run_command(cmd, cwd=local_repo, timeout=timeout)
        passed = out is not None
        results.append({
            "framework": "PHPUnit",
            "targets": php_tests,
            "passed": passed,
            "output": out if passed else err
        })

    # 4. Python / pytest
    py_tests = mapped_tests.get("python_pytest", [])
    if py_tests and (os.path.exists(os.path.join(local_repo, "pyproject.toml")) or os.path.exists(os.path.join(local_repo, "requirements.txt"))):
        files_arg = " ".join(f'"{f}"' for f in py_tests)
        log(f"  🧪 [Python/pytest] Running {len(py_tests)} test fixture(s)...")
        cmd = f"pytest {files_arg}"
        out, err = run_command(cmd, cwd=local_repo, timeout=timeout)
        passed = out is not None
        results.append({
            "framework": "pytest",
            "targets": py_tests,
            "passed": passed,
            "output": out if passed else err
        })

    return results

def check_pairwise_disjointness(pr_files_map):
    """Evaluates if multiple PRs touch non-overlapping code paths."""
    disjoint_report = []
    all_disjoint = True
    keys = list(pr_files_map.keys())

    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            p1, p2 = keys[i], keys[j]
            s1 = {f for f in pr_files_map[p1] if not f.lower().startswith(('.jules/', '.github/'))}
            s2 = {f for f in pr_files_map[p2] if not f.lower().startswith(('.jules/', '.github/'))}
            overlap = s1.intersection(s2)
            is_disjoint = len(overlap) == 0
            if not is_disjoint:
                all_disjoint = False
            disjoint_report.append({
                "pr1": p1,
                "pr2": p2,
                "is_disjoint": is_disjoint,
                "overlap": sorted(list(overlap))
            })
    return all_disjoint, disjoint_report

def cmd_map_tests(args):
    files = [f.strip() for f in args.files.split(",") if f.strip()]
    base_dir = os.path.abspath(args.base_dir or ".")
    mapped = map_related_tests(base_dir, files)
    log(f"Mapped {len(files)} files to targeted test suites:")
    for fw, targets in mapped.items():
        if targets:
            log(f"  • {fw}: {', '.join(targets)}")
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(mapped, f, indent=2)


def setup_worktree(base_dir, repo, pr_num):
    import shutil
    local_repo = find_local_repo_dir(base_dir, repo)
    if not local_repo: return None, None
    
    out, err = run_command(f"gh pr view {pr_num} -R {repo} --json headRefName")
    if err: return None, None
    import json
    branch = json.loads(out).get("headRefName")
    
    wt_dir = os.path.join(base_dir, ".wts", f"{repo.split('/')[-1]}-pr-{pr_num}")
    if os.path.exists(wt_dir):
        run_command(f"git worktree remove {wt_dir} --force", cwd=local_repo)
        shutil.rmtree(wt_dir, ignore_errors=True)
        
    os.makedirs(os.path.dirname(wt_dir), exist_ok=True)
    run_command("git fetch origin", cwd=local_repo)
    run_command(f"git fetch origin {branch}:{branch}", cwd=local_repo)
    run_command(f"git worktree add {wt_dir} {branch}", cwd=local_repo)
    
    if os.path.exists(os.path.join(wt_dir, "package.json")):
        run_command("npm install", cwd=wt_dir)
    elif os.path.exists(os.path.join(wt_dir, "composer.json")):
        run_command("composer install", cwd=wt_dir)
        
    return wt_dir, local_repo

def teardown_worktree(local_repo, wt_dir):
    import shutil
    if local_repo and wt_dir and os.path.exists(wt_dir):
        run_command(f"git worktree remove {wt_dir} --force", cwd=local_repo)
        shutil.rmtree(wt_dir, ignore_errors=True)

def cmd_verify(args):

    prs = [p.strip() for p in args.pr_list.split(",") if p.strip()]
    base_dir = os.path.abspath(args.base_dir or ".")
    log(f"🔍 Verifying {len(prs)} PR(s) across polyglot test runners...")

    pr_files_map = {}
    audit_results = []

    for item in prs:
        parts = item.split("#")
        if len(parts) != 2:
            log(f"❌ Invalid PR format: {item}. Expected OWNER/REPO#NUMBER")
            continue
        repo, num = parts[0], parts[1]
        local_repo_base = find_local_repo_dir(base_dir, repo)
        
        diff_files = get_pr_diff_files(repo, num, local_repo_base)
        pr_files_map[item] = diff_files

        log(f"\n📦 [{item}] Found {len(diff_files)} modified file(s). Setting up Worktree...")
        wt_dir, local_repo = setup_worktree(base_dir, repo, num)
        if not wt_dir:
            log(f"❌ Failed to setup worktree for {item}")
            continue
            
        try:
            mapped = map_related_tests(wt_dir, diff_files)
            test_runs = execute_targeted_tests(wt_dir, mapped, timeout=args.timeout)
        finally:
            log(f"  🧹 Tearing down isolated worktree...")
            teardown_worktree(local_repo, wt_dir)
        all_passed = all(t["passed"] for t in test_runs) if test_runs else True
        
        audit_results.append({
            "pr": item,
            "repo": repo,
            "number": num,
            "modified_files": diff_files,
            "mapped_tests": mapped,
            "test_runs": test_runs,
            "all_passed": all_passed
        })

    # Disjointness check
    all_disjoint = True
    disjoint_pairs = []
    if len(prs) > 1:
        log("\n📊 Evaluating pairwise file disjointness...")
        all_disjoint, disjoint_pairs = check_pairwise_disjointness(pr_files_map)
        for dp in disjoint_pairs:
            status = "✅ DISJOINT" if dp["is_disjoint"] else f"⚠️ OVERLAP: {', '.join(dp['overlap'])}"
            log(f"  • {dp['pr1']} vs {dp['pr2']}: {status}")

    final_payload = {
        "prs": audit_results,
        "all_disjoint": all_disjoint,
        "disjoint_analysis": disjoint_pairs
    }

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, indent=2)
        log(f"\n📄 Verification report saved to: {args.output}")

def main():
    parser = argparse.ArgumentParser(description="Polyglot Targeted PR Verifier CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: map-tests
    p_map = subparsers.add_parser("map-tests", help="Map modified files to targeted test suites")
    p_map.add_argument("--files", required=True, help="Comma-separated list of modified file paths")
    p_map.add_argument("--base-dir", default=".", help="Local repository base directory")
    p_map.add_argument("--output", help="Optional JSON output filepath")
    p_map.set_defaults(func=cmd_map_tests)

    # Subcommand: verify
    p_ver = subparsers.add_parser("verify", help="Run targeted tests and disjoint checks for PR list")
    p_ver.add_argument("--pr-list", required=True, help="Comma-separated list of REPO#NUMBER")
    p_ver.add_argument("--base-dir", default=".", help="Parent directory containing repositories/submodules")
    p_ver.add_argument("--timeout", type=int, default=60, help="Per-suite timeout in seconds (default: 60)")
    p_ver.add_argument("--output", help="Optional JSON output filepath")
    p_ver.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
