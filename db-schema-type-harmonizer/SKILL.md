---
name: db-schema-type-harmonizer
description: Audits and harmonizes database DDL scripts (PostgreSQL and SQLite) to eliminate type casting errors (SQLSTATE[22P02]), foreign key type mismatches, and non-idempotent table creation statements across multi-engine DDD applications.
---

# Database Schema Type Harmonizer

This skill provides step-by-step diagnostic and auditing procedures to harmonize schema definitions across dual database setups (e.g. PostgreSQL production + SQLite integration test environments) in Domain-Driven Design (DDD) projects.

## Common Error Triggers

1. **`SQLSTATE[22P02]: Invalid text representation for type uuid`**:
   Occurs in PostgreSQL when DDLs specify `UUID` primary/foreign keys, but application code or test suites pass arbitrary string identifiers (e.g., `"user-1"`, `"serial-a"`).

2. **Foreign Key Incompatible Type Error**:
   `ERROR: foreign key constraint cannot be implemented - Key columns are of incompatible types: uuid and character varying`.
   Occurs when a primary key (e.g., `journal_entries.id`) is updated to `VARCHAR(100)`, but foreign key tables (e.g., `quickbooks_journal_mappings.journal_entry_id`) remain `UUID`.

3. **`SQLSTATE[42P01]: Undefined table`**:
   Occurs when a feature table (e.g., `rfid_tags`) is present in application code or workers but missing from SQL init scripts (`docker/postgres/init/*.sql`) or test database setup helpers (e.g., `SqliteSetup.php`).

---

## Harmonization Checklist & Workflow

### 1. Audit Primary Key and Foreign Key Data Types
Inspect all `.sql` scripts under `docker/postgres/init/*.sql` and SQLite schema definitions (e.g., `src/Infrastructure/Persistence/sqlite_setup.php`):
- Ensure primary keys support string identifiers by using `VARCHAR(100)` or `VARCHAR(255)` rather than strict `UUID`.
- Use default UUID generators that emit text compatible with string PKs: `VARCHAR(100) PRIMARY KEY DEFAULT gen_random_uuid()`.

### 2. Verify Cross-Table Foreign Key Alignment
For every foreign key constraint (`REFERENCES target_table(target_col)`):
- Verify that both the child FK column and the parent PK column use identical types (`VARCHAR(100)` on both sides).
- Example:
  ```sql
  CREATE TABLE IF NOT EXISTS quickbooks_journal_mappings (
    id               VARCHAR(100) PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_entry_id VARCHAR(100) NOT NULL UNIQUE REFERENCES journal_entries(id) ON DELETE CASCADE,
    ...
  );
  ```

### 3. Ensure Idempotent DDL Execution
- All table creations MUST use `CREATE TABLE IF NOT EXISTS`.
- All index creations MUST use `CREATE INDEX IF NOT EXISTS`.
- All extension statements MUST use `CREATE EXTENSION IF NOT EXISTS`.

### 4. Validate Table Parity Between PostgreSQL and SQLite
Verify that every table defined in PostgreSQL init scripts is also registered in SQLite test schema setup functions (e.g. `SqliteSetup::createSchema()`), ensuring test environments can run integration tests without table missing exceptions.

### 5. Audit ORM Schema Mappings Against Raw SQL
When using explicit `initdb` SQL migrations alongside ORMs like Prisma:
- **Symptom**: `Raw query failed. Code: 42703. Message: column "locationId" does not exist` during raw queries or `$executeRaw`, or `prisma db push` altering hypertable structures unintentionally.
- **Cause**: Prisma defaults to camelCase database columns for camelCase schema fields unless explicitly mapped, conflicting with existing snake_case SQL definitions.
- **Fix**: Verify that all camelCase model fields have explicit column mapping attributes (e.g., `@map("snake_case_col")`). Ensure that any raw SQL queries (like `$executeRaw`) use the mapped database column names (e.g. `location_id`), not the Prisma schema field names.
