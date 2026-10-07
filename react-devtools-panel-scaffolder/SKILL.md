---
name: react-devtools-panel-scaffolder
description: Scaffolds premium developer experience panels in React SPAs that consume multi-backend APIs.
---

# React DevTools Panel Scaffolder

This skill guides the process of scaffolding premium developer experience panels in React SPAs that consume multi-backend APIs. It includes instructions for analyzing design systems, building health monitors, conformance viewers, API spec viewers, and enhanced backend switchers.

## 1. Design System Analysis

Before scaffolding new components, analyze the existing React app's styling approach:
- **Style System**: Determine if the app uses vanilla CSS (`import './styles.css'`), Tailwind CSS (utility classes), or CSS Modules (`import styles from './styles.module.css'`).
- **Design Tokens**: Extract the core color palette, typography (fonts), spacing units, and border styles.
- **Utility Classes**: Identify reusable CSS classes, e.g., `.glass-panel`, `.stat-card`, `.btn-primary`, `.badge-success`.
- **Component Patterns**: Note how hooks, props, and context are used across the application.

## 2. Backend Health Monitor Panel

Create a panel to monitor the health of multiple backend APIs simultaneously.

- Use `fetch()` directly instead of the app's standard API client to avoid interceptors or global error handling.
- Display status cards indicating:
  - Backend Name & Port
  - Health Status (🟢 Online / 🔴 Offline / 🟡 Checking)
  - Response Latency (in ms)
  - Last Checked Timestamp
- Implement auto-refresh with configurable polling intervals.

**State Shape Example:**
```typescript
type HealthState = Record<string, { status: 'online' | 'offline' | 'checking'; latencyMs: number }>;
```

## 3. Conformance Results Viewer

Display cross-backend API conformance testing results.

- **Parity Matrix Table**:
  - Rows: Test scenario modules.
  - Columns: Target backends.
- **Color-Coded Cells**:
  - Green: 100% Pass
  - Yellow: Partial Pass
  - Red: Failures
- **Summary Stats**: Total tests, pass, fail, skip, and overall parity percentage.
- **Interactivity**: Expandable rows to view individual test details. Load and parse conformance JSON reports.

## 4. API Spec Viewer Panel

Provide quick access to backend API specifications.

- **Tabbed Navigation**: Switch between OpenAPI REST and GraphQL SDL formats.
- **Collapsible Groups**: Group endpoints by path prefix.
- **Method Badges**: Use standard colors for HTTP methods:
  - GET = Blue
  - POST = Green
  - PUT = Amber
  - DELETE = Red
- **Search/Filter**: Text input to quickly find endpoints.
- **cURL Generation**: A "Copy as cURL" button for quick testing.
- **Syntax Highlighting**: Highlight code blocks for SDL and YAML specs.

## 5. Enhanced Backend Switcher

Upgrade basic select dropdowns to premium card-based selectors.

- Replace `<select>` with interactive cards.
- Show live health dots (🟢/🔴) next to each backend.
- Display response latency.
- Include conformance pass/fail badges.
- Highlight the active backend with a premium glow effect (e.g., `box-shadow: 0 0 15px rgba(99, 102, 241, 0.5)`).

## 6. App Integration Checklist

When integrating new devtools panels:
1. **Tabs**: Add new tab types to the main `Tab` union type.
2. **Navigation**: Add sidebar nav links separated by a "Developer Tools" header.
3. **Routing**: Add panel rendering conditionals based on the active tab.
4. **Imports**: Ensure all new components are correctly imported.
5. **Styles**: Add necessary CSS styles for new elements to the global or scoped stylesheet.

## 7. Styling Guidelines

Aim for a premium, modern design aesthetic:
- **Theme**: Glassmorphism dark theme (rgba backgrounds, backdrop blur, subtle borders).
- **Color Palette**:
  - Indigo: `#6366f1`
  - Emerald: `#10b981`
  - Red: `#ef4444`
  - Amber: `#f59e0b`
  - Magenta: `#d946ef`
- **Scoped Styles**: Use component-scoped styles or inline `<style>` blocks when appropriate.
- **Interactivity**: Add micro-animations and hover effects (e.g., `transition: all 0.3s ease`, `transform: translateY(-2px)` on hover) for a premium feel.
