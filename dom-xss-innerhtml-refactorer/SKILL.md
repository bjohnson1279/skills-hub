---
name: dom-xss-innerhtml-refactorer
description: >
  Audits, detects, and refactors DOM-based Cross-Site Scripting (XSS) vulnerabilities caused by unsafe dynamic innerHTML assignments across TypeScript/JavaScript codebases into safe DOM manipulation APIs with modernized unit test fixtures.
---

# DOM-based XSS innerHTML Refactorer & Test Modernizer

This skill provides automated detection, secure refactoring patterns, and test assertion modernizers for eliminating dynamic `innerHTML` string interpolations across TypeScript, JavaScript, browser extensions, and web client applications.

---

## Vulnerability Overview

When web applications construct dynamic user interface elements (such as buttons, badges, toast notifications, and modal dialogs) using template string interpolation assigned to `element.innerHTML`, any untrusted or unexpected character sequences introduce severe DOM-based Cross-Site Scripting (DOM XSS) vulnerabilities:

```typescript
// ❌ VULNERABLE: String interpolation with innerHTML creates DOM XSS hazard
btn.innerHTML = `<span aria-hidden="true">${icon}</span> <span>${message}</span><kbd aria-hidden="true">${shortcut}</kbd>`;
```

---

## Safe DOM Manipulation Protocol

Always replace dynamic `innerHTML` assignments with structured DOM element construction using `document.createElement`, `textContent`, `setAttribute`, and `appendChild`:

```typescript
// ✅ SECURE: Safe DOM construction with zero XSS hazard
function updateButtonContent(btn: HTMLElement, icon: string, text: string, shortcut?: string): void {
    btn.textContent = ''; // Clear previous contents safely
    
    const iconSpan = document.createElement('span');
    iconSpan.setAttribute('aria-hidden', 'true');
    iconSpan.textContent = icon;
    
    const textSpan = document.createElement('span');
    textSpan.textContent = text;
    
    btn.appendChild(iconSpan);
    btn.appendChild(textSpan);

    if (shortcut) {
        const kbd = document.createElement('kbd');
        kbd.setAttribute('aria-hidden', 'true');
        kbd.textContent = shortcut;
        btn.appendChild(kbd);
    }
}
```

---

## Unit Test Assertion Modernization

When `innerHTML` assignments are refactored to DOM node trees, legacy unit test assertions that check raw HTML string snippets must be modernized to query the DOM structure:

| Legacy Fragile Assertion | Modernized DOM Query Assertion |
| :--- | :--- |
| `expect(btn.innerHTML).toContain('<kbd')` | `expect(btn.querySelector('kbd')).not.toBeNull()` |
| `expect(btn.innerHTML).toContain('<span>Copy</span>')` | `expect(btn.textContent).toContain('Copy')` |
| `expect(toast.innerHTML).toContain('alert-icon')` | `expect(toast.querySelector('.alert-icon')).not.toBeNull()` |

---

## CLI Helper Utility

Run the bundled CLI tool to scan repositories and modernize test suites:

```bash
# 1. Audit repository for dynamic innerHTML usage and DOM XSS risks
python C:/Users/johns/.gemini/config/skills/dom-xss-innerhtml-refactorer/scripts/dom_refactorer.py audit \
  --target-dir C:/Users/johns/DEV/tampermonkey_collection \
  --output audit_results.json

# 2. Modernize test assertions checking innerHTML to structured DOM queries
python C:/Users/johns/.gemini/config/skills/dom-xss-innerhtml-refactorer/scripts/dom_refactorer.py modernize-tests \
  --target-dir C:/Users/johns/DEV/tampermonkey_collection
```

---

## Common Pitfalls

1. **Using `element.children.length = 0` or `innerHTML = ''` to clear**: Use `element.textContent = ''` or `replaceChildren()` to empty containers safely.
2. **Forgetting `aria-hidden` attributes on decorative icons**: When creating icon `<span>` elements dynamically, always call `setAttribute('aria-hidden', 'true')` to prevent screen reader noise.
3. **Updating source code without test assertion updates**: Ensure unit tests are updated simultaneously so CI test suites pass without regressions.
