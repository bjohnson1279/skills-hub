---
name: multi-repo-ci-triage-auditor
description: Audits open Pull Requests across multi-repository workspaces, clusters correlated CI check failures to identify systemic workflow bugs vs code regressions, exports structured JSON reports, and safely manages batch job reruns.
---

# Multi-Repository CI Triage Auditor

This skill provides an automated audit and triage CLI to scan open pull requests across all repositories and nested submodules in a multi-repo workspace, cluster correlated CI failures to detect systemic workflow bugs or test harness outages, export structured JSON reports, and manage safe batch job reruns.

## Purpose & Problem Addressed

In large multi-repository ecosystems with automated bots (Jules, Sentinel, Bolt, Palette, Dependabot):
1. **Correlated CI False Positives**: Defective CI workflow YAML, syntax bugs, or broken regexes often cause simultaneous failures across dozens of repositories, masking true code health.
2. **Triaging Overhead**: Checking individual repository PRs manually is slow and misses macro-patterns across repos.
3. **Safe Remediation**: Once a workflow bug is patched, developers need a safe, bounded way to rerun only the affected failed runs without manual point-and-click or accidental spam.

## CLI Usage

The core CLI script is located at:
`~/.gemini/config/skills/multi-repo-ci-triage-auditor/scripts/ci_triage_auditor.py`

### 1. Audit Open PRs & Cluster Correlated Failures

```bash
# Full audit across all repositories under DEV, exporting structured JSON
python "C:\Users\johns\.gemini\config\skills\multi-repo-ci-triage-auditor\scripts\ci_triage_auditor.py" audit \
  --base-dir "C:\Users\johns\DEV" \
  --output "C:\Users\johns\DEV\ci_audit_report.json"

# Filter to failing bot PRs only with 6 parallel workers
python "C:\Users\johns\.gemini\config\skills\multi-repo-ci-triage-auditor\scripts\ci_triage_auditor.py" audit \
  --base-dir "C:\Users\johns\DEV" \
  --failing-only \
  --bot-only \
  --workers 6 \
  --output "C:\Users\johns\DEV\failing_bots.json"

# Audit a single target repository
python "C:\Users\johns\.gemini\config\skills\multi-repo-ci-triage-auditor\scripts\ci_triage_auditor.py" audit \
  --base-dir "C:\Users\johns\DEV" \
  --repo "inventory" \
  --output "C:\Users\johns\DEV\inventory_audit.json"
```

### 2. Cross-Repo PR Auditor (Global Scan)

Bypass repository boundaries and GitHub CLI limits to scan all open PRs for a specific owner, reporting any merge conflicts or test failures in a single view:

```bash
python "C:\Users\johns\.gemini\config\skills\multi-repo-ci-triage-auditor\scripts\audit_all_prs.py" --owner "bjohnson1279" --limit 100
```

### 3. Inspect Failed Job Logs

Fetch the exact failed log output for a specific GitHub Actions run ID without opening a browser:

```bash
python "C:\Users\johns\.gemini\config\skills\multi-repo-ci-triage-auditor\scripts\ci_triage_auditor.py" inspect-log \
  --repo-path "C:\Users\johns\DEV\inventory\gql-ddd-inventory" \
  --run-id 34777092296 \
  --output "C:\Users\johns\DEV\failed_run_34777092296.log"
```

### 3. Safely Rerun Failed Check Suites

Rerun failed check suites from a generated audit report. **Reruns are dry-run by default**; `--execute` must be explicitly passed to confirm execution.

```bash
# Preview candidate failed runs matching a specific check (dry-run)
python "C:\Users\johns\.gemini\config\skills\multi-repo-ci-triage-auditor\scripts\ci_triage_auditor.py" rerun \
  --input "C:\Users\johns\DEV\ci_audit_report.json" \
  --check-name "Audit Bot PR Diff & Guardrails"

# Execute batch reruns on GitHub Actions
python "C:\Users\johns\.gemini\config\skills\multi-repo-ci-triage-auditor\scripts\ci_triage_auditor.py" rerun \
  --input "C:\Users\johns\DEV\ci_audit_report.json" \
  --check-name "Audit Bot PR Diff & Guardrails" \
  --execute
```

## JSON Report Schema

```json
{
  "timestamp": "2026-09-13T23:45:00Z",
  "base_dir": "C:\\Users\\johns\\DEV",
  "summary": {
    "total_repositories_scanned": 27,
    "repositories_with_results": 9,
    "total_prs_evaluated": 25,
    "failing_prs_count": 11,
    "passing_prs_count": 14,
    "unique_failing_checks": 4
  },
  "correlated_failures": [
    {
      "check_name": "Audit Bot PR Diff & Guardrails",
      "failure_count": 9,
      "affected_repo_count": 7,
      "affected_repositories": ["ams-proto", "bash_encoding", "convo-sim", "..."],
      "likely_cause": "Correlated Workflow Defect / False Positive Risk",
      "affected_prs": [
        { "repo": "ams-proto", "pr_number": 103, "run_id": 34789123456 }
      ]
    }
  ],
  "repositories": { ... }
}
```

## Correlated Failure Heuristics

- **`Correlated Workflow Defect / False Positive Risk`**: When the same check name fails across $\ge 2$ distinct repositories. Typically indicates an upstream runner issue, third-party dependency outage, or flawed workflow YAML/regex.
- **`Isolated PR / Test Regression`**: When a failure is restricted to a single repository or branch. Indicates functional code regressions, broken unit tests, or missing environment variables.

## Related Skills

- [`bot-guardrail-installer`](file:///C:/Users/johns/.gemini/config/skills/bot-guardrail-installer/SKILL.md): Fixes and updates `.github/workflows/bot-guard.yml` and `.jules/*.md` rules when guardrails drift or produce false positives.
- [`bot-pr-triage-and-guardrail`](file:///C:/Users/johns/.gemini/config/skills/bot-pr-triage-and-guardrail/SKILL.md): Orchestrates closing or merging bot PRs once CI verification is green.
- [`pr-destructive-diff-auditor`](file:///C:/Users/johns/.gemini/config/skills/pr-destructive-diff-auditor/SKILL.md): Performs in-depth diff analysis on isolated failures.
