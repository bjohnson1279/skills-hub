---
name: crosswalk-dedup-etl-scaffolder
description: Standardizes multi-format legacy data ingestion, crosswalk transformation pipelines, smart fuzzy customer deduplication (FEIN/SSN, Name, Address), and non-destructive dry-run analysis endpoints. Activate this skill when building or updating legacy data migration adapters or onboarding acquired agency systems.
---

# Crosswalk Ingestion & Smart Deduplication ETL Scaffolder

This skill standardizes the architecture and implementation of legacy data ingestion, crosswalk ETL transformation pipelines, fuzzy customer deduplication engines, and dry-run preview endpoints across agency management systems.

## When to Activate

Activate this skill when:
- Building ETL migration pipelines for acquired insurance brokerages.
- Normalizing disparate legacy data formats (SQL dumps, flat files, XML exports, JSON streams).
- Implementing duplicate detection logic to prevent duplicate customer profiles.
- Scaffolding dry-run preview endpoints (`POST /api/v1/integration/dry-run`).

---

## Technical Guidelines

### 1. Ingestion Payload Contract
Define a standard `IngestionPayload` structure supporting batch and single record imports:
```typescript
export interface IngestionPayload {
  systemSource: 'FORMAT_A' | 'FORMAT_B' | 'FORMAT_C' | 'FORMAT_D';
  exportedAt: string;
  dryRun?: boolean;
  data: unknown | unknown[];
}
```

### 2. Crosswalk Transformation Logic
Implement dedicated transformers per format implementing standard field crosswalk rules:
* **Primary Keys**: Map format primary keys (`Client_PK`, `CUST_ID`, `ClientNum`, `account_uuid`) to canonical customer IDs (`CUST-FMT-A-{id}`).
* **Line of Business (LOB)**: Map legacy LOB codes (`AUTOC`, `WORKCOMP`, `COMM_AUTO`) to standard canonical enums (`Commercial Auto`, `Workers Comp`).
* **Date Normalization**: Convert disparate date strings (`MM/DD/YYYY`, compact `YYYYMMDD`, ISO string) to standardized `YYYY-MM-DD`.
* **Currency Conversion**: Convert cents (`annual_premium_cents`) to float dollars (`cents / 100`).

### 3. High-Throughput Smart Deduplication Engine
Implement a fuzzy evaluation engine (`DeduplicationEngine`) comparing candidate records against pre-existing customers.

#### A. Constructor-Level Pre-Normalization Caching
To prevent $\mathcal{O}(N \times M)$ repeated regex execution and GC thrashing across large migration batches, **always pre-compute normalized customer tokens in the constructor**:
```typescript
interface CachedCustomer {
  customer: Customer;
  cleanFein: string;
  cleanName: string;
  cleanZip: string;
}

export class DeduplicationEngine {
  private existingCustomersCache: CachedCustomer[] = [];

  constructor(existingCustomers: Customer[]) {
    // Pre-calculate normalized fields once instead of inside every evaluate() candidate loop
    this.existingCustomersCache = (existingCustomers || []).map(existing => ({
      customer: existing,
      cleanFein: this.normalizeTaxId(existing.feinOrSsn),
      cleanName: this.normalizeName(
        existing.businessName || `${existing.firstName || ''} ${existing.lastName || ''}`
      ),
      cleanZip: (existing.address?.postalCode || '').trim().substring(0, 5)
    }));
  }

  public evaluate(candidate: Customer): DeduplicationMatch | null {
    if (!this.existingCustomersCache || this.existingCustomersCache.length === 0) {
      return null;
    }
    const cleanCandFein = this.normalizeTaxId(candidate.feinOrSsn);
    const cleanCandName = this.normalizeName(
      candidate.businessName || `${candidate.firstName || ''} ${candidate.lastName || ''}`
    );
    const cleanCandZip = (candidate.address?.postalCode || '').trim().substring(0, 5);

    let bestMatch: DeduplicationMatch | null = null;
    let highestScore = 0;

    for (const cached of this.existingCustomersCache) {
      const { customer: existing, cleanFein: cleanExistingFein, cleanName: cleanExistingName, cleanZip: cleanExistingZip } = cached;
      // Fast equality / token matching on pre-normalized properties...
    }
    return bestMatch;
  }
}
```

#### B. Weighted Scoring Matrix & Recommendation Rules
* **FEIN / SSN Match (Weight 50%)**: Exact match on clean 9-digit numeric tax ID.
* **Name Match (Weight 35%)**: Exact or substring match on normalized corporate / individual name.
* **Address / ZIP Match (Weight 15%)**: Match on 5-digit postal code and normalized street address.
* **Confidence Threshold ($\ge 75\%$)**: Triggers `LINK_TO_EXISTING` recommendation with matched fields and explanation; scores $< 75\%$ flag as new customer candidate.

### 4. Dry-Run Analysis Endpoints
Expose `/api/v1/integration/dry-run` to return transformation summaries, mapping logs (`INFO`/`WARN`/`ERROR`), exceptions, and deduplication recommendations without persisting changes to the core database.
