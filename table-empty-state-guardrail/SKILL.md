---
name: table-empty-state-guardrail
description: >-
  Audits, detects, and generates accessible, actionable empty states (data.length === 0) across frontend
  data tables (HTML, JSX/TSX, Vue). Verifies colspan alignment with table headers, enforces actionable
  Call-to-Action buttons, detects lingering Git conflict markers, and auto-generates test suites.
---

# Table Empty State Guardrail

## Overview
When data tables in administrative panels, enterprise dashboards, or data workbenches are empty, displaying an empty table body can mislead users into believing data is still loading or broken. 

This skill enforces accessible, user-friendly empty states by:
1. **Empty State Presence**: Ensuring every `<table>` has an explicit fallback row spanning all columns (`colspan`) when data is empty.
2. **Colspan Alignment**: Validating that `colspan` matches the exact number of table headers (`<th>`).
3. **Actionable CTAs**: Verifying that empty states provide actionable buttons (e.g. `+ Receive Premium Payment`, `⚡ Parse AL3 Download`, `⚡ Go to Migration Workbench`) to unblock user workflows.
4. **Persistent Screen Reader Announcers**: Ensuring empty states do NOT dynamically inject inline `aria-live="polite"` via `innerHTML` (an anti-pattern where assistive tech misses announcements), but instead declare a persistent static `#sr-announcer` live region with `.sr-only` CSS and programmatic announcements.
5. **Git Conflict Guardrail**: Auditing frontend templates to guarantee zero lingering Git merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
6. **Test Generation**: Auto-generating Jest or Vitest test suites (e.g. `tests/ui.empty-states.test.ts`) to prevent regressions in CI.

---

## Dependencies
- **Python 3.8+**
- **Node.js / Jest or Vitest** (for running generated test fixtures)

---

## Quick Start

### 1. Scan Frontend Templates for Empty State & Conflict Compliance
Scan an HTML file, directory, or SPA component folder:

```bash
python C:/Users/johns/.gemini/config/skills/table-empty-state-guardrail/scripts/audit_empty_states.py scan \
  --target public/index.html \
  --output empty_states_audit.json
```

### 2. Auto-Generate a Jest / Vitest Regression Test Suite
Generate a unit test suite to continuously enforce table empty states:

```bash
python C:/Users/johns/.gemini/config/skills/table-empty-state-guardrail/scripts/audit_empty_states.py generate-test \
  --target-file public/index.html \
  --output tests/ui.empty-states.test.ts \
  --empty-states "No General Ledger entries found,No agency bill invoices found,No download batches found,No crosswalk rules defined"
```

---

## CLI Reference (`audit_empty_states.py`)

### Commands

#### `scan`
Scans HTML, JSX, TSX, and Vue files for:
- Table count vs empty state count.
- Colspan mismatches against header columns.
- Actionable call-to-action buttons.
- Merge conflict markers.

```bash
python scripts/audit_empty_states.py scan --target <file_or_dir> [--output <report.json>]
```

#### `generate-test`
Generates a Jest/Vitest test file asserting that:
1. No merge conflict markers exist in the frontend markup.
2. All specified empty state strings are present.
3. Actionable buttons exist inside empty states.

```bash
python scripts/audit_empty_states.py generate-test \
  --target-file <path_to_html_or_template> \
  --output <path_to_test_file.test.ts> \
  [--empty-states "<comma_separated_strings>"]
```

---

## Best Practices & Guidelines
1. **Always Match Colspan**: If a table has 8 columns in `<thead>`, the empty state `<td>` MUST specify `colspan="8"`. A mismatched colspan distorts the table layout and breaks border styling.
2. **Provide Actionable Call-To-Action**: An empty state should never be a dead end. Always provide a button navigating to creation modals, import wizards, or workbenches.
3. **Harmonize Identifiers**: Standardize terminology across empty states (e.g. `"No General Ledger entries found"` rather than inconsistent colloquial variations) so automated regression tests and users share clear expectations.
4. **Centralize Screen Reader Announcements**: Never inject `aria-live="polite"` inside dynamic `innerHTML` blocks or template strings. Always attach `aria-live="polite"` to a persistent `.sr-only` DOM element in static HTML (e.g. `<div id="sr-announcer" class="sr-only" aria-live="polite"></div>`) and update its text content dynamically via JavaScript (`announceToScreenReader(...)`).