---
name: ts-controller-syntax-repairer
description: Detects and fixes TypeScript compilation errors in API controllers, including duplicate variable initializers (TS7022/TS2448/TS2588), corrupted inline type casts (TS1005/TS1472), and malformed ORM client accesses.
---

# TypeScript Controller Syntax Repairer

This skill provides workflow rules and refactoring guidelines to resolve TypeScript compilation errors in Express, Fastify, NestJS, and GraphQL API controllers.

## Common Error Triggers

1. **`TS7022: 'tags' implicitly has type 'any'...` / `TS2448: Block-scoped variable used before declaration`**:
   Occurs when duplicate variable initializers exist in the controller method body (e.g. `const tags = await ...` repeated on consecutive lines).

2. **`TS1005: ':' expected` / `TS1472: 'catch' or 'finally' expected`**:
   Occurs when inline type assertion parenthesization breaks AST parsing in async/await expressions (such as `await (prisma as any).model.findMany(...)`).

3. **`TS2353: Object literal may only specify known properties`**:
   Occurs when Prisma or ORM models are accessed on strict typed clients before dynamic model extensions are recognized by `tsc`.

---

## Refactoring Protocol

### 1. Extract Typed ORM Client Instances
Never invoke inline type assertions directly inside `await` call chains (e.g., avoid `await (prisma as any).model.method(...)`).
Instead, extract a typed database handle at the start of the try-block:
```typescript
// BEFORE (Buggy):
const tags = await (prisma as any).rfidTagModel.findMany({ ... });

// AFTER (Clean):
const db = prisma as any;
const tags = await db.rfidTagModel.findMany({ ... });
```

### 2. Remove Duplicate Variable Initializers
Ensure each variable name (`tags`, `tag`, `result`) is declared exactly once per scope:
```typescript
// BEFORE (Corrupted):
const tags = await prisma.rfidTagModel.findMany({ ... });
const tags = await (prisma as any).rfidTagModel.findMany({ ... });

// AFTER (Fixed):
const db = prisma as any;
const tags = await db.rfidTagModel.findMany({ ... });
```

### 3. Verify Controller Compilation
Validate that the controller file compiles without errors before running full test suites:
```bash
npx tsc --noEmit src/infrastructure/http/controllers/TargetController.ts
```
Or execute the target test suite in isolation:
```bash
npx jest tests/infrastructure/http/TargetE2E.test.ts
```
