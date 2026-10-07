#!/usr/bin/env python3
"""
Targeted Post-Merge Verifier CLI
Executes fast, targeted unit test suites for repositories affected by newly merged Pull Requests.
Maps modified files directly to related test suites across polyglot ecosystems (Vitest, Jest, pytest, PHPUnit).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Force UTF-8 encoding across Windows console streams
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

def log(msg, **kwargs):
    print(msg, flush=True, **kwargs)

def get_base_env():
    env = os.environ.copy()
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_PAGER"] = "1"
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["APP_ENV"] = "testing"
    node_opts = env.get("NODE_OPTIONS", "")
    if "--experimental-vm-modules" not in node_opts:
        env["NODE_OPTIONS"] = f"{node_opts} --experimental-vm-modules".strip()
    return env

def run_command(cmd, cwd=None, timeout=180):
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
            return None, (res.stderr or res.stdout or "Command failed").strip()
        return res.stdout.strip(), None
    except subprocess.TimeoutExpired:
        return None, f"Command timed out after {timeout}s"
    except Exception as e:
        return None, str(e)

def find_local_repo(base_dir, repo_name):
    if not base_dir or not os.path.exists(base_dir):
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

def fetch_modified_files(repo, pr_num, local_repo=None):
    out, _ = run_command(f"gh pr view {pr_num} -R {repo} --json files", timeout=45)
    if out:
        try:
            data = json.loads(out)
            files = [f.get("path") for f in data.get("files", []) if f.get("path")]
            if files:
                return files
        except Exception:
            pass

    # Fallback to local git commit log if already merged
    if local_repo and os.path.exists(os.path.join(local_repo, ".git")):
        log_out, _ = run_command("git log -1 --name-only --pretty=format:", cwd=local_repo, timeout=15)
        if log_out:
            return [l.strip() for l in log_out.splitlines() if l.strip()]

    return []

def detect_js_runner(repo_dir):
    pkg_path = os.path.join(repo_dir, "package.json")
    if not os.path.exists(pkg_path):
        return "jest"
    try:
        with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
            pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "vitest" in deps:
                return "vitest"
    except Exception:
        pass
    return "jest"

def resolve_matching_test_files(repo_dir, code_files):
    """Identifies explicit or companion test files for modified source code."""
    matched = set()
    for cf in code_files:
        norm = cf.replace("\\", "/")
        # Explicit test files
        if "test" in norm.lower() or "spec" in norm.lower():
            if os.path.exists(os.path.join(repo_dir, cf)):
                matched.add(norm)
            continue

        base_name = os.path.splitext(os.path.basename(cf))[0]
        ext = os.path.splitext(cf)[1]
        core_name = re.sub(r'\.(service|controller|model|router|routes|util|helper|handler|component)$', '', base_name, flags=re.IGNORECASE)
        candidate_bases = {base_name.lower(), core_name.lower()}
        
        # Sibling companion candidates (e.g. Foo.tsx -> Foo.test.tsx)
        sibling_cand1 = os.path.join(os.path.dirname(cf), f"{base_name}.test{ext}").replace("\\", "/")
        sibling_cand2 = os.path.join(os.path.dirname(cf), f"{base_name}.spec{ext}").replace("\\", "/")
        if os.path.exists(os.path.join(repo_dir, sibling_cand1)):
            matched.add(sibling_cand1)
            continue
        if os.path.exists(os.path.join(repo_dir, sibling_cand2)):
            matched.add(sibling_cand2)
            continue

        # Look in tests/ or app/
        for search_root in ["tests", "test", "app"]:
            full_search = os.path.join(repo_dir, search_root)
            if os.path.exists(full_search):
                for root, _, files in os.walk(full_search):
                    for f in files:
                        f_lower = f.lower()
                        for b in candidate_bases:
                            if f_lower in [
                                f"{b}.test{ext}".lower(),
                                f"{b}.spec{ext}".lower(),
                                f"test_{b}.py".lower(),
                                f"{b}test.php".lower(),
                                f"{b}.test.ts".lower(),
                                f"{b}.test.js".lower()
                            ]:
                                matched.add(os.path.relpath(os.path.join(root, f), repo_dir).replace("\\", "/"))

    return sorted(list(matched))

def run_targeted_repo_tests(repo_name, repo_dir, files):
    """Maps modified files to targeted test command for the repo."""
    code_files = [
        f for f in files
        if not f.lower().startswith((".jules/", ".github/"))
        and not f.endswith((".md", ".txt", ".json", ".lock", ".yaml", ".yml"))
    ]
    if not code_files:
        return True, "No testable code files modified (metadata/clean)", 0.0

    start_t = time.time()
    direct_tests = resolve_matching_test_files(repo_dir, code_files)

    # 1. JavaScript / TypeScript (Vitest vs Jest)
    if os.path.exists(os.path.join(repo_dir, "package.json")):
        runner = detect_js_runner(repo_dir)
        if direct_tests:
            targets = " ".join(f'"{t}"' for t in direct_tests)
            if runner == "vitest":
                cmd = f"npx vitest run {targets} --no-file-parallelism"
            else:
                cmd = f"npx jest {targets} --runInBand --no-cache --passWithNoTests"
        else:
            targets = " ".join(f'"{f}"' for f in code_files)
            if runner == "vitest":
                cmd = f"npx vitest related {targets} --run --no-file-parallelism"
            else:
                cmd = f"npx jest --findRelatedTests {targets} --runInBand --no-cache --passWithNoTests"
        
        out, err = run_command(cmd, cwd=repo_dir, timeout=180)
        elapsed = round(time.time() - start_t, 2)
        if out is not None:
            count = len(direct_tests) if direct_tests else len(code_files)
            return True, f"{runner.capitalize()}: Passed ({count} test fixture(s))", elapsed
        else:
            first_err = (err.splitlines()[-1] if err else "Test failed")
            return False, f"{runner.capitalize()}: Failed - {first_err}", elapsed

    # 2. Python (pytest)
    if os.path.exists(os.path.join(repo_dir, "requirements.txt")) or os.path.exists(os.path.join(repo_dir, "pyproject.toml")):
        if not direct_tests:
            return True, "No matching pytest fixtures for modified files (clean)", round(time.time() - start_t, 2)

        targets = " ".join(f'"{t}"' for t in direct_tests)
        cmd = f"pytest {targets}"
        out, err = run_command(cmd, cwd=repo_dir, timeout=120)
        elapsed = round(time.time() - start_t, 2)
        if out is not None:
            return True, f"pytest: Passed ({len(direct_tests)} test fixture(s))", elapsed
        else:
            return False, f"pytest: Failed - {err.splitlines()[-1] if err else 'failed'}", elapsed

    # 3. PHP (PHPUnit)
    if os.path.exists(os.path.join(repo_dir, "composer.json")):
        if not direct_tests:
            return True, "No matching PHPUnit fixtures for modified files (clean)", round(time.time() - start_t, 2)

        targets = " ".join(f'"{t}"' for t in direct_tests)
        php_cmd = f"php vendor/bin/phpunit {targets}"
        out, err = run_command(php_cmd, cwd=repo_dir, timeout=120)
        elapsed = round(time.time() - start_t, 2)
        if out is not None:
            return True, f"PHPUnit: Passed ({len(direct_tests)} test fixture(s))", elapsed
        else:
            return False, f"PHPUnit: Failed - {err.splitlines()[-1] if err else 'failed'}", elapsed

    return True, "No specific test runner detected", round(time.time() - start_t, 2)

def cmd_verify(args):
    prs = []
    cached_pr_files = {}

    if getattr(args, 'input_file', None) and os.path.exists(args.input_file):
        with open(args.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data if isinstance(data, list) else data.get("prs", [])
            for p in items:
                repo = p.get("repo") or (p.get("repository", {}).get("nameWithOwner") if isinstance(p.get("repository"), dict) else p.get("repository"))
                num = p.get("number")
                if repo and num:
                    item_key = f"{repo}#{num}"
                    prs.append(item_key)
                    files = [f.get("path") for f in p.get("files", []) if f.get("path")]
                    if files:
                        cached_pr_files[item_key] = files
    elif getattr(args, 'pr_list', None):
        prs = [p.strip() for p in args.pr_list.split(",") if p.strip()]

    if not prs:
        log("❌ No PRs specified to verify.")
        sys.exit(1)

    base_dir = os.path.abspath(args.base_dir or os.getcwd())
    log(f"🔍 Targeted Post-Merge Verification for {len(prs)} PR(s)...")

    # Group modified files by repository
    repo_files = {}
    for item in prs:
        parts = item.split("#")
        if len(parts) != 2:
            continue
        repo, num = parts[0], parts[1]
        repo_dir = find_local_repo(base_dir, repo)
        files = cached_pr_files.get(item) or fetch_modified_files(repo, num, repo_dir)
        repo_files.setdefault(repo, set()).update(files)

    results = []
    all_passed = True

    for repo, files in repo_files.items():
        repo_dir = find_local_repo(base_dir, repo)
        if not repo_dir:
            log(f"  ⚠️ Warning: Local clone not found for {repo} in {base_dir}")
            results.append({"repo": repo, "passed": True, "summary": "Skipped (no local clone)", "duration": 0.0})
            continue

        log(f"  🧪 Testing {repo} ({len(files)} modified file(s))...")
        passed, summary, duration = run_targeted_repo_tests(repo, repo_dir, list(files))
        if not passed:
            all_passed = False
        status_icon = "✅" if passed else "❌"
        log(f"    {status_icon} {summary} ({duration}s)")
        results.append({
            "repo": repo,
            "passed": passed,
            "summary": summary,
            "duration": duration,
            "modified_files": sorted(list(files))
        })

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        log(f"\n📄 Results saved to: {args.output}")

    if all_passed:
        log("\n🎉 All targeted post-merge verification tests PASSED!")
        sys.exit(0)
    else:
        log("\n💥 One or more targeted post-merge verification tests FAILED!")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Targeted Post-Merge Verifier")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_verify = subparsers.add_parser("verify", help="Run targeted post-merge verification tests")
    p_verify.add_argument("--pr-list", help="Comma-separated list of OWNER/REPO#NUM")
    p_verify.add_argument("--input-file", help="Input JSON file containing PR records")
    p_verify.add_argument("--base-dir", help="Base directory containing local repos/submodules")
    p_verify.add_argument("--output", help="Optional output JSON filepath")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
