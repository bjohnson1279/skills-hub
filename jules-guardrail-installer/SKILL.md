---
name: jules-guardrail-installer
description: Installs automated CI bot guardrails (bot-guard.yml) and hardens .jules/*.md directive files across polyglot repositories to auto-reject zero-diff hallucinatory PRs, full-file overwrites, and scratch file commits.
---

# Jules Bot Guardrail Installer

This skill provides automated templates and procedures for installing `.github/workflows/bot-guard.yml` and hardening `.jules/sentinel.md` & `bolt.md` directive files across new or existing repositories.

---

## Installation Procedure

### 1. Create `.github/workflows/bot-guard.yml`
In the target repository workflow directory, create `bot-guard.yml`:

```yaml
name: Automated Bot Guardrail

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  audit-bot-pr:
    runs-on: ubuntu-latest
    if: contains(github.actor, 'jules') || contains(github.actor, 'sentinel') || contains(github.head_ref, 'sentinel') || contains(github.head_ref, 'jules')
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Inspect Diff Statistics for Destructive Changes
        run: |
          echo "=== Auditing PR Diff for Bot Regressions & Hallucinations ==="

          # Check for zero-diff or hallucinatory acknowledgment PRs
          CHANGED_FILES=$(git diff --name-only origin/${{ github.base_ref }}...HEAD | grep -v '^\.jules/' | grep -v 'package.*json' | grep -v 'composer\.lock' || true)
          if [ -z "$CHANGED_FILES" ]; then
            echo "❌ ERROR: PR contains 0 code changes (hallucinatory task acknowledgment). Auto-failing."
            exit 1
          fi

          # Check for forbidden scratch files
          TOUCHED_NON_TEST_FILES=$(git diff --name-only --diff-filter=d origin/${{ github.base_ref }}...HEAD | grep -v -E '(^|/)(tests|__tests__|test)/' || true)
          SCRATCH_FILES=$(echo "$TOUCHED_NON_TEST_FILES" | grep -E '(^|/)test(_.*)?\.(ts|js|cjs|mjs|py|php|sh|bash)$|(^|/)fix_.*\.(php|cjs|js|ts|sh)$|(^|/)patch_.*\.(php|cjs|js|ts|py|sh|bash)$|(^|/)update_.*\.(php|cjs|js|ts|sh)$|(^|/)scratch_.*|.*\.scratch$|^plan\.md$' || true)
          if [ -n "$SCRATCH_FILES" ]; then
            echo "❌ ERROR: PR contains forbidden scratch verification files:"
            echo "$SCRATCH_FILES"
            exit 1
          fi

          # Check for line deletions in critical schema files
          DELETED_LINES=$(git diff --stat origin/${{ github.base_ref }}...HEAD | grep -E 'schema\.prisma|src/index\.ts|public/index\.php|docker/postgres/init/' | awk '{print $5}' | grep '-' || true)
          for count in $DELETED_LINES; do
            num=$(echo "$count" | tr -d '-')
            if [ "$num" -gt 15 ]; then
              echo "❌ ERROR: PR deletes $num lines from a core schema or entrypoint file, exceeding safety threshold (max 15)."
              exit 1
            fi
          done

          # Check for CI workflow tampering
          CI_DIFF=$(git diff origin/${{ github.base_ref }}...HEAD -- .github/workflows/ | grep -E '\|\|\s*true|continue-on-error:\s*true' || true)
          if [ -n "$CI_DIFF" ]; then
            echo "❌ ERROR: Bot PR modifies .github/workflows to suppress errors ('|| true' or 'continue-on-error: true'). Auto-failing."
            echo "$CI_DIFF"
            exit 1
          fi

          # Check for unresolved merge conflict markers
          CONFLICTS=$(git diff origin/${{ github.base_ref }}...HEAD | grep -E '^\+([<]{7}( .*|$)|[=]{7}\r?$|[>]{7}( .*|$)|[|]{7}( .*|$))' || true)
          if [ -n "$CONFLICTS" ]; then
            echo "❌ ERROR: PR adds unresolved Git merge conflict markers (<<<<<<<, =======, >>>>>>>). Auto-failing."
            echo "$CONFLICTS"
            exit 1
          fi

          echo "✅ Bot Guardrail Passed."
```

### 2. Harden `.jules/*.md` Directives
Append the following negative constraints to `.jules/sentinel.md`, `bolt.md`, `palette.md`, and `jules.md` in the target repository:

```markdown
## Prevention Directives for Automated Refactoring
- **Never Overwrite Complete Files**: Always use range-scoped replacement chunks (`StartLine`/`EndLine`) for edits to `schema.prisma`, `index.ts`, `public/index.php`, or DDL SQL scripts.
- **Do Not Remove Core Declarations**: Do not delete existing route registrations or database DDL tables.
- **Environment Isolation Compatibility**: When replacing fallback secrets, preserve test environment execution via `!getenv('APP_ENV')` or `getenv('APP_ENV') === 'testing'`.
- **No Scratch Files**: Never stage or commit `test_*.ts`, `test_*.js`, `test.cjs`, `fix_*.cjs`, `fix_*.php`, or `patch_*.py` files to git.
- **No Unresolved Conflict Markers**: Never stage or commit files containing Git merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`). Always resolve conflicts cleanly before committing.

## Scope Verification, Minimal Churn & CI Protection Directives
- **Scope Verification Before Variable Binding**: When adding interactive states or accessibility attributes (e.g. `disabled={loading}`, `aria-busy={loading}`, `isSubmitting`), NEVER assume a variable identifier exists. Always inspect component props, local state hooks (`useState`), or declaration scope first. If not defined, declare the state hook or reuse an existing scope variable. Never introduce TS2304 / TS2552 ("Cannot find name") compile errors.
- **Surgical Edits Only (No Whole-File Formatting)**: Never run whole-file code formatters (Prettier, Black, Pint, rustfmt) across unmodified lines. Changes must be strictly range-scoped and limited to the minimal AST block needed. Avoid noisy quote/whitespace churn that masks real logic changes and causes merge conflicts. Verify with `git diff -w` that non-functional churn is zero.
- **Zero Scratch File Commits**: Never stage or commit ad-hoc verification, patch, or debug scripts (`test.cjs`, `fix_*.cjs`, `fix_*.php`, `patch_*.py`, `patch_*.sh`, `scratch_*`). Execute checks via the project's native test commands (`npm test`, `pytest`, `phpunit`, etc.) and delete temporary scripts before creating git commits.
- **Never Weaken CI Workflows**: Do not modify `.github/workflows/**` to bypass failures (e.g. adding `|| true`, setting `continue-on-error: true`, or commenting out assertions). Always resolve the defect in the source code or test fixture.
- **Explicit Parameter & Variable Types**: In TypeScript files, avoid implicit `any` by always providing explicit types on functions, parameters, and arrow callbacks (e.g. `(id: string) => ...`). Verify zero type errors with `tsc --noEmit` before committing.

## Hallucinatory Task & Empty PR Directives
- **Zero-Diff Task Termination**: If the requested optimization, refactor, or fix is ALREADY natively present in the target branch, DO NOT create an empty pull request or commit an acknowledgment PR. Exit the task cleanly without opening a PR.
- **Stale Suggestion Guard**: Always verify the current code on `main`/`master` before planning changes. If no actionable diff is required, cancel task execution immediately.

## Assertiveness, Decisive PR Execution & Comparative Recommendations
- **Proactive & Decisive PR Submission**: Do NOT repeatedly pause to ask permission to open a pull request (e.g., avoid "Would you like me to open a PR for this?", "Can I submit the PR?", "Should I go ahead and create the PR?"). When an optimization, fix, or feature satisfies requirements, passes local test runners/linters, and preserves architectural invariants, proceed decisively to create and submit the Pull Request with a clear, structured summary and rationale.
- **Explicit Recommendations on Options**: When presenting multiple implementation strategies or architecture options (e.g., Option A vs. Option B), NEVER leave the choice open-ended or passive. Always make an explicit, reasoned recommendation (prefixed with `(Recommended)`) based on **overall technical effectiveness**:
  1. *Algorithmic & Complexity Gains*: Time and space complexity impact (O(N*M) -> O(N+M), reduction of nested scans).
  2. *Resource Overhead*: Heap allocations, memory pressure, and GC pause reduction.
  3. *Domain & Architecture Invariants*: Strict backward compatibility, contract stability, and prevention of regression risks.
  4. *Security & Reliability*: Input validation, cryptographic safety, and concurrency safety.
- **Lead with Recommended Path**: State clearly why the recommended solution delivers the highest net value and immediately execute or propose it as the primary course of action rather than asking open-ended questions.

## Scope Quarantine, Journaling & Security Test Invariants
- **Strictly Append-Only Journaling**: When adding learnings to `.jules/*.md`, append strictly at the end of the file. Do not rewrite, deduplicate, or remove lines beginning with `## YYYY-MM-DD`.
- **Surgical Scope Quarantine**: Modify only the files directly involved in the issue and their corresponding test fixtures. Do not delete, rename, or perform drive-by cleanups of unrelated root-level scripts or legacy files.
- **Coupled Test Fixture Awareness for Security Invariants**: When changing fail-open fallback behavior (such as hardening decryption to fail closed), always update upstream test mocks that rely on plaintext credentials or mock values.
```

### 3. Update `.gitignore`
Append scratch verification patterns to `.gitignore`:
```gitignore
# Bot scratch verification files
test.js
test_*.ts
test_*.js
test.cjs
fix_*.cjs
fix_*.php
patch_*.py
patch_*.sh
update_*.php
scratch_*
*.scratch
*.timestamp-*.mjs
```

---

### 4. Inject Merge Conflict Marker Check into Primary CI Pipelines

In addition to bot PR guardrails, ensure standard human commits, bot PRs, and direct pushes to the default branch fail-fast if conflict markers are committed.

Inject this step immediately after `actions/checkout` in the repository's primary CI workflow (`ci.yml`, `test.yml`, `phpunit.yml`, `conformance.yml`):

```yaml
      - name: Check for Merge Conflict Markers
        run: |
          echo "Scanning codebase for git merge conflict markers..."
          if git grep -n -I -E '^(<{7}|={7}|>{7}|\|{7})([[:space:]]|$)'; then
            echo "::error::Merge conflict markers detected in tracked files! Please resolve conflicts before merging."
            exit 1
          fi
          echo "No conflict markers detected."
```

#### Key Regex Features:
- `^(<{7}|={7}|>{7}|\|{7})`: Matches standard 7-character conflict indicators:
  - `<<<<<<<` (conflict start)
  - `=======` (separator)
  - `>>>>>>>` (conflict end)
  - `|||||||` (git diff3 base / ancestor marker)
- `([[:space:]]|$)`: Ensures the characters are at the beginning of a line followed by a space or end-of-line, avoiding false positives on syntax like `=====` or bitwise `<<<` in documentation.
- `-I`: Ignores binary files.
- `-n`: Prints line numbers for instant error localization.

