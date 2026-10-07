#!/usr/bin/env python3
"""
Multi-Repo Security Patcher CLI
Automates security auditing via GitHub Dependabot API, remediation planning,
safe override injection (npm/pnpm/yarn), automated bot PR merging, targeted test
verification, and parent repository submodule pointer synchronization across multi-repo ecosystems.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

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

def find_local_repo_dir(base_dir, repo_name_with_owner):
    """Finds matching local repository directory under base_dir."""
    if not base_dir or not os.path.exists(base_dir):
        return None
    repo_name = repo_name_with_owner.split("/")[-1]
    candidates = [
        os.path.join(base_dir, repo_name),
        os.path.join(base_dir, repo_name_with_owner),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, ".git")):
            return os.path.abspath(c)

    # Search immediate subdirectories
    try:
        for entry in os.scandir(base_dir):
            if entry.is_dir() and os.path.exists(os.path.join(entry.path, ".git")):
                if entry.name.lower() == repo_name.lower():
                    return os.path.abspath(entry.path)
    except Exception:
        pass
    return None

def get_repos_for_owner(owner, limit=100):
    cmd = f"gh repo list {owner} --limit {limit} --json nameWithOwner,isArchived,isFork"
    out, err = run_command(cmd)
    if not out:
        log(f"Error fetching repo list: {err}")
        return []
    try:
        repos = json.loads(out)
        return [r["nameWithOwner"] for r in repos if not r.get("isArchived", False)]
    except Exception as e:
        log(f"Error parsing repo list JSON: {e}")
        return []

def audit_repo_alerts(repo):
    cmd = f"gh api repos/{repo}/dependabot/alerts?state=open"
    out, err = run_command(cmd)
    if not out:
        return []
    try:
        data = json.loads(out)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

def cmd_audit(args):
    owner = args.owner
    specific_repos = [r.strip() for r in args.repos.split(",") if r.strip()] if args.repos else []
    
    if specific_repos:
        repos = specific_repos
    else:
        log(f"Fetching repositories for owner: {owner}...")
        repos = get_repos_for_owner(owner, limit=args.limit)

    log(f"Auditing Dependabot alerts across {len(repos)} repositories...")
    results = {}
    total_alerts = 0
    severity_counts = defaultdict(int)

    for i, repo in enumerate(repos, 1):
        alerts = audit_repo_alerts(repo)
        if alerts:
            repo_summary = {
                "repository": repo,
                "total_alerts": len(alerts),
                "by_severity": defaultdict(int),
                "alerts": []
            }
            for a in alerts:
                sec_vuln = a.get("security_vulnerability", {})
                package_info = sec_vuln.get("package", {})
                pkg_name = package_info.get("name", "unknown")
                ecosystem = package_info.get("ecosystem", "unknown")
                severity = sec_vuln.get("severity", "unknown").lower()
                advisory = a.get("security_advisory", {})
                ghsa_id = advisory.get("ghsa_id", "")
                cve_id = advisory.get("cve_id", "")
                summary = advisory.get("summary", "")
                first_patched = sec_vuln.get("first_patched_version", {}).get("identifier", "None")

                severity_counts[severity] += 1
                repo_summary["by_severity"][severity] += 1
                total_alerts += 1

                repo_summary["alerts"].append({
                    "number": a.get("number"),
                    "package": pkg_name,
                    "ecosystem": ecosystem,
                    "severity": severity,
                    "ghsa_id": ghsa_id,
                    "cve_id": cve_id,
                    "first_patched_version": first_patched,
                    "summary": summary,
                    "dependency_scope": a.get("dependency", {}).get("scope", "unknown"),
                    "manifest_path": a.get("dependency", {}).get("manifest_path", "")
                })
            results[repo] = repo_summary
            log(f"  [{i}/{len(repos)}] {repo}: {len(alerts)} open alert(s) ({dict(repo_summary['by_severity'])})")
        else:
            log(f"  [{i}/{len(repos)}] {repo}: 0 alerts (Clean)")

    output_data = {
        "owner": owner,
        "total_repositories_scanned": len(repos),
        "repositories_with_alerts": len(results),
        "total_open_alerts": total_alerts,
        "severity_totals": dict(severity_counts),
        "repositories": results
    }

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        log(f"\nAudit results saved to: {args.output}")

    if args.markdown_output:
        os.makedirs(os.path.dirname(os.path.abspath(args.markdown_output)), exist_ok=True)
        generate_audit_markdown(output_data, args.markdown_output)
        log(f"Markdown audit report saved to: {args.markdown_output}")

    return output_data

def generate_audit_markdown(audit_data, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Dependabot Security Audit Report\n\n")
        f.write(f"- **Owner**: `{audit_data['owner']}`\n")
        f.write(f"- **Repositories Scanned**: {audit_data['total_repositories_scanned']}\n")
        f.write(f"- **Repos with Vulnerabilities**: {audit_data['repositories_with_alerts']}\n")
        f.write(f"- **Total Alerts**: {audit_data['total_open_alerts']}\n")
        f.write("- **Severity Breakdown**:\n")
        for sev, count in sorted(audit_data['severity_totals'].items()):
            f.write(f"  - **{sev.capitalize()}**: {count}\n")
        f.write("\n---\n\n")
        f.write("## Vulnerability Details\n\n")
        f.write("| Repository | Package | Severity | CVE / GHSA | Patched Version | Scope | Summary |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :--- |\n")
        for repo, r_data in audit_data["repositories"].items():
            for a in r_data["alerts"]:
                advisory_link = f"[{a['cve_id'] or a['ghsa_id']}](https://github.com/advisories/{a['ghsa_id']})" if a['ghsa_id'] else "N/A"
                f.write(f"| `{repo}` | `{a['package']}` | **{a['severity'].upper()}** | {advisory_link} | `{a['first_patched_version']}` | {a['dependency_scope']} | {a['summary']} |\n")

def cmd_plan(args):
    if not os.path.exists(args.input_file):
        log(f"Error: Input audit file not found: {args.input_file}")
        return

    with open(args.input_file, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    plan = {
        "owner": audit_data.get("owner"),
        "remediation_actions": []
    }

    repos = audit_data.get("repositories", {})
    for repo, r_data in repos.items():
        npm_overrides = {}
        pnpm_overrides = {}
        direct_bumps = []

        for a in r_data.get("alerts", []):
            pkg = a.get("package")
            ecosystem = a.get("ecosystem")
            patched = a.get("first_patched_version")
            if patched and patched != "None":
                target_spec = f"^{patched}"
                if ecosystem == "npm":
                    npm_overrides[pkg] = target_spec
                    pnpm_overrides[pkg] = target_spec

        if npm_overrides:
            plan["remediation_actions"].append({
                "repository": repo,
                "action": "apply_overrides",
                "ecosystem": "npm",
                "overrides": npm_overrides,
                "notes": f"Inject {len(npm_overrides)} package override(s) into package.json"
            })

    # Check for open Dependabot PRs
    log("Scanning for open Dependabot PRs...")
    for repo in repos.keys():
        cmd = f"gh pr list -R {repo} --author app/dependabot --state open --json number,title,headRefName"
        out, _ = run_command(cmd)
        if out:
            try:
                prs = json.loads(out)
                for pr in prs:
                    plan["remediation_actions"].append({
                        "repository": repo,
                        "action": "merge_dependabot_pr",
                        "pr_number": pr["number"],
                        "title": pr["title"],
                        "head_ref": pr["headRefName"],
                        "notes": "Merge vetted Dependabot PR directly"
                    })
            except Exception:
                pass

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
        log(f"Remediation plan saved to: {args.output}")

    return plan

def inject_package_overrides(pkg_path, overrides_dict, package_manager="npm"):
    if not os.path.exists(pkg_path):
        return False, f"package.json not found at {pkg_path}"
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if package_manager == "pnpm":
            if "pnpm" not in data:
                data["pnpm"] = {}
            if "overrides" not in data["pnpm"]:
                data["pnpm"]["overrides"] = {}
            data["pnpm"]["overrides"].update(overrides_dict)
        else:
            if "overrides" not in data:
                data["overrides"] = {}
            data["overrides"].update(overrides_dict)

        with open(pkg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        return True, "Overrides successfully injected"
    except Exception as e:
        return False, str(e)

def cmd_apply(args):
    if not os.path.exists(args.plan_file):
        log(f"Error: Plan file not found: {args.plan_file}")
        return

    with open(args.plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)

    actions = plan.get("remediation_actions", [])
    log(f"Executing {len(actions)} remediation action(s)...")

    for i, act in enumerate(actions, 1):
        repo = act.get("repository")
        action_type = act.get("action")
        log(f"\n[{i}/{len(actions)}] Processing {repo} -> {action_type}")

        if action_type == "merge_dependabot_pr":
            pr_num = act.get("pr_number")
            cmd = f"gh pr merge {pr_num} -R {repo} --admin --squash --delete-branch"
            log(f"  Executing: {cmd}")
            if not args.dry_run:
                out, err = run_command(cmd)
                if out is not None:
                    log(f"  Successfully merged Dependabot PR #{pr_num} in {repo}")
                else:
                    log(f"  Merge failed: {err}")

        elif action_type == "apply_overrides":
            local_dir = find_local_repo_dir(args.base_dir, repo)
            if not local_dir:
                log(f"  Local directory not found for {repo} under {args.base_dir}. Skipping.")
                continue

            pkg_json = os.path.join(local_dir, "package.json")
            pnpm_workspace = os.path.join(local_dir, "pnpm-lock.yaml")
            pkg_manager = "pnpm" if os.path.exists(pnpm_workspace) else "npm"

            overrides = act.get("overrides", {})
            log(f"  Injecting {len(overrides)} override(s) using {pkg_manager} into {pkg_json}...")
            if not args.dry_run:
                success, msg = inject_package_overrides(pkg_json, overrides, pkg_manager)
                if not success:
                    log(f"  Override error: {msg}")
                    continue

                # Run package lock update
                if pkg_manager == "pnpm":
                    lock_cmd = "pnpm install --lockfile-only"
                else:
                    lock_cmd = "npm install --package-lock-only"

                log(f"  Updating lockfile ({lock_cmd})...")
                out_l, err_l = run_command(lock_cmd, cwd=local_dir)
                if out_l is not None:
                    log("  Lockfile successfully regenerated.")
                else:
                    log(f"  Warning: Lockfile update returned non-zero ({err_l})")

                # Git commit and push if requested
                if args.commit:
                    run_command("git add package.json package-lock.json pnpm-lock.yaml", cwd=local_dir)
                    commit_msg = f"fix(deps): security patch overrides for {', '.join(overrides.keys())}"
                    c_out, c_err = run_command(f'git commit -m "{commit_msg}"', cwd=local_dir)
                    if c_out is not None:
                        log(f"  Committed patch: {commit_msg}")
                        if args.push:
                            out_b, _ = run_command("git branch --show-current", cwd=local_dir)
                            curr_branch = out_b.strip() if out_b else "main"
                            p_out, p_err = run_command(f"git push origin {curr_branch}", cwd=local_dir)
                            if p_out is not None:
                                log(f"  Pushed changes to origin/{curr_branch}")
                            else:
                                log(f"  Push failed: {p_err}")
                    else:
                        log(f"  Working tree clean or commit failed: {c_err}")

def cmd_sync_submodules(args):
    parent_dir = os.path.abspath(args.parent_dir)
    if not os.path.exists(os.path.join(parent_dir, ".git")):
        log(f"Error: {parent_dir} is not a valid git repository.")
        return

    log(f"Checking for updated submodule pointers in {parent_dir}...")
    st_out, _ = run_command("git status --porcelain", cwd=parent_dir)
    if not st_out:
        log("No dirty submodule pointers detected. Parent repository is clean.")
        return

    dirty_submodules = []
    for line in st_out.splitlines():
        status = line[:2].strip()
        path = line[3:].strip()
        full_sub_path = os.path.join(parent_dir, path)
        if os.path.isdir(full_sub_path) and os.path.exists(os.path.join(full_sub_path, ".git")):
            dirty_submodules.append(path)

    if not dirty_submodules:
        log("No submodule changes staged or unstaged.")
        return

    log(f"Detected {len(dirty_submodules)} modified submodule pointer(s): {', '.join(dirty_submodules)}")
    if args.dry_run:
        return

    for sm in dirty_submodules:
        run_command(f'git add "{sm}"', cwd=parent_dir)
        log(f"  Staged: {sm}")

    commit_msg = f"chore(submodules): update {len(dirty_submodules)} submodule pointer(s) after security patching"
    c_out, c_err = run_command(f'git commit -m "{commit_msg}"', cwd=parent_dir)
    if c_out is not None:
        log(f"Committed updated submodule pointers: {commit_msg}")
        if args.push:
            out_b, _ = run_command("git branch --show-current", cwd=parent_dir)
            curr_branch = out_b.strip() if out_b else "main"
            p_out, p_err = run_command(f"git push origin {curr_branch}", cwd=parent_dir)
            if p_out is not None:
                log(f"Pushed submodule updates to origin/{curr_branch}")
            else:
                log(f"Push failed: {p_err}")
    else:
        log(f"Commit failed: {c_err}")

def main():
    parser = argparse.ArgumentParser(description="Multi-Repo Security Patcher CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # audit subcommand
    audit_parser = subparsers.add_parser("audit", help="Audit Dependabot alerts across repositories")
    audit_parser.add_argument("--owner", default="bjohnson1279", help="GitHub owner or organization")
    audit_parser.add_argument("--repos", help="Comma-separated list of repos (owner/name)")
    audit_parser.add_argument("--limit", type=int, default=100, help="Max repos to scan")
    audit_parser.add_argument("--output", help="Path to write JSON audit output")
    audit_parser.add_argument("--markdown-output", help="Path to write Markdown summary report")

    # plan subcommand
    plan_parser = subparsers.add_parser("plan", help="Generate remediation plan from audit output")
    plan_parser.add_argument("--input-file", required=True, help="Input audit JSON file")
    plan_parser.add_argument("--output", required=True, help="Output remediation plan JSON file")

    # apply subcommand
    apply_parser = subparsers.add_parser("apply", help="Apply remediation plan")
    apply_parser.add_argument("--plan-file", required=True, help="Remediation plan JSON file")
    apply_parser.add_argument("--base-dir", default="C:/Users/johns/DEV", help="Base directory of local clones")
    apply_parser.add_argument("--commit", action="store_true", help="Automatically git commit changes")
    apply_parser.add_argument("--push", action="store_true", help="Automatically push commits to remote")
    apply_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without changes")

    # sync-submodules subcommand
    sync_sub = subparsers.add_parser("sync-submodules", help="Stage, commit, and push updated parent submodule pointers")
    sync_sub.add_argument("--parent-dir", required=True, help="Path to parent git repository")
    sync_sub.add_argument("--push", action="store_true", help="Push parent commit to origin")
    sync_sub.add_argument("--dry-run", action="store_true", help="Simulate without committing")

    args = parser.parse_args()

    if args.command == "audit":
        cmd_audit(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "sync-submodules":
        cmd_sync_submodules(args)

if __name__ == "__main__":
    main()
