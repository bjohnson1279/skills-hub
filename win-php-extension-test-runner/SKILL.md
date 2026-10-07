---
name: win-php-extension-test-runner
description: >
  Configures and executes PHPUnit test suites on Windows environments by dynamically discovering PHP extension directories (WinGet, Chocolatey, XAMPP) and injecting CLI extension flags (-d extension_dir and -d extension=...) for mbstring, pdo_sqlite, and sqlite3.
---

# Windows PHP Extension Test Runner

This skill provides automated discovery and execution patterns for running PHPUnit test suites on Windows hosts where PHP binary extensions (`php_mbstring.dll`, `php_pdo_sqlite.dll`, `php_sqlite3.dll`) exist on disk but are not loaded in the default CLI `php.ini`.

---

## Problem Statement

On Windows development environments (WinGet packages, standalone PHP builds, Chocolatey), running `php vendor/bin/phpunit` often fails with:
- `PHPUnit requires the "mbstring" extension, but the "mbstring" extension is not available.`
- `PDOException: could not find driver` when connecting to SQLite test databases.

Modifying global `php.ini` is often constrained or non-portable across team environments.

---

## Automated Dynamic Runner

Use the built-in runner script which automatically detects the active PHP extension path and executes PHPUnit:

```bash
# Run all unit tests
python C:/Users/johns/.gemini/config/skills/win-php-extension-test-runner/scripts/run_phpunit_win.py   --cwd C:/Users/johns/DEV/inventory/php-ddd-inventory   --no-coverage tests/Unit

# Target a specific test class
python C:/Users/johns/.gemini/config/skills/win-php-extension-test-runner/scripts/run_phpunit_win.py   --cwd C:/Users/johns/DEV/inventory/php-ddd-inventory   tests/Unit/Domain/Compliance/Services/ComplianceLedgerServiceTest.php

# Print discovered extension CLI flags for use in custom commands
python C:/Users/johns/.gemini/config/skills/win-php-extension-test-runner/scripts/run_phpunit_win.py --discover-only
```

---

## Manual Execution Workflow

If formulating manual commands, locate the extension folder and pass `-d` flags:

```powershell
# 1. Locate PHP ext folder
# WinGet: %LOCALAPPDATA%\Microsoft\WinGet\Packages\PHP.PHP.8.1_...\ext

# 2. Formulate runtime PHP command
php -d extension_dir="<ext_path>" -d extension=php_mbstring.dll -d extension=php_pdo_sqlite.dll -d extension=php_sqlite3.dll vendor/bin/phpunit tests/Unit
```
