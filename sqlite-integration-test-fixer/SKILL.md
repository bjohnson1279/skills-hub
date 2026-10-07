---
name: sqlite-integration-test-fixer
description: Fixes common SQLite database locking, background worker process collisions, and port assignment issues in PHP/Laravel integration test suites.
---

# SQLite Integration Test Fixer

This skill provides generic scripts and workflow instructions to automatically resolve SQLite table lock contention (`database is locked`), background worker process environment variables, and HTTP server port collisions in integration and E2E test suites.

## Capabilities & Included Scripts

1. **Enable SQLite WAL & Busy Timeout**:
   Configures `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout=10000;` on test database connection bootstraps to prevent lock contention under concurrent process execution.
   ```bash
   python "C:\Users\johns\.gemini\config\skills\sqlite-integration-test-fixer\scripts\add_wal_mode.py"
   ```

2. **Assign Isolated HTTP Test Ports**:
   Assigns unique local ports (8085+) per HTTP E2E test suite class to eliminate background web server port collisions.
   ```bash
   python "C:\Users\johns\.gemini\config\skills\sqlite-integration-test-fixer\scripts\assign_unique_ports.py"
   ```

3. **Isolate Database Connections per E2E Test Suite**:
   Ensures background worker CLI process instances and test classes use isolated Capsule/PDO database instances and unique database files.
   ```bash
   python "C:\Users\johns\.gemini\config\skills\sqlite-integration-test-fixer\scripts\isolate_e2e_databases.py"
   ```

4. **Wrap CLI Worker Process Executions**:
   Wraps `exec()` worker process calls with `DB::disconnect()` and `DB::reconnect()` to prevent SQLite database lock holding during CLI process invocations.
   ```bash
   python "C:\Users\johns\.gemini\config\skills\sqlite-integration-test-fixer\scripts\fix_worker_cmd.py"
   ```

## Recommended Workflow for Test Failures

When integration tests fail due to `SQLSTATE[HY000]: General error: 5 database is locked` or background process execution errors:

1. Run `add_wal_mode.py` to enable WAL mode on database connection initialization.
2. Run `assign_unique_ports.py` to isolate server ports across HTTP test suites.
3. Run `fix_worker_cmd.py` to handle DB connection pooling around CLI worker calls.
4. Run `vendor/bin/phpunit` to verify clean test execution.
