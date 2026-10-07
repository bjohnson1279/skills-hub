---
name: multi-tenant-signature-drift-harmonizer
description: Audits polyglot services, PR branches, and test suites for parameter arity drift (missing tenantId) and async Promise call mismatches during architectural multi-tenant migrations.
---

# Multi-Tenant Method Signature Drift Harmonizer

## Overview
During large-scale domain migrations to multi-tenant architectures, service and repository methods often transition:
1. **Arity changes**: From single-tenant `method(payload)` to multi-tenant `method(tenantId, payload)`.
2. **Synchronous to Asynchronous**: From synchronous return types `T` to async `Promise<T>` due to database abstraction layers.

Automated bots (Jules, Sentinel, Dependabot) often open Pull Requests branched from older commits, using outdated single-tenant calling conventions (e.g. `service.createPolicy(payload)` without `tenantId` and without `await`).

This skill scans repository test suites and PR diffs, detects arity and async drift against current service definitions, and auto-harmonizes calling signatures.

---

## Capabilities

1. **Service Method Signature Discovery**:
   Extracts all exported service methods and repository interfaces requiring `tenantId: string` and returning `Promise<T>`.

2. **Test Calling Convention Audit**:
   Detects test fixtures or controller routes invoking multi-tenant methods with missing `tenantId` parameters or missing `await` statements.

3. **Automated Signature Harmonization**:
   Auto-injects test tenant parameters (e.g., `'tenant-001'`) into test fixtures to resolve TypeScript compiler and runtime errors.

---

## Usage

```bash
# 1. Audit repository test suites for signature drift
python "C:\Users\johns\.gemini\config\skills\multi-tenant-signature-drift-harmonizer\scripts\harmonize_signature_drift.py" --project-root .

# 2. Output JSON report for CI/bot triage runners
python "C:\Users\johns\.gemini\config\skills\multi-tenant-signature-drift-harmonizer\scripts\harmonize_signature_drift.py" --project-root . --json

# 3. Auto-fix test fixtures with default tenant ID
python "C:\Users\johns\.gemini\config\skills\multi-tenant-signature-drift-harmonizer\scripts\harmonize_signature_drift.py" --project-root . --fix --tenant-id "'tenant-001'"
```
