---
name: db-query-security-auditor
description: Audits database query handlers across TypeScript, PHP, Python, and Go codebases to identify raw string concatenations, unsanitized parameters, and refactor them to use parameterized queries ($1, ? placeholders) or ORM bindings (Prisma, Eloquent, SQLAlchemy, TypeORM).
---

# Database Query Security Auditor

This skill standardizes the audit and refactoring process for identifying raw string concatenations in database query handlers and rewriting them using parameterized queries or ORM bindings.

## Detection Rules & High-Risk Patterns

1. **Raw String Concatenation in SQL Strings**:
   - Template literals or string concatenation directly inserting variables into SQL queries:
     ```typescript
     // UNSAFE:
     const query = `SELECT * FROM users WHERE id = '${userId}'`;
     await pool.query(query);
     ```
   - Unsanitized PHP string interpolation in PDO or Raw DB statements:
     ```php
     // UNSAFE:
     $db->statement("UPDATE inventory SET status = '$status' WHERE id = " . $itemId);
     ```
   - Python format strings in raw cursor operations:
     ```python
     # UNSAFE:
     cursor.execute(f"SELECT * FROM products WHERE sku = '{sku}'")
     ```

2. **Unquoted or Inline Dynamic Filters**:
   - Building SQL `WHERE` clauses dynamically by concatenating string fragments without bound parameter placeholders.

---

## Refactoring Protocols

### 1. PostgreSQL Native Driver (`pg` / `pg-pool`)
Use numbered parameter placeholders (`$1`, `$2`, ...) and pass values as an array parameter:
```typescript
// SECURE:
const query = 'SELECT * FROM inventory_items WHERE sku = $1 AND location_id = $2';
const res = await pool.query(query, [sku, locationId]);
```

### 2. Prisma ORM
Prefer Prisma's fluent query builder, or use tagged template literal `Prisma.sql` for raw queries:
```typescript
// SECURE (Prisma Query Builder):
const item = await prisma.inventoryItem.findFirst({
  where: { sku, locationId }
});

// SECURE (Raw Query with Prisma.sql):
const items = await prisma.$queryRaw(Prisma.sql`SELECT * FROM inventory_items WHERE sku = ${sku}`);
```

### 3. Laravel / PHP Eloquent ORM
Use Eloquent's query builder methods with parameterized bindings:
```php
// SECURE (Eloquent Query Builder):
$totals = DB::table('product_locations')
    ->where('product_id', $productId)
    ->where('location_id', $locationId)
    ->first();

// SECURE (Raw Expression with Bindings):
$results = DB::select('SELECT * FROM inventory_items WHERE sku = ? AND tenant_id = ?', [$sku, $tenantId]);
```

### 4. Python DB-API 2.0 / SQLAlchemy / AsyncPG
Use positional `?` or `%s` placeholders (or `:param` named bindings depending on driver context):
```python
# SECURE (DB-API / sqlite3 / psycopg2):
cursor.execute("SELECT * FROM inventory_items WHERE sku = %s AND location_id = %s", (sku, location_id))

# SECURE (SQLAlchemy text with params):
stmt = text("SELECT * FROM inventory_items WHERE sku = :sku").bindparams(sku=sku)
session.execute(stmt)
```

### 5. Dynamic Schema/Identifier Escaping
For dynamic table names, column names, or database names where bound parameters cannot be used:
- Enforce strict whitelist validation (e.g. `/^[a-zA-Z_][a-zA-Z0-9_]*$/`).
- Use identifier escaping functions such as `pg-format` (`%I` specifier) in Node.js or `PDO::quote` / system escaping helpers.

---

## Verification & Audit Checklist

1. **Grep Search**: Scan the repository for unparameterized raw query calls:
   ```bash
   grep -rnE "`.*SELECT|`.*UPDATE|`.*INSERT|`.*DELETE|SELECT.*\\+|UPDATE.*\\+" src/
   ```
2. **Typecheck & Linting**: Run static typecheck analysis (`tsc --noEmit`, `php -l`, `mypy`) to confirm query handler signatures match expected parameter shapes.
3. **Automated Testing**: Run integration and E2E unit tests to ensure query responses remain identical after refactoring.
