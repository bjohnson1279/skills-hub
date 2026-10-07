---
name: env-security-fallback-harmonizer
description: >
  Audits and harmonizes environment variable configuration fallbacks across security PRs, background worker processes, and E2E test suites to prevent unhandled RuntimeExceptions in testing without compromising production security.
---

# Env Security Fallback Harmonizer

This skill provides automated scanning and harmonization procedures for security fixes that remove hardcoded fallback secrets. It ensures that security enhancements do not break unit, integration, or E2E test suites where `.env` files and production secrets are intentionally omitted.

---

## Automated CLI Audit Tool

Scan an open PR or a local source file for aggressive environment variable removals:

```bash
# Audit an open PR
python C:/Users/johns/.gemini/config/skills/env-security-fallback-harmonizer/scripts/harmonize_env_fallback.py \
  --repo bjohnson1279/js-ddd-inventory \
  --pr 799

# Audit a local file
python C:/Users/johns/.gemini/config/skills/env-security-fallback-harmonizer/scripts/harmonize_env_fallback.py \
  --file C:/Users/johns/DEV/inventory/js-ddd-inventory/src/application/services/AuthService.ts
```

---

## Language-Specific Standard Patterns

### 1. TypeScript / Node.js
```typescript
const JWT_SECRET = process.env.JWT_SECRET || (process.env.NODE_ENV === 'test' ? 'test-jwt-secret' : undefined);
if (!JWT_SECRET) {
  throw new Error('JWT_SECRET environment variable is required for security.');
}
```

### 2. PHP
```php
private static function getSecretKey(): string
{
    $key = getenv('SECRET_KEY') ?: (getenv('APP_ENV') === 'testing' ? 'test-secret-key-12345' : null);
    if (!$key) {
        throw new \RuntimeException('SECRET_KEY environment variable is not set.');
    }
    return $key;
}
```

### 3. Python
```python
secret_key = os.getenv("SECRET_KEY") or ("test-secret-key" if os.getenv("APP_ENV") == "test" else None)
if not secret_key:
    raise ValueError("SECRET_KEY environment variable is required.")
```

### 4. Go
```go
secret := os.Getenv("SECRET_KEY")
if secret == "" && os.Getenv("APP_ENV") == "test" {
    secret = "test-secret-key"
}
if secret == "" {
    return nil, errors.New("SECRET_KEY environment variable is required")
}
```

---

## Test Runner Configuration

### PHPUnit (`phpunit.xml`)
Ensure `phpunit.xml` sets `APP_ENV=testing` inside the `<php>` block:
```xml
    <php>
        <env name="APP_ENV" value="testing"/>
    </php>
```

### Jest / Vitest
In `vitest.config.ts` or `jest.config.ts`:
```typescript
process.env.NODE_ENV = 'test';
```
