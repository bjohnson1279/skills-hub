---
name: a11y-dom-feature-test-augmenter
description: >-
  Audits frontend code and git diffs for newly introduced WCAG accessibility features
  (skip-to-content links, persistent live regions, modal focus guards, aria-hidden icons),
  and auto-generates or augments Jest/Vitest DOM assertions in existing test suites.
---

# Accessibility DOM Feature Test Augmenter

## Overview
When frontend bots (such as Palette) introduce micro-UX and accessibility improvements (e.g. keyboard skip links, `tabindex="-1"` container focus targets, or `aria-hidden="true"` emoji tags), test suites often lack assertions verifying that these accessibility features remain intact across future refactors.

This skill scans git diffs or component files for newly added accessibility structures and automatically generates regression assertions into existing test suites (e.g., `tests/ui.empty-states.test.ts` or `ui.a11y.test.ts`).

---

## Dependencies
- **Python 3.8+**
- **Node.js / Jest or Vitest** (for test execution)

---

## Capabilities & Usage

### 1. Scan Component or HTML for Accessibility Features
```bash
python C:/Users/johns/.gemini/config/skills/a11y-dom-feature-test-augmenter/scripts/augment_a11y_tests.py \
  --scan-file public/index.html \
  --dry-run
```

### 2. Auto-Augment Existing Test Suite
Injects test assertions directly into the targeted Jest/Vitest test file before the closing test block:
```bash
python C:/Users/johns/.gemini/config/skills/a11y-dom-feature-test-augmenter/scripts/augment_a11y_tests.py \
  --scan-file public/index.html \
  --target-test tests/ui.empty-states.test.ts
```

### 3. Scan from Bot PR Unified Diff
```bash
python C:/Users/johns/.gemini/config/skills/a11y-dom-feature-test-augmenter/scripts/augment_a11y_tests.py \
  --scan-diff pr_patch.diff \
  --target-test tests/ui.empty-states.test.ts
```

---

## Verified Accessibility Feature Patterns

1. **Skip-to-Content Links**:
   - Asserts `<a href="#main-content" class="skip-link">` exists in document root.
   - Asserts `<main id="main-content" tabindex="-1">` allows programmatic focus transfer.
2. **Persistent Screen Reader Announcers**:
   - Asserts `<div id="sr-announcer" class="sr-only" aria-live="polite">` is statically present.
   - Enforces absence of dynamic `aria-live` inside dynamic innerHTML nodes.
3. **Decorative Emoji Concealment**:
   - Asserts non-semantic emojis (`✅`, `📋`, `🤖`, `✨`) are enclosed in `<span aria-hidden="true">`.
