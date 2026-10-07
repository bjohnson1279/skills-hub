---
name: pr-destructive-diff-auditor
description: >
  Audits open Pull Requests for automated bot regressions, destructive schema deletions, root scratch verification scripts (*.cjs, fix_*.php, update_*.php), deleted test suites, and corrupted TypeScript/PHP syntax prior to merging, with automated collateral diff restoration.
---

# PR Destructive Diff Auditor

This skill provides automated inspection procedures to audit open Pull Requests across polyglot repositories, identifying destructive bot regressions, accidental file deletions, root scratch artifact pollution, and broken syntax. It also provides automated repair mechanisms to salvage valid bot PRs that accidentally introduce collateral deletions into shared files (e.g. `src/api/graphql.ts`, `schema.prisma`).

---

## Automated CLI Audit & Repair Tools

### 1. Audit Open PR

```bash
# Human-readable report
python C:/Users/johns/.gemini/config/skills/pr-destructive-diff-auditor/scripts/audit_pr_destructive.py \
  --repo bjohnson1279/react-ddd-inventory-client \
  --pr 270

# JSON machine-readable output for pipeline integration
python C:/Users/johns/.gemini/config/skills/pr-destructive-diff-auditor/scripts/audit_pr_destructive.py \
  --repo bjohnson1279/react-ddd-inventory-client \
  --pr 270 \
  --json
```

### 2. Auto-Repair Salvageable PRs & Scratch Pruning
When a PR contains valid functional changes (e.g., accessibility fixes or component optimizations) but inadvertently commits temporary exploratory scripts (`plan.md`, `test_*.sh`, `test*.cjs`) or deletes declarations in collateral files due to an outdated branch base, run:

```bash
python C:/Users/johns/.gemini/config/skills/pr-destructive-diff-auditor/scripts/audit_pr_destructive.py \
  --repo bjohnson1279/react-ddd-inventory-client \
  --pr 270 \
  --prune-scratch
```

### 3. Standalone Collateral File Restoration

```bash
python C:/Users/johns/.gemini/config/skills/pr-destructive-diff-auditor/scripts/restore_collateral.py \
  --repo bjohnson1279/react-ddd-inventory-client \
  --pr 270 \
  --files src/api/graphql.ts
```

---

## Diagnostic Checkpoints

### 1. Root Scratch & Benchmark Script Pollution
Automated bots often commit exploratory or verification files into root directories. Flag for cleanup/removal if diff contains:
- `test*.cjs` / `test_reduce.cjs` / `test.cjs`
- `fix_*.php` / `update_*.php` / `fix_*.cjs`
- `scratch_*.py` / `temp_*.js`

### 2. Destructive Entrypoint & Schema Deletions
Flag as destructive if a PR introduces >15 line deletions with <5 additions in core architecture files:
- Schemas & DDL: `schema.prisma`, `init.sql`, `schema.sql`, `types.ts`
- API Adapters: `graphql.ts`, `api.ts`, `client.ts`, `endpoints.ts`
- Core Entrypoints: `index.ts`, `index.php`, `server.ts`, `app.ts`, `main.py`, `routes.php`

### 3. Lockfile & Test Suite Deletions
- Complete deletion of `pnpm-lock.yaml`, `package-lock.json`, `composer.lock`, or `mix.lock`.
- Deletion or hollow replacement of test fixtures under `tests/`.

### 4. Zero Functional Diff / Superseded Tasks
- PRs with 0 code changes outside `.jules/` agent notes or scratch files.
- PRs whose changes have already been merged into `main`/`master` via duplicate sibling tasks.
