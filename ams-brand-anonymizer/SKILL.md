---
name: ams-brand-anonymizer
description: Audits, detects, and refactors proprietary/trademarked Agency Management System (AMS) vendor names (AMS360, Applied Epic, TAM, HawkSoft, EZLynx, Vertafore) across polyglot repositories, test suites, and documentation into generic abstract codenames (CoreAMS, Format A, Format B, Format C, Format D). Activate this skill when sanitizing agency integration code or public GitHub repositories.
---

# AMS Brand Anonymizer & Privacy Guardrail

This skill provides automated auditing and refactoring guidelines for removing real-world proprietary Agency Management System (AMS) vendor trademarks, brand names, and copyrighted format identifiers from public repositories, test fixtures, documentation, and UI text.

## When to Activate

Activate this skill when:
- Preparing an agency management or data migration repository for public GitHub hosting.
- Writing integration prototypes or training grounds for insurance brokerage migrations.
- Auditing legacy export payloads and transformer code for trademark compliance.

---

## Anonymization Mapping Standard

Always enforce abstract codenames across code, comments, test scripts, documentation, and UI labels:

| Proprietary Real-World Vendor / System | Abstract Codenamed Equivalent | Architectural Format Classification |
| :--- | :--- | :--- |
| **Core Destination AMS (e.g. AMS360)** | `CoreAMS` / `ApexCore` | Target Enterprise Agency Management System |
| **Enterprise SQL/SOAP Export (e.g. Applied Epic)** | `Format A` | Enterprise Relational SQL & SOAP Export Schema |
| **Classic DB Flat-File Export (e.g. TAM)** | `Format B` | Legacy DB Flat-File / Table Export Schema |
| **Desktop CMS XML Export (e.g. HawkSoft)** | `Format C` | Desktop CMS XML & Local DB Export Schema |
| **Cloud JSON Stream (e.g. EZLynx)** | `Format D` | Cloud-Native JSON Stream / REST API Export Schema |

---

## Audit & Verification Workflow

1. **Automated Search Audit**:
   Execute regex search across the repository to flag any sensitive vendor strings:
   ```bash
   grep -iE "\b(ams360|epic|tam|hawksoft|ezlynx|vertafore|applied)\b" .
   ```

2. **Internal Reference Isolation**:
   Store internal mapping context strictly in `.commercial_crosswalk_reference.notes` and ensure `.gitignore` contains:
   ```gitignore
   .commercial_crosswalk_reference.notes
   ```

3. **Public Interface Verification**:
   Verify that all public API endpoints (`/api/v1/integration/import`), UI headers, Dec-Page titles, and README documentation use neutral terms (`CoreAMS`, `Format A`, `Format B`, `Format C`, `Format D`).
