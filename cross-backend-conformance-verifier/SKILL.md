---
name: cross-backend-conformance-verifier
description: Audits and verifies behavioral parity, API contract equivalence, and JSON payload consistency across GraphQL TypeScript, Express REST, and PHP REST backends.
---

# Cross-Backend Conformance Verifier

This skill runs black-box behavioral scenario checks against all three backend targets (`gql-ddd-inventory` on port 4000, `js-ddd-inventory` on port 5000, and `php-ddd-inventory` on port 8000) to ensure zero API drift.

## Verification Scenarios

1. **Stock Levels & Item Queries**:
   - Compares inventory item query responses between GraphQL, Express REST, and PHP REST.
2. **Lot Quarantine & Recall Traceability**:
   - Asserts that lot status transitions (`QUARANTINED`, `RECALLED`, `ACTIVE`) return identical status fields and traceability structures.
3. **Cross-Docking Evaluation**:
   - Asserts that direct dock-to-dock transfer calculations yield identical recommended quantities across backends.
4. **Domain Error Message Parity**:
   - Asserts that all custom Error string messages in domain entities strictly match their expected testing assertions across GraphQL, Express, and Laravel backends to pass cross-backend conformance tests.
5. **Test Database DDL Schema Parity**:
   - When new domain models or entities are added (e.g. `approval_workflows`, `report_definitions`), ensures corresponding table definitions are mirrored in in-memory test databases (such as `src/Infrastructure/Persistence/sqlite_setup.php` for PHP) to prevent test database `SQLSTATE[HY000]: no such table` or `sqlite_sequence` truncation errors during conformance runs.

## Usage

### 1. Pre-Flight Port & Container Environment Diagnostics
Audit host port availability (4000, 5000, 8000, 8001), detect colliding external containers, and verify Docker daemon readiness prior to running `docker compose`:
```bash
python "C:\Users\johns\.gemini\config\skills\cross-backend-conformance-verifier\scripts\verify_conformance.py" --preflight
```

### 2. Contract Specification Parity Audit
Audit behavioral contract specifications across all active backend services:
```bash
python "C:\Users\johns\.gemini\config\skills\cross-backend-conformance-verifier\scripts\verify_conformance.py" --audit
```

