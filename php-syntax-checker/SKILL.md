---
name: php-syntax-checker
description: Fast automated PHP linter tool to scan and detect ParseErrors, syntax errors, and unexpected token bugs across PHP codebases.
---

# PHP Syntax Checker

This skill provides a fast linter tool to recursively scan any directory or PHP file for syntax errors, missing brackets, unclosed closures, and unexpected tokens using `php -l`.

## Capabilities

1. **Recursively Lint PHP Codebase**:
   Scans the current repository (or a target directory/file) and checks every `.php` file for syntax errors, excluding vendor and build directories.
   ```bash
   python "C:\Users\johns\.gemini\config\skills\php-syntax-checker\scripts\check_php_syntax.py" [path]
   ```

## Recommended Usage

- Run after resolving git merge conflicts to ensure no corrupted conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) or bad line splices caused PHP `ParseError` exceptions.
- Run prior to executing PHPUnit test suites when test runners crash on loading files.
