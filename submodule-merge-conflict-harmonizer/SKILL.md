---
name: submodule-merge-conflict-harmonizer
description: Audits, resolves, and harmonizes diverged git branches and unmerged conflict paths across parent repositories and nested polyglot submodules.
---

# Submodule Merge Conflict Harmonizer

This skill provides a systematic workflow to audit root repositories and nested submodules, detect committed or unmerged conflict markers (`<<<<<<< HEAD`, `=======`, `>>>>>>>`), reconcile polyglot source and test files, verify syntax & schema drift integrity, and commit clean submodule pointers.

## When to Use

1. A git working directory reports unmerged paths or modified content inside submodules (e.g. `php-ddd-inventory`, `gql-ddd-inventory`, `js-ddd-inventory`, `react-ddd-inventory-client`).
2. Automated PR bots (e.g. Jules, Bolt, Sentinel) or rebase operations merge unresolved conflict markers directly into `main` or `master` tracking branches.
3. Local submodules are checked out on detached PR commits instead of clean tracking branches.

---

## Workflow Steps

### 1. Audit Submodule Tracking Branches & Working Directory Status

Inspect root repository and submodule statuses to locate detached branches or uncommitted changes:

```bash
# Check root repo status
git status

# Verify submodule branch checkouts (ensure main/master tracking branch)
git submodule foreach 'git status'
```

If submodules are checked out on detached bot PR branches (e.g., `bolt-...`, `test/...`), restore clean tracking branches:

```bash
# In each submodule directory:
git checkout main # or master
```

### 2. Search for Leaked Conflict Markers Across All Submodules

Perform explicit grep searches across all source code and test files in each submodule directory:

```bash
# Search for raw merge markers across submodules
grep -rn "<<<<<<<" --include="*.ts" --include="*.tsx" --include="*.php" --include="*.js" --include="*.py" .
```

### 3. Resolve Conflict Markers & Reconcile Test Blocks

Harmonize differences between `HEAD` and incoming branches:
- **Strict Types & Declarations**: Preserve `declare(strict_types=1);`, Prisma models (`@prisma/client`), and namespace imports.
- **Domain Entities & Value Objects**: Ensure property names and constructor signatures match domain interfaces.
- **ORM Repositories**: Verify Prisma/Eloquent `upsert` and `save` calls contain complete `create` and `update` parameters.
- **Unit Test Suites**: 
  - Remove duplicate `describe` / `beforeEach` / `afterEach` blocks created by aborted 3-way merges.
  - Preserve valid assertions from both branches to maintain test coverage.

### 4. Execute Polyglot Verification & Schema Drift Linting

Lint modified files and execute verification commands across all backends before staging:

```bash
# 1. TypeScript syntax check
npx tsc --noEmit # inside each TypeScript submodule

# 2. PHP syntax check
python scripts/check_php_syntax.py # or find src -type f -name "*.php" -exec php -l {} \;

# 3. OpenAPI & GraphQL schema drift check
python scripts/lint_schema_drift.py
```

#### Error Handling & Repair Guidance
- **Sufficient Context**: If TypeScript or PHP linting raises missing imports, implicit `any` types (e.g., `conn: any`), or broken test assertions where the fix is unambiguous, repair them automatically.
- **Ambiguous Failure**: If a test failure points to missing business logic or contradictory requirements across branches, halt and request user clarification before mutating domain logic.

### 5. Stage, Commit Submodule Changes, and Update Parent Pointers

Commit clean files inside each submodule, then stage updated submodule commit pointers in the root repository:

```bash
# Inside each updated submodule:
git add .
git commit -m "fix(<submodule>): resolve merge conflict markers and test suite duplicates"

# In the root repository:
git add <submodule-paths>
git commit -m "fix(ci): update submodule pointers with resolved merge conflict markers across all services"
git status
```

---

## Common Pitfalls

1. **Submodule Detachment**: Forgetting to check out `main` or `master` inside submodules before editing, resulting in commits made to detached HEADs.
2. **Incomplete Upsert Statements**: Deleting `create` blocks when resolving Prisma `upsert` merge conflicts, causing Prisma runtime failures.
3. **Duplicate Test Blocks**: Leaving duplicate `describe(...)` or `beforeEach(...)` blocks in test files, causing Jest or Vitest to fail during collection.
