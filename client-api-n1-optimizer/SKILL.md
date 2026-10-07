---
name: client-api-n1-optimizer
description: Audits, detects, and refactors client-side N+1 REST/GraphQL request loops across frontend API adapters (React, Vue, TypeScript) into bounded Promise.all chunked batches with resilient error isolation and performance benchmark tests.
---

# Client API N+1 Request Optimizer

This skill provides static analysis, transformation patterns, and automated performance testing recipes for detecting and refactoring client-side $O(N)$ serial HTTP request bottlenecks in frontend API adapters and client SDKs.

---

## When to Activate

Activate this skill when:
- Auditing frontend API client adapters (`src/api/*.ts`, `src/services/*.ts`, `src/adapters/*.ts`) for performance bottlenecks.
- Detecting serial `await` calls inside iterative loops (`for`, `for...of`, `while`, or `.forEach`).
- Refactoring un-chunked `Promise.all` arrays that risk browser socket exhaustion or backend HTTP 429 / connection pool drops.
- Adding concurrency performance benchmarks in Vitest or Jest.

---

## 1. Automated Detection

Run the included static analyzer across the target client codebase:

```bash
# Scan a directory
python C:/Users/johns/.gemini/config/skills/client-api-n1-optimizer/scripts/n1_scanner.py \
  C:/Users/johns/DEV/inventory/react-ddd-inventory-client/src/api

# Output JSON report for CI/bot auditing
python C:/Users/johns/.gemini/config/skills/client-api-n1-optimizer/scripts/n1_scanner.py \
  C:/Users/johns/DEV/inventory/react-ddd-inventory-client/src/api \
  --output n1_audit.json
```

---

## 2. Refactoring Recipes & Anti-Patterns

### Anti-Pattern 1: Serial Await in Nested Loops (O(N) RTT Latency)
❌ **Slow & Sequential**:
```typescript
// Each HTTP round-trip blocks the next one
for (const p of productsList) {
  for (const v of p.variants || []) {
    const stockRes = await this.request('GET', `/api/inventory/${v.sku}/stock`);
    stockItems.push({ sku: v.sku, quantity: stockRes.quantity });
  }
}
```

✅ **Refactored: Bounded Concurrent Chunking with Fallback**:
```typescript
const variants = productsList.flatMap((p: any) => p.variants || []);
const chunkSize = 20; // Bounded batch to prevent socket saturation

for (let i = 0; i < variants.length; i += chunkSize) {
  const chunk = variants.slice(i, i + chunkSize);
  const chunkResults = await Promise.all(
    chunk.map(async (v: any) => {
      try {
        const stockRes = await this.request('GET', `/api/inventory/${v.sku}/stock`);
        return {
          id: `${v.id}-stock`,
          sku: v.sku,
          locationId: stockRes.location_id || 'default',
          quantity: stockRes.available_quantity ?? stockRes.quantity ?? 0,
          version: 1
        };
      } catch {
        return {
          id: `${v.id}-stock`,
          sku: v.sku,
          locationId: 'default',
          quantity: 0,
          version: 1
        };
      }
    })
  );
  stockItems.push(...chunkResults);
}
```

---

### Anti-Pattern 2: Serial Item Submission on Onboarding / Bulk Mutation
❌ **Slow Serial Posting**:
```typescript
for (const item of items) {
  await this.request('POST', `/api/onboardings/${onboardingId}/items`, {
    variant_id: item.variantId,
    quantity: item.quantity,
    unit_cost_cents: item.unitCostCents
  });
}
```

✅ **Refactored: Bounded Batch Mutation**:
```typescript
const BATCH_SIZE = 10;
for (let i = 0; i < items.length; i += BATCH_SIZE) {
  const batch = items.slice(i, i + BATCH_SIZE);
  const promises = batch.map(item => this.request('POST', `/api/onboardings/${onboardingId}/items`, {
    variant_id: item.variantId,
    quantity: item.quantity,
    unit_cost_cents: item.unitCostCents
  }));
  await Promise.all(promises);
}
```

---

### Anti-Pattern 3: Nested Iteration over Pre-Calculated Reports
❌ **Un-indexed Lookup Inside Nested Loops**:
```typescript
for (const p of products) {
  for (const v of p.variants) {
    const qty = invItems.filter(i => i.sku === v.sku).reduce((acc, i) => acc + i.quantity, 0);
    if (qty > 0) {
      const val = await this.request('GET', `/accounting/valuation/${v.id}?quantity=${qty}`);
      items.push({ sku: v.sku, totalValueCents: val.totalCostCents });
    }
  }
}
```

✅ **Refactored: O(1) Map Lookup + Concurrent Promise.all**:
```typescript
// 1. Pre-calculate lookup map in O(M) time
const skuQtyMap = new Map<string, number>();
for (const item of invItems) {
  skuQtyMap.set(item.sku, (skuQtyMap.get(item.sku) || 0) + item.quantity);
}

// 2. Fetch all variant valuations concurrently
const promises: Promise<ValuationItem>[] = [];
for (const p of products) {
  for (const v of p.variants) {
    const qty = skuQtyMap.get(v.sku) || 0;
    if (qty > 0) {
      promises.push(
        this.request('GET', `/accounting/valuation/${v.id}?tenantId=${tenantId}&quantity=${qty}`)
          .then(val => ({
            variantId: v.id,
            sku: v.sku,
            name: p.name,
            totalQuantity: qty,
            totalValueCents: val.totalCostCents || 0,
            unitCostCents: val.unitCostCents || 0
          }))
          .catch(() => ({
            variantId: v.id,
            sku: v.sku,
            name: p.name,
            totalQuantity: 0,
            totalValueCents: 0,
            unitCostCents: 0
          }))
      );
    }
  }
}

const items = await Promise.all(promises);
```

---

## 3. Performance Benchmark Test Template (Vitest / Jest)

When optimizing an adapter method, always author a regression test that mocks network latency and asserts concurrent execution time:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { ExpressRESTAdapter } from '../../src/api/express';
import { Item } from '../../src/api/client';

describe('Performance: createStockOnboarding', () => {
  it('should execute item creation concurrently under 300ms for 5 items with 100ms simulated network delay', async () => {
    const adapter = new ExpressRESTAdapter();
    const mockRequest = vi.spyOn(adapter as any, 'request').mockImplementation(async (method, url) => {
      await new Promise(resolve => setTimeout(resolve, 100)); // Simulated network latency
      if (url === '/onboarding') return { id: 'onboarding-123' };
      return { success: true };
    });

    const items: Item[] = [
      { variantId: 'v1', quantity: 10, unitCostCents: 100 },
      { variantId: 'v2', quantity: 20, unitCostCents: 200 },
      { variantId: 'v3', quantity: 30, unitCostCents: 300 },
      { variantId: 'v4', quantity: 40, unitCostCents: 400 },
      { variantId: 'v5', quantity: 50, unitCostCents: 500 },
    ];

    const startTime = Date.now();
    await adapter.createStockOnboarding('tenant1', 'loc1', '2026-08-16', items);
    const duration = Date.now() - startTime;

    // 100ms for header creation + 100ms for concurrent items = ~200ms (vs >600ms serial)
    expect(duration).toBeLessThan(300);

    mockRequest.mockRestore();
  });
});
```
