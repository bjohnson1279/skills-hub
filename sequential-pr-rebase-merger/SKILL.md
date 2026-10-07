---
name: sequential-pr-rebase-merger
description: >
  Orchestrates safe sequential batch merging of overlapping Pull Requests across polyglot repositories with containerized lockfile rebuilding, adaptive mergeability settling latches, and automated submodule pointer advancement.
---

# Sequential PR Rebase Merger

This skill provides an automated workflow to merge chains of overlapping PRs (e.g. Dependabot bumps, Sentinel bot fixes, Bolt optimizations) where merging the first PR causes subsequent PRs to conflict or become stale.

---

## Key Features

1. **Adaptive Settling Latch (`wait_for_mergeable_settling`)**:
   After force-pushing a rebased PR branch, polls GitHub API (`gh pr view --json mergeable,mergeStateStatus`) with progressive backoff until the mergeability state machine settles to `MERGEABLE`. This prevents transient `GraphQL: Pull Request is not mergeable` or `This branch can't be rebased` errors.

2. **Containerized Lockfile Rebuilding**:
   When sequential PRs touch dependency manifests, automatically resolves lockfile conflicts using isolated Docker containers:
   - Ruby: `ruby:3.3.8-slim bundle lock`
   - PHP: `composer:2 composer update --lock --no-install`
   - Node: `node:20-alpine npm install --package-lock-only`
   - PNPM: `node:20-alpine npx pnpm install --lockfile-only`

3. **Admin Merge Authorization**:
   Uses `--admin` during `gh pr merge` by default so protected branch rules do not block programmatic merges when all CI checks pass.

4. **Automated Submodule Pointer Synchronization**:
   When `--sync-submodules` and `--push-parent` are specified, automatically fast-forwards parent submodule git pointers and commits the update.

5. **Additive Jules Documentation Reconciliation**:
   When sequential PRs generate append conflicts in `.jules/*.md` (e.g. `bolt.md`, `sentinel.md`), automatically extracts branch sections and additively unions entries chronologically without losing optimization learnings or blocking rebase merges.

---

## CLI Usage

```bash
python C:/Users/johns/.gemini/config/skills/sequential-pr-rebase-merger/scripts/rebase_merger.py \
  --pr-list bjohnson1279/gql-ddd-inventory#696,bjohnson1279/gql-ddd-inventory#697 \
  --base-dir C:/Users/johns/DEV \
  --sync-submodules \
  --push-parent
```

### Options:
- `--pr-list`: Comma-separated list of `owner/repo#pr_num`
- `--base-dir`: Local workspace root directory (defaults to `C:/Users/johns/DEV`)
- `--no-admin`: Omit `--admin` flag during `gh pr merge`
- `--sync-submodules`: Advance parent repository submodule pointers
- `--push-parent`: Automatically push updated parent submodule pointers to remote
