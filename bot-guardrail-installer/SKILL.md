---
name: bot-guardrail-installer
description: Installs automated CI bot guardrails (bot-guard.yml) and hardens .jules/*.md directive files across polyglot repositories to auto-reject zero-diff hallucinatory PRs, full-file overwrites, syntax errors, and scratch file commits.
---

# Bot Guardrail Installer

This skill provides an automated CLI to scan and install `.github/workflows/bot-guard.yml`, hardened `.jules/*.md` directive files, and `.gitignore` safety entries across polyglot repositories.

## Purpose & Enforcement Gates

Automated coding bots (Jules, Sentinel, Bolt, Palette, Dependabot) can introduce subtle regressions or premature completions when CI lacks targeted feedback:
1. **Zero-Diff & Journal-Only PRs**: Opening PRs when no functional code changes were required, or opening PRs that only add `.jules/*.md` journal logs without accompanying code changes or tests.
   - *Exemption*: Dependency update bots (`dependabot`, `dependabot[bot]`) modifying `package.json` or dependency lockfiles (`pnpm-lock.yaml`, `composer.lock`, etc.) are explicitly exempted from zero-diff code gates.
2. **Conflict Markers & Syntax Errors**: Committing Git conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`) or invalid shell/script syntax into production files.
   - *Regex Standard*: Must use character count repetition `^\+\s*(<{7}|={7}|>{7}|\|{7})`. Never use backslashed brackets (`\<` or `\>`), as GNU grep treats these as zero-width word-boundary assertions (`\b`), causing every added line of code starting with a word to falsely fail CI.
3. **Destructive Schema Deletions**: Truncating or deleting large sections (>15 lines) of DDL SQL schemas, Prisma models, or routing tables.
4. **Missing Parameter Validation & Implicit Any**: Adding or changing routes without attaching parameter schemas (e.g. `z.string().uuid()`), or introducing TypeScript `TS7006` implicit `any` parameter types.
5. **In-Memory Query Antipatterns**: Adding in-memory array filtering instead of proper database indexing.
6. **Scratch Files**: Leaving temporary verification scripts (`test.js`, `test_*.ts`, `test.cjs`, `fix_*.cjs`, `fix_*.php`, `patch_*.py`) in the repository index.
7. **CI Workflow Tampering**: Modifying `.github/workflows/**` to weaken checks (`|| true`, `continue-on-error: true`, or commented assertions).
8. **UI Scope Verification**: Binding undeclared variables (`disabled={loading}`, `aria-busy={loading}`) without verifying their existence in component scope, causing `TS2304` errors.
9. **Whole-File Reformatting**: Running unconfigured formatters across entire files (1,000+ lines of stylistic diff) rather than surgical AST/range-scoped edits.
10. **Windows UTF-8 Shell Execution**: Encoding stdout/stderr safely to avoid Python cp1252 charmap crashes when processing bot emoji headers (`⚡`, `💡`, `📊`).

This skill deploys automated CI checks and in-repo directives to stop these failure modes at PR creation time.

## CLI Usage

```bash
# Audit repositories for outdated guardrails or false-positive risks without modifying files
python "C:\Users\johns\.gemini\config\skills\bot-guardrail-installer\scripts\install_guardrails.py" \
  --all-in-base "C:\Users\johns\DEV" \
  --audit

# Scan and install/upgrade guardrails for a single repository (dry-run)
python "C:\Users\johns\.gemini\config\skills\bot-guardrail-installer\scripts\install_guardrails.py" \
  --target-dir "C:\Users\johns\DEV\ruby-crm" \
  --dry-run

# Install/upgrade across all repositories and submodules in base directory
python "C:\Users\johns\.gemini\config\skills\bot-guardrail-installer\scripts\install_guardrails.py" \
  --all-in-base "C:\Users\johns\DEV"

# Install, commit, and push guardrails to default branch
python "C:\Users\johns\.gemini\config\skills\bot-guardrail-installer\scripts\install_guardrails.py" \
  --all-in-base "C:\Users\johns\DEV" \
  --commit-and-push
```

## Common Traps & False Positives Avoided

- **GNU Grep `\<` and `\>` Word Boundary Bug**: Escaping angle brackets in GNU grep (`\<` or `\>`) changes them from literal characters to word-start / word-end anchors. In diffs, lines starting with `+const`, `+  for`, `+    public`, or `+id=` matched `\<\<\<\<\<\<\<` as 7 consecutive zero-width assertions. Always enforce `(<{7}|={7}|>{7}|\|{7})`.
- **Dependabot Empty Diff False Positives**: Filtering lockfiles from PR diffs must only apply to refactoring bots (Bolt, Jules, Sentinel). Dependabot exclusively modifies manifests and lockfiles and must be bypassed on zero-diff checks.
- **Test Suite Path False Positives & Shell Scratch Omission**: Scratch verification rules (`test_*.py`, `test_*.ts`) must filter out recognized test directories (`tests/`, `test/`, `__tests__/`) and scope checks to newly added files (`--diff-filter=A`) to prevent breaking tracked test suites (e.g. `app/test_sidecar.py`). Patterns must also explicitly include `.sh`, `.bash`, and `plan.md` to catch automated bot exploratory scripts.
- **Deleted File False Positives on Scratch Scanner (`--diff-filter=d`)**: When PRs legitimately delete legacy scratch or test verification files already in `main`, `git diff --name-only` includes deleted files in its output, falsely triggering scratch file rejection rules. Always pass `--diff-filter=d` so deletions of old scratch scripts pass CI cleanly.
- **Vitest Timestamp Artifacts**: Vitest creates transient `*.timestamp-*.mjs` files on abnormal process interruption. Ignore these via `.gitignore` to prevent spurious diff errors.

