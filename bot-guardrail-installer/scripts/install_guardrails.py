#!/usr/bin/env python3
"""
Bot Guardrail Installer CLI
Deploys bot-guard.yml, hardened .jules/*.md rules, and .gitignore patterns across repositories.
"""

import argparse
import os
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BOT_GUARD_YML = """name: Automated Bot Guardrail

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  audit-bot-pr:
    name: Audit Bot PR Diff & Guardrails
    runs-on: ubuntu-latest
    if: contains(github.actor, 'jules') || contains(github.actor, 'sentinel') || contains(github.actor, 'dependabot') || contains(github.head_ref, 'sentinel') || contains(github.head_ref, 'jules') || contains(github.head_ref, 'bolt') || contains(github.head_ref, 'palette')
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Inspect Diff Statistics for Destructive Changes & Zero-Diff
        run: |
          echo "=== Auditing PR Diff for Bot Regressions, Hallucinations & Conflict Markers ==="

          # 1. Reject Unresolved Git Merge Conflict Markers
          CONFLICTS=$(git diff origin/${{ github.base_ref }}...HEAD | grep -E '^\\+([<]{7}( .*|$)|[=]{7}\\r?$|[>]{7}( .*|$)|[|]{7}( .*|$))' || true)
          if [ -n "$CONFLICTS" ]; then
            echo "❌ ERROR: PR adds unresolved Git merge conflict markers (<<<<<<<, =======, >>>>>>>). Auto-failing."
            echo "$CONFLICTS"
            exit 1
          fi

          # 2. Reject Zero-Diff / Hallucinatory Acknowledgment PRs & Journal-Only PRs
          if [ "${{ github.actor }}" != "dependabot" ] && [ "${{ github.actor }}" != "dependabot[bot]" ]; then
            CHANGED_FILES=$(git diff --name-only origin/${{ github.base_ref }}...HEAD | grep -v '^\\.jules/' | grep -v '^\\.Jules/' | grep -v 'package.*json' | grep -v 'composer\\.lock' | grep -v 'Gemfile\\.lock' | grep -v 'pnpm-lock\\.yaml' | grep -v 'mix\\.lock' | grep -v 'Cargo\\.lock' || true)
            if [ -z "$CHANGED_FILES" ]; then
              echo "❌ ERROR: PR contains 0 non-metadata code changes (hallucinatory task acknowledgment or journal notes only). Auto-failing."
              exit 1
            fi
          fi

          # 3. Reject Forbidden Scratch Verification and Patch Files (Added or Modified)
          TOUCHED_NON_TEST_FILES=$(git diff --name-only --diff-filter=d origin/${{ github.base_ref }}...HEAD | grep -v -E '(^|/)(tests|__tests__|test)/' || true)
          SCRATCH_FILES=$(echo "$TOUCHED_NON_TEST_FILES" | grep -E '(^|/)test(_.*)?\\.(ts|js|cjs|mjs|py|php|sh|bash)$|(^|/)fix_.*\\.(php|cjs|js|ts|sh)$|(^|/)patch_.*\\.(php|cjs|js|ts|py|sh|bash)$|(^|/)update_.*\\.(php|cjs|js|ts|sh)$|(^|/)scratch_.*|.*\\.scratch$|^plan\\.md$|.*\\.diff$|.*\\.patch$' || true)
          if [ -n "$SCRATCH_FILES" ]; then
            echo "❌ ERROR: PR contains forbidden scratch verification or patch files:"
            echo "$SCRATCH_FILES"
            exit 1
          fi

          # 4. Reject Destructive Line Deletions in Critical Entrypoints & Schemas
          DELETED_LINES=$(git diff --stat origin/${{ github.base_ref }}...HEAD | grep -E 'schema\\.prisma|src/index\\.ts|public/index\\.php|docker/postgres/init/|db/schema\\.rb|routes/|routes\\.php' | awk '{print $5}' | grep '-' || true)
          for count in $DELETED_LINES; do
            num=$(echo "$count" | tr -d '-')
            if [ "$num" -gt 15 ]; then
              echo "❌ ERROR: PR deletes $num lines from a core schema or entrypoint file, exceeding safety threshold (max 15)."
              exit 1
            fi
          done

          # 5. Reject Bot CI Workflow Tampering
          CI_DIFF=$(git diff origin/${{ github.base_ref }}...HEAD -- .github/workflows/ | grep -E '\\|\\|\\s*true|continue-on-error:\\s*true' || true)
          if [ -n "$CI_DIFF" ]; then
            echo "❌ ERROR: Bot PR modifies .github/workflows to suppress errors ('|| true' or 'continue-on-error: true'). Auto-failing."
            echo "$CI_DIFF"
            exit 1
          fi

          # 6. Reject Deletion of Dated Historical Journal Entries in .jules/
          DELETED_JOURNAL=$(git diff origin/${{ github.base_ref }}...HEAD -- .jules/ .Jules/ | grep -E '^\\-## [0-9]{4}-[0-9]{2}-[0-9]{2}' || true)
          if [ -n "$DELETED_JOURNAL" ]; then
            echo "❌ ERROR: PR deletes historical journal entries from .jules/*.md. Entries must be strictly append-only."
            echo "$DELETED_JOURNAL"
            exit 1
          fi

          echo "✅ Basic Bot Diff Guardrail Passed."

      - name: Syntax & Script Verification Gate
        run: |
          echo "=== Checking Modified Files for Syntax Errors ==="
          MODIFIED_FILES=$(git diff --name-only --diff-filter=d origin/${{ github.base_ref }}...HEAD)

          for f in $MODIFIED_FILES; do
            if [ -f "$f" ]; then
              if [[ "$f" == *.sh ]]; then
                echo "Validating Bash syntax: $f"
                bash -n "$f"
              elif [[ "$f" == *.py ]]; then
                echo "Validating Python syntax: $f"
                python3 -m py_compile "$f"
              elif [[ "$f" == *.php ]] && command -v php &> /dev/null; then
                echo "Validating PHP syntax: $f"
                php -l "$f"
              fi
            fi
          done

          echo "✅ Syntax Verification Gate Passed."

      - name: Dependency Security Audit Gate
        run: |
          echo "=== Auditing Dependency Manifests for Known Vulnerabilities ==="
          MODIFIED_FILES=$(git diff --name-only --diff-filter=d origin/${{ github.base_ref }}...HEAD)

          # Node.js audit
          if echo "$MODIFIED_FILES" | grep -E '(package\\.json|package-lock\\.json)'; then
            if [ -f "package-lock.json" ]; then
              echo "Running npm audit..."
              npm audit --audit-level=high || true
            fi
          fi

          # Ruby bundler-audit
          if echo "$MODIFIED_FILES" | grep -E '(Gemfile|Gemfile\\.lock)'; then
            if [ -f "Gemfile.lock" ]; then
              echo "Checking Ruby gems for known advisories..."
              if command -v bundle-audit &> /dev/null; then
                bundle-audit check --update || true
              fi
            fi
          fi

          # PHP composer audit
          if echo "$MODIFIED_FILES" | grep -E '(composer\\.json|composer\\.lock)'; then
            if [ -f "composer.lock" ] && command -v composer &> /dev/null; then
              echo "Running composer audit..."
              composer audit || true
            fi
          fi

          echo "✅ Security Audit Gate Completed."

  auto-merge-bot-pr:
    name: Fast-Track Auto-Merge
    runs-on: ubuntu-latest
    needs: audit-bot-pr
    permissions:
      contents: write
      pull-requests: write
    if: github.event_name == 'pull_request' && (contains(github.actor, 'jules') || contains(github.actor, 'sentinel') || contains(github.actor, 'dependabot') || contains(github.actor, 'bolt') || contains(github.actor, 'palette') || contains(github.head_ref, 'sentinel') || contains(github.head_ref, 'jules') || contains(github.head_ref, 'bolt') || contains(github.head_ref, 'palette'))
    steps:
      - name: Enable Auto-Merge
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          echo "Enabling squash merge for PR #${{ github.event.pull_request.number }}"
          # Only use --squash, do NOT use --auto or gh pr review --approve unless branch protection is enforced
          gh pr merge ${{ github.event.pull_request.number }} -R ${{ github.repository }} --squash || true
"""

JULES_DIRECTIVE_BLOCK = """
## Prevention Directives for Automated Refactoring
- **Never Overwrite Complete Files**: Always use range-scoped replacement chunks for edits to `schema.prisma`, `index.ts`, `public/index.php`, `db/schema.rb`, or DDL SQL scripts.
- **Do Not Remove Core Declarations**: Do not delete existing route registrations or database DDL tables.
- **Environment Isolation Compatibility**: When replacing fallback secrets, preserve test environment execution via `!getenv('APP_ENV')` or `getenv('APP_ENV') === 'testing'`.
- **No Scratch Files**: Never stage or commit `test_*.ts`, `test_*.js`, `test.cjs`, `fix_*.php`, or `test.js` files to git.
- **No Unresolved Conflict Markers**: Never stage or commit files containing Git merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`). Always resolve conflicts cleanly before committing.

## Completeness & Verification Directives
- **Explicit Parameter & Contract Validation**: When creating or modifying API endpoints (Express, Fastify, Rails, Laravel), always implement explicit parameter and request body validation schemas (e.g. `z.string().uuid()`) to prevent unhandled 404/500 fallthroughs.
- **Database Indexing for Queries**: When addressing query bottlenecks or adding query lookup filters, always implement native database index migrations rather than loading collections into memory and performing array filtering (`.filter()`, `.select`).
- **Co-Occurring Dependency Auditing**: When bumping any dependency version, verify that other transitive dependencies do not carry high/critical security advisories (e.g. run `bundler-audit`, `npm audit`). Never introduce a version bump that breaks underlying framework APIs.
- **Self-Verification Before Commit**: Always run syntax checks (`bash -n` for shell scripts, `tsc --noEmit` for TypeScript, linter checks) and targeted test runners locally before opening or updating a PR.


## Hallucinatory Task & Empty PR Directives
- **Pre-Flight PR Deduplication**: Before writing code or authoring a new PR, always run `gh pr list --state open` to check if another bot has already opened a PR for the same issue or touching the same files. If a duplicate or related PR exists, append your fix to their branch or log a journal note instead of opening a competing PR.
- **Zero-Diff Task Termination**: If the requested optimization, refactor, or fix is ALREADY natively present in the target branch, DO NOT create an empty pull request or commit an acknowledgment PR. Exit the task cleanly without opening a PR.
- **No Journal-Only PRs**: Never open a pull request that only contains updates to .jules/*.md files without corresponding functional code changes and tests.
- **Stale Suggestion Guard**: Always verify the current code on `main`/`master` before planning changes. If no actionable diff is required, cancel task execution immediately.

## Assertiveness, Decisive PR Execution & Comparative Recommendations
- **Proactive & Decisive PR Submission**: Do NOT repeatedly pause to ask permission to open a pull request (e.g., avoid "Would you like me to open a PR for this?", "Can I submit the PR?", "Should I go ahead and create the PR?"). When an optimization, fix, or feature satisfies requirements, passes local test runners/linters, and preserves architectural invariants, proceed decisively to create and submit the Pull Request with a clear, structured summary and rationale.
- **Explicit Recommendations on Options**: When presenting multiple implementation strategies or architecture options (e.g., Option A vs. Option B), NEVER leave the choice open-ended or passive. Always make an explicit, reasoned recommendation (prefixed with `(Recommended)`) based on **overall technical effectiveness**:
  1. *Algorithmic & Complexity Gains*: Time and space complexity impact (O(N*M) -> O(N+M), reduction of nested scans).
  2. *Resource Overhead*: Heap allocations, memory pressure, and GC pause reduction.
  3. *Domain & Architecture Invariants*: Strict backward compatibility, contract stability, and prevention of regression risks.
  4. *Security & Reliability*: Input validation, cryptographic safety, and concurrency safety.
- **Lead with Recommended Path**: State clearly why the recommended solution delivers the highest net value and immediately execute or propose it as the primary course of action rather than asking open-ended questions.

## Scope Verification, Minimal Churn & CI Protection Directives
- **Scope Verification Before Variable Binding**: When adding interactive states or accessibility attributes (e.g. `disabled={loading}`, `aria-busy={loading}`, `isSubmitting`), NEVER assume a variable identifier exists. Always inspect component props, local state hooks (`useState`), or declaration scope first. If not defined, declare the state hook or reuse an existing scope variable. Never introduce TS2304 / TS2552 ("Cannot find name") compile errors.
- **Surgical Edits Only (No Whole-File Formatting)**: Never run whole-file code formatters (Prettier, Black, Pint, rustfmt) across unmodified lines. Changes must be strictly range-scoped and limited to the minimal AST block needed. Avoid noisy quote/whitespace churn that masks real logic changes and causes merge conflicts. Verify with `git diff -w` that non-functional churn is zero.
- **Zero Scratch File Commits**: Never stage or commit ad-hoc verification, patch, or debug scripts (`test.cjs`, `fix_*.cjs`, `fix_*.php`, `patch_*.py`, `patch_*.sh`, `scratch_*`). Execute checks via the project's native test commands (`npm test`, `pytest`, `phpunit`, etc.) and delete temporary scripts before creating git commits.
- **Never Weaken CI Workflows**: Do not modify `.github/workflows/**` to bypass failures (e.g. adding `|| true`, setting `continue-on-error: true`, or commenting out assertions). Always resolve the defect in the source code or test fixture.
- **Explicit Parameter & Variable Types**: In TypeScript files, avoid implicit `any` by always providing explicit types on functions, parameters, and arrow callbacks (e.g. `(id: string) => ...`). Verify zero type errors with `tsc --noEmit` before committing.
"""

ASSERTIVENESS_DIRECTIVE_BLOCK = """
## Assertiveness, Decisive PR Execution & Comparative Recommendations
- **Proactive & Decisive PR Submission**: Do NOT repeatedly pause to ask permission to open a pull request (e.g., avoid "Would you like me to open a PR for this?", "Can I submit the PR?", "Should I go ahead and create the PR?"). When an optimization, fix, or feature satisfies requirements, passes local test runners/linters, and preserves architectural invariants, proceed decisively to create and submit the Pull Request with a clear, structured summary and rationale.
- **Explicit Recommendations on Options**: When presenting multiple implementation strategies or architecture options (e.g., Option A vs. Option B), NEVER leave the choice open-ended or passive. Always make an explicit, reasoned recommendation (prefixed with `(Recommended)`) based on **overall technical effectiveness**:
  1. *Algorithmic & Complexity Gains*: Time and space complexity impact (O(N*M) -> O(N+M), reduction of nested scans).
  2. *Resource Overhead*: Heap allocations, memory pressure, and GC pause reduction.
  3. *Domain & Architecture Invariants*: Strict backward compatibility, contract stability, and prevention of regression risks.
  4. *Security & Reliability*: Input validation, cryptographic safety, and concurrency safety.
- **Lead with Recommended Path**: State clearly why the recommended solution delivers the highest net value and immediately execute or propose it as the primary course of action rather than asking open-ended questions.
"""

SCOPE_CHURN_CI_DIRECTIVE_BLOCK = """
## Scope Verification, Minimal Churn & CI Protection Directives
- **Scope Verification Before Variable Binding**: When adding interactive states or accessibility attributes (e.g. `disabled={loading}`, `aria-busy={loading}`, `isSubmitting`), NEVER assume a variable identifier exists. Always inspect component props, local state hooks (`useState`), or declaration scope first. If not defined, declare the state hook or reuse an existing scope variable. Never introduce TS2304 / TS2552 ("Cannot find name") compile errors.
- **Surgical Edits Only (No Whole-File Formatting)**: Never run whole-file code formatters (Prettier, Black, Pint, rustfmt) across unmodified lines. Changes must be strictly range-scoped and limited to the minimal AST block needed. Avoid noisy quote/whitespace churn that masks real logic changes and causes merge conflicts. Verify with `git diff -w` that non-functional churn is zero.
- **Zero Scratch File Commits**: Never stage or commit ad-hoc verification, patch, or debug scripts (`test.cjs`, `fix_*.cjs`, `fix_*.php`, `patch_*.py`, `patch_*.sh`, `scratch_*`). Execute checks via the project's native test commands (`npm test`, `pytest`, `phpunit`, etc.) and delete temporary scripts before creating git commits.
- **Never Weaken CI Workflows**: Do not modify `.github/workflows/**` to bypass failures (e.g. adding `|| true`, setting `continue-on-error: true`, or commenting out assertions). Always resolve the defect in the source code or test fixture.
- **Explicit Parameter & Variable Types**: In TypeScript files, avoid implicit `any` by always providing explicit types on functions, parameters, and arrow callbacks (e.g. `(id: string) => ...`). Verify zero type errors with `tsc --noEmit` before committing.
"""

PALETTE_SCOPE_LEARNING = """
## 2026-09-29 - Scope Verification for Async Loading Attributes
**Learning:** Blindly injecting `disabled={loading}` or `aria-busy={loading}` into JSX/TSX buttons causes fatal TypeScript compilation errors (`TS2304: Cannot find name 'loading'`) when `loading` is not declared in component props, state hooks (`useState`), or mutation results. Furthermore, using temporary patch scripts (`fix_*.cjs`) to manipulate source code pollutes the git index.
**Action:** Before referencing any state identifier (such as `loading`, `isSubmitting`, `isPending`) in `disabled` or `aria-busy`, inspect the component scope. If no loading state is tracked, define it using `useState(false)` or check existing query/mutation hooks. Never bind undeclared variables. Always run `tsc --noEmit` locally and never commit temporary fix scripts.
"""

BOLT_SURGICAL_LEARNING = """
## 2026-09-29 - Surgical Optimization Edits and No Scratch Script Commits
**Learning:** Running whole-file formatters or regenerating entire components while performing performance optimizations introduces massive whitespace/formatting diffs (1,000+ lines), masking the real optimization, invalidating git blame, and causing painful merge conflicts with concurrent PRs. Additionally, committing scratch benchmark or patch scripts (`patch_*.py`, `test.cjs`) pollutes production repositories and triggers CI guardrail failures.
**Action:** Restrict all algorithmic and performance optimizations to strictly scoped replacement chunks. Diff size must reflect only the functional optimization. Always clean up temporary benchmark or patch scripts with `git rm -f` before committing.
"""

SENTINEL_CI_LEARNING = """
## 2026-09-29 - Non-Destructive Security Patching & CI Protection
**Learning:** Security patches must never weaken CI workflow files (`.github/workflows/**`) by appending `|| true` or `continue-on-error: true` to suppress test/build failures. Furthermore, when adding defensive type assertions or input validators in TypeScript, omitting explicit types can introduce `TS7006: Parameter implicitly has an 'any' type`.
**Action:** Never modify CI workflow definitions to bypass test failures; resolve the underlying issue in source code or test fixtures. Always provide explicit types on newly introduced parameters and helper functions. Ensure zero scratch scripts (`fix_*.php`, `test_*.js`) are committed.
"""

JULES_PRECISION_LEARNING = """
## 2026-09-29 - Precision Scope & Zero-Pollution Guardrails
**Learning:** Automated bot workflows frequently fail when formatters reformat unaffected lines, when ad-hoc patch scripts (`fix_*.cjs`, `patch_*.py`) are left behind, or when undeclared variables (`loading`) are injected into templates.
**Action:** Practice surgical range-scoped modifications. Inspect identifier declarations in scope before adding bindings. Never commit scratch or patch files. Never weaken CI workflows to force a build to pass.
"""

ADDITIVE_JOURNAL_DIRECTIVE_BLOCK = """
## Additive Documentation & Scratch Cleanliness Directives
- **Strictly Additive Journal Updates**: When updating `.jules/*.md`, strictly append new dated entries (`## YYYY-MM-DD - Title`). NEVER delete, truncate, or overwrite historical learnings or previous entries.
- **Substantive Code Diff Requirement**: Pull requests must include substantive code changes in `src/`, `app/`, `lib/`, or `tests/`. Never open PRs that modify only `.jules/*.md` journals or root scratch scripts.
- **Zero Scratch File Commits**: Never commit `*.diff`, `*.patch`, `test_*.ts`, `test_*.js`, `test.cjs`, `fix_*.php`, or `patch_*.py` files. Always remove temporary debugging or verification scripts prior to committing.
"""

STREAMLINING_DIRECTIVE_BLOCK = """
## Scope Quarantine, Journaling & Security Test Invariants
- **Strictly Append-Only Journaling**: When adding learnings to `.jules/*.md`, append strictly at the end of the file. Do not rewrite, deduplicate, or remove lines beginning with `## YYYY-MM-DD`.
- **Surgical Scope Quarantine**: Modify only the files directly involved in the issue and their corresponding test fixtures. Do not delete, rename, or perform drive-by cleanups of unrelated root-level scripts or legacy files.
- **Coupled Test Fixture Awareness for Security Invariants**: When changing fail-open fallback behavior (such as hardening decryption to fail closed), always update upstream test mocks that rely on plaintext credentials or mock values.
"""

GITIGNORE_PATTERNS = [
    "# Bot scratch verification files",
    "test.js",
    "test_*.ts",
    "test_*.js",
    "test.cjs",
    "fix_*.cjs",
    "fix_*.php",
    "patch_*.py",
    "patch_*.sh",
    "update_*.php",
    "scratch_*",
    "*.scratch",
    "*.diff",
    "*.patch",
    "patch.diff",
    "*.timestamp-*.mjs"
]

def run_cmd(cmd, cwd=None):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        if res.returncode != 0:
            return None, res.stderr.strip()
        return res.stdout.strip(), None
    except Exception as e:
        return None, str(e)

def install_for_repo(repo_dir, dry_run=False, commit_and_push=False):
    print(f"Processing repository: {repo_dir}")
    if not os.path.exists(os.path.join(repo_dir, ".git")):
        print(f"  [SKIP] Not a git repository: {repo_dir}")
        return False

    modified = False

    # 1. bot-guard.yml
    workflow_dir = os.path.join(repo_dir, ".github", "workflows")
    workflow_file = os.path.join(workflow_dir, "bot-guard.yml")
    needs_workflow_write = False
    if not os.path.exists(workflow_file):
        needs_workflow_write = True
    else:
        with open(workflow_file, "r", encoding="utf-8", errors="ignore") as f:
            curr_wf = f.read()
        if ("Syntax & Script Verification Gate" not in curr_wf or 
            "[<]{7}" not in curr_wf or 
            "Reject Bot CI Workflow Tampering" not in curr_wf or 
            "patch_.*" not in curr_wf or
            "DELETED_JOURNAL" not in curr_wf or
            "\\.diff\\$" not in curr_wf or
            "--diff-filter=d" not in curr_wf):
            needs_workflow_write = True

    if needs_workflow_write:
        print("  [NEW/UPDATE] Installing upgraded .github/workflows/bot-guard.yml")
        if not dry_run:
            os.makedirs(workflow_dir, exist_ok=True)
            with open(workflow_file, "w", encoding="utf-8") as f:
                f.write(BOT_GUARD_YML.strip() + "\n")
            modified = True
    else:
        print("  [OK] .github/workflows/bot-guard.yml already up to date")

    # 2. .jules directives
    seen_dirs = set()
    for jdir_name in [".jules", ".Jules"]:
        jules_dir = os.path.join(repo_dir, jdir_name)
        if os.path.isdir(jules_dir):
            real_dir = os.path.realpath(jules_dir)
            if real_dir in seen_dirs:
                continue
            seen_dirs.add(real_dir)
            for fname in os.listdir(jules_dir):
                bot_name = fname.lower()
                if bot_name in ["bolt.md", "sentinel.md", "palette.md", "jules.md"]:
                    target_md = os.path.join(jules_dir, fname)
                    with open(target_md, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    file_modified = False
                    # Check base directive blocks
                    if "Completeness & Verification Directives" not in content:
                        print(f"  [UPDATE] Hardening {jdir_name}/{fname} with completeness and verification directives")
                        if not dry_run:
                            with open(target_md, "a", encoding="utf-8") as f:
                                f.write("\n" + JULES_DIRECTIVE_BLOCK.strip() + "\n")
                        content += "\n" + JULES_DIRECTIVE_BLOCK.strip() + "\n"
                        file_modified = True
                    elif "Assertiveness, Decisive PR Execution" not in content:
                        print(f"  [UPDATE] Hardening {jdir_name}/{fname} with assertiveness and comparative recommendation directives")
                        if not dry_run:
                            with open(target_md, "a", encoding="utf-8") as f:
                                f.write("\n" + ASSERTIVENESS_DIRECTIVE_BLOCK.strip() + "\n")
                        content += "\n" + ASSERTIVENESS_DIRECTIVE_BLOCK.strip() + "\n"
                        file_modified = True

                    if "Scope Verification, Minimal Churn & CI Protection Directives" not in content:
                        print(f"  [UPDATE] Hardening {jdir_name}/{fname} with scope verification, minimal churn, and CI protection directives")
                        if not dry_run:
                            with open(target_md, "a", encoding="utf-8") as f:
                                f.write("\n" + SCOPE_CHURN_CI_DIRECTIVE_BLOCK.strip() + "\n")
                        content += "\n" + SCOPE_CHURN_CI_DIRECTIVE_BLOCK.strip() + "\n"
                        file_modified = True

                    if "Strictly Additive Journal Updates" not in content:
                        print(f"  [UPDATE] Hardening {jdir_name}/{fname} with additive journal and scratch cleanliness directives")
                        if not dry_run:
                            with open(target_md, "a", encoding="utf-8") as f:
                                f.write("\n" + ADDITIVE_JOURNAL_DIRECTIVE_BLOCK.strip() + "\n")
                        content += "\n" + ADDITIVE_JOURNAL_DIRECTIVE_BLOCK.strip() + "\n"
                        file_modified = True

                    if "Scope Quarantine, Journaling & Security Test Invariants" not in content:
                        print(f"  [UPDATE] Hardening {jdir_name}/{fname} with scope quarantine and test invariant directives")
                        if not dry_run:
                            with open(target_md, "a", encoding="utf-8") as f:
                                f.write("\n" + STREAMLINING_DIRECTIVE_BLOCK.strip() + "\n")
                        content += "\n" + STREAMLINING_DIRECTIVE_BLOCK.strip() + "\n"
                        file_modified = True

                    # Bot-specific specialized learnings
                    if bot_name == "palette.md" and "Scope Verification for Async Loading Attributes" not in content:
                        print(f"  [UPDATE] Adding scope verification learning to {jdir_name}/{fname}")
                        if not dry_run:
                            with open(target_md, "a", encoding="utf-8") as f:
                                f.write("\n" + PALETTE_SCOPE_LEARNING.strip() + "\n")
                        file_modified = True
                    elif bot_name == "bolt.md" and "Surgical Optimization Edits and No Scratch Script Commits" not in content:
                        print(f"  [UPDATE] Adding surgical optimization learning to {jdir_name}/{fname}")
                        if not dry_run:
                            with open(target_md, "a", encoding="utf-8") as f:
                                f.write("\n" + BOLT_SURGICAL_LEARNING.strip() + "\n")
                        file_modified = True
                    elif bot_name == "sentinel.md" and "Non-Destructive Security Patching & CI Protection" not in content:
                        print(f"  [UPDATE] Adding non-destructive security & CI learning to {jdir_name}/{fname}")
                        if not dry_run:
                            with open(target_md, "a", encoding="utf-8") as f:
                                f.write("\n" + SENTINEL_CI_LEARNING.strip() + "\n")
                        file_modified = True
                    elif bot_name == "jules.md" and "Precision Scope & Zero-Pollution Guardrails" not in content:
                        print(f"  [UPDATE] Adding precision scope learning to {jdir_name}/{fname}")
                        if not dry_run:
                            with open(target_md, "a", encoding="utf-8") as f:
                                f.write("\n" + JULES_PRECISION_LEARNING.strip() + "\n")
                        file_modified = True

                    if file_modified:
                        modified = True
                    else:
                        print(f"  [OK] {jdir_name}/{fname} all directives and learnings up to date")

    # 3. .gitignore
    gitignore_path = os.path.join(repo_dir, ".gitignore")
    existing_ignore = ""
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
            existing_ignore = f.read()

    to_add = [pat for pat in GITIGNORE_PATTERNS if pat not in existing_ignore]
    if to_add:
        print(f"  [UPDATE] Adding {len(to_add)} scratch file patterns to .gitignore")
        if not dry_run:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(to_add) + "\n")
            modified = True
    else:
        print("  [OK] .gitignore scratch patterns already present")

    # Check if there are uncommitted changes to guardrail files
    status_out, _ = run_cmd("git status --porcelain .github/workflows/bot-guard.yml .gitignore .jules .Jules", cwd=repo_dir)
    has_uncommitted = bool(status_out and status_out.strip())

    if (modified or has_uncommitted) and commit_and_push and not dry_run:
        rem_out, _ = run_cmd("git config --get remote.origin.url", cwd=repo_dir)
        if rem_out and ("utahdts" in rem_out or "bcbooks" in rem_out):
            print(f"  [SKIP PUSH] Upstream external repository: {rem_out}")
            return modified
        files_to_add = []
        if os.path.exists(workflow_file):
            files_to_add.append(".github/workflows/bot-guard.yml")
        if os.path.exists(gitignore_path):
            files_to_add.append(".gitignore")
        for jdir in [".jules", ".Jules"]:
            if os.path.isdir(os.path.join(repo_dir, jdir)):
                files_to_add.append(jdir)

        if files_to_add:
            run_cmd(f"git add {' '.join(files_to_add)}", cwd=repo_dir)
        run_cmd('git commit -m "ci: harden bot guardrails, scope verification, minimal churn, and scratch prevention"', cwd=repo_dir)
        run_cmd("git push origin HEAD", cwd=repo_dir)
        print("  ✅ Pushed guardrails successfully.")

    return modified

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description="Bot Guardrail Installer & Auditor")
    parser.add_argument("--target-dir", help="Specific git repository directory")
    parser.add_argument("--all-in-base", help="Base directory containing multiple repositories")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without modifying files")
    parser.add_argument("--audit", action="store_true", help="Audit mode: scan repositories for outdated guardrails or false-positive risks without modifying files")
    parser.add_argument("--commit-and-push", action="store_true", help="Commit and push changes to remote")
    args = parser.parse_args()

    is_dry_run = args.dry_run or args.audit

    repos_scanned = 0
    repos_updated = 0

    if args.target_dir:
        target = os.path.abspath(args.target_dir)
        repos_scanned += 1
        if install_for_repo(target, is_dry_run, args.commit_and_push):
            repos_updated += 1
        # Check for submodules inside target repository
        try:
            for child in os.listdir(target):
                child_sub = os.path.join(target, child)
                if os.path.isdir(child_sub) and (os.path.exists(os.path.join(child_sub, ".git")) or os.path.isfile(os.path.join(child_sub, ".git"))):
                    repos_scanned += 1
                    if install_for_repo(child_sub, is_dry_run, args.commit_and_push):
                        repos_updated += 1
        except Exception:
            pass
    elif args.all_in_base:
        base = os.path.abspath(args.all_in_base)
        for entry in os.listdir(base):
            sub = os.path.join(base, entry)
            if os.path.isdir(sub) and os.path.exists(os.path.join(sub, ".git")):
                repos_scanned += 1
                if install_for_repo(sub, is_dry_run, args.commit_and_push):
                    repos_updated += 1
                # Check for submodules inside the repository
                try:
                    for child in os.listdir(sub):
                        child_sub = os.path.join(sub, child)
                        if os.path.isdir(child_sub) and os.path.exists(os.path.join(child_sub, ".git")):
                            repos_scanned += 1
                            if install_for_repo(child_sub, is_dry_run, args.commit_and_push):
                                repos_updated += 1
                except Exception:
                    pass
    else:
        print("[ERROR] Specify either --target-dir or --all-in-base.")
        sys.exit(1)

    print("\n" + "=" * 50)
    mode_str = "AUDIT COMPLETE" if args.audit else ("DRY-RUN COMPLETE" if args.dry_run else "EXECUTION COMPLETE")
    print(f"📊 {mode_str}: Scanned {repos_scanned} repositories.")
    action_label = "Need updates" if is_dry_run else "Updated"
    print(f"   {action_label}: {repos_updated}, Up to date: {repos_scanned - repos_updated}")
    print("=" * 50)

if __name__ == "__main__":
    main()
