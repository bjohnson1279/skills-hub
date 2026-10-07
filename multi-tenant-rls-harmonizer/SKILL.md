---
name: multi-tenant-rls-harmonizer
description: Audits and harmonizes PostgreSQL Row-Level Security (RLS) policies, Prisma multi-tenant models, Eloquent tenant scope traits, and JWT tenant claim validation across multi-tenant DDD applications. Activate this skill when modifying multi-tenant database schemas, RLS policies, or authentication middleware.
---

# Multi-Tenant RLS Harmonizer

This skill ensures robust multi-tenant data isolation across PostgreSQL Row-Level Security (RLS) policies, Prisma ORM models, Eloquent traits, and JWT token authorization headers.

## When to Activate

Activate this skill when:
- Creating new database tables or DDL migrations to ensure `tenant_id` columns and RLS policies are applied.
- Adding API endpoints or GraphQL resolvers to verify cross-tenant access prevention.
- Auditing multi-tenant row isolation across PostgreSQL database scripts (`01_init.sql`).

---

## Best Practices & Guidelines

### 1. Database Level (PostgreSQL RLS)
* Enable Row Level Security: `ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;`
* Create tenant policy:
  ```sql
  CREATE POLICY tenant_isolation_policy ON <table_name>
    USING (tenant_id = current_setting('app.current_tenant_id', true));
  ```

### 2. Application Context & JWT Claims
* Extract `tenantId` from JWT claim or `X-Tenant-Id` HTTP header.
* Enforce cross-tenant access check in resolvers/controllers:
  - Reject requests where `context.auth.tenantId !== request.tenantId`.

### 3. Role-Based Access Control (RBAC)
* Support standard enterprise roles:
  1. `admin`: Full administrative access.
  2. `warehouse_operator`: Operational scanning, Receiving/Dispatch, Assembly, Serial tracking.
  3. `accountant`: Onboarding sheets, General Ledger entries, Valuation reports.
  4. `viewer`: Read-only catalog and inventory metrics.
