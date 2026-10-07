---
name: ts-test-syntax-fixer
description: Scans TypeScript/Jest test suites for duplicate object literal keys (TS1117), corrupted merge block syntax (TS1005/TS2695), and runs fast tsc typechecking prior to executing heavy test runners.
---

# TypeScript Test Syntax Checker & Fixer

This skill provides generic scripts and workflow instructions to diagnose and fix TypeScript syntax errors, duplicate object literal property keys (`TS1117`), and corrupted block merges across TypeScript Jest test suites.

## Capabilities

1. **Scan for Duplicate Keys (`TS1117`), Type Errors & Mock Leakage**:
   Scans all `.ts` / `.test.ts` files in the repository for object literals with duplicate keys (`TS1117`), missing `.js` extensions in dynamic imports (`TS2835`), persistent spy mock leaks (`jest.spyOn()` without `mockImplementationOnce` or `afterEach` restore), and corrupted merge blocks (`TS1005`/`TS2695`), executing `tsc --noEmit` to report compilation errors prior to running Jest.
   ```bash
   # Scan only
   python "C:\Users\johns\.gemini\config\skills\ts-test-syntax-fixer\scripts\check_ts_test_syntax.py" [project_path]

   # Scan and auto-refactor persistent spy mocks to mockImplementationOnce()
   python "C:\Users\johns\.gemini\config\skills\ts-test-syntax-fixer\scripts\check_ts_test_syntax.py" [project_path] --fix-mock-leaks
   ```

2. **Isolated Jest Suite Execution**:
   Runs Jest targeted specifically at failing test suites without spawning all 90+ test files, preventing memory bloat and worker timeouts.
   ```bash
   npx jest path/to/failing.test.ts
   ```

## Recommended Workflow for TS Test Failures

When Jest test runs fail with TypeScript compilation errors (such as `TS1117`, `TS2835`, `TS2448`, `TS2451`, `TS1005`, `TS2695`):

1. Run `python "C:\Users\johns\.gemini\config\skills\ts-test-syntax-fixer\scripts\check_ts_test_syntax.py"` inside the project directory to locate duplicate object property keys and type errors.
2. Inspect and deduplicate mock object definitions in flagged test files.
3. Check for missing `.js` extensions on relative dynamic imports under Node16 module resolution (`import('./path.js')`).
4. Run `npx jest path/to/target.test.ts` to verify clean compilation and test execution.
