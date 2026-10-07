---
name: openapi-spec-auto-generator
description: Auto-generates OpenAPI 3.1 YAML specifications from Express.js routes, PHP dispatch tables, and canonical TypeScript interfaces.
---

# OpenAPI Spec Auto-Generator

This skill provides instructions and tools for automatically generating OpenAPI 3.1 specifications by introspecting source code from Express.js and PHP backends, alongside canonical TypeScript interfaces.

## 1. Source Code Introspection Patterns

### Express.js
To extract routes from Express.js:
- Parse `app.use('/prefix', router)` mount patterns in the main application entry point (e.g., `index.ts`).
- Parse router registrations: `router.get()`, `router.post()`, `router.put()`, `router.delete()`.
- Parse inline registrations: `app.post('/path', handler)`.

Example pattern to look for:
```typescript
app.use('/api/products', productRouter);
// inside productRouter:
router.get('/', getProducts);
```

### PHP
To extract routes from PHP:
- Parse front-controller route dispatch tables typically found in `public/index.php` or framework route files.
- Look for `switch` or `match` statements handling `$method` and `$path` combinations.

Example pattern:
```php
$method = $_SERVER['REQUEST_METHOD'];
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

if ($method === 'GET' && $path === '/api/products') {
    // ...
}
```

### Canonical Types
To extract schema definitions:
- Parse TypeScript interface definitions from a shared `client.ts` or `types.ts` file.
- Extract property names, their types (string, number, boolean, object, array), and optionality (indicated by `?`).

## 2. OpenAPI 3.1 Generation

When generating the OpenAPI YAML:
- **Paths**: Map extracted routes to OpenAPI path items (`/api/products`), with appropriate methods (`get`, `post`). Add generic summaries and generated `operationId`s.
- **Schemas**: Convert TypeScript interfaces to OpenAPI `components/schemas` JSON Schema objects.
- **Security**: Add a `BearerAuth` security scheme (JWT) to the components and apply it globally or per-endpoint if needed.
- **Requests & Responses**: 
  - Generate request body schemas based on method types (e.g., POST/PUT requests use the corresponding interface).
  - Generate response schemas referencing the components.
- **Servers**: Configure the `servers` array differently for each backend based on provided configuration.

## 3. Multi-Backend Spec Generation

To support multiple backends (e.g., Express and PHP):
- Produce structurally identical specifications for all REST backends.
- The only difference between the specs should be the `servers` URL.
- Ensure consistent path ordering and schema naming to allow straightforward drift detection.

## 4. Drift Detection

To ensure specifications remain accurate:
- Compare generated specs against committed specs in version control using `git diff --exit-code`.
- Cross-validate REST OpenAPI specs against GraphQL SDL type definitions for domain model parity.
- Verify that client interface methods cover all generated spec endpoints.
- Ensure scripts return non-zero exit codes (e.g., `1`) when drift is detected to fail CI pipelines.

## 5. GraphQL SDL Export

For GraphQL backends:
- Use programmatic Apollo Federation schema introspection.
- Extract the SDL using `printSchema()` from `graphql`.
- Export composed supergraph SDL files for comprehensive API documentation.
