---
name: bot-pr-zero-diff-and-scratch-cleaner
description: >-
  Audits open Pull Requests across repositories to identify zero-diff (already incorporated/superseded) and scratch-only bot PRs, providing automated batch closure with polite GitHub audit explanations and branch pruning.
---

# Bot PR Zero-Diff & Scratch Cleaner

## Overview
Automated development agents (such as Jules, Bolt, Sentinel, and Dependabot) frequently create Pull Requests that become redundant:
1. **Zero-Diff PRs**: A sibling PR, manual merge, or base rebase incorporated the exact same changes onto the target default branch, leaving 0 functional lines of diff between `origin/<base>` and `origin/<head>` (excluding documentation notes).
2. **Scratch-Only PRs**: An exploratory run committed temporary test or benchmark files to the repository root (e.g., `test_postgres_approval.php`, `fix_cache.php`, `test_reduce.cjs`) without providing core application changes or automated unit tests.

This skill provides an automated audit and batch-cleaning workflow to identify these PRs across single repositories or full multi-submodule monorepo workspaces and close them cleanly with descriptive GitHub comments and remote branch deletion.

---

## Quick Start

### 1. Audit Open PRs Across a Multi-Submodule Workspace
```bash
python C:/Users/johns/.gemini/config/skills/bot-pr-zero-diff-and-scratch-cleaner/scripts/pr_cleaner.py audit \
  --workspace C:/Users/johns/DEV/inventory \
  --output audit_report.json
```

### 2. Audit a Single Repository
```bash
python C:/Users/johns/.gemini/config/skills/bot-pr-zero-diff-and-scratch-cleaner/scripts/pr_cleaner.py audit \
  --repo bjohnson1279/python-ddd-inventory \
  --local-dir C:/Users/johns/DEV/inventory/python-ddd-inventory
```

### 3. Dry-Run Preview of Closures
```bash
python C:/Users/johns/.gemini/config/skills/bot-pr-zero-diff-and-scratch-cleaner/scripts/pr_cleaner.py close \
  --workspace C:/Users/johns/DEV/inventory \
  --dry-run
```

### 4. Execute Batch Closure with Branch Pruning
```bash
python C:/Users/johns/.gemini/config/skills/bot-pr-zero-diff-and-scratch-cleaner/scripts/pr_cleaner.py close \
  --workspace C:/Users/johns/DEV/inventory
```

---

## Categorization Standards

| Category | Criteria | Resolution Action |
| :--- | :--- | :--- |
| **`ZERO_DIFF`** | Net code diff against current upstream default branch is 0 files (or only `.jules/*.md`). | Closes with explanation that changes are already incorporated into upstream branch, plus `--delete-branch`. |
| **`SCRATCH_ONLY`** | Diff consists solely of root-level verification/diagnostic scripts (`test_*.php`, `fix_*.php`, `test*.cjs`, `scratch_*.py`). | Rejects with notification regarding repository clean-code and scratch guardrails, plus `--delete-branch`. |
| **`VALID`** | Modifies core application code files, unit tests, or domain logic. | Preserved for effectiveness evaluation and review. |

---

## Safety Guardrails

1. **Dry-Run Confirmation**: Always supports `--dry-run` to preview candidate closures prior to invoking `gh pr close`.
2. **Learning Preservation**: Diff evaluations exclude `.jules/*.md` files so documentation entries can be reconciled before closure.
3. **Branch Pruning**: Automatically passes `--delete-branch` to prevent remote git repository clutter.
