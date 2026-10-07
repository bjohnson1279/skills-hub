---
name: targeted-post-merge-verifier
description: >
  Maps modified files from merged Pull Requests directly to isolated unit and contract test suites (Vitest, Jest, pytest, PHPUnit) to achieve fast post-merge verification without full monorepo suite timeouts.
---

# Targeted Post-Merge Verifier

## Overview
Executes fast, targeted test suites across polyglot DDD microservices and submodules following batch PR merges. Rather than executing full monorepo end-to-end suites that take 15+ minutes, this tool inspects the modified files in each merged PR and triggers only the related unit test fixtures.

## Dependencies
* `gh` (GitHub CLI authenticated with repository read access)
* `python` 3.8+ or `uv`
* Reference skills: `bot-pr-triage-runner`, `polyglot-targeted-pr-verifier`

## Quick Start

Verify a list of merged PRs against local repositories:

```bash
python C:/Users/johns/.gemini/config/skills/targeted-post-merge-verifier/scripts/post_merge_verifier.py verify \
  --pr-list "bjohnson1279/js-ddd-inventory#793,bjohnson1279/react-ddd-inventory-client#262" \
  --base-dir C:/Users/johns/DEV/inventory \
  --output post_merge_verification.json
```

Or verify directly from a triage audit JSON output:

```bash
python C:/Users/johns/.gemini/config/skills/targeted-post-merge-verifier/scripts/post_merge_verifier.py verify \
  --input-file audited_prs.json \
  --base-dir C:/Users/johns/DEV/inventory \
  --output post_merge_verification.json
```

## Utility Scripts

### `verify`
Inspects modified files per repository and executes the appropriate targeted runner:
- **Vitest**: `npx vitest related <files> --run --no-file-parallelism`
- **Jest**: `npx jest --findRelatedTests <files> --runInBand --passWithNoTests`
- **pytest**: Maps modified modules to `tests/test_*.py` and executes targeted `pytest`
- **PHPUnit**: Maps modified classes to `tests/*Test.php` and executes `vendor/bin/phpunit`

```bash
python scripts/post_merge_verifier.py verify \
  [--pr-list "OWNER/REPO#NUM,..."] \
  [--input-file <path_to_json>] \
  [--base-dir <workspace_root>] \
  [--output <results.json>]
```

## Common Mistakes
1. **Running full test suites post-merge**: Full E2E and integration suites in large DDD repositories can take 15+ minutes or stall on long-running worker processes; always run targeted tests first.
2. **Ignoring Windows test parallelism hazards**: Vitest on Windows can crash or hang with file-level parallelism; the runner automatically injects `--no-file-parallelism` to ensure stable execution.
