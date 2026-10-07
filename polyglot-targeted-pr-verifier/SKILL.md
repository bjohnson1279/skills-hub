---
name: polyglot-targeted-pr-verifier
description: >
  Maps modified PR source files to unit/integration test fixtures and executes targeted test runners (Jest --findRelatedTests, PHPUnit, pytest) with pairwise disjointness and static check analysis across polyglot DDD microservices.
---

# Polyglot Targeted PR Verifier

This skill provides fast, delta-focused verification for Pull Requests across polyglot technology stacks (TypeScript, PHP, Python), ensuring incoming code patches are tested without triggering expensive full-suite executions.

---

## When to Use

1. **Targeted Pre-Merge Validation**: Validate PR diffs against corresponding unit test fixtures without running entire monolithic test suites.
2. **Pairwise Disjointness Analysis**: Verify if multiple open PRs modify 100% disjoint file sets, confirming they can be merged concurrently without merge ordering hazards.
3. **Automated Test Target Mapping**: Discover which test files correspond to a set of changed source files across TypeScript/JavaScript, PHP, and Python.

---

## Workflow Procedure

### 1. Map Changed Files to Test Suites
Given a list of modified files, discover the related test files:

```bash
python C:/Users/johns/.gemini/config/skills/polyglot-targeted-pr-verifier/scripts/targeted_verifier.py map-tests \
  --base-dir C:/Users/johns/DEV/inventory/php-ddd-inventory \
  --files "src/Application/Returns/UseCases/ReceiveRMA.php"
```

### 2. Verify PRs with Targeted Test Runners
Inspect open or local PR branches, run related tests, and check pairwise disjointness:

```bash
python C:/Users/johns/.gemini/config/skills/polyglot-targeted-pr-verifier/scripts/targeted_verifier.py verify \
  --pr-list "bjohnson1279/js-ddd-inventory#671,bjohnson1279/php-ddd-inventory#528,bjohnson1279/php-ddd-inventory#527" \
  --base-dir C:/Users/johns/DEV/inventory \
  --output pr_verification_report.json
```

---

## Supported Frameworks & Flags

| Language | Test Framework | Targeted Execution Mode |
| :--- | :--- | :--- |
| **TypeScript / JS** | Jest | `npx jest --findRelatedTests <files> --passWithNoTests --runInBand` |
| **PHP** | PHPUnit | `vendor/bin/phpunit tests/Unit/.../<Fixture>Test.php` |
| **Python** | pytest | `pytest tests/test_<module>.py` |

---

## Command Reference

| Subcommand | Flag | Description |
| :--- | :--- | :--- |
| `map-tests` | `--files` | Comma-separated list of modified files. |
| `map-tests` | `--base-dir` | Local repository path. |
| `map-tests` | `--output` | Optional JSON output path. |
| `verify` | `--pr-list` | Comma-separated list of `OWNER/REPO#PR_NUM`. |
| `verify` | `--base-dir` | Workspace root containing repositories/submodules. |
| `verify` | `--timeout` | Timeout per test suite in seconds (default: 60). |
| `verify` | `--output` | Optional JSON output path. |
