---
name: acord-dec-page-generator
description: Standardizes ACORD 125/126 Commercial Policy Declaration Page payload construction, insurance coverage schedules (vehicles, properties, drivers), claims histories, and policy endorsement formatting (IL 00 17, CG 00 01) across Node/TypeScript and polyglot InsurTech services. Activate this skill when building insurance policy documentation, dec-page endpoints, or ACORD form generators.
---

# ACORD 125/126 Declaration Page & Schedule Builder

This skill standardizes the construction of ACORD-compliant Commercial Policy Declaration Page (Dec-Page) payloads, coverage schedules (Vehicles, Properties, Drivers), and claims histories across InsurTech APIs.

## When to Activate

Activate this skill when:
- Exposing policy declaration page endpoints (`GET /api/v1/policies/:id/dec-page`).
- Building commercial insurance policy documentation or ACORD form rendering services.
- Mapping coverage schedules, deductibles, limits, and policy endorsement codes (`IL 00 17`, `CG 00 01`).

---

## ACORD Payload Structure Standard

Ensure dec-page payloads follow standardized ACORD 125/126 Commercial Declaration structure:

```typescript
export interface AcordDecPagePayload {
  documentTitle: string; // e.g. "ACORD 125/126 COMMERCIAL INSURANCE POLICY DECLARATION"
  acordStandard: string; // "ACORD COMPLIANT"
  generatedTimestamp: string;
  agencyInfo: {
    agencyName: string;
    agencyCode: string;
    producerName: string;
    licenseNumber: string;
    address: string;
    phone: string;
  };
  insuredHeader: {
    customerId: string;
    name: string;
    entityType: 'Commercial' | 'Individual';
    taxId: string;
    address: string;
    email: string;
    phone: string;
  };
  carrierInfo: {
    carrierId: string;
    carrierName: string;
    naicNumber: string;
    writingCompany: string;
  };
  policySummary: {
    policyId: string;
    policyNumber: string;
    lineOfBusiness: string;
    effectiveDate: string;
    expirationDate: string;
    termLengthMonths: number;
    status: string;
    billingType: string;
  };
  coverageDetails: Array<{
    coverageCode: string;
    description: string;
    limit: string;
    deductible: string;
    premium: string;
  }>;
  financials: {
    totalPremium: string;
    surplusLinesTax?: string;
    totalAmountDue: string;
  };
  formsAndEndorsements: Array<{
    formCode: string;
    editionDate: string;
    title: string;
  }>;
}
```

## Calculation & Formatting Rules
1. **Term Length**: Calculate exact policy term length in months between `effectiveDate` and `expirationDate`.
2. **Currency Formatting**: Format all limits and premiums with currency symbols and thousand separators (`$1,000,000.00`).
3. **Mandatory Endorsements**: Include standard commercial form numbers:
   - `IL 00 17 11 98` (Common Policy Conditions)
   - `CG 00 01 04 13` (Commercial General Liability Coverage Form)
   - `CA 00 01 10 13` (Business Auto Coverage Form)
