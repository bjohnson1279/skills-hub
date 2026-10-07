---
name: npm-deep-audit-remediator
description: >-
  Automates the resolution of deep, transitive NPM vulnerabilities by analyzing npm audit --json, tracing blocking top-level dependencies, auto-applying minor/patch updates, and prompting the user before crossing major version boundaries.
---

# NPM Deep Audit Remediator

## Overview
Automates the resolution of deep, transitive NPM vulnerabilities. Standard `npm audit fix` cannot resolve vulnerabilities blocked by top-level packages relying on outdated minor/patch versions. This skill analyzes the audit tree, determines the top-level blockers, queries the NPM registry for updates, and automatically applies safe (minor/patch) updates.

## Dependencies
None.

## Quick Start
1. Generate the audit file:
   `npm audit --json > audit.json`
2. Analyze the audit output:
   `uv run python C:\Users\johns\.gemini\config\skills\npm-deep-audit-remediator\scripts\audit-remediator.py analyze --audit-file audit.json --output update_plan.json`
3. Apply the safe updates:
   `uv run python C:\Users\johns\.gemini\config\skills\npm-deep-audit-remediator\scripts\audit-remediator.py apply-safe --plan update_plan.json`

## Utility Scripts

### `analyze`
Parses the audit JSON, queries the public NPM registry, and generates a plan.

**Arguments:**
- `--audit-file`: Path to npm audit --json output
- `--output`: Path to write the JSON plan file

### `apply-safe`
Executes `npm install` for all packages identified as safe minor/patch upgrades.

**Arguments:**
- `--plan`: Path to the JSON plan file

## Rate Limiting
The `analyze` script queries `registry.npmjs.org` and enforces a strict limit of 10 requests per second across the script using `time.monotonic()`. It implements exponential backoff on HTTP 429 and 5xx errors.

## Common Mistakes
- **Forgetting to regenerate the audit**: Always run `npm audit --json > audit.json` right before running `analyze`, as dependency trees change rapidly.
- **Skipping breaking updates**: If `breaking_updates` are found in the plan, you must pause execution and ask the user for permission before applying them manually.
