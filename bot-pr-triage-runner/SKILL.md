---
name: bot-pr-triage-runner
description: >
  Audits, categorizes, syncs stale bases, and batch-processes open Pull Requests from automated bots (Jules, Sentinel, Dependabot) across GitHub repositories with mandatory user confirmation prompts before execution.
---

# Bot PR Triage & Batch Merge Runner

This skill provides an automated workflow to discover, audit, categorize, base-sync, and batch process open Pull Requests from automated agents across GitHub owner repositories.

---

## Workflow Procedure

### Step 1: Discover & Audit Open PRs
Run the helper script to search open PRs with optional workspace / repository filtering or direct single-repo query:

```bash
# Search open PRs across an entire owner/org (with auto-fallback to direct repo lists if search times out)
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py search \
  --owner bjohnson1279 \
  --state open \
  --limit 100 \
  --workspace-filter C:/Users/johns/DEV/inventory \
  --output open_prs.json

# Or query a specific repository directly (fast path avoiding search API timeouts)
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py search \
  --owner bjohnson1279 \
  --repo bjohnson1279/ams-proto \
  --state open \
  --limit 50 \
  --output open_prs.json

# Audit diffs, CI checks, and run in-memory 3-way merge conflict detection (git merge-tree)
# Pass --verify-local-tests for targeted unit tests and --check-security for Dependabot alert auditing
# Pass --wait-ci to actively monitor and wait for in-flight CI checks before finalizing categorization
# (Auto-detects TypeScript/Vitest vs Jest, dynamically discovers Windows PHP extensions for PHPUnit, pytest, and Elixir)
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py audit \
  --input-file open_prs.json \
  --output audited_prs.json \
  --base-dir C:/Users/johns/DEV/inventory \
  --verify-local-tests \
  --check-security \
  --wait-ci \
  --markdown-output triage_report.md
```

### Step 1.5: CI Watchdog & In-Flight Commit Monitoring (Optional)
When bot PRs have checks in-progress or have recently pushed self-healing commits, monitor them until full completion:

```bash
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py watch-ci \
  --pr-list "bjohnson1279/gql-ddd-inventory#677,bjohnson1279/react-ddd-inventory-client#228" \
  --timeout 300
```

### Step 2: Categorize PRs
The audit step classifies PRs into four groups:
1. **Group A: Safe & High Value (MERGE)**
   - All CI checks passed (`SUCCESS`).
   - Guardrail check passed (`audit-bot-pr`).
   - Valid code changes (performance, security, accessibility, or unit tests).
2. **Group A (CI In-Progress / Bot Self-Healing In-Flight)**
   - Checks currently executing (`IN_PROGRESS`, `QUEUED`, `PENDING`), or bot pushed self-healing commit pending CI.
3. **Group A (Needs Base Sync)**
   - Failed CI strictly due to stale base commit (e.g. historical conflict markers in base branch).
   - Clean 3-way merge against latest remote base.
4. **Group B: Destructive or Defective (CLOSE / HARMONIZE)**
   - Fails CI build or unit tests due to actual code defects.
   - Strips required environment fallback secrets without development mocks.
   - Contains uncleaned scratch or benchmark verification files (`test_*.ts`, `test*.cjs`, `fix_*.php`, `update_*.php`).
   - Deletes >15 lines from critical entrypoint or schema files.
5. **Group C: Zero-Diff / Hallucinatory / Superseded (CLOSE)**
   - **Zero-Diff**: Contains 0 code diffs outside `.jules/` log files, lockfiles, or root scratch files.
   - **Superseded**: Substantive code changes were already merged via a duplicate or successor PR into the target base branch, or superseded by a superior sibling PR in the same batch with an in-memory `git merge-tree` conflict.

---

### Step 2.5: Auto-Repair Corrupted or Stale PR Branches (Optional)
When PRs are flagged in Group B due to dangling conflict markers (`<<<<<<< HEAD`, `=======`, `>>>>>>>`) or repetitive hallucinated comment bloat, run the automated auto-repair script:

```bash
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py auto-repair \
  --pr-list "bjohnson1279/react-ddd-inventory-client#111,bjohnson1279/php-ddd-inventory#524" \
  --base-dir C:/Users/johns/DEV/inventory
```

#### Smart Union Merge Tool for `.jules/*.md`:
Resolve merge conflicts on agent memory files additively without manual editing:
```bash
# In-place file resolution:
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/smart_union_merge.py file path/to/.jules/bolt.md

# Or via triage_runner CLI:
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py union-merge --file path/to/.jules/bolt.md

# Configure Git Custom Merge Driver for .jules/*.md across repos:
git config merge.jules-union.name "Smart Jules Markdown Union Driver"
git config merge.jules-union.driver "python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/smart_union_merge.py driver %O %A %B %P"
# In .gitattributes:
# .jules/*.md merge=jules-union
# .Jules/*.md merge=jules-union
```

#### Automated Repair Capabilities:
- **Dangling Conflict Markers**: Scans modified files and strips stray `<<<<<<<`, `=======`, `>>>>>>>` lines left by automated bot commit collisions.
- **Smart Markdown Log Unioning**: Additively merges dated learnings (`## YYYY-MM-DD - ...`) and deduplicates directives at the bottom of the document.
- **Case-Collision Index Harmonization (`.jules/` vs `.Jules/`)**: Detects colliding tree entries on case-insensitive filesystems (Windows/macOS), unifies markdown learning notes into canonical `.jules/`, and cleans index caches.
  ```bash
  python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py harmonize-case --base-dir C:/Users/johns/DEV/inventory
  ```
- **Repetitive Bloat Deduplication**: Truncates runs of >10 identical comment or stub lines hallucinated during bot generation loops.
- **Git Lock Cleanup**: Auto-removes orphaned `.git/refs/**/*.lock` files on Windows hosts that block git checkout/fetch operations.
- **Agent Rule Preservation**: Unifies `.jules/*.md` learning notes from `HEAD` and `base` without overwriting historical insights.

---

## Step 3: Mandatory User Confirmation Prompt

> [!IMPORTANT]
> **DO NOT** execute batch merges or closures automatically. Present the categorized table to the user and request explicit confirmation:
> `"Would you like me to proceed with merging the Group A PRs and closing Group B/C PRs?"`

---

## Step 4: Base Sync & Batch Execution (After Confirmation)

### 1. Sync Stale PR Branches with Remote Base (with Smart Conflict Unioning)
The `sync-base` runner automatically resolves lockfile conflicts from base and unions `.jules/*.md` learning notes from both `HEAD` and `base`:
```bash
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py sync-base \
  --pr-list "bjohnson1279/php-ddd-inventory#523" \
  --base-dir C:/Users/johns/DEV/inventory
```
* **Auto-Resolvable Files**: Lockfiles (`pnpm-lock.yaml`, `package-lock.json`, `composer.lock`, `mix.lock`) are checked out clean from `origin/<base>`.
* **Agent Memory**: Agent learning files (`.jules/*.md`) are parsed and merged to preserve all unique timestamped insights.
* **Test Method Union Splicer**: Non-conflicting test methods added to the same test file across sibling PRs (PHPUnit, pytest, Jest/Vitest) are automatically detected and spliced into a unified test class without manual intervention.
* **Diff Purification**: Automatically prints the purified diff against `origin/<base>` to verify irrelevant overlapping changes are pruned.


### 2. Merge Safe Group A PRs (with Disjoint Fast-Path, Base Sync & Sequential Rebase Recovery)
```bash
# Option A: Merge all audited Group A (Clean & Safe) PRs directly from audited JSON:
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py merge-batch \
  --input-file audited_prs.json \
  --base-dir C:/Users/johns/DEV/inventory \
  --run-tests \
  --sync-submodules \
  --push-parent

# Option B: Merge a specific explicit PR list:
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py merge-batch \
  --pr-list "bjohnson1279/js-ddd-inventory#618,bjohnson1279/gql-ddd-inventory#552" \
  --base-dir C:/Users/johns/DEV/inventory \
  --sync-submodules \
  --push-parent
```
* **Post-Merge Full Test Suite Execution (`--run-tests`)**: Automatically triggers full polyglot test runners (`vitest run`, `jest`, `phpunit`, `pytest`, `mix test`) across all modified repositories after merging to confirm zero introduced regressions (with Windows `--no-file-parallelism` safety for Vitest).
* **Dependabot Security Patch Auditing (`--check-security`)**: Integrates real-time GitHub Dependabot API vulnerability checks during triage to flag repositories with open High/Critical alerts.
* **Concurrent Pairwise Disjoint Evaluation**: Fetches modified PR file manifests in parallel using thread pools with live streaming progress, determining zero-ordering-hazard fast paths.
* **Resilient Admin Downgrade & Sequential Rebase**: Attempts `--admin --merge` first, automatically downgrades to standard `--merge` if administrator privileges are not needed or restricted, and executes sequential re-sync and isolated diff rebasing upon base advance conflicts.
* **Local Branch Auto-Pruning**: Automatically cleans up temporary local testing branches (e.g. `pr-<number>`) in local submodules once remote merge completes.
* **Submodule Pointer Auto-Advance (`--sync-submodules`)**: Pulls merged commits into all local submodule clones and commits updated pointers in the parent repository.
* **Parent Push (`--push-parent`)**: Automatically pushes parent repository pointer updates to `origin/main`.

### 3. Direct GitHub CLI Fast Merge & Local Sync (Single / Disjoint Repos)
For standalone repositories with disjoint PRs, use the GitHub CLI directly:
```bash
# Squash or merge commit and delete remote branch
gh pr merge 13 --merge --delete-branch
gh pr merge 14 --merge --delete-branch

# Post-Merge Working Tree Hygiene & Fast-Forward Local Main
# (Cleans transient lockfiles/build artifacts generated during local test runs before pulling)
git checkout -- .
git clean -fd
git pull origin main

# Post-Merge Test Augmentation & Precommit Verification
# (Add unit test assertions for new bot features e.g. a11y attributes, helper formatting, then run precommit)
docker compose run --rm app mix precommit  # Or: npm test / vendor/bin/phpunit
```

### 4. Close Destructive / Zero-Diff Group B & C PRs
```bash
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py close-batch \
  --pr-list "bjohnson1279/repo#123" \
  --reason "Closing due to 0-diff task acknowledgment or failed CI checks."
```


---

## Step 5: Harvest Stalled or Orphaned Remote Branches (Recovery)

When PRs are closed due to historical merge conflicts or stale base branches, valuable logic (such as N+1 optimizations, missing security headers, or missing unit tests) may remain orphaned on remote branches.

Use the `harvest` command to scan a repository's remote branches for unmerged commits:

```bash
python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/triage_runner.py harvest \
  --base-dir C:/Users/johns/DEV/inventory/react-ddd-inventory-client \
  --base-branch main \
  --output harvest_report.json
```

#### Harvest Capabilities:
1. **Remote Branch Enumeration**: Scans all `origin/*` branches and filters for those with commits ahead of the base branch (`git log origin/main..<branch>`).
2. **Merge-Tree Simulation**: Evaluates `git merge-tree` to determine whether the unmerged commits merge cleanly or contain conflicts.
3. **Diff Stat Summaries**: Summarizes line changes and modified files to quickly isolate high-value code patches for cherry-picking or manual reconciliation into `main`.
