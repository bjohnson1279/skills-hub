---
name: bot-pr-triage-and-guardrail
description: Audits, categorizes, and processes open Pull Requests across polyglot repositories. Identifies valid performance/security PRs, destructive line-deletion regressions (>15 lines in schema/index), and zero-diff/hallucinatory PRs, performing batch merges and closures.
---

# Bot Pull Request Triage and Guardrail

This skill provides a systematic procedure for auditing, categorizing, and batch-processing open Pull Requests from automated agents (Jules, Sentinel, Dependabot) across repositories.

---

## Triage Procedure

### Step 1: Discover Open Pull Requests
Search all open PRs across owner repositories using GitHub CLI:
```bash
gh search prs --owner bjohnson1279 --state open --limit 100
```

### Step 2: Inspect PR Statistics & CI Status
For each open PR, fetch file diff statistics and check run statuses:
```bash
gh pr view <PR_NUMBER> -R <OWNER>/<REPO> --json number,title,state,mergeable,files,statusCheckRollup
```

### Step 2.5: Verify Security Alerts (Dependabot Audit)
Check whether the target repository has open Dependabot security advisories before approving PRs:
```bash
gh api repos/<OWNER>/<REPO>/dependabot/alerts?state=open
```


### Step 3: Categorize PRs
Group open PRs into three strict categories:

1. **Group A: Safe & High Value (MERGE)**
   - All CI status checks passed (`SUCCESS`).
   - `audit-bot-pr` guardrail check passed (`SUCCESS`).
   - Contains actionable code improvements (performance batching, security encryption, a11y improvements, or unit test suites).

2. **Group B: Destructive or Polluted (CLOSE)**
   - Deletes >15 lines from core schema/entrypoint files (`prisma/schema.prisma`, `src/index.ts`, `public/index.php`, `docker/postgres/init/*.sql`).
   - Contains uncleaned root scratch verification files (`test.js`, `test_*.ts`, `test.cjs`, `fix_*.cjs`, `fix_*.php`, `patch_*.py`).
   - Weakens CI workflows (e.g. adding `|| true`, `continue-on-error: true`, or commented assertions in `.github/workflows/**`).
   - Introduces TS2304 undeclared identifiers (e.g. `disabled={loading}`) or TS7006 implicit `any` parameter types.
   - Applies whole-file formatting overwriting hundreds of lines of unaffected code instead of surgical AST changes.
   - Failed CI build or integration test checks.
   - **Security Anti-Patterns:**
     - (Elixir/LiveView) Uses silent string truncation (`String.slice/3`) inside event handlers to fix Memory DoS (which fails to prevent initial memory allocation). Enforce boundary guard clauses instead (`when byte_size(val) <= 64`).
     - (State Pollution) Uses a single global scalar variable to track state (e.g. rate limits or timestamps) across a multi-entity system. Enforce Map/Dict scoping by entity ID (`%{id => timestamp}`).

3. **Group C: Zero-Diff / Hallucinatory Acknowledgments (CLOSE)**
   - Contains 0 code diffs (excluding `.jules/` log files or `package-lock.json`).
   - Created when an automated bot verifies that an issue is already natively solved on `main`.

---

## Batch Execution

### Merge Safe Group A PRs
```bash
gh pr merge <PR_NUMBER> -R <OWNER>/<REPO> --admin --merge --delete-branch
```

### Step 4: Post-Merge Test Verification & Clean Working Tree
After completing merges, pull updated default branches and run the complete test suite on each updated repository to guarantee no functional regressions were introduced:
```bash
git checkout main && git pull origin main
# Node / TypeScript:
npm test  # or: npx vitest run --no-file-parallelism
# PHP / PHPUnit:
vendor/bin/phpunit
# Python / pytest:
pytest
# Elixir / Phoenix:
docker compose run --rm app mix test
```


### Close Destructive / No-Op Group B & C PRs
```bash
gh pr close <PR_NUMBER> -R <OWNER>/<REPO> --comment "Closing due to destructive line deletions / 0-diff no-op."
```
