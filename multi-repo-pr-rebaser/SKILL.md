---
name: multi-repo-pr-rebaser
description: Executes automated multi-repository PR rebase and merge-conflict resolution using merge_master_into_prs.py across DDD mono and poly-repos, automatically resolving lockfile and .jules/*.md conflict paths.
---

# Multi-Repo PR Rebaser

This skill provides automated commands for rebasing and synchronizing open Pull Request branches against `main`/`master` across repositories, automatically resolving `.jules/*.md`, `.Jules/*.md`, and polyglot lockfile conflict paths.

---

## Execution Workflow

### 1. Run Automated Rebase Script
Run `merge_master_into_prs.py` from the target repository directory:

```bash
# For repositories with target branch 'main':
python "C:\Users\johns\.gemini\config\skills\pr-merge-conflict-resolver\scripts\merge_master_into_prs.py" main

# For repositories with target branch 'master':
python "C:\Users\johns\.gemini\config\skills\pr-merge-conflict-resolver\scripts\merge_master_into_prs.py" master
```

### 2. Manual Conflict Resolution Protocol (for non-automated conflicts)
If a feature branch experiences an unhandled merge conflict:

```bash
# Checkout feature branch
gh pr checkout <PR_NUMBER>

# Force-checkout clean copies of target branch config/schema/lockfiles
git checkout origin/main -- .jules/bolt.md .Jules/palette.md pnpm-lock.yaml package-lock.json composer.lock package.json docker/postgres/init/

# Complete merge and push
git commit -m "fix(merge): resolve config/schema conflicts with target branch"
git push origin HEAD -f
```
