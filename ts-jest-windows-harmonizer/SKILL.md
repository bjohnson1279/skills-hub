---
name: ts-jest-windows-harmonizer
description: Diagnoses, tunes, and repairs Jest TypeScript test execution errors, ESM module import failures, open handle deadlocks, and ts-jest compilation performance under Node.js on Windows. Activate this skill when fixing failing Jest unit tests, optimizing TDD test runners, or setting up GitHub Actions CI pipelines.
---

# ts-jest Windows Test Harness Harmonizer

This skill provides diagnostic procedures and configuration guidelines for ensuring fast, reliable Jest test execution across TypeScript projects running on Windows environments and in GitHub Actions CI pipelines.

## When to Activate

Activate this skill when:
- Encountering Jest module import errors (`Cannot use import statement outside a module`).
- Debugging slow Jest startup times or worker thread deadlocks under Windows PowerShell/CMD.
- Configuring `jest.config.cjs` and `package.json` for ESM / TypeScript compatibility.
- Setting up GitHub Actions CI workflows (`.github/workflows/ci.yml`).

---

## Configuration Best Practices

### 1. `jest.config.cjs` Configuration
Use `ts-jest` transformation targeting CommonJS for reliable in-memory compilation without VM module experimental warnings:

```javascript
/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
  },
  transform: {
    '^.+\\.tsx?$': [
      'ts-jest',
      {
        useESM: false,
        isolatedModules: true, // Enables sub-second ts-jest compilation
        tsconfig: {
          module: 'commonjs',
          moduleResolution: 'node',
        },
      },
    ],
  },
  testMatch: ['**/tests/**/*.test.ts'],
};
```

### 2. Package Scripts & Node ESM (`"type": "module"`) Execution
When testing TypeScript ESM packages (`"type": "module"`) under Node.js on Windows PowerShell/CMD:
1. **Experimental VM Modules**: Node requires `--experimental-vm-modules` to enable dynamic ES module loading inside Jest.
2. **Worker Deadlock Prevention**: Always pass `--runInBand` (or `-i`) and `--forceExit` when running under Windows subprocesses or background tasks to prevent worker threads from hanging indefinitely during teardown.

```json
"scripts": {
  "build": "tsc",
  "test": "node --experimental-vm-modules node_modules/jest/bin/jest.js --runInBand --forceExit --no-cache",
  "test:import": "tsx src/scripts/testImport.ts"
}
```

CLI direct runner pattern:
```bash
node --experimental-vm-modules node_modules/jest/bin/jest.js --runInBand --forceExit
```

> [!WARNING]
> **npm 7+ Flag Forwarding**: Avoid passing `-- --runInBand` to `npm test` (`npm test -- --runInBand`), which triggers `npm warn Unknown cli config "--runInBand"`. Either invoke the Node command directly as shown above or bake `--runInBand --forceExit` into the `package.json` `"test"` script.

### 3. Vitest on Windows Configuration (`pool: 'threads'` & `singleThread: true`)
When using Vitest in React or TypeScript frontends on Windows environments (e.g. `react-ddd-inventory-client`), two common failure modes occur:
1. **Worker initialization deadlock**: Vitest's default `forks` pool hangs when spawning Node subprocesses.
2. **Threads pool startup timeout**: `[vitest-pool-runner]: Timeout waiting for worker to respond` occurs when multiple thread workers compete during JSDOM initialization under Windows.

Always configure `pool: 'threads'` with `poolOptions.threads.singleThread: true` in `vite.config.ts`:

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    pool: 'threads',
    poolOptions: {
      threads: {
        singleThread: true, // Eliminates worker startup timeouts on Windows
      },
    },
  },
});
```

And in `package.json`:
```json
"scripts": {
  "test:unit": "vitest run",
  "test:unit:watch": "vitest"
}
```

---

### 4. Supertest & Express Middleware Testing
- When testing Express root routes (`GET /`) alongside static file serving (`express.static('public')`), pass explicit Accept headers (`.set('Accept', 'application/json')`) to ensure JSON endpoints respond deterministically in Supertest assertion blocks.

---

### 5. Windows Worker Heap Exhaustion & OOM Scavenge Guard (`--runInBand`)

#### Symptom:
When running Jest test suites containing DOM mocks, JSDOM environments, or browser extension scripts on Windows:
```text
FAIL src/kslCommentsHide.test.ts
  ● Test suite failed to run
    Jest worker ran out of memory and crashed
      at ChildProcessWorker._onExit (node_modules/jest-worker/build/index.js:924:26)
```
Followed by repeated V8 garbage collection logs:
```text
<--- Last few GCs --->
Scavenge (during sweeping) ... allocation failure;
```
And extreme IPC latency where a 5-second test suite takes 75s+ across spawned Node worker processes.

#### Root Cause:
On Windows, Jest's default multi-process worker pool (`jest-worker`) incurs heavy memory and IPC process creation overhead. When multiple worker threads compile TypeScript in parallel while initializing JSDOM/DOM globals, worker memory reaches the default Node heap ceiling, triggering V8 allocation failures.

#### Solution & Best Practices:
1. **Pass `--runInBand` (or `-i`) for CLI Runs**:
   Running in-band executes all test suites sequentially within the primary process, sharing compiled TypeScript artifacts and eliminating worker IPC overhead.
   ```bash
   npx jest --runInBand
   # or
   npm test -- --runInBand
   ```
   *Performance Benchmark*: Drops test execution time from **77s down to 4.9s (15x speedup)** and completely eliminates out-of-memory worker crashes.

2. **Conditional `maxWorkers` in `jest.config.cjs`**:
   To automatically optimize across platforms without requiring manual CLI flags:
   ```javascript
   /** @type {import('ts-jest').JestConfigWithTsJest} */
   module.exports = {
     preset: 'ts-jest',
     testEnvironment: 'jsdom',
     // Limit to 1 worker on Windows to avoid IPC and heap exhaustion
     maxWorkers: process.platform === 'win32' ? 1 : '50%',
     // ...
   };
   ```

### 6. Express / Supertest Open Handle & Worker Force Exit Mitigation

#### Symptom:
After all tests pass, Jest logs:
```text
A worker process has failed to exit gracefully and has been force exited.
This is likely caused by tests leaking due to improper teardown.
Try running with --detectOpenHandles to find leaks. Active timers can also cause this, ensure that .unref() was called on them.
```

#### Remediation Patterns:
1. **Explicit Server Lifecycle in Integration Tests**:
   Avoid instantiating persistent `app.listen()` servers without closing them in `afterAll`:
   ```typescript
   import { Server } from 'http';
   import { app } from '../src/app.js';

   let server: Server;

   beforeAll((done) => {
     server = app.listen(0, done);
   });

   afterAll((done) => {
     server.close(done);
   });
   ```
2. **Timer and Interval Cleanup**:
   Ensure polling or recurring interval timers use `.unref()` or are explicitly cleared with `clearInterval()`.
3. **CLI Flags for CI & Subprocesses**:
   Pass `--detectOpenHandles --forceExit` in package script definitions to prevent CI runner timeouts:
   ```json
   "test": "node --experimental-vm-modules node_modules/jest/bin/jest.js --forceExit --no-cache"
   ```
