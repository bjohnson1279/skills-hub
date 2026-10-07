---
name: react-client-feature-auditor
description: Audits backend API routes and GraphQL schemas against React SPA components to ensure 100% UI coverage and scaffold missing frontend controls.
---

# React Client Feature Auditor

This skill scans backend API route definitions (`resolvers.ts`, `routes/`, `public/index.php`) and cross-checks them against the React frontend (`react-ddd-inventory-client/src/App.tsx` and `Panels.tsx`).

## Capability

1. **Audit UI Coverage**:
   - Detects backend endpoints that lack corresponding UI panels or state handlers in the frontend.
2. **Scaffold Missing Panels**:
   - Generates glassmorphism panel components in `Panels.tsx` matching the project design system.

## Usage

Run the UI completeness audit:
```bash
python "C:\Users\johns\.gemini\config\skills\react-client-feature-auditor\scripts\audit_ui_completeness.py"
```
