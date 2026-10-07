---
name: persistent-aria-announcer-harmonizer
description: >-
  Audits frontend applications for dynamic aria-live injection anti-patterns (innerHTML, template strings),
  refactors them into centralized persistent .sr-only screen reader announcers, and generates automated accessibility regression test suites.
---

# Persistent ARIA Announcer Harmonizer

## Overview
Injecting elements with `aria-live` (e.g. `aria-live="polite"`) into the DOM dynamically via `innerHTML` or conditional template strings is a well-known accessibility anti-pattern. Screen readers and assistive technologies often miss announcements because the live region was not registered during initial DOM parsing or browser mutation observers fire inconsistently across vendors.

This skill audits frontend codebases for dynamic `aria-live` injections, implements the standardized **Persistent Live Region Pattern** (`<div id="sr-announcer" class="sr-only" aria-live="polite"></div>`), and generates automated Jest/Vitest test suites to enforce compliance in CI.

---

## Dependencies
- **Python 3.8+**
- **Node.js / Jest or Vitest** (for test execution)

---

## Quick Start

### 1. Scan Frontend Codebase for Dynamic ARIA Live Injections
Scan HTML files, Vue/React templates, or entire directories:
```bash
python C:/Users/johns/.gemini/config/skills/persistent-aria-announcer-harmonizer/scripts/announcer_harmonizer.py scan \
  --target public/index.html \
  --output announcer_audit.json
```

### 2. Retrieve Standard Scaffolding Snippets
Get canonical `.sr-only` CSS, HTML live region, and JavaScript dispatcher helper:
```bash
python C:/Users/johns/.gemini/config/skills/persistent-aria-announcer-harmonizer/scripts/announcer_harmonizer.py scaffold
```

### 3. Generate Accessibility Regression Test Suite
Auto-generate a Jest test verifying persistent announcer presence and zero inline `aria-live` mutations:
```bash
python C:/Users/johns/.gemini/config/skills/persistent-aria-announcer-harmonizer/scripts/announcer_harmonizer.py generate-test \
  --target-file public/index.html \
  --output tests/ui.announcer.test.ts \
  --messages "No General Ledger entries found,No customers found,No certificates found"
```

---

## Architecture Pattern

### 1. Static HTML Live Region
Place a persistent announcer directly in the static `<body>` container:
```html
<div id="sr-announcer" class="sr-only" aria-live="polite"></div>
```

### 2. WCAG-Compliant `.sr-only` Styling
Visually hides the element while ensuring assistive technologies continue tracking it:
```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
```

### 3. Centralized Dispatcher Helper
Update the announcer's `textContent` whenever dynamic state transitions occur:
```javascript
function announceToScreenReader(message) {
  const announcer = document.getElementById('sr-announcer');
  if (announcer) {
    announcer.textContent = message;
  }
}
```

---

## CLI Reference (`announcer_harmonizer.py`)

### `scan`
* `--target`: Path to file or directory.
* `--output`: Optional JSON output filepath.

### `scaffold`
* `--output`: Optional JSON output filepath for boilerplate snippets.

### `generate-test`
* `--target-file`: Path to markup or template file.
* `--output`: Output test file path (`.test.ts`).
* `--messages`: Comma-separated list of dynamic state notification strings to assert against.

---

## Common Mistakes
1. **Adding `aria-live` to `innerHTML` empty states**: Screen readers miss live region declarations inserted after page load.
2. **Using `display: none` or `visibility: hidden`**: Hiding an element with CSS `display: none` instructs screen readers to completely ignore the element and all its children. Always use `.sr-only` clipping.
3. **Using `aria-live="assertive"` for non-critical empty states**: Reserve `assertive` for severe system errors or authentication timeouts; use `polite` for dynamic data filters, table searches, and empty states.
