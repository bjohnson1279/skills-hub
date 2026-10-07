---
name: php-cli-server-e2e-fixer
description: Diagnoses and repairs PHP built-in dev server (php -S) E2E test failures, duplicate namespace import compile errors, error handler recursion loops, and empty HTTP 500 responses across PHP integration test suites.
---

# PHP CLI Server E2E Fixer

This skill automates the diagnosis and repair of PHP integration and E2E test suite failures where background development servers (`php -S 127.0.0.1:PORT`) return generic `500 Internal Server Error` status codes with empty response bodies (`{"status": 500, "body": ""}`).

---

## 1. Diagnostic Checklist

When PHP integration HTTP tests fail with `500` and empty body `""`:

### A. Duplicate `use` Import Statements (Compile-Time Fatal Error)
- **Symptom**: Server crashes instantly on incoming requests without executing any code. `server.log` shows:
  `PHP Fatal error: Cannot use Namespace\Class as Class because the name is already in use in public/index.php`
- **Cause**: Declaring identical `use` statements at different places in a single router file (e.g. at line 35 and line 95).
- **Fix**: Remove duplicate `use` declarations so each imported symbol is declared exactly once at top level.

### B. Error Handler Recursion in Exception Handling
- **Symptom**: `server.log` shows `Fatal error: Exception thrown without a stack frame in Unknown on line 0`.
- **Cause**: Calling functions like `error_log()` inside `set_exception_handler()` while custom `set_error_handler()` converts warnings into `ErrorException`.
- **Fix**: Add `restore_error_handler();` at the start of `set_exception_handler()` before performing any logging or headers/output operations.

### C. Missing `Throwable` Catching in Route Handlers
- **Symptom**: PHP 7+ `TypeError` or `Error` bypasses `catch (\Exception $e)` and triggers unhandled fatal server crashes.
- **Fix**: Replace `catch (\Exception $e)` with `catch (\Throwable $e)` in router blocks to safely capture all PHP errors and return formatted JSON responses.

### D. Invalid UTF-8 Output in JSON Response Serialization
- **Symptom**: `$response->getContent()` executes `json_encode($body)`. If `$body` contains raw database driver binary bytes or non-UTF8 strings, `json_encode()` returns `false`, causing `echo false;` to print an empty 0-byte string `""` with HTTP status 500.
- **Fix**: Pass `JSON_INVALID_UTF8_SUBSTITUTE | JSON_PARTIAL_OUTPUT_ON_ERROR` to `json_encode()` in HTTP response wrappers and exception handlers.

### E. E2E Test Server Log Diagnostics
- **Fix**: Update E2E test `request()` helper methods to read and attach `server.log` contents to `$result['body']` whenever `$statusCode >= 500` or `$result === ''` or `$decoded === null`.

### F. Health Check Timeouts During Heavy Bootstrapping
- **Symptom**: `httpx.get` or other E2E health probes timeout (e.g., `timeout=2.0s`) while connecting to the PHP server even though the server is running. Log shows delayed `[200]: GET /api/health` 8-10 seconds after connection is accepted.
- **Cause**: The `/api/health` route is defined late in the entrypoint file (`public/index.php`), causing the server to execute heavy database connections, Eloquent bootstrapping, and synchronous queries before responding to the health check.
- **Fix**: Move the health check "fast-path" logic (e.g., `if ($uri === '/api/health')`) to the very top of the entrypoint file, immediately after autoloader and exception handler configuration, so it responds instantly without hitting the database.
