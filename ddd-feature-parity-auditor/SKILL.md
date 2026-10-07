---
name: ddd-feature-parity-auditor
description: Audits business logic and feature parity across multi-backend Domain-Driven Design (DDD) projects (e.g. GraphQL TypeScript, Express REST, Laravel PHP REST). Ensures consistent domain entity models, costing strategies (FIFO/LIFO/WAC/FEFO), unit conversion rules, serial lifecycles, and auto-generates test coverage for parity verification. Activate this skill when adding or auditing features across polyglot or multi-backend DDD repositories.
---

# DDD Feature Parity Auditor

This skill provides step-by-step procedures for auditing, harmonizing, and maintaining feature parity across multi-backend Domain-Driven Design (DDD) projects.

## When to Activate

Activate this skill when:
- Adding a new domain feature or strategy (e.g., FEFO costing, RMA workflows, location bin routing) to one application that needs to be ported to sibling applications.
- Performing periodic code audits to ensure entity models, value objects, and repository contracts remain synchronized.
- Verifying cross-backend API parity across GraphQL schema type definitions, OpenAPI REST specs, and frontend client abstractions.

---

## Audit Workflow

### 1. Domain Layer Comparison
* Compare domain entities across projects:
  - TypeScript: `src/domain/entities/` or `src/domain/<bounded-context>/`
  - PHP: `src/Domain/<BoundedContext>/Entities/`
* Verify value objects (e.g., `Money`, `Sku`, `LocationId`, `CostBreakdown`) preserve equal precision and validation bounds.

### 2. Strategy & Enum Harmonization
* Audit strategy registries (e.g. `CostingStrategyRegistry`):
  - **FIFO**: First-In, First-Out (received date ascending)
  - **LIFO**: Last-In, First-Out (received date descending)
  - **WAC**: Weighted Average Costing
  - **FEFO**: First-Expired, First-Out (expiration date ascending, unexpired fallback)
* Ensure all enum cases (e.g. `CostingMethod`, `SerialStatus`, `ReasonCode`) match case-by-case across languages (`TS enum` vs `PHP 8.1 enum`).

### 3. Repository & Data Mapper Parity
* Check data persistence mappings:
  - Prisma schemas (`schema.prisma`)
  - Eloquent models & PostgreSQL DDL scripts (`01_init.sql`)
  - In-Memory repository implementations for zero-db unit testing.

### 4. Verification & Testing Strategy
* Generate corresponding unit tests for each runtime:
  - TypeScript (Jest): `npx jest tests/domain/`
  - PHP (PHPUnit): `vendor/bin/phpunit tests/Unit/Domain/`
* Ensure edge cases (such as zero quantity remaining, insufficient inventory exceptions, null expiration dates) behave identically.
