---
name: multi-repo-security-patcher
description: >
  Audits, plans, patches, and verifies security vulnerabilities across multi-repo and mono-repo ecosystems via GitHub Dependabot API, dependency overrides, automated bot PR merging, and parent submodule pointer synchronization.
---

# Multi-Repo Security Patcher

This skill provides an end-to-end automated workflow for scanning GitHub organizations and multi-repository workspaces for open security vulnerabilities (Dependabot alerts), generating safe non-breaking remediation plans, applying package manager overrides or merging vetted security PRs, and synchronizing parent submodule pointers.

---

## Capabilities

1. **Dependabot Vulnerability Auditing**:
   - Queries GitHub Dependabot API across all repositories under an owner or organization.
   - Categorizes alerts by severity (`CRITICAL`, `HIGH`, `MODERATE`, `LOW`) and extracts CVEs, GHSAs, affected packages, and first patched versions.
   - Exports machine-readable JSON and formatted Markdown tables.

2. **Remediation Planning**:
   - Analyzes open alerts to identify minimal non-breaking transitive dependency overrides (e.g. `overrides` in `package.json` or `pnpm.overrides`).
   - Identifies open, ready-to-merge Dependabot Pull Requests.

3. **Remediation Execution**:
   - Safely injects targeted override specifications into `package.json` without mutating unrelated dependency constraints.
   - Executes lockfile-only updates (`npm install --package-lock-only` or `pnpm install --lockfile-only`).
   - Merges verified Dependabot PRs using `gh pr merge --admin --squash`.
   - Optionally commits and pushes security fixes to remote branches.

4. **Parent Submodule Pointer Synchronization**:
   - Scans parent repositories containing git submodules.
   - Detects dirty or advanced submodule pointers after security updates and commits/pushes atomic pointer updates to the parent repository.

---

## CLI Usage

The skill is driven by `scripts/security_patcher.py`:

### 1. Audit Vulnerabilities Across Repositories
```bash
python C:/Users/johns/.gemini/config/skills/multi-repo-security-patcher/scripts/security_patcher.py audit \
  --owner bjohnson1279 \
  --output audit.json \
  --markdown-output security_audit.md
```

### 2. Formulate Remediation Plan
```bash
python C:/Users/johns/.gemini/config/skills/multi-repo-security-patcher/scripts/security_patcher.py plan \
  --input-file audit.json \
  --output remediation_plan.json
```

### 3. Apply Remediation Plan (with Auto Commit & Push)
```bash
python C:/Users/johns/.gemini/config/skills/multi-repo-security-patcher/scripts/security_patcher.py apply \
  --plan-file remediation_plan.json \
  --base-dir C:/Users/johns/DEV \
  --commit \
  --push
```

### 4. Synchronize Submodule Pointers in Parent Repositories
```bash
python C:/Users/johns/.gemini/config/skills/multi-repo-security-patcher/scripts/security_patcher.py sync-submodules \
  --parent-dir C:/Users/johns/DEV/inventory \
  --push
```
