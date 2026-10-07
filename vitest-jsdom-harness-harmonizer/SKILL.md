---
name: vitest-jsdom-harness-harmonizer
description: >
  Audits, diagnoses, and harmonizes Vitest and JSDOM test harness configurations across React/Vite TypeScript applications. Automatically injects robust window.localStorage, window.sessionStorage, and global fetch mocks into setup files, resolves deprecated poolOptions configurations in vitest.config.ts, configures Windows-safe file parallelism, and modernizes Vite/Vitest dependencies to resolve security advisories.
---

# Vitest JSDOM Harness Harmonizer

This skill provides an automated diagnosis and repair mechanism for Vitest + JSDOM test harness configurations in React and TypeScript frontends.

---

## Capabilities

1. **Storage API Mocking**: Injects full in-memory `window.localStorage` and `window.sessionStorage` mock objects into test setup files (`setup.ts` / `setupTests.ts`), eliminating `TypeError: Cannot read properties of undefined (reading 'getItem')` on component mount and hook initialization.
2. **Worker Pool Harmonization (Vitest 4+)**: Automatically migrates deprecated `test.poolOptions` blocks using brace-balanced AST-safe replacement to top-level `pool: 'forks'`, preventing worker thread deadlocks, syntax errors, and timeouts under Node.js on Windows hosts.
3. **Windows Worker File-Parallelism Safety**: For Vitest 4+ environments on Windows, automatically configures `fileParallelism: false` or passes `--no-file-parallelism` to eliminate `[vitest-pool-runner]: Timeout waiting for worker to respond` deadlocks.
4. **Build Scope Harmonization (`tsconfig.json`)**: Automatically audits and updates `tsconfig.json` to exclude test files (`src/**/*.test.ts`, `src/**/*.test.tsx`, `tests`), preventing `npm run build` (`tsc && vite build`) failures when test-only imports or mocks are placed in `src/`.
5. **Atomic Vite & Vitest Upgrades (`--upgrade-v4`)**: Safely bumps `vite` (v8+) and `vitest` (v4+) to resolve critical Vite DOM clobbering advisories (CVE-2026-47429) and deprecation warnings in lockfiles and package manifests.

---

## CLI Usage

Run the harmonizer script against any frontend workspace directory:

```bash
# Basic harmonization (mock storage, migrate poolOptions, clean tsconfig)
python C:/Users/johns/.gemini/config/skills/vitest-jsdom-harness-harmonizer/scripts/harmonize_vitest.py \
  --dir C:/Users/johns/DEV/inventory/react-ddd-inventory-client

# Full stack harmonization + atomic upgrade to Vitest 4 / Vite 8:
python C:/Users/johns/.gemini/config/skills/vitest-jsdom-harness-harmonizer/scripts/harmonize_vitest.py \
  --dir C:/Users/johns/DEV/inventory/react-ddd-inventory-client \
  --upgrade-v4

# Immediate Windows CLI Workaround (prior to harmonizing vitest.config.ts):
npx vitest run --no-file-parallelism src/components/ProcurementPanel.test.tsx
```
