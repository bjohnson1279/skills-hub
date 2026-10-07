---
name: polyglot-pr-batch-merger
description: >
  Automates triage, sequential base synchronization, lockfile conflict auto-resolution, and admin merging across multi-technology DDD repositories (TypeScript, Node/Prisma, PHP/Laravel, React/Vite, Python/FastAPI).
---

# Polyglot PR Batch Merger

This skill provides an end-to-end automated CLI tool to discover, triage, categorize, base-synchronize, and batch-merge open Pull Requests across polyglot microservice repositories.

---

## Capabilities & Architecture

- **Parallel Triage**: Categorizes open PRs into:
  - **Group A**: Safe & High Value (CI passed, non-destructive code, test, security, or performance changes).
  - **Group B**: Destructive / Polluted (Fails CI, contains uncleaned scratch verification files, or deletes >15 lines from critical schemas/entrypoints).
  - **Group C**: Zero-Diff / Documentation Only (Contains zero source code diffs).
- **Sequential Base Syncing**: Sequentially syncs `origin/<base>` into feature branch heads prior to merging, preventing GitHub merge conflicts when base branches update mid-batch.
- **Lockfile Auto-Resolution & Additive Jules Log Unioning**: Automatically checks out `origin/<base>` copies of `package-lock.json`, `composer.lock`, `package.json`, `pnpm-lock.yaml`, `mix.lock`, and dynamically unions all timestamped entries in `.jules/*.md` and `.Jules/*.md`.
- **Protected Branch Fallback**: Uses `--admin` privilege flags (`gh pr merge --admin --merge --delete-branch`) to merge approved PRs through branch protection policies seamlessly.

---

## Command Quick Start

### 1. Triage Open Pull Requests
```bash
python C:/Users/johns/.gemini/config/skills/polyglot-pr-batch-merger/scripts/batch_merger.py triage --owner bjohnson1279 --limit 100 --output triaged_prs.json
```

### 2. Execute Pre-Merge Batch Compatibility Testing (Optional but Recommended)
Before executing sequential base-syncs and direct branch merging, verify logical compatibility of all Group A PRs:
```bash
git checkout -b test/combine-prs-batch master
# Iteratively merge all Group A remote branches
git merge origin/<branch-1> origin/<branch-2> ...
# Run the local test suite to ensure no overlapping logic regressions
docker compose run --rm app mix precommit # (or equivalent test runner)
```

### 3. Execute Batch Closures and Base-Synced Merges
```bash
python C:/Users/johns/.gemini/config/skills/polyglot-pr-batch-merger/scripts/batch_merger.py execute --input-file triaged_prs.json --base-dir C:/Users/johns/DEV/inventory
```

---

## Common Mistakes to Avoid

1. **Skipping Base Sync**: Merging 10+ PRs in a single repo without checking out and pulling `origin/<base>` into each feature branch will cause subsequent PR merges to fail with `merge commit cannot be cleanly created`.
2. **Missing `--admin` Flag**: Merging into protected branches without `--admin` results in `the base branch policy prohibits the merge`.
3. **Ignoring Lockfile Collisions**: Failing to stage lockfiles during base sync causes git merge state to stall.
4. **Phantom Case-Sensitivity Changes**: On Windows, case-insensitivity (e.g. `.jules` vs `.Jules`) can cause phantom unstaged changes that block checking out branches or rebasing. The `execute` script now defensively runs `git restore .` before rebasing to mitigate this.
