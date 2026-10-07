---
name: sentinel-bot-syntax-auditor
description: Audits and repairs broken PHP syntax, unexpected token errors, and unclosed control blocks introduced by automated security bot PRs (Sentinel, Dependabot, CodeQL) when replacing hardcoded fallback secrets.
---

# Sentinel Bot Syntax Auditor

This skill provides automated detection and repair procedures for automated security bot PRs (Sentinel, Dependabot, CodeQL) that attempt to replace hardcoded fallback secrets with `throw new \RuntimeException(...)`, but introduce syntax errors or corrupted control flow blocks.

---

## Common Bot Regressions

Automated security bots often generate AST diffs or regular expression replacements that create:
1. **Unclosed `if` Statements**: Duplicating `if (getenv('APP_ENV') === 'testing') {` without a matching closing brace `}`.
2. **`ParseError: syntax error, unexpected token "public"`**: Unclosed method bodies cause PHP to encounter subsequent visibility modifiers while still inside a function scope.
3. **Broken Exception Assertions**: Unit tests assertion failures when `ParseError` is thrown instead of the expected `RuntimeException`.

---

## Audit & Repair Procedure

### 1. Fast Syntax Linting
Run PHP CLI linter across modified domain files:

```bash
php -l src/Domain/Compliance/Services/ComplianceLedgerService.php
```

If corrupted, output will report: `Parse error: syntax error, unexpected token "public" in ... on line X`.

### 2. Standardized Control Flow Pattern
Harmonize the secret key getter logic using clean brace structure and environment checks:

```php
private static function getPrivateKey(): string
{
    $key = getenv('COMPLIANCE_PRIVATE_KEY') ?: getenv('COMPLIANCE_KEY');
    if (!$key || empty(trim($key))) {
        $env = getenv('APP_ENV');
        if ($env === 'testing' || !$env || $env === 'development') {
            return 'compliance-fallback-secret-key-12345!@#';
        }
        throw new \RuntimeException('Compliance private key environment variable is not set.');
    }
    return $key;
}
```

### 3. Verify Unit Exception Test Coverage
Ensure tests asserting production exceptions wrap environment mutations in `try...finally`:

```php
public function testExceptionIsThrownWhenPrivateKeyIsNotSet()
{
    putenv('COMPLIANCE_PRIVATE_KEY=');
    putenv('APP_ENV=production');

    try {
        $this->expectException(\RuntimeException::class);
        Service::getPrivateKey();
    } finally {
        putenv('APP_ENV=testing');
    }
}
```
## Dependencies
- **exact-merge-conflict-resolver**: When auditing and replacing broken syntax caused by Sentinel PRs (like broken config blocks), use `uv run python C:\Users\johns\.gemini\config\skills\exact-merge-conflict-resolver\scripts\conflict-splicer.py splice` to accurately replace corrupted code without relying on fuzzy find-and-replace tools.
