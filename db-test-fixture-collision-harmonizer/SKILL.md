---
name: db-test-fixture-collision-harmonizer
description: >-
  Audits, detects, and harmonizes database unique constraint and enum collisions between test setup seed fixtures (setUp, beforeEach) and test method payloads across polyglot test suites (PHPUnit, Jest, pytest).
---

# Database Test Fixture Collision Harmonizer

## Overview
In multi-tenant Domain-Driven Design (DDD) architectures, integration and unit tests often seed database baseline records during test setup (`setUp()` in PHPUnit/Python or `beforeEach()` in Jest/Vitest). When individual test methods (such as `testCreateWorkflow`, `it('creates a new record')`) reuse identical hardcoded unique attributes (e.g. `(tenant_id, trigger_event)`, `sku`, `email`, `code`), database drivers running against real PostgreSQL or SQLite instances reject insertions with unique constraint violations (e.g. `SQLSTATE[23505]: Unique violation: 7 ERROR: duplicate key value violates unique constraint`).

This skill provides an automated audit and refactoring suite to identify collisions between fixture setups and test method payloads and automatically assign disjoint enum members or unique identifiers.

---

## Quick Start

### 1. Scan a Test File or Suite for Fixture Collisions
```bash
python C:/Users/johns/.gemini/config/skills/db-test-fixture-collision-harmonizer/scripts/fixture_collision_harmonizer.py scan \
  --path C:/Users/johns/DEV/inventory/php-ddd-inventory/tests/Integration/Http/ApprovalControllerTest.php
```

### 2. Export Detailed Collision Audit Report
```bash
python C:/Users/johns/.gemini/config/skills/db-test-fixture-collision-harmonizer/scripts/fixture_collision_harmonizer.py scan \
  --path C:/Users/johns/DEV/inventory/php-ddd-inventory/tests \
  --output fixture_collisions.json
```

### 3. Automatically Harmonize & Repair Collisions
```bash
python C:/Users/johns/.gemini/config/skills/db-test-fixture-collision-harmonizer/scripts/fixture_collision_harmonizer.py repair \
  --path C:/Users/johns/DEV/inventory/php-ddd-inventory/tests/Integration/Http/ApprovalControllerTest.php
```

---

## Supported Ecosystems & Frameworks

| Language | Test Framework | Fixture Scope |
| :--- | :--- | :--- |
| **PHP** | PHPUnit | `setUp()` method array declarations vs `test*()` method requests |
| **TypeScript / JavaScript** | Jest, Vitest, Mocha | `beforeEach()` blocks vs `it()` / `test()` request payloads |
| **Python** | pytest, unittest | `setUp()` / `setup_method()` vs `test_*()` functions |

---

## Candidate Fields Monitored

- `triggerEvent` / `trigger_event`
- `sku` / `product_sku`
- `email` / `username`
- `code` / `slug`
- `serial_number` / `serialNumber`
- `batch_number` / `batchNumber`

---

## Safety Guardrails

1. **Setup Integrity**: The `repair` command modifies only test case method payloads (`testCreate*`, `it(...)`), leaving initial baseline seed data in `setUp()` intact.
2. **Domain Enum Conformity**: Replaces colliding enum values with valid alternative members registered in domain specifications (e.g. replacing colliding `PO_CREATED` with `STOCK_ADJUSTED` or `CYCLE_COUNT_COMPLETED`), preventing downstream schema validation errors.
