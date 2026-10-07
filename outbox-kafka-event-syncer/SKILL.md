---
name: outbox-kafka-event-syncer
description: Audits, diagnoses, and repairs the Transactional Outbox pattern, Kafka message publishers, dead-letter event retry queues, and real-time subscription streams (WebSockets and Server-Sent Events). Activate this skill when working on asynchronous message publishing, Kafka event streams, or real-time event notifications.
---

# Outbox & Kafka Event Syncer

This skill provides guidelines for inspecting and maintaining transactional outbox workers, Kafka event streams, and real-time event notifications across multi-backend architectures.

## When to Activate

Activate this skill when:
- Investigating missing asynchronous domain events (`StockChanged`, `JournalEntryCreated`, `WebhookDeliveryFailed`).
- Maintaining outbox tables (`OutboxEvent`), outbox workers (`worker.ts` / `OutboxWorker`), or dead-letter queue retries.
- Synchronizing WebSocket (`ws://`) or Server-Sent Event (`SSE`) real-time notification streams.

---

## Architectural Principles

### 1. Transactional Outbox Pattern
* Store event payloads in the database within the same transaction as domain state mutations.
* Background workers poll for `Pending` outbox records, publish to Kafka topics, and mark as `Processed` or `Failed`.

### 2. Dead-Letter Retry Queue
* Failed events increment attempt counts and record `lastError` details.
* Expose administrative management operations (`outboxStats`, `deadLetterEvents`, `retryOutboxEvent`) in GraphQL & REST endpoints.

### 3. Real-Time Push Channels
* **Node.js / GraphQL**: Broadcast scanner events over GraphQL WebSocket subscriptions (`ws://.../graphql`) and collaborative WS sockets (`ws://localhost:5000`).
* **PHP / Laravel**: Stream push notifications over Server-Sent Events (`/api/notifications/subscribe`).
