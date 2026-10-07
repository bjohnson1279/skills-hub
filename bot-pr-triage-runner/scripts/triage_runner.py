#!/usr/bin/env python3
"""
Bot PR Triage Runner CLI
Helper script to search, audit, categorize, sync, and batch process open bot PRs.
Enhanced with Windows UTF-8 safety, non-interactive GH flags, local 3-way diff analysis,
stale-base auto-healing, and workspace/submodule filtering.
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Add script directory to sys.path for relative imports
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from smart_union_merge import (
        smart_union_texts,
        resolve_in_place_file,
        has_git_conflict_markers,
        git_merge_driver,
        is_test_file,
    )
except ImportError:
    smart_union_texts = None
    resolve_in_place_file = None
    has_git_conflict_markers = None
    git_merge_driver = None
    is_test_file = None

# Force UTF-8 encoding and line-buffered output across Windows console streams
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
    return env

def run_command(cmd, cwd=None, timeout=60):
    try:
        is_list = isinstance(cmd, list)
        res = subprocess.run(
            cmd,
            shell=not is_list,
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

def detect_js_test_runner(local_repo):
    """Detects whether project uses vitest or jest."""
    pkg_path = os.path.join(local_repo, "package.json")
    if not os.path.exists(pkg_path):
        return "jest"
    try:
        with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
            pkg_data = json.load(f)
            deps = pkg_data.get("dependencies", {})
            dev_deps = pkg_data.get("devDependencies", {})
            scripts = pkg_data.get("scripts", {})
            if "vitest" in deps or "vitest" in dev_deps or any("vitest" in s for s in scripts.values()):
                return "vitest"
    except Exception:
        pass
    return "jest"

def get_windows_php_extension_flags():
    """Discovers Windows PHP extension directories for phpunit."""
    if os.name != 'nt':
        return ""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = []
    if local_app_data:
        winget_pkgs = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
        if os.path.exists(winget_pkgs):
            for entry in os.listdir(winget_pkgs):
                if entry.startswith("PHP.PHP"):
                    ext_dir = os.path.join(winget_pkgs, entry, "ext")
                    if os.path.exists(ext_dir):
                        candidates.append(ext_dir)
    
    # Also check where.exe php parent ext directory
    where_out, _ = run_command("where.exe php")
    if where_out:
        for p in where_out.splitlines():
            ext_dir = os.path.join(os.path.dirname(p.strip()), "ext")
            if os.path.exists(ext_dir) and ext_dir not in candidates:
                candidates.append(ext_dir)

    for c in candidates:
        has_mb = os.path.exists(os.path.join(c, "php_mbstring.dll"))
        has_sqlite = os.path.exists(os.path.join(c, "php_pdo_sqlite.dll")) or os.path.exists(os.path.join(c, "php_sqlite3.dll"))
        if has_mb or has_sqlite:
            flags = f'-d extension_dir="{c}" -d extension=php_mbstring.dll -d extension=php_pdo_sqlite.dll -d extension=php_sqlite3.dll'
            return flags
    return ""


_SECURITY_ALERTS_CACHE = {}

def check_repo_dependabot_security(repo_name):
    """Queries Dependabot API for open vulnerabilities on the repository (memoized)."""
    if repo_name in _SECURITY_ALERTS_CACHE:
        return _SECURITY_ALERTS_CACHE[repo_name]
    cmd = f"gh api repos/{repo_name}/dependabot/alerts?state=open"
    out, err = run_command(cmd)
    res = []
    if out:
        try:
            data = json.loads(out)
            if isinstance(data, list):
                res = data
        except Exception:
            pass
    _SECURITY_ALERTS_CACHE[repo_name] = res
    return res

def analyze_diff_patterns(diff_text):
    """Audits diff content for algorithmic, memory, and security patterns."""
    findings = {
        "complexity_optimizations": [],
        "memory_optimizations": [],
        "security_improvements": [],
        "accessibility_improvements": [],
        "potential_risks": [],
        "lines_added": 0,
        "lines_deleted": 0
    }
    if not diff_text:
        return findings

    lines = diff_text.splitlines()
    for line in lines:
        if line.startswith("+") and not line.startswith("+++"):
            findings["lines_added"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            findings["lines_deleted"] += 1

    # Complexity checks
    if re.search(r'new\s+Map\s*<', diff_text) or (re.search(r'\.get\(', diff_text) and 'find(' in diff_text):
        findings["complexity_optimizations"].append("Replaced O(N) array scan with O(1) Map lookup")
    if re.search(r'Cache|cache|precompute|normalize.*constructor', diff_text, re.IGNORECASE):
        findings["complexity_optimizations"].append("Pre-computed/cached normalized fields outside loop")
    if re.search(r'for\s*\(\s*let\s+i\s*=\s*0;', diff_text) and ('for...of' in diff_text or 'forEach' in diff_text):
        findings["complexity_optimizations"].append("Converted iterator/closure loop to indexed loop for reduced GC")

    # Memory / GC checks
    if re.search(r'toLowerCase\(\)', diff_text) and ('search' in diff_text or 'pre' in diff_text.lower()):
        findings["memory_optimizations"].append("Hoisted string case transformations out of comparison loops")
    if re.search(r'(consolidat|fold|eliminat|reduc).*(array|allocation|intermediate|\.map|\.filter)', diff_text, re.IGNORECASE) or \
       (re.search(r'\.split\(', diff_text) and re.search(r'for\s*\(\s*(const|let|var)\s+\w+\s+of\s+', diff_text) and ('filter(' in diff_text or 'map(' in diff_text or '.push(' in diff_text)):
        findings["memory_optimizations"].append("Consolidated chained array operations (.map/.filter) into single-pass iteration to eliminate intermediate array allocations")

    # Security checks
    if re.search(r'escapeHtml|sanitize|DOMPurify|htmlspecialchars', diff_text):
        findings["security_improvements"].append("Added HTML/XSS entity escaping on dynamic inputs")
    if re.search(r'\$\d+|\?', diff_text) and re.search(r'SELECT|INSERT|UPDATE|DELETE', diff_text, re.IGNORECASE):
        findings["security_improvements"].append("Parameterized SQL query placeholders to prevent injection")

    # Accessibility checks
    if re.search(r'aria-label|aria-expanded|role=|tabindex|aria-hidden', diff_text):
        findings["accessibility_improvements"].append("Added ARIA accessibility attributes or keyboard navigation")
    if re.search(r'activeElement|focus\(\)|aria-modal="true"|role=["\']dialog["\']', diff_text) and ('modal' in diff_text.lower() or 'dialog' in diff_text.lower() or 'close' in diff_text.lower()):
        findings["accessibility_improvements"].append("Implemented WCAG focus management (active element retention, programmatic focus shifts, or modal trapping)")

    return findings

CONFLICT_MARKER_DIFF_REGEX = re.compile(
    r'^\+([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))$',
    re.MULTILINE
)
CONFLICT_MARKER_FILE_REGEX = re.compile(
    r'^([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))$',
    re.MULTILINE
)

def detect_conflict_markers_in_diff(diff_text):
    """
    Scans unified diff text for additions of Git merge conflict markers:
    <<<<<<< [HEAD/branch]
    =======
    >>>>>>> [branch/commit]
    ||||||| [base/ancestor]
    Returns (has_conflict_markers: bool, count: int, sample_lines: list).
    """
    if not diff_text:
        return False, 0, []
    matches = CONFLICT_MARKER_DIFF_REGEX.findall(diff_text)
    if matches:
        samples = [m.strip() for m in matches[:5]]
        return True, len(matches), samples
    return False, 0, []

def detect_conflict_markers_in_file(file_path):
    """Checks whether a file on disk contains Git merge conflict markers."""
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        return False, 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        matches = CONFLICT_MARKER_FILE_REGEX.findall(content)
        return (len(matches) > 0), len(matches)
    except Exception:
        return False, 0

def run_full_repository_tests(local_repo):
    """Executes full test suite across polyglot repository technologies after merging."""
    if not local_repo or not os.path.exists(local_repo):
        return True, "No local repo found"

    results = []
    
    # 1. Node / TypeScript (npm / pnpm / yarn)
    if os.path.exists(os.path.join(local_repo, "package.json")):
        runner = detect_js_test_runner(local_repo)
        if runner == "vitest":
            cmd = "npx vitest run"
            # On Windows Vitest 4, add --no-file-parallelism if needed
            if os.name == 'nt':
                cmd += " --no-file-parallelism"
        else:
            cmd = "npm test -- --runInBand"

        log(f"  🧪 Executing full test suite ({runner}) in {local_repo}...")
        out, err = run_command(cmd, cwd=local_repo, timeout=180)
        if out is not None:
            results.append((f"JS/{runner}", True, "Passed"))
        else:
            results.append((f"JS/{runner}", False, err or "Failed"))

    # 2. PHP (PHPUnit)
    if os.path.exists(os.path.join(local_repo, "composer.json")):
        php_ext_flags = get_windows_php_extension_flags()
        php_cmd = f"php {php_ext_flags} vendor/bin/phpunit".strip() if php_ext_flags else "vendor/bin/phpunit"
        log(f"  🧪 Executing full PHPUnit test suite in {local_repo}...")
        out, err = run_command(php_cmd, cwd=local_repo, timeout=180)
        if out is not None:
            results.append(("PHP/PHPUnit", True, "Passed"))
        else:
            results.append(("PHP/PHPUnit", False, err or "Failed"))

    # 3. Python (pytest)
    if os.path.exists(os.path.join(local_repo, "pyproject.toml")) or os.path.exists(os.path.join(local_repo, "requirements.txt")):
        log(f"  🧪 Executing full pytest test suite in {local_repo}...")
        out, err = run_command("pytest", cwd=local_repo, timeout=120)
        if out is not None:
            results.append(("Python/pytest", True, "Passed"))
        else:
            results.append(("Python/pytest", False, err or "Failed"))

    # 4. Elixir / Phoenix (Mix)
    if os.path.exists(os.path.join(local_repo, "mix.exs")):
        has_docker = (
            os.path.exists(os.path.join(local_repo, "docker-compose.yml"))
            or os.path.exists(os.path.join(local_repo, "compose.yaml"))
        )
        runner_prefix = "docker compose run --rm app " if has_docker else ""
        log(f"  🧪 Executing full Elixir test suite in {local_repo}...")
        out, err = run_command(f"{runner_prefix}mix test", cwd=local_repo, timeout=240)
        if out is not None:
            results.append(("Elixir/Mix", True, "Passed"))
        else:
            results.append(("Elixir/Mix", False, err or "Failed"))

    if not results:
        return True, "No automated test framework detected"

    all_passed = all(r[1] for r in results)
    summary = "; ".join(f"{r[0]}: {'PASSED' if r[1] else 'FAILED'}" for r in results)
    return all_passed, summary

def run_targeted_tests_for_files(local_repo, modified_files):
    """
    Discovers and executes targeted unit tests for modified source files across
    TypeScript/JavaScript (Vitest / Jest), PHP (PHPUnit), and Python (pytest).
    """
    if not local_repo or not modified_files:
        return True, "No files to test"

    test_results = []
    
    # 1. TypeScript / JavaScript (Vitest / Jest)
    ts_files = [f for f in modified_files if f.endswith(('.ts', '.tsx', '.js', '.jsx')) and not f.startswith('.')]
    if ts_files and os.path.exists(os.path.join(local_repo, "package.json")):
        runner = detect_js_test_runner(local_repo)
        files_arg = " ".join(f'"{f}"' for f in ts_files)
        if runner == "vitest":
            flags = "--passWithNoTests"
            if os.name == 'nt':
                flags += " --no-file-parallelism"
            cmd = f"npx vitest run {flags} {files_arg}"
            log_prefix = "TypeScript/Vitest"
            log(f"    🧪 Running Vitest related tests for {len(ts_files)} file(s)...")
        else:
            cmd = f"npx jest --findRelatedTests {files_arg} --passWithNoTests --runInBand"
            log_prefix = "TypeScript/Jest"
            log(f"    🧪 Running Jest related tests for {len(ts_files)} file(s)...")

        out, err = run_command(cmd, cwd=local_repo, timeout=60)
        
        if out is None:
            log(f"    🩹 Tests failed. Attempting lockfile auto-heal (syncing from main and installing with --ignore-scripts)...")
            run_command("git checkout origin/main -- pnpm-lock.yaml package.json package-lock.json yarn.lock", cwd=local_repo)
            
            if os.path.exists(os.path.join(local_repo, "pnpm-lock.yaml")):
                run_command("pnpm install --ignore-scripts", cwd=local_repo, timeout=120)
            elif os.path.exists(os.path.join(local_repo, "yarn.lock")):
                run_command("yarn install --ignore-scripts", cwd=local_repo, timeout=120)
            else:
                run_command("npm install --ignore-scripts", cwd=local_repo, timeout=120)
                
            log(f"    🔄 Retrying tests after auto-heal...")
            out, err = run_command(cmd, cwd=local_repo, timeout=60)

        if out is not None:
            test_results.append((log_prefix, True, "Passed"))
        else:
            test_results.append((log_prefix, False, err or "Tests failed"))

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
            php_ext_flags = get_windows_php_extension_flags()
            php_cmd = f"php {php_ext_flags} vendor/bin/phpunit {test_target}".strip() if php_ext_flags else f"vendor/bin/phpunit {test_target}"
            log(f"    🧪 Running PHPUnit on {len(matched_tests)} targeted test fixture(s)...")
            out, err = run_command(php_cmd, cwd=local_repo, timeout=60)
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


def verify_accessibility_field_alignment(local_repo, modified_files, head_branch, base_branch):
    """Verifies that automated accessibility PRs do not pass non-existent domain fields into aria-label/title attributes."""
    if not local_repo or not head_branch:
        return True, "No local repo"
    
    # Check diff for new aria-label or title bindings in JSX/TSX
    jsx_files = [f for f in modified_files if f.endswith(('.tsx', '.jsx'))]
    if not jsx_files:
        return True, "No JSX files"
        
    diff_out, _ = run_command(f"git diff origin/{base_branch}...origin/{head_branch} -- {' '.join(jsx_files)}", cwd=local_repo)
    if not diff_out:
        return True, "No JSX diff"
        
    # Detect patterns like: aria-label={`... ${item.nonExistentField}`}
    suspicious_patterns = re.findall(r'\+.*(?:aria-label|title|alt)=[{`"][^>]*\$\{([a-zA-Z0-9_\.]+)\}[^>]*[}`"]', diff_out)
    if suspicious_patterns:
        # Check typecheck if tsconfig exists
        if os.path.exists(os.path.join(local_repo, "tsconfig.json")):
            tc_out, tc_err = run_command("npx tsc --noEmit", cwd=local_repo, timeout=45)
            if tc_out is None and tc_err and ("Property" in tc_err and "does not exist on type" in tc_err):
                return False, f"TypeScript error: {tc_err.splitlines()[-1]}"
    return True, "Accessibility attributes typecheck clean"

def find_local_repo_dir(base_dir, repo_name):
    search_dirs = []
    if base_dir:
        search_dirs.append(base_dir)
    default_dev = r"C:\Users\johns\DEV"
    if os.path.exists(default_dev) and default_dev not in search_dirs:
        search_dirs.append(default_dev)

    if not search_dirs:
        return None

    repo_basename = repo_name.split("/")[-1]
    for b_dir in search_dirs:
        candidates = [
            os.path.join(b_dir, repo_basename),
            os.path.join(b_dir, repo_name),
            b_dir if os.path.basename(os.path.abspath(b_dir)) == repo_basename else None
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

def fetch_repo_prs_graphql(owner, repo, state="OPEN", limit=50):
    """
    Fetches open PRs, metadata, commit status, and modified files in a single-shot GraphQL query.
    """
    if state.upper() == "ALL":
        gql_state = "[OPEN, CLOSED, MERGED]"
    else:
        gql_state = f"[{state.upper()}]"
    query = f"""query {{
      repository(owner: "{owner}", name: "{repo}") {{
        pullRequests(states: {gql_state}, first: {limit}, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
          nodes {{
            number
            title
            body
            state
            author {{ login }}
            headRefName
            baseRefName
            mergeable
            additions
            deletions
            url
            commits(last: 1) {{
              nodes {{
                commit {{
                  oid
                  messageHeadline
                  statusCheckRollup {{
                    state
                    contexts(first: 25) {{
                      nodes {{
                        ... on CheckRun {{
                          name
                          conclusion
                          status
                        }}
                        ... on StatusContext {{
                          context
                          state
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            files(first: 100) {{
              nodes {{
                path
                additions
                deletions
              }}
            }}
          }}
        }}
      }}
    }}"""
    clean_query = query.replace("\n", " ").strip()
    cmd = ["gh", "api", "graphql", "-f", f"query={clean_query}"]
    out, err = run_command(cmd, timeout=30)
    if not out:
        return None
    try:
        data = json.loads(out)
        nodes = data.get("data", {}).get("repository", {}).get("pullRequests", {}).get("nodes", [])
        formatted = []
        for n in nodes:
            files = [f for f in n.get("files", {}).get("nodes", [])]
            commit_nodes = n.get("commits", {}).get("nodes", [])
            last_commit = commit_nodes[0].get("commit", {}) if commit_nodes else {}
            rollup_contexts = last_commit.get("statusCheckRollup", {}).get("contexts", {}).get("nodes", []) if last_commit.get("statusCheckRollup") else []
            
            checks = []
            for ctx in rollup_contexts:
                if "name" in ctx:
                    checks.append({
                        "name": ctx.get("name"),
                        "conclusion": ctx.get("conclusion"),
                        "status": ctx.get("status")
                    })
                elif "context" in ctx:
                    checks.append({
                        "name": ctx.get("context"),
                        "conclusion": ctx.get("state"),
                        "status": "COMPLETED"
                    })
            
            formatted.append({
                "number": n.get("number"),
                "title": n.get("title"),
                "body": n.get("body", ""),
                "state": n.get("state"),
                "author": n.get("author", {}),
                "headRefName": n.get("headRefName"),
                "baseRefName": n.get("baseRefName"),
                "mergeable": n.get("mergeable"),
                "additions": n.get("additions"),
                "deletions": n.get("deletions"),
                "url": n.get("url"),
                "files": files,
                "statusCheckRollup": checks,
                "headRefOid": last_commit.get("oid"),
                "repository": {"nameWithOwner": f"{owner}/{repo}", "name": repo}
            })
        return formatted
    except Exception as e:
        return None

def cmd_search(args):
    prs = []
    # If specific repo is provided or owner contains a slash (e.g. owner/repo)
    target_repo = getattr(args, "repo", None)
    if not target_repo and args.owner and "/" in args.owner:
        target_repo = args.owner

    if target_repo:
        parts = target_repo.split("/")
        if len(parts) == 2:
            print(f"Fetching PRs via single-shot GraphQL for repository: {target_repo} (state: {args.state}, limit: {args.limit})...")
            gql_prs = fetch_repo_prs_graphql(parts[0], parts[1], state=args.state, limit=args.limit)
            if gql_prs is not None:
                prs = gql_prs

        if not prs:
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
        raw_output, err = run_command(cmd, timeout=120)
        if raw_output:
            try:
                prs = json.loads(raw_output)
            except Exception as e:
                print(f"⚠️ JSON parse error on gh search prs: {e}", file=sys.stderr)
        elif err:
            print(f"⚠️ gh search prs failed or timed out: {err}", file=sys.stderr)
        
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

def poll_pr_ci_status(repo_name, pr_number, timeout=300, interval=10):
    """
    Polls GitHub Actions CI checks for a PR until all runs complete or timeout is reached.
    """
    start_time = time.time()
    log(f"⏱️ [Watchdog] Monitoring CI checks for {repo_name}#{pr_number} (timeout: {timeout}s)...")
    
    last_completed = -1
    while time.time() - start_time < timeout:
        view_cmd = f"gh pr view {pr_number} -R {repo_name} --json statusCheckRollup,headRefOid"
        view_out, _ = run_command(view_cmd, timeout=30)
        if not view_out:
            time.sleep(interval)
            continue
        try:
            data = json.loads(view_out)
            status_checks = data.get("statusCheckRollup", []) or []
            in_flight = [c for c in status_checks if c.get("status") in ["IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED"]]
            total = len(status_checks)
            completed = total - len(in_flight)
            
            if in_flight:
                in_flight_names = ", ".join([c.get("name", "check") for c in in_flight[:2]])
                if len(in_flight) > 2:
                    in_flight_names += f" (+{len(in_flight)-2} more)"
                if completed != last_completed:
                    elapsed = int(time.time() - start_time)
                    log(f"  ⏳ [{elapsed}s] {repo_name}#{pr_number}: {completed}/{total} completed (in-progress: {in_flight_names})...")
                    last_completed = completed
                time.sleep(interval)
            else:
                elapsed = int(time.time() - start_time)
                failed = [c for c in status_checks if c.get("conclusion") in ["FAILURE", "CANCELLED", "TIMED_OUT"]]
                if failed:
                    failed_names = ", ".join([c.get("name", "check") for c in failed])
                    log(f"  ❌ [{elapsed}s] {repo_name}#{pr_number}: CI finished with failure(s): {failed_names}")
                else:
                    log(f"  ✅ [{elapsed}s] {repo_name}#{pr_number}: All {total} CI check(s) PASSED!")
                return status_checks, len(failed) == 0
        except Exception:
            time.sleep(interval)
    
    log(f"  ⚠️ [Watchdog] Timed out after {timeout}s waiting for {repo_name}#{pr_number} CI checks.")
    return None, False

def cmd_watch_ci(args):
    """Monitors in-flight CI runs for specified PRs."""
    prs = [p.strip() for p in args.pr_list.split(",") if p.strip()]
    timeout = getattr(args, 'timeout', 300)
    interval = getattr(args, 'interval', 10)
    print(f"🐕 Starting CI Watchdog for {len(prs)} PR(s) (timeout: {timeout}s)...")
    
    results = {}
    for item in prs:
        parts = item.split("#")
        if len(parts) != 2:
            print(f"❌ Invalid PR format: {item}", file=sys.stderr)
            continue
        repo, num = parts[0], parts[1]
        checks, passed = poll_pr_ci_status(repo, num, timeout=timeout, interval=interval)
        results[item] = "SUCCESS" if passed else "FAILED_OR_TIMEOUT"

    print("\n📊 CI Watchdog Summary:")
    for item, res in results.items():
        icon = "✅" if res == "SUCCESS" else "❌"
        print(f"  {icon} {item}: {res}")

def cmd_union_merge(args):
    """Unions conflicting .jules/*.md logs using smart_union_merge."""
    if args.file:
        if resolve_in_place_file:
            success = resolve_in_place_file(args.file)
            sys.exit(0 if success else 1)
        else:
            print("❌ smart_union_merge module not available", file=sys.stderr)
            sys.exit(1)
    elif args.ours and args.theirs:
        if smart_union_texts:
            ours_text = Path(args.ours).read_text(encoding="utf-8", errors="replace")
            theirs_text = Path(args.theirs).read_text(encoding="utf-8", errors="replace")
            res = smart_union_texts(ours_text, theirs_text)
            if args.output:
                Path(args.output).write_text(res, encoding="utf-8")
                print(f"✅ Union written to: {args.output}")
            else:
                sys.stdout.write(res)
            sys.exit(0)
        else:
            print("❌ smart_union_merge module not available", file=sys.stderr)
            sys.exit(1)
    elif args.driver:
        if git_merge_driver:
            anc, ours, theirs = args.driver[0], args.driver[1], args.driver[2]
            path_name = args.driver[3] if len(args.driver) > 3 else ""
            code = git_merge_driver(anc, ours, theirs, path_name)
            sys.exit(code)
        else:
            print("❌ smart_union_merge module not available", file=sys.stderr)
            sys.exit(1)

def fetch_single_pr_view(pr):
    repo_name = pr.get("repository", {}).get("nameWithOwner", "")
    pr_number = pr.get("number")
    view_cmd = f"gh pr view {pr_number} -R {repo_name} --json number,title,state,author,files,statusCheckRollup,body,headRefName,baseRefName,mergeable,mergeStateStatus,headRefOid,commits"
    view_out, err = run_command(view_cmd, timeout=90)
    if not view_out:
        # Retry once on timeout or transient failure
        time.sleep(2)
        view_out, err = run_command(view_cmd, timeout=90)
    if not view_out:
        return pr, None, err
    try:
        details = json.loads(view_out)
        details["repository"] = pr.get("repository")
        details["url"] = pr.get("url")
        return pr, details, None
    except Exception as e:
        return pr, None, str(e)

def harmonize_sibling_pr_conflicts(audited_prs, base_dir):
    """
    Evaluates in-memory 3-way merge conflicts across sibling PRs in the same repository.
    When two candidate Group A PRs modify overlapping code files and conflict with each other,
    the lower-scoring or older sibling PR is downgraded to Group C (Superseded).
    """
    if not audited_prs or not base_dir:
        return

    repo_groups = {}
    for p in audited_prs:
        cat = p.get("category", "")
        if cat.startswith("Group A"):
            r = p.get("repo")
            repo_groups.setdefault(r, []).append(p)

    for repo, candidates in repo_groups.items():
        if len(candidates) < 2:
            continue

        local_repo = find_local_repo_dir(base_dir, repo)
        if not local_repo:
            continue

        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                pr1 = candidates[i]
                pr2 = candidates[j]
                if not pr1.get("category", "").startswith("Group A") or not pr2.get("category", "").startswith("Group A"):
                    continue

                files1 = {f.get("path") for f in pr1.get("files", []) if f.get("path") and not f.get("path", "").lower().startswith((".jules/", ".github/"))}
                files2 = {f.get("path") for f in pr2.get("files", []) if f.get("path") and not f.get("path", "").lower().startswith((".jules/", ".github/"))}
                overlap = files1.intersection(files2)
                if not overlap:
                    continue

                h1 = pr1.get("headRefName")
                h2 = pr2.get("headRefName")
                if not h1 or not h2:
                    continue

                # Ensure refs exist or fetch them
                run_command(f"git fetch origin {h1} {h2}", cwd=local_repo, timeout=30)
                merge_out, _ = run_command(f"git merge-tree origin/{h1} origin/{h2}", cwd=local_repo, timeout=30)
                has_conflict = merge_out is None or "<<<<<<<" in merge_out or "CONFLICT" in (merge_out or "")

                if has_conflict:
                    MANIFEST_FILES = {
                        "requirements.txt", "requirements-dev.txt", "setup.py", "pyproject.toml",
                        "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
                        "composer.json", "composer.lock",
                        "gemfile", "gemfile.lock",
                        "mix.exs", "mix.lock",
                        "cargo.toml", "cargo.lock",
                    }
                    non_manifest_overlap = {f for f in overlap if os.path.basename(f).lower() not in MANIFEST_FILES}
                    if not non_manifest_overlap:
                        # Sibling conflict is strictly on dependency manifests/lockfiles - not a functional supersession!
                        second = pr2 if (pr1.get("number", 0) < pr2.get("number", 0)) else pr1
                        first = pr1 if second is pr2 else pr2
                        second["category"] = "Group A (Needs Base Sync)"
                        second["group"] = "Group A (Needs Base Sync)"
                        second_reasons = second.setdefault("auditReasons", [])
                        second_reasons.append(f"Dependency manifest collision with sibling PR #{first.get('number')} on {sorted(list(overlap))}; requires sequential rebase after #{first.get('number')} merges.")
                        log(f"  ⚡ Manifest Sibling Collision: {repo}#{second.get('number')} collides with #{first.get('number')} on {sorted(list(overlap))}. Retained #{second.get('number')} -> Group A (Needs Base Sync)")
                        continue

                    eff1 = pr1.get("effectiveness", {})
                    eff2 = pr2.get("effectiveness", {})
                    score1 = (len(eff1.get("complexity_optimizations", [])) * 25 +
                              len(eff1.get("memory_optimizations", [])) * 15 +
                              len(eff1.get("security_improvements", [])) * 25)
                    score2 = (len(eff2.get("complexity_optimizations", [])) * 25 +
                              len(eff2.get("memory_optimizations", [])) * 15 +
                              len(eff2.get("security_improvements", [])) * 25)
                    num1 = pr1.get("number", 0)
                    num2 = pr2.get("number", 0)

                    if score2 > score1 or (score2 == score1 and num2 > num1):
                        winner, loser = pr2, pr1
                    else:
                        winner, loser = pr1, pr2

                    loser["category"] = "Group C (Superseded)"
                    loser["group"] = "Group C (Superseded)"
                    loser["supersededBy"] = f"Sibling PR #{winner.get('number')}"
                    loser_reasons = loser.setdefault("auditReasons", [])
                    loser_reasons.append(f"In-memory merge-tree conflict with sibling PR #{winner.get('number')} on {sorted(list(overlap))}; superseded by superior/newer optimization")
                    log(f"  ⚡ Sibling Conflict Detected: {repo}#{loser.get('number')} conflicts with #{winner.get('number')} on {sorted(list(overlap))}. Downgraded #{loser.get('number')} -> Group C (Superseded by #{winner.get('number')})")

def cmd_audit(args):
    if not os.path.exists(args.input_file):
        print(f"❌ Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.input_file, "r", encoding="utf-8") as f:
        prs = json.load(f)

    audited_prs = []
    print(f"Auditing {len(prs)} PRs (fetching details concurrently)...")

    # Concurrent fetch of PR details across repositories (bypasses fetch if already populated by GraphQL)
    pr_details_map = {}
    if prs:
        unresolved_prs = []
        for pr in prs:
            key = (pr.get("repository", {}).get("nameWithOwner", ""), pr.get("number"))
            if "files" in pr and "statusCheckRollup" in pr and pr.get("files") is not None:
                pr_details_map[key] = (pr, None)
            else:
                unresolved_prs.append(pr)

        if unresolved_prs:
            workers = min(8, len(unresolved_prs))
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_pr = {executor.submit(fetch_single_pr_view, pr): pr for pr in unresolved_prs}
                for future in concurrent.futures.as_completed(future_to_pr):
                    orig_pr, details, err = future.result()
                    key = (orig_pr.get("repository", {}).get("nameWithOwner", ""), orig_pr.get("number"))
                    pr_details_map[key] = (details, err)

    for i, pr in enumerate(prs, 1):
        repo_name = pr.get("repository", {}).get("nameWithOwner", "")
        pr_number = pr.get("number")
        
        details, err = pr_details_map.get((repo_name, pr_number), (None, "Details unavailable"))
        if not details:
            print(f"  [{i}/{len(prs)}] ⚠️ Warning: Failed to fetch {repo_name}#{pr_number}: {err}")
            continue

        files = details.get("files", [])
        status_checks = details.get("statusCheckRollup", []) or []
        head_branch = details.get("headRefName", "")
        base_branch = details.get("baseRefName", "main")
        remote_state = details.get("state", "OPEN")
        
        # Scratch file detection (e.g. root test.cjs, fix_sentinel.cjs, fix_interface_mock.php, etc.)
        has_scratch = any(
            re.search(r'^(test(_.*)?\.(ts|js|cjs|mjs)|test.*\.cjs|fix_.*\.(php|cjs|js|ts)|update_.*\.(php|cjs|js|ts)|scratch_.*|temp_.*)$', f.get("path", "").lower())
            for f in files
        )
        
        # Meta files vs code files
        non_meta_files = [
            f for f in files
            if not f.get("path", "").lower().startswith(".jules/")
            and not f.get("path", "").lower().startswith(".github/")
            and f.get("path", "") not in ["package.json", "package-lock.json", "composer.lock", "pnpm-lock.yaml"]
        ]
        is_metadata_only = len(non_meta_files) == 0

        # CI Checks analysis & In-Flight Commit Detection
        in_flight_checks = [c for c in status_checks if c.get("status") in ["IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED"]]
        ci_in_flight = len(in_flight_checks) > 0
        ci_failed = any(c.get("conclusion") in ["FAILURE", "CANCELLED", "TIMED_OUT"] for c in status_checks)
        audit_bot_failed = any(c.get("name") == "audit-bot-pr" and c.get("conclusion") in ["FAILURE", "CANCELLED", "TIMED_OUT"] for c in status_checks)

        # In-flight bot commit & self-healing recognition
        commits = details.get("commits", []) or []
        self_healing_commit = False
        if len(commits) > 1:
            latest_commit = commits[-1]
            latest_msg = (latest_commit.get("messageHeadline") or latest_commit.get("message") or "").lower()
            if any(term in latest_msg for term in ["prune", "fix", "heal", "resolve", "clean", "remove scratch", "marker"]):
                self_healing_commit = True

        # If --wait-ci is enabled and CI is in-flight or self-healing commit needs fresh CI evaluation
        if getattr(args, 'wait_ci', False) and (ci_in_flight or (ci_failed and self_healing_commit)):
            log(f"  🐕 [Watchdog] Waiting for in-flight CI runs on {repo_name}#{pr_number}...")
            updated_checks, all_passed = poll_pr_ci_status(repo_name, pr_number, timeout=getattr(args, 'timeout', 300))
            if updated_checks is not None:
                status_checks = updated_checks
                details["statusCheckRollup"] = status_checks
                in_flight_checks = [c for c in status_checks if c.get("status") in ["IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED"]]
                ci_in_flight = len(in_flight_checks) > 0
                ci_failed = any(c.get("conclusion") in ["FAILURE", "CANCELLED", "TIMED_OUT"] for c in status_checks)
                audit_bot_failed = any(c.get("name") == "audit-bot-pr" and c.get("conclusion") in ["FAILURE", "CANCELLED", "TIMED_OUT"] for c in status_checks)

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
        pr_diff_text = ""

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
                            subst_diff, _ = run_command(f'git diff {base_branch} origin/{head_branch} -- {paths_arg}', cwd=local_repo)
                            if subst_diff is not None:
                                superseded_by = top_commit
                                pr_diff_text = subst_diff

            if not pr_diff_text and not local_zero_diff:
                raw_diff, _ = run_command(f"git diff {base_branch}...origin/{head_branch}", cwd=local_repo)
                if raw_diff:
                    pr_diff_text = raw_diff

        # Fallback to remote diff if local diff is empty and not zero-diff
        if not pr_diff_text and not local_zero_diff:
            remote_diff, _ = run_command(f"gh pr diff {pr_number} -R {repo_name}", timeout=30)
            if remote_diff:
                pr_diff_text = remote_diff

        # Detect unresolved Git merge conflict markers in diff
        has_conflict_markers, marker_count, marker_samples = detect_conflict_markers_in_diff(pr_diff_text)

        # Initialize category and reasons at top of classification
        category = "Group A"
        reasons = []

        # Analyze effectiveness & optimization patterns
        effectiveness = analyze_diff_patterns(pr_diff_text)
        details["effectiveness"] = effectiveness

        # Verify accessibility field alignment in TSX/JSX
        a11y_ok, a11y_msg = verify_accessibility_field_alignment(local_repo, [f.get("path", "") for f in files], head_branch, base_branch)
        if not a11y_ok:
            category = "Group B"
            reasons.append(f"Accessibility property drift: {a11y_msg}")

        # Detect remote GitHub merge conflict status
        remote_mergeable = details.get("mergeable")
        remote_merge_state = details.get("mergeStateStatus")
        remote_merge_conflict = (remote_mergeable == "CONFLICTING" or remote_merge_state == "DIRTY")

        if remote_state in ["MERGED", "CLOSED"]:
            category = "Group C"
            reasons.append(f"PR already {remote_state} on GitHub")
        elif superseded_by:
            category = "Group C (Superseded)"
            reasons.append(f"Superseded by merged commit on {base_branch}: {superseded_by}")
        elif is_metadata_only or local_zero_diff:
            category = "Group C"
            reasons.append("Zero non-metadata code diffs (already integrated or hallucinatory)")
        elif has_conflict_markers:
            category = "Group B"
            reasons.append(f"Contains {marker_count} unresolved Git merge conflict marker(s) in diff: {', '.join(marker_samples[:3])}")
        elif local_merge_conflict or remote_merge_conflict:
            category = "Group B"
            reasons.append("Unresolved GitHub merge conflict against base branch (mergeable: CONFLICTING)" if remote_merge_conflict else "Unresolved 3-way merge conflict against base branch")
        elif destructive_deletion:
            category = "Group B"
            reasons.append("Destructive line deletions in critical schema/entrypoint files")
        elif has_scratch:
            category = "Group B"
            reasons.append("Contains uncleaned scratch verification files")
        elif ci_in_flight:
            category = "Group A (CI In-Progress)"
            reasons.append(f"CI status checks currently executing ({len(in_flight_checks)} in-flight)")
        elif ci_failed:
            if self_healing_commit:
                category = "Group A (Bot Self-Healing In-Flight)"
                reasons.append("Bot pushed self-healing commit; pending updated CI run")
            elif stale_base_detected and not local_merge_conflict:
                category = "Group A (Needs Base Sync)"
                reasons.append("CI failed on stale base branch (sync required)")
            else:
                category = "Group B"
                reasons.append("Failed one or more CI status checks")
        elif audit_bot_failed:
            category = "Group B"
            reasons.append("Failed audit-bot-pr guardrail check")

        # Local targeted unit tests verification (optional)
        local_tests_passed = True
        local_tests_summary = ""
        if local_repo and getattr(args, 'verify_local_tests', False) and not local_merge_conflict and not has_conflict_markers:
            modified_paths = [f.get("path") for f in files if f.get("path")]
            local_tests_passed, local_tests_summary = run_targeted_tests_for_files(local_repo, modified_paths)
            if not local_tests_passed:
                category = "Group B"
                reasons.append(f"Targeted test failure: {local_tests_summary}")

        details["category"] = category
        details["group"] = category
        details["repo"] = repo_name
        details["hasConflictMarkers"] = has_conflict_markers
        details["conflictMarkerCount"] = marker_count
        details["conflictMarkerSamples"] = marker_samples
        
        # Check repository open security vulnerabilities via Dependabot API (memoized)
        security_alerts = []
        if getattr(args, 'check_security', False):
            security_alerts = check_repo_dependabot_security(repo_name)
            if security_alerts:
                high_crit = [a for a in security_alerts if a.get("security_vulnerability", {}).get("severity", "").lower() in ["critical", "high"]]
                if high_crit:
                    reasons.append(f"Repository has {len(high_crit)} open critical/high security alerts")
        details["securityAlertsCount"] = len(security_alerts)
        details["auditReasons"] = reasons
        details["localZeroDiff"] = local_zero_diff
        details["localMergeConflict"] = local_merge_conflict
        details["localTestsPassed"] = local_tests_passed
        details["localTestsSummary"] = local_tests_summary
        details["staleBase"] = stale_base_detected
        details["supersededBy"] = superseded_by
        audited_prs.append(details)

        # Highlight detected optimizations in progress log
        opt_notes = []
        if effectiveness.get("complexity_optimizations"):
            opt_notes.append("⚡ " + effectiveness["complexity_optimizations"][0])
        if effectiveness.get("memory_optimizations"):
            opt_notes.append("🧠 " + effectiveness["memory_optimizations"][0])
        if effectiveness.get("security_improvements"):
            opt_notes.append("🛡️ " + effectiveness["security_improvements"][0])
        opt_str = f" [{', '.join(opt_notes)}]" if opt_notes else ""

        print(f"  [{i}/{len(prs)}] {repo_name}#{pr_number} -> {category} ({', '.join(reasons) if reasons else 'Clean & Safe'}){opt_str}")

    # Harmonize in-memory sibling PR conflicts and supersession
    if args.base_dir:
        harmonize_sibling_pr_conflicts(audited_prs, args.base_dir)

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
        f.write("| Repo | PR # | Title | Category | Optimizations & Highlights | Reasons | URL |\n")
        f.write("| :--- | :---: | :--- | :---: | :--- | :--- | :--- |\n")
        for pr in audited_prs:
            repo = pr.get("repository", {}).get("nameWithOwner", "")
            num = pr.get("number")
            title = pr.get("title", "").replace("|", "\\|")
            cat = pr.get("category", "Group A")
            if pr.get("hasConflictMarkers"):
                cat = "⚠️ " + cat
            reasons = "; ".join(pr.get("auditReasons", [])) or "Clean & Safe"
            eff = pr.get("effectiveness", {})
            highlights = []
            if eff.get("complexity_optimizations"):
                highlights.extend(eff["complexity_optimizations"])
            if eff.get("memory_optimizations"):
                highlights.extend(eff["memory_optimizations"])
            if eff.get("security_improvements"):
                highlights.extend(eff["security_improvements"])
            highlight_str = "; ".join(highlights) if highlights else "Standard maintenance diff"
            url = pr.get("url", "")
            f.write(f"| `{repo}` | **#{num}** | {title} | **{cat}** | {highlight_str} | {reasons} | [Link]({url}) |\n")

def union_jules_markdown_files(file_path, local_dir, base_branch):
    """Unions markdown learning sections from HEAD and base branch without conflict markers using smart union."""
    full_path = os.path.join(local_dir, file_path)
    
    # If the file in working tree already has conflict markers, resolve in place
    if os.path.exists(full_path) and has_git_conflict_markers and resolve_in_place_file:
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if has_git_conflict_markers(content):
                success = resolve_in_place_file(full_path)
                if success:
                    return
        except Exception:
            pass

    base_content, _ = run_command(f'git show "origin/{base_branch}:{file_path}"', cwd=local_dir)
    head_content, _ = run_command(f'git show "HEAD:{file_path}"', cwd=local_dir)
    
    if smart_union_texts:
        merged_text = smart_union_texts(head_content or "", base_content or "")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(merged_text)
        return

    # Fallback to simple heading union
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
    clean_git_locks(local_dir)
    harmonize_case_collision_index(local_dir)
    run_command(f"git checkout {base} -f", cwd=local_dir)
    run_command(f"git pull origin {base}", cwd=local_dir)
    run_command("git merge --abort", cwd=local_dir)
    run_command(f"git fetch origin {head}:{head}", cwd=local_dir)
    run_command(f"git checkout \"{head}\" -f", cwd=local_dir)
    harmonize_case_collision_index(local_dir)

    # Capture original PR file scope before merge
    orig_diff_out, _ = run_command(f"git diff --name-only origin/{base}...HEAD", cwd=local_dir)
    orig_pr_files = {f.strip() for f in (orig_diff_out or "").splitlines() if f.strip()}

    code_m, err_m = run_command(f"git merge origin/{base} --no-edit", cwd=local_dir)
    if code_m is None:
        print(f"  ⚠️ Merge conflict encountered. Checking for auto-resolvable lockfiles and agent notes...")
        diff_u, _ = run_command("git diff --name-only --diff-filter=U", cwd=local_dir)
        conflict_files = [line.strip() for line in (diff_u or "").splitlines() if line.strip()]
        if not conflict_files:
            res_st, _ = run_command("git status --porcelain", cwd=local_dir)
            if res_st:
                conflict_files = [
                    line[3:].strip() for line in res_st.splitlines()
                    if len(line) > 3 and line[:2] in {'UU', 'AA', 'UD', 'DU', 'DD', 'AU', 'UA'}
                ]

        # Auto-revert collateral conflict files outside original PR scope
        if conflict_files and orig_pr_files:
            collateral_conflicts = [
                cf for cf in conflict_files
                if cf not in orig_pr_files
                and not any(cf.endswith(ext) for ext in ['package-lock.json', 'composer.lock', 'package.json', 'pnpm-lock.yaml', 'Gemfile.lock', 'Cargo.lock'])
                and not '.jules' in cf.lower()
            ]
            for cf in collateral_conflicts:
                print(f"  🛡️ Reverting collateral conflict outside original PR scope: {cf}")
                run_command(f'git checkout origin/{base} -- "{cf}"', cwd=local_dir)
                run_command(f'git add "{cf}"', cwd=local_dir)
            conflict_files = [cf for cf in conflict_files if cf not in collateral_conflicts]

        # Check if remaining conflict files can be auto-resolved
        # (lockfiles, .jules logs, or auto-splicable test methods)
        test_conflicts = [cf for cf in conflict_files if is_test_file and is_test_file(cf)]
        test_spliced_successfully = True
        for tcf in test_conflicts:
            full_tcf = os.path.join(local_dir, tcf)
            if resolve_in_place_file and resolve_in_place_file(full_tcf):
                print(f"  🧪 Cleanly auto-spliced disjoint test methods in {tcf}")
            else:
                test_spliced_successfully = False

        auto_resolvable = test_spliced_successfully and all(
            any(cf.endswith(ext) for ext in ['package-lock.json', 'composer.lock', 'package.json', 'pnpm-lock.yaml', 'Gemfile.lock', 'Cargo.lock'])
            or '.jules' in cf.lower()
            or (is_test_file and is_test_file(cf))
            for cf in conflict_files
        )
        if auto_resolvable:
            for cf in conflict_files:
                if '.jules' in cf.lower() and cf.endswith('.md'):
                    print(f"  📝 Unioning agent learning notes in {cf}...")
                    union_jules_markdown_files(cf, local_dir, base)
                    run_command(f"git add \"{cf}\"", cwd=local_dir)
                elif is_test_file and is_test_file(cf):
                    run_command(f"git add \"{cf}\"", cwd=local_dir)
                else:
                    run_command(f"git checkout origin/{base} -- \"{cf}\"", cwd=local_dir)
                    run_command(f"git add \"{cf}\"", cwd=local_dir)
            run_command(f"git commit -m \"fix(merge): sync latest {base}, union agent notes and splice test methods\"", cwd=local_dir)
            harmonize_case_collision_index(local_dir)
        else:
            run_command("git merge --abort", cwd=local_dir)
            return False, f"Non-lockfile merge conflicts in: {', '.join(conflict_files)}"

    # Revert accidental collateral modifications outside original PR scope
    post_diff_out, _ = run_command(f"git diff --name-only origin/{base}...HEAD", cwd=local_dir)
    if post_diff_out and orig_pr_files:
        collateral_reverted = False
        for f_line in post_diff_out.splitlines():
            cf = f_line.strip()
            if not cf:
                continue
            if cf not in orig_pr_files and not any(cf.endswith(ext) for ext in ['package-lock.json', 'composer.lock', 'package.json', 'pnpm-lock.yaml', 'Gemfile.lock', 'Cargo.lock']) and not cf.lower().startswith('.jules/'):
                print(f"  🛡️ Reverting collateral modified file not in original PR scope: {cf}")
                run_command(f'git checkout origin/{base} -- "{cf}"', cwd=local_dir)
                run_command(f'git add "{cf}"', cwd=local_dir)
                collateral_reverted = True
        if collateral_reverted:
            run_command("git commit -m \"chore: revert collateral modifications outside original PR scope\"", cwd=local_dir)


    # Check for destructive cross-file deletions
    numstat_out, _ = run_command(f"git diff --numstat origin/{base}...HEAD", cwd=local_dir)
    if numstat_out:
        repaired_files = []
        for line in numstat_out.splitlines():
            parts = line.strip().split()
            if len(parts) == 3:
                try:
                    additions = int(parts[0])
                    deletions = int(parts[1])
                    filepath = parts[2]
                    if '.jules' in filepath.lower() and filepath.endswith('.md') and deletions > 0:
                        print(f"  📝 Detected learning note truncation in {filepath} (-{deletions} lines). Auto-unioning notes...")
                        union_jules_markdown_files(filepath, local_dir, base)
                        run_command(f"git add \"{filepath}\"", cwd=local_dir)
                        repaired_files.append(filepath)
                    elif deletions > 15 and additions < 5:
                        print(f"  🩹 Detected suspicious cross-file deletion in {filepath} (+{additions} / -{deletions}). Auto-repairing from base...")
                        run_command(f"git checkout origin/{base} -- \"{filepath}\"", cwd=local_dir)
                        run_command(f"git add \"{filepath}\"", cwd=local_dir)
                        repaired_files.append(filepath)
                except ValueError:
                    pass
        if repaired_files:
            run_command("git commit -m \"chore: harmonize agent learnings and revert accidental deletions\"", cwd=local_dir)


    # Diff purification check
    stat_out, _ = run_command(f"git diff origin/{base}...HEAD --stat", cwd=local_dir)
    if stat_out:
        print(f"  📊 Purified PR diff against origin/{base}:\n{stat_out}")

    # HARD GUARDRAIL: Assert zero conflict markers in branch diff before push
    diff_check_out, _ = run_command(f"git diff origin/{base}...HEAD", cwd=local_dir)
    has_conflicts, c_count, c_samples = detect_conflict_markers_in_diff(diff_check_out)
    if has_conflicts:
        print(f"  ❌ GUARD BLOCKED: Synced branch '{head}' contains {c_count} unresolved conflict marker(s) ({', '.join(c_samples[:3])})! Aborting push.")
        return False, f"Branch contains unresolved merge conflict markers ({', '.join(c_samples[:2])})"

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
        if re.match(r'^([<]{7}(?: .*|\r?$)|[=]{7}\r?$|[>]{7}(?: .*|\r?$)|[|]{7}(?: .*|\r?$))', line):
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

    # Check for destructive cross-file deletions
    numstat_out, _ = run_command(f"git diff --numstat origin/{base}...HEAD", cwd=local_dir)
    cross_file_deleted = False
    if numstat_out:
        for line in numstat_out.splitlines():
            parts = line.strip().split()
            if len(parts) == 3:
                try:
                    additions = int(parts[0])
                    deletions = int(parts[1])
                    filepath = parts[2]
                    if deletions > 15 and additions < 5:
                        print(f"  🩹 Detected suspicious cross-file deletion in {filepath} (+{additions} / -{deletions}). Auto-repairing from base...")
                        run_command(f"git checkout origin/{base} -- \"{filepath}\"", cwd=local_dir)
                        run_command(f"git add \"{filepath}\"", cwd=local_dir)
                        cross_file_deleted = True
                except ValueError:
                    pass
        if cross_file_deleted:
            run_command("git commit -m \"chore: revert accidental cross-file deletions to protect base branch\"", cwd=local_dir)

    # Find modified files in this PR
    diff_files_out, _ = run_command(f"git diff --name-only origin/{base}...HEAD", cwd=local_dir)
    if not diff_files_out and not cross_file_deleted:
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

    # HARD GUARDRAIL: Assert zero conflict markers in branch diff before push
    diff_check_out, _ = run_command(f"git diff origin/{base}...HEAD", cwd=local_dir)
    has_conflicts, c_count, c_samples = detect_conflict_markers_in_diff(diff_check_out)
    if has_conflicts:
        print(f"  ❌ GUARD BLOCKED: Repaired branch '{head}' still contains {c_count} unresolved conflict marker(s) ({', '.join(c_samples[:3])})! Aborting push.")
        return False, f"Branch contains unresolved merge conflict markers ({', '.join(c_samples[:2])})"

    if push and repaired_count > 0:
        print(f"  ⬆️ Pushing repaired branch '{head}' to origin...")
        run_command(f"git push origin \"{head}\"", cwd=local_dir)
        return True, f"Repaired {repaired_count} file(s) and pushed"
    elif repaired_count > 0:
        return True, f"Repaired {repaired_count} file(s) (dry-run)"
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
    prs = []
    if getattr(args, 'input_file', None):
        if not os.path.exists(args.input_file):
            print(f"❌ Input file not found: {args.input_file}", file=sys.stderr)
            return
        with open(args.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data if isinstance(data, list) else data.get("prs", [])
            for p in items:
                cat = p.get("category", "") or p.get("group", "")
                if "Group A" in cat or "Clean & Safe" in cat:
                    repo = p.get("repo") or (p.get("repository", {}).get("nameWithOwner") if isinstance(p.get("repository"), dict) else p.get("repository"))
                    num = p.get("number")
                    if repo and num:
                        prs.append(f"{repo}#{num}")
        print(f"Loaded {len(prs)} Group A (Clean & Safe) PR(s) from {args.input_file}")
    elif getattr(args, 'pr_list', None):
        prs = [p.strip() for p in args.pr_list.split(",") if p.strip()]
    else:
        print("❌ Either --pr-list or --input-file must be provided.", file=sys.stderr)
        return

    if not prs:
        print("ℹ️ No PRs to merge.")
        return

    # Pre-flight hygiene: clean orphaned git index locks across repositories
    if args.base_dir and os.path.exists(args.base_dir):
        for root, dirs, _ in os.walk(args.base_dir):
            if ".git" in dirs:
                lock_file = os.path.join(root, ".git", "index.lock")
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                        print(f"🧹 Removed stale index lock: {lock_file}")
                    except Exception:
                        pass

    print(f"Merging {len(prs)} PRs with base sync...")

    # Optional: Disjoint file analysis
    if len(prs) > 1 and getattr(args, 'check_disjoint', True):
        log(f"\n📊 Evaluating pairwise modified file overlap across {len(prs)} PRs...")
        pr_files = {}

        def fetch_files_for_pr(item):
            parts = item.split("#")
            if len(parts) == 2:
                r, num = parts[0], parts[1]
                files = get_pr_modified_files_remote(r, num)
                # Ignore agent memory logs from code overlap calculations
                code_files = {f for f in files if not f.lower().startswith(".jules/") and not f.lower().startswith(".github/")}
                return item, code_files
            return item, set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(prs), 8)) as executor:
            future_to_pr = {executor.submit(fetch_files_for_pr, p): p for p in prs}
            for idx, future in enumerate(concurrent.futures.as_completed(future_to_pr), 1):
                p_item, c_files = future.result()
                pr_files[p_item] = c_files
                log(f"  [{idx}/{len(prs)}] Fetched modified files for {p_item} ({len(c_files)} file(s))")

        all_disjoint = True
        pr_keys = list(pr_files.keys())
        for i in range(len(pr_keys)):
            for j in range(i + 1, len(pr_keys)):
                p1, p2 = pr_keys[i], pr_keys[j]
                overlap = pr_files[p1].intersection(pr_files[p2])
                if overlap:
                    all_disjoint = False
                    log(f"  ⚠️ Overlap between {p1} and {p2}: {sorted(list(overlap))}")
                else:
                    log(f"  ✅ {p1} & {p2}: Completely Disjoint")

        if all_disjoint:
            log("🚀 Fast-Path Enabled: All PRs in batch touch 100% disjoint files (zero merge ordering hazards).\n")

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

        # HARD PRE-MERGE GUARDRAIL: Verify PR introduces zero merge conflict markers against base
        pr_diff_check = ""
        local_dir = find_local_repo_dir(args.base_dir, repo) if args.base_dir else None
        if local_dir:
            pr_diff_check, _ = run_command(f"git diff origin/main...HEAD", cwd=local_dir)
            if not pr_diff_check:
                pr_diff_check, _ = run_command(f"git diff origin/master...HEAD", cwd=local_dir)
        if not pr_diff_check:
            pr_diff_check, _ = run_command(f"gh pr diff {pr_num} -R {repo}", timeout=30)

        has_conflicts, c_count, c_samples = detect_conflict_markers_in_diff(pr_diff_check)
        if has_conflicts:
            log(f"  ❌ GUARD BLOCKED: PR {item} introduces {c_count} unresolved merge conflict marker(s) ({', '.join(c_samples[:3])})! Refusing to merge into default branch.")
            continue

        cmd = f"gh pr merge {pr_num} -R {repo} --admin --merge --delete-branch"
        log(f"Executing: {cmd}")
        merged_successfully = False
        if not args.dry_run:
            out, err = run_command(cmd)
            if out is not None:
                log(f"✅ Successfully merged {item}")
                merged_repos.add(repo)
                merged_successfully = True
            else:
                # Attempt standard merge without --admin if admin failed
                cmd_std = f"gh pr merge {pr_num} -R {repo} --merge --delete-branch"
                out_std, err_std = run_command(cmd_std)
                if out_std is not None:
                    log(f"✅ Successfully merged {item} (standard merge)")
                    merged_repos.add(repo)
                    merged_successfully = True
                else:
                    # Attempt automated sequential rebase and retry
                    log(f"  ⚠️ Direct merge failed ({err_std or err}). Attempting sequential re-sync and retry...")
                    synced, sync_msg = sync_single_pr_base(repo, pr_num, args.base_dir, push=True)
                    if synced:
                        log("  ⏳ Waiting 5 seconds for GitHub mergeable calculation to settle...")
                        time.sleep(5)
                        out_retry, err_retry = run_command(cmd_std)
                        if out_retry is not None:
                            log(f"✅ Successfully merged {item} on retry after sequential base sync")
                            merged_repos.add(repo)
                            merged_successfully = True
                        else:
                            log(f"❌ Failed to merge {item} on retry: {err_retry}")
                    else:
                        # Attempt feature diff rebase directly on updated origin/<base>
                        local_dir = find_local_repo_dir(args.base_dir, repo)
                        if local_dir:
                            view_info, _ = run_command(f"gh pr view {pr_num} -R {repo} --json headRefName,baseRefName")
                            if view_info:
                                try:
                                    v_data = json.loads(view_info)
                                    head = v_data.get("headRefName")
                                    base = v_data.get("baseRefName", "main")
                                    log(f"  🔄 Attempting isolated diff rebase for '{head}' on latest 'origin/{base}'...")
                                    run_command(f"git fetch origin {base}:{base}", cwd=local_dir)
                                    run_command(f"git checkout \"{head}\" -f", cwd=local_dir)
                                    run_command(f"git reset --hard origin/{base}", cwd=local_dir)
                                    diff_paths_out, _ = run_command(f"git diff --name-only origin/{base}...origin/{head}", cwd=local_dir)
                                    if diff_paths_out:
                                        for p in diff_paths_out.splitlines():
                                            p_str = p.strip()
                                            if p_str and not p_str.endswith('lock.json') and not p_str.endswith('lock.yaml'):
                                                run_command(f"git checkout origin/{head} -- \"{p_str}\"", cwd=local_dir)
                                        run_command(f"git add -A", cwd=local_dir)
                                        diff_staged, _ = run_command("git diff --cached", cwd=local_dir)
                                        rebase_conflicts, rc_count, rc_samples = detect_conflict_markers_in_diff(diff_staged)
                                        if rebase_conflicts:
                                            log(f"  ❌ GUARD BLOCKED: Rebased staged files contain {rc_count} conflict marker(s) ({', '.join(rc_samples[:2])}). Aborting rebase.")
                                            run_command(f"git reset --hard origin/{base}", cwd=local_dir)
                                            continue
                                        run_command(f"git commit -m \"chore: rebase {head} onto updated {base}\"", cwd=local_dir)
                                        run_command(f"git push origin \"{head}\" --force", cwd=local_dir)
                                        out_retry2, err_retry2 = run_command(cmd_std)
                                        if out_retry2 is not None:
                                            log(f"✅ Successfully merged {item} on isolated diff rebase")
                                            merged_repos.add(repo)
                                            merged_successfully = True
                                        else:
                                            log(f"❌ Failed to merge {item} after isolated diff rebase: {err_retry2}")
                                except Exception as rebase_err:
                                    log(f"❌ Rebase error: {rebase_err}")
            
            # If merged, clean up any temporary local evaluation branch for this PR
            if merged_successfully and args.base_dir:
                local_dir = find_local_repo_dir(args.base_dir, repo)
                if local_dir:
                    run_command(f"git branch -D pr-{pr_num}", cwd=local_dir)
        else:
            merged_repos.add(repo)

    # Optional: Fast-forward local submodules and advance parent pointer
        # Execute full post-merge test suite on all updated repositories
    if getattr(args, 'run_tests', False) and args.base_dir and merged_repos and not args.dry_run:
        print(f"\n🧪 Running full post-merge test suites across {len(merged_repos)} updated repository(ies)...")
        all_tests_passed = True
        for repo in merged_repos:
            local_dir = find_local_repo_dir(args.base_dir, repo)
            if local_dir:
                passed, summary = run_full_repository_tests(local_dir)
                if passed:
                    print(f"  ✅ {repo}: {summary}")
                else:
                    print(f"  ❌ {repo}: {summary}", file=sys.stderr)
                    all_tests_passed = False
        if not all_tests_passed:
            print("⚠️ Warning: One or more post-merge test suites encountered failures!", file=sys.stderr)

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
    p_audit.add_argument("--check-security", action="store_true", help="Audit repository Dependabot open security alerts during PR review")
    p_audit.add_argument("--wait-ci", action="store_true", help="Wait for in-flight CI checks to complete before finalizing audit")
    p_audit.add_argument("--timeout", type=int, default=300, help="Max wait time in seconds for CI checks (default: 300)")
    p_audit.add_argument("--markdown-output", help="Optional output Markdown report filepath")
    p_audit.set_defaults(func=cmd_audit)

    # Subcommand: watch-ci
    p_watch = subparsers.add_parser("watch-ci", help="Monitor in-flight CI runs for specified PRs until completion")
    p_watch.add_argument("--pr-list", required=True, help="Comma-separated list of REPO#PR_NUM")
    p_watch.add_argument("--timeout", type=int, default=300, help="Max wait time in seconds (default: 300)")
    p_watch.add_argument("--interval", type=int, default=10, help="Polling interval in seconds (default: 10)")
    p_watch.set_defaults(func=cmd_watch_ci)

    # Subcommand: union-merge
    p_union = subparsers.add_parser("union-merge", help="Smart union merge for .jules/*.md files and Git conflict markers")
    p_union.add_argument("--file", help="Path to conflicted markdown file to resolve in-place")
    p_union.add_argument("--ours", help="Path to ours file for 2-way/3-way union")
    p_union.add_argument("--theirs", help="Path to theirs file for 2-way/3-way union")
    p_union.add_argument("-o", "--output", help="Optional output path for union result")
    p_union.add_argument("--driver", nargs="+", help="Git merge driver interface (%%O %%A %%B [%%P])")
    p_union.set_defaults(func=cmd_union_merge)

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
    p_merge.add_argument("--pr-list", help="Comma-separated list of REPO#PR_NUM (e.g. bjohnson1279/js-ddd-inventory#620)")
    p_merge.add_argument("--input-file", help="Input audited JSON file (automatically filters and merges Group A Clean & Safe PRs)")
    p_merge.add_argument("--base-dir", help="Base directory containing local git repos for branch syncing")
    p_merge.add_argument("--no-sync", action="store_true", help="Skip automatic base branch synchronization")
    p_merge.add_argument("--no-disjoint-check", dest="check_disjoint", action="store_false", help="Skip pairwise disjoint file set analysis")
    p_merge.add_argument("--run-tests", action="store_true", help="Execute full test suites across all modified repositories after merging")
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

