---
name: erp-integration-adapter-generator
description: Standardizes third-party accounting and ERP connector patterns (QuickBooks V3, NetSuite SuiteTalk REST, Xero ManualJournals) across GraphQL resolvers and REST controllers with mock credential fallbacks and Bearer/HMAC authorization. Activate this skill when building or updating ERP sync integrations.
---

# ERP Integration Adapter Generator

This skill standardizes the design and implementation of third-party ERP and accounting integrations (QuickBooks, Oracle NetSuite, Xero, Shopify) across GraphQL and REST inventory services.

## When to Activate

Activate this skill when:
- Adding external ERP accounting sync support to a new backend.
- Exposing journal posting or inventory sync mutations in GraphQL or REST endpoints.
- Building resilient mock fallbacks for testing without live credentials.

---

## Integration Architecture Guidelines

### 1. Domain Interfaces
Always define a clean domain interface before creating concrete HTTP clients:
- `IQuickBooksClient`: Handles Intuit QuickBooks V3 JournalEntry API.
- `INetSuiteClient`: Handles Oracle NetSuite SuiteTalk REST API.
- `IXeroClient`: Handles Xero ManualJournals API.

### 2. Payload Normalization Rules
* **Currency Conversion**: Convert integer cents (`amountCents`) to decimal dollars (`amountCents / 100`) as required by Intuit, NetSuite, and Xero endpoints.
* **Posting Types**: Map `type: "debit"` to `"Debit"` / positive values, and `type: "credit"` to `"Credit"` / negative line amounts.
* **Mock Fallback Handling**: If credentials contain `"mock"` or are empty, return deterministic mock IDs (e.g. `mock-qbo-journal-<random>`) to allow local integration tests to pass without external network dependencies.

### 3. API & Resolver Wiring
* **GraphQL**: Add schema inputs and mutations (`syncQuickBooksJournal`, `syncNetSuiteJournal`, `syncXeroJournal`) in `typeDefs.ts` and resolve in `resolvers.ts`. Enforce role-based access controls (`admin`, `accountant`).
* **REST**: Expose `/api/integrations/<provider>/sync` HTTP POST routes in controllers with validation middleware.

### 4. Logging & Observability
* Use structured logging (`console.log` or dedicated logger) capturing context, action, target URL, and sanitized payload details (redacting auth tokens).
