---
name: polyglot-ddd-feature-syncer
description: Standardizes and automates multi-backend Domain-Driven Design (DDD) feature scaffolding and synchronization across GraphQL TypeScript, Express REST, PHP Hexagonal, and React Client applications.
---

# Polyglot DDD Feature Syncer

This skill standardizes the multi-layer pattern required to add or update domain features across comparative polyglot repositories (`gql-ddd-inventory`, `js-ddd-inventory`, `php-ddd-inventory`, and `react-ddd-inventory-client`).

## Workflow Steps

1. **Schema Harmonization**:
   - Update Prisma schemas in `gql-ddd-inventory/prisma/schema.prisma` and `js-ddd-inventory/prisma/schema.prisma`.
   - Update PostgreSQL/SQLite init DDL scripts in `php-ddd-inventory/docker/postgres/init/`.

2. **Domain Entities & Services**:
   - Implement core domain entity classes and domain services in:
     - `gql-ddd-inventory/src/domain/`
     - `js-ddd-inventory/src/domain/`
     - `php-ddd-inventory/src/Domain/`

3. **API Contracts**:
   - Define GraphQL `typeDefs` and `resolvers` in `gql-ddd-inventory/src/infrastructure/graphql/`.
   - Register Express REST endpoints in `js-ddd-inventory/src/index.ts` or route modules.
   - Register PHP REST handlers in `php-ddd-inventory/public/index.php` or controllers.

4. **Frontend Integration**:
   - Add new panel component to `react-ddd-inventory-client/src/components/Panels.tsx`.
   - Mount navigation sidebar link and panel render block in `react-ddd-inventory-client/src/App.tsx`.
   - **Crucial**: Update TypeScript union types for active navigation state (e.g., `type Tab = ...` or `useState<Tab>`) in `App.tsx` when adding new UI panels to prevent production build failures.

5. **Omnichannel Synchronization (If Applicable)**:
   - When porting omnichannel integration features, ensure the `BaseChannelAdapter` (from `shared/src/api/integrations/types.ts`) is implemented.
   - Scaffold domain models (`Channel`, `Order`, `ChannelAllocationPool`) into the new backend's domain layer.
   - Ensure the backend exposes a `ChannelWebhookController` or similar for receiving external events.

6. **Parity Testing**:
   - Add unit tests in Jest (`gql-ddd-inventory` & `js-ddd-inventory`) and PHPUnit (`php-ddd-inventory`).

## Helper Script

Run feature checklist generator:
```bash
python "C:\Users\johns\.gemini\config\skills\polyglot-ddd-feature-syncer\scripts\scaffold_feature.py" --feature [feature_name]
```
