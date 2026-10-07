---
name: memory-repo-parity-harmonizer
description: Audits in-memory multi-tenant repository implementations, seed data deep-copies, query filter evaluations, double-entry GL balance posting, and Express router mounts across polyglot DDD services.
---

# In-Memory Repository & Router Parity Auditor

## Overview
When microservices and DDD applications adopt repository patterns (e.g. separating PostgreSQL production adapters from in-memory testing adapters), in-memory repositories often suffer from architectural drift:
1. **Empty Stub Arrays**: Initializing entities as empty arrays (`[]`) rather than deep-copying baseline seed data from `seedData.ts`.
2. **Ignored Query Filters**: Methods like `getAll(tenantId, filter)` that accept filter parameters but return un-filtered datasets.
3. **Missing Business Logic Parity**: Double-entry journal entry posting omitting account `currentBalance` mutations.
4. **Unmounted Routers**: Scaffolded router files in `src/routes/*.routes.ts` forgotten and omitted from `src/routes/index.ts`.

This skill audits repository implementations and Express router dispatchers to prevent runtime regressions and 404 test failures.

---

## Capabilities

1. **Repository Stub & Seed Data Audit**:
   Detects empty stub arrays (`= []`) in in-memory repository classes and ensures baseline domain models are populated.

2. **Query Filter Evaluation Verification**:
   Flags repository `getAll()` methods that declare `filter` arguments but return un-filtered arrays.

3. **General Ledger Balance Parity**:
   Verifies that in-memory accounting repositories correctly calculate and post double-entry debits/credits to GL account balances.

4. **Express Router Mount Audit**:
   Scans `src/routes/*.routes.ts` against `src/routes/index.ts` to detect unmounted routes before deployment.

---

## Usage

```bash
# 1. Audit in-memory repositories and route mounting in current workspace
python "C:\Users\johns\.gemini\config\skills\memory-repo-parity-harmonizer\scripts\harmonize_memory_repos.py" --project-root .

# 2. Output JSON report for automated CI bot triage runners
python "C:\Users\johns\.gemini\config\skills\memory-repo-parity-harmonizer\scripts\harmonize_memory_repos.py" --project-root . --json
```
