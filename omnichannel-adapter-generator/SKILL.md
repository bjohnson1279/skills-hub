---
name: omnichannel-adapter-generator
description: Standardizes the scaffolding of new sales channel adapters (Shopify, Amazon, WooCommerce, etc.) across the DDD backends by implementing BaseChannelAdapter, domain models, and ingestion services.
---

# Omnichannel Adapter Generator

This skill standardizes the design and implementation of third-party sales channel integrations across the DDD inventory services.

## When to Activate

Activate this skill when:
- Adding a new sales channel integration (e.g., TikTok Shop, Walmart Marketplace, Magento).
- Upgrading a stubbed adapter to a concrete implementation.
- Refactoring how external orders are mapped into the domain.

---

## Integration Architecture Guidelines

### 1. Domain Models
Ensure the target backend's domain layer includes the omnichannel aggregates:
- `Channel`: Aggregate root representing the sales channel.
- `Order`: Must include `channelId` and `externalOrderId`.
- `ChannelAllocationPool`: Manages physical inventory reservations dedicated to the channel.

### 2. BaseChannelAdapter Implementation
Create a new adapter class in `src/application/integrations/<channel>/<Channel>Integration.ts` that implements `BaseChannelAdapter<T>` from `shared/src/api/integrations/types.ts`:
- `syncInventory()`: Fetch or push inventory stock levels.
- `ingestOrder()`: Map the external payload to internal `OrderLineItem` format and call the `ChannelIngestionService`.
- `pushFulfillmentStatus()`: Send tracking and shipped status back to the external channel.

### 3. ChannelIngestionService Wiring
- All adapters must pass parsed external orders into the centralized `ChannelIngestionService`.
- Do NOT bypass the ingestion service, as it handles critical **oversell conflict resolution** logic and routing.

### 4. Webhook Controllers
- Register webhook listeners in `src/infrastructure/http/webhooks/ChannelWebhookController.ts`.
- Ensure payloads are wrapped with necessary context (like `tenantId` and `channelId`) before passing to the adapter's `ingestOrder` method.
