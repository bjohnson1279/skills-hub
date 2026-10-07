---
name: apollo-error-sanitizer
description: >
  Audits and hardens GraphQL Apollo Server and Apollo Gateway instances by injecting production-safe formatError handlers that strip internal exceptions, SQL syntax traces, and raw stack traces before errors reach client consumers.
---

# Apollo Error Sanitizer

This skill provides automated auditing and security remediation for GraphQL Apollo Server and Apollo Gateway endpoints, preventing internal error leakage and CWE-209 (Information Exposure Through an Error Message) vulnerabilities.

---

## Diagnostic Checklist

1. **Production Masking**: Ensure `process.env.NODE_ENV === 'production'` checks exist inside `formatError`.
2. **Exception Object Stripping**: Ensure `delete formattedError.extensions.exception` is performed.
3. **Stacktrace Deletion**: Ensure `delete formattedError.extensions.stacktrace` is performed before serializing the GraphQL error payload.

---

## CLI Usage

### Audit GraphQL Files
```bash
python C:/Users/johns/.gemini/config/skills/apollo-error-sanitizer/scripts/sanitize_apollo_errors.py   --path C:/Users/johns/DEV/inventory/gql-ddd-inventory
```

### Auto-Remediate Vulnerable Endpoints
```bash
python C:/Users/johns/.gemini/config/skills/apollo-error-sanitizer/scripts/sanitize_apollo_errors.py   --path C:/Users/johns/DEV/inventory/gql-ddd-inventory   --fix
```
