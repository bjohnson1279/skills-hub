---
name: polyglot-submodule-isolated-typecheck-harmonizer
description: >
  Audits, detects, and fixes isolated submodule boundary violations, including relative import breakouts outside submodule rootDirs, missing package.json dependencies in child repositories, and un-emitted TypeScript compilation errors across polyglot microservice architectures.
---

# Polyglot Submodule Isolated Typecheck Harmonizer

This skill prevents and repairs compilation failures when submodules in a multi-repo / submodule architecture break their isolation boundaries or lack local package dependencies.

---

## When to Use

1. **Submodule RootDir Breakouts (`TS6059` / `TS2307`)**:
   - TypeScript code inside a submodule imports files outside its root directory (e.g., `import ... from '../../../../shared/src/api/...'` or `../../../../../shared/...`).
   - TypeScript flags: `error TS6059: File '...' is not under 'rootDir' '...'. 'rootDir' is expected to contain all source files.` or `error TS2307: Cannot find module '...'`.
2. **Missing Dependencies in Child Submodules**:
   - A feature ported from one submodule (e.g., `js-ddd-inventory`) to another (e.g., `gql-ddd-inventory`) references packages (`exceljs`, `pdfkit`, `fast-csv`) that exist in the source submodule but are missing in the target's `package.json`.
3. **Pre-commit / Pre-push Isolated Typecheck**:
   - Running fast, non-emitting TypeScript validation in each submodule (`npx tsc --noEmit`) to ensure portability when cloned independently in CI.

---

## Architectural Rules for Submodule Portability

> [!IMPORTANT]
> **Submodules Must Be Self-Contained**: Every git submodule must compile and pass tests in complete isolation without assuming the existence of parent directories or sibling submodules.

1. **Localize Shared Type Definitions**:
   - If submodules need common interfaces (such as `BaseChannelAdapter`, `ExternalMapping`), place them in a local path within the submodule (e.g., `<submodule>/src/application/integrations/types.ts` or `<submodule>/shared/src/api/integrations/types.ts`).
   - Never use relative imports that navigate above the submodule root (i.e., paths containing `../` that ascend higher than the submodule's top-level folder).

2. **Audit Imported Modules in `package.json`**:
   - Before committing newly ported services or controllers, check all imported npm modules against `dependencies` and `devDependencies` in `package.json`.
   - If an external library is imported, either add it via `npm install / pnpm add` or provide an internal mock / lightweight native implementation.

---

## Verification Workflow

Run isolated typechecks across all TypeScript submodules:

```powershell
# Check js-ddd-inventory
cd C:/Users/johns/DEV/inventory/js-ddd-inventory
npx tsc --noEmit

# Check gql-ddd-inventory
cd C:/Users/johns/DEV/inventory/gql-ddd-inventory
npx tsc --noEmit
```

---

## Automated Audit Script

Use the helper script to detect directory breakouts and missing package dependencies:

```bash
python C:/Users/johns/.gemini/config/skills/polyglot-submodule-isolated-typecheck-harmonizer/scripts/audit_submodule_boundaries.py --repo-dir C:/Users/johns/DEV/inventory
```
