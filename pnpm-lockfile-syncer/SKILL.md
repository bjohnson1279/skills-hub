---
name: pnpm-lockfile-syncer
description: Automatically fixes pnpm lockfile specifier mismatches (ERR_PNPM_OUTDATED_LOCKFILE), missing dependency resolutions (ERR_PNPM_LOCKFILE_MISSING_DEPENDENCY), and duplicate YAML keys (ERR_PNPM_BROKEN_LOCKFILE) across pnpm projects.
---

# pnpm Lockfile Syncer & Repairer

This skill provides step-by-step diagnostic and remediation procedures for fixing corrupted or desynchronized `pnpm-lock.yaml` files in Node.js and TypeScript projects running `pnpm install --frozen-lockfile` in CI/CD pipelines.

## Common Diagnostic Error Codes

1. **`ERR_PNPM_OUTDATED_LOCKFILE`**:
   Occurs when `package.json` contains dependencies that are missing from or inconsistent with `importers: . : dependencies:` in `pnpm-lock.yaml`.

2. **`ERR_PNPM_LOCKFILE_MISSING_DEPENDENCY`**:
   Occurs when `importers` in `pnpm-lock.yaml` references a package version without matching resolution metadata in the `packages:` or `snapshots:` sections.

3. **`ERR_PNPM_BROKEN_LOCKFILE`**:
   Occurs when `pnpm-lock.yaml` contains duplicate YAML keys (e.g., multiple `specifier:` entries under the same package block) resulting from improper git merge conflict resolution.

4. **`ERR_PNPM_IGNORED_BUILDS`**:
   Occurs in pnpm (v9+) when dependencies with build scripts (e.g., `esbuild`, `node-gyp`, `@swc/core`) are blocked by default until explicitly approved.
   Example error: `[ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: esbuild@0.28.2. Run "pnpm approve-builds" to pick which dependencies should be allowed to run scripts.`

---

## Step-by-Step Resolution Workflow

### 1. Audit Dependency Usage
Inspect source files (`src/**/*.ts`, `src/**/*.js`) to verify whether any flagged mismatched packages are actually imported.
- If a dependency (e.g., `@apollo/gateway` or `mqtt`) is **unused in source code**, remove it from `package.json`.

### 2. Harmonize `package.json` and `pnpm-lock.yaml`
Ensure `importers: . : dependencies:` in `pnpm-lock.yaml` matches `package.json` 1:1:
- Remove specifiers for unused packages from `pnpm-lock.yaml`.
- For duplicate YAML mapping keys (such as `duplicated mapping key (13:9)`), delete the redundant `specifier:` lines or restore the clean lockfile from `main`/`master`:
  ```bash
  git checkout origin/main -- pnpm-lock.yaml package.json
  ```

### 3. Handle `ERR_PNPM_IGNORED_BUILDS`
When encountering unapproved build scripts during installs or test runner executions:
- **Option A (Persistent Configuration)**: Add `onlyBuiltDependencies` to `package.json`:
  ```json
  "pnpm": {
    "onlyBuiltDependencies": [
      "esbuild"
    ]
  }
  ```
- **Option B (CLI Approval)**: Run `pnpm approve-builds` interactively or pass flags in CI environments:
  ```bash
  pnpm approve-builds
  ```
- **Option C (Direct Runner Fallback)**: For test runner execution when package scripts trigger install checks, run jest directly using `node`:
  ```bash
  node --experimental-vm-modules node_modules/jest/bin/jest.js --no-cache
  ```

### 4. Verify Frozen Lockfile Validation
Validate that `pnpm install --frozen-lockfile` completes with zero errors:
```bash
npx pnpm install --frozen-lockfile
```

