#!/usr/bin/env python3
"""
Multi-Repository CI Triage Auditor CLI
Discovers repositories, audits open PR status checks, clusters correlated CI failures,
and safely manages batch job reruns.
"""

import argparse
import concurrent.futures
import datetime
import json
import os
import subprocess
import sys
import time

# Ensure UTF-8 I/O across Windows environments
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BOT_IDENTIFIERS = ("jules", "sentinel", "bolt", "palette", "dependabot")

def run_gh_command(cmd, cwd, max_retries=3):
    """Executes a gh CLI command with exponential backoff on rate limit or transient errors."""
    delay = 1.0
    for attempt in range(max_retries):
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45
            )
            if res.returncode == 0:
                return res.stdout.strip(), None
            err = res.stderr.strip()
            # Check for GitHub API secondary rate limit
            if "rate limit" in err.lower() or "secondary rate limit" in err.lower():
                time.sleep(delay)
                delay *= 2.0
                continue
            return None, err
        except subprocess.TimeoutExpired:
            if attempt == max_retries - 1:
                return None, "Command timed out after 45 seconds"
            time.sleep(delay)
            delay *= 2.0
        except Exception as e:
            return None, str(e)
    return None, "Exceeded maximum retry attempts"

def discover_repositories(base_dir, target_repo=None):
    """Finds all Git repositories and first-level submodules under base_dir."""
    repos = []
    base_dir = os.path.abspath(base_dir)
    if not os.path.exists(base_dir):
        return repos

    for entry in sorted(os.listdir(base_dir)):
        sub = os.path.join(base_dir, entry)
        if target_repo and entry.lower() != target_repo.lower():
            continue
        if os.path.isdir(sub) and os.path.exists(os.path.join(sub, ".git")):
            repos.append((entry, sub))
            # Check for submodules inside the repository
            try:
                for child in sorted(os.listdir(sub)):
                    child_sub = os.path.join(sub, child)
                    if os.path.isdir(child_sub) and os.path.exists(os.path.join(child_sub, ".git")):
                        repos.append((f"{entry}/{child}", child_sub))
            except Exception:
                pass
    return repos

def inspect_repository_prs(repo_tuple, bot_only=False, failing_only=False):
    """Queries open PRs and checks for a single repository."""
    repo_name, repo_path = repo_tuple
    cmd = [
        "gh", "pr", "list",
        "--json", "number,title,headRefName,statusCheckRollup,url,author",
        "--state", "open",
        "-L", "50"
    ]
    stdout, err = run_gh_command(cmd, cwd=repo_path)
    if err:
        return repo_name, repo_path, {"error": err, "prs": []}
    if not stdout:
        return repo_name, repo_path, {"prs": []}

    try:
        raw_prs = json.loads(stdout)
    except Exception as e:
        return repo_name, repo_path, {"error": f"Failed to parse JSON: {e}", "prs": []}

    processed_prs = []
    for pr in raw_prs:
        author_login = pr.get("author", {}).get("login", "").lower()
        head_ref = pr.get("headRefName", "").lower()
        title = pr.get("title", "")

        is_bot = any(b in author_login or b in head_ref or b in title.lower() for b in BOT_IDENTIFIERS)
        if bot_only and not is_bot:
            continue

        checks = pr.get("statusCheckRollup", [])
        failing_checks = []
        passing_checks = []

        for c in checks:
            name = c.get("name") or c.get("context") or "Unknown check"
            conclusion = (c.get("conclusion") or "").lower()
            status = (c.get("status") or "").lower()
            run_url = c.get("detailsUrl") or c.get("targetUrl") or ""

            # Extract run ID if available from URL
            run_id = None
            if "actions/runs/" in run_url:
                try:
                    run_id = int(run_url.split("actions/runs/")[1].split("/")[0])
                except Exception:
                    pass

            check_obj = {
                "name": name,
                "status": status,
                "conclusion": conclusion,
                "run_id": run_id,
                "url": run_url
            }

            if conclusion in ("failure", "timed_out", "action_required"):
                failing_checks.append(check_obj)
            elif conclusion == "success":
                passing_checks.append(check_obj)

        if failing_only and not failing_checks:
            continue

        processed_prs.append({
            "number": pr.get("number"),
            "title": title,
            "head_ref": pr.get("headRefName"),
            "url": pr.get("url"),
            "is_bot": is_bot,
            "failing_checks": failing_checks,
            "passing_checks_count": len(passing_checks),
            "total_checks_count": len(checks)
        })

    return repo_name, repo_path, {"prs": processed_prs}

def audit_command(args):
    """Executes the audit subcommand."""
    repos = discover_repositories(args.base_dir, args.repo)
    if not repos:
        print(f"[ERROR] No Git repositories found in: {args.base_dir}")
        sys.exit(1)

    print(f"🔍 Discovered {len(repos)} repositories. Auditing open PR checks with up to {args.workers} workers...")

    results = {}
    total_prs = 0
    failing_prs = 0
    passing_prs = 0
    check_failure_counts = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, 8)) as executor:
        future_map = {
            executor.submit(inspect_repository_prs, r, args.bot_only, args.failing_only): r[0]
            for r in repos
        }
        for future in concurrent.futures.as_completed(future_map):
            repo_name, repo_path, data = future.result()
            prs = data.get("prs", [])
            err = data.get("error")

            if err:
                results[repo_name] = {"path": repo_path, "error": err, "prs": []}
                continue

            if prs or not args.failing_only:
                results[repo_name] = {"path": repo_path, "prs": prs}

            for p in prs:
                total_prs += 1
                if p["failing_checks"]:
                    failing_prs += 1
                    for fc in p["failing_checks"]:
                        cname = fc["name"]
                        if cname not in check_failure_counts:
                            check_failure_counts[cname] = {
                                "count": 0,
                                "affected_repos": set(),
                                "affected_prs": []
                            }
                        check_failure_counts[cname]["count"] += 1
                        check_failure_counts[cname]["affected_repos"].add(repo_name)
                        check_failure_counts[cname]["affected_prs"].append({
                            "repo": repo_name,
                            "pr_number": p["number"],
                            "run_id": fc.get("run_id")
                        })
                else:
                    passing_prs += 1

    # Correlate failures: steps failing across 2 or more repos are likely workflow / harness issues
    correlated_failures = []
    for cname, info in sorted(check_failure_counts.items(), key=lambda x: x[1]["count"], reverse=True):
        repo_count = len(info["affected_repos"])
        likely_cause = "Correlated Workflow Defect / False Positive Risk" if repo_count >= 2 else "Isolated PR / Test Regression"
        correlated_failures.append({
            "check_name": cname,
            "failure_count": info["count"],
            "affected_repo_count": repo_count,
            "affected_repositories": sorted(list(info["affected_repos"])),
            "likely_cause": likely_cause,
            "affected_prs": info["affected_prs"]
        })

    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "base_dir": os.path.abspath(args.base_dir),
        "summary": {
            "total_repositories_scanned": len(repos),
            "repositories_with_results": len(results),
            "total_prs_evaluated": total_prs,
            "failing_prs_count": failing_prs,
            "passing_prs_count": passing_prs,
            "unique_failing_checks": len(check_failure_counts)
        },
        "correlated_failures": correlated_failures,
        "repositories": results
    }

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n✅ Structured audit report saved to: {os.path.abspath(args.output)}")

    # Print human-readable summary
    print("\n" + "=" * 60)
    print(f"📊 CI TRIAGE AUDIT SUMMARY ({report['summary']['total_repositories_scanned']} Repos)")
    print(f"   Total PRs: {total_prs} | Passing: {passing_prs} | Failing: {failing_prs}")
    print("=" * 60)

    if correlated_failures:
        print("\n⚠️ Correlated Check Failures Detected Across Repositories:")
        for cf in correlated_failures:
            print(f"  • {cf['check_name']} ({cf['failure_count']} failures across {cf['affected_repo_count']} repos)")
            print(f"    Assessment: {cf['likely_cause']}")
            print(f"    Repos: {', '.join(cf['affected_repositories'][:6])}")
    else:
        print("\n✨ No correlated check failures detected.")

def inspect_log_command(args):
    """Fetches failed step logs for a specific GitHub Actions run ID."""
    cmd = ["gh", "run", "view", str(args.run_id), "--log-failed"]
    stdout, err = run_gh_command(cmd, cwd=args.repo_path)
    if err:
        print(f"[ERROR] Failed to fetch log for run {args.run_id}: {err}")
        sys.exit(1)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(stdout)
        print(f"✅ Failed log saved to: {os.path.abspath(args.output)}")
    else:
        print(stdout)

def rerun_command(args):
    """Safely reruns failed check suites from an audit report."""
    if not os.path.exists(args.input):
        print(f"[ERROR] Input report not found: {args.input}")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    target_runs = []
    correlated = data.get("correlated_failures", [])

    for cf in correlated:
        if args.check_name and cf["check_name"].lower() != args.check_name.lower():
            continue
        for item in cf.get("affected_prs", []):
            rid = item.get("run_id")
            if rid and rid not in [r["run_id"] for r in target_runs]:
                target_runs.append({
                    "run_id": rid,
                    "repo": item["repo"],
                    "pr_number": item["pr_number"],
                    "check_name": cf["check_name"]
                })

    if not target_runs:
        print("No matching failed runs found in report.")
        return

    print(f"\nFound {len(target_runs)} candidate failed runs to rerun:")
    for tr in target_runs:
        print(f"  • Run {tr['run_id']} [{tr['repo']} PR #{tr['pr_number']}] - {tr['check_name']}")

    if not args.execute:
        print("\n⚠️ Dry-run mode: No runs were triggered.")
        print("   Pass '--execute' to confirm and trigger reruns.")
        return

    print("\n🚀 Executing reruns via GitHub CLI...")
    successes = 0
    failures = 0
    repos_map = {r: data.get("repositories", {}).get(r, {}).get("path") for r in set(tr["repo"] for tr in target_runs)}

    for tr in target_runs:
        repo_path = repos_map.get(tr["repo"])
        if not repo_path or not os.path.exists(repo_path):
            print(f"  [SKIP] Invalid repo path for {tr['repo']}")
            failures += 1
            continue
        cmd = ["gh", "run", "rerun", str(tr["run_id"]), "--failed"]
        _, err = run_gh_command(cmd, cwd=repo_path)
        if err:
            print(f"  ❌ Run {tr['run_id']} ({tr['repo']}): {err}")
            failures += 1
        else:
            print(f"  ✅ Triggered rerun for Run {tr['run_id']} ({tr['repo']})")
            successes += 1

    print(f"\nFinished: {successes} reruns triggered, {failures} failed.")

def main():
    parser = argparse.ArgumentParser(description="Multi-Repository CI Triage Auditor")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: audit
    audit_parser = subparsers.add_parser("audit", help="Scan repositories and audit open PR status checks")
    audit_parser.add_argument("--base-dir", required=True, help="Base directory containing repositories")
    audit_parser.add_argument("--repo", help="Optional specific repository filter")
    audit_parser.add_argument("--failing-only", action="store_true", help="Filter to failing PRs only")
    audit_parser.add_argument("--bot-only", action="store_true", help="Filter to bot-generated PRs only")
    audit_parser.add_argument("--workers", type=int, default=4, help="Concurrent workers (default: 4, max: 8)")
    audit_parser.add_argument("--output", required=True, help="Path to write JSON output report")

    # Subcommand: inspect-log
    log_parser = subparsers.add_parser("inspect-log", help="Fetch failed log for a run ID")
    log_parser.add_argument("--repo-path", required=True, help="Local path to repository")
    log_parser.add_argument("--run-id", type=int, required=True, help="GitHub Actions run ID")
    log_parser.add_argument("--output", help="Optional path to write log text")

    # Subcommand: rerun
    rerun_parser = subparsers.add_parser("rerun", help="Safely rerun failed CI check suites from audit report")
    rerun_parser.add_argument("--input", required=True, help="Path to audit JSON report")
    rerun_parser.add_argument("--check-name", help="Filter rerun by specific failed check name")
    rerun_parser.add_argument("--execute", action="store_true", help="Execute reruns (requires explicit flag)")

    args = parser.parse_args()

    if args.subcommand == "audit":
        audit_command(args)
    elif args.subcommand == "inspect-log":
        inspect_log_command(args)
    elif args.subcommand == "rerun":
        rerun_command(args)

if __name__ == "__main__":
    main()
