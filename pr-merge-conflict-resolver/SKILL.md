---
name: pr-merge-conflict-resolver
description: Automatically check and resolve merge conflicts, stale lockfiles, and corrupted DDL schemas between master/main branch and all open Pull Requests across any repository.
---

# Pull Request Merge Conflict & Lockfile Resolver

This skill provides step-by-step git workflows to checkout open Pull Requests, resolve merge conflicts, replace corrupted lockfiles/DDLs with clean target branch versions, and push fixes directly to remote PR feature branches.

## Common Use Cases

1. **Stale/Corrupted Lockfiles in PRs**:
   Open PRs throw `ERR_PNPM_OUTDATED_LOCKFILE` or `duplicated mapping key` because the feature branch's `pnpm-lock.yaml` or `package.json` was out of sync with `main`/`master`.

2. **Outdated Feature Branch Schemas**:
   Open PRs fail DB schema application steps in CI because `main`/`master` updated database DDLs (e.g. `docker/postgres/init/*.sql`), but the PR feature branch still runs outdated SQL definitions.

3. **TypeScript Test Syntax Merges**:
   Git auto-merges left syntax artifacts or duplicated test blocks inside test suites on PR branches.

---

## Workflow for Repairing Open PR Branches

### Step 0: Pre-Flight Supersession & Redundancy Check
Before resolving conflicts, check if the PR's substantive changes were already merged via a duplicate or successor PR into `main`/`master`:
```bash
# Check if substantive diff is empty against main/master
git diff origin/main...origin/<FEATURE_BRANCH_NAME> -- ':!.jules/' ':!package-lock.json' ':!pnpm-lock.yaml'

# Check recent commit history on target files in main
git log origin/main -n 5 -- <MODIFIED_FILES>
```
* If all substantive code changes are already present on `origin/main`, **do not merge or rebase**. Close the PR as superseded referencing the merged successor PR/commit:
  ```bash
  gh pr close <PR_NUMBER> --comment "Closing as superseded: changes already merged into main via commit <HASH>."
  ```

### Step 1: Fetch and Checkout the Target PR Branch
Fetch the remote pull request reference into a local working branch:
```bash
git fetch origin pull/<PR_NUMBER>/head:pr-<PR_NUMBER>
git checkout <FEATURE_BRANCH_NAME>
```

### Step 2: Reset Corrupted Configuration Files or Union Markdown Logs
To immediately eliminate lockfile mismatches or broken DDL schemas on the PR branch, force-checkout clean copies from `origin/main` (or `origin/master`):
```bash
# For pnpm / npm lockfiles and package.json:
git checkout origin/main -- pnpm-lock.yaml package.json mix.lock composer.lock

# For database initialization DDLs:
git checkout origin/main -- docker/postgres/init/
```

#### Additive Reconciliation for Agent Logs (`.jules/*.md` vs `.Jules/*.md`)
**Never discard either branch's learning entries.** When multiple bot PRs introduce learning notes into `.jules/<bot>.md` (e.g., `bolt.md`, `palette.md`, `sentinel.md`):
1. **Case-Collision Index Detection (Windows/macOS)**:
   Automated bots may commit under `.Jules/` (uppercase `J`) as a standalone file while the base repository tracks `.jules/` (lowercase). On case-insensitive filesystems, check for duplicate index entries:
   ```bash
   git ls-files .jules .Jules
   ```
2. **Harmonize Index Entries**:
   Remove the uppercase cached entry without deleting local files:
   ```bash
   git rm --cached .Jules/*.md
   ```
3. **Additive Reconciliation (Automated Smart Union)**:
   Use the Smart Union Merge Tool to automatically resolve in-place conflicts while preserving all timestamped learnings, deduping directives, and placing guardrails cleanly at the bottom:
   ```bash
   # Automated in-place conflict resolution:
   python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/smart_union_merge.py file .jules/bolt.md

   # Or configure the Git Custom Merge Driver across repositories:
   git config merge.jules-union.name "Smart Jules Markdown Union Driver"
   git config merge.jules-union.driver "python C:/Users/johns/.gemini/config/skills/bot-pr-triage-runner/scripts/smart_union_merge.py driver %O %A %B %P"
   # In .gitattributes:
   # .jules/*.md merge=jules-union
   ```
4. **Stage and Commit Canonical Path**:
   ```bash
   git add .jules/*.md
   git commit -m "fix(jules): harmonize .Jules/ to .jules/ and unify historical agent notes"
   ```


#### Cumulative Test Suite Merging (`*test*.exs`, `*.test.ts`, `*Test.php`, `test_*.sh`, `*.bats`)
When `main`/`master` and the PR branch both add new test cases or assertion strategies into the same test file:
1. **Cumulative Assertions**: Keep **both** sets of test cases/assertions (e.g. structured JSON validation alongside raw `--no-json` variable assertions) rather than choosing one.
2. **Isolated Shell Function Extractions**: If merge conflicts occur in `sed -n` function extractions:
   - Harmonize into a single sequential multi-pattern extractor: `sed -n '/^cleanup_name() {/,/^}/p; /^json_escape() {/,/^}/p; /^parseFilename() {/,/^}/p' script.sh > "$TMP_FILE"`
   - Resolve all prerequisite helper subroutines in declaration order using `bash-isolated-test-harmonizer` (`python .agents/skills/bash-isolated-test-harmonizer/scripts/test_harmonizer.py audit`).
3. **Execute Pre-Commit Verification**: Run the repository's verification command (`mix precommit`, `pnpm test`, `npm test`, `./vendor/bin/phpunit`, or `python .agents/skills/bash-isolated-test-harmonizer/scripts/test_harmonizer.py verify`) to confirm cumulative test suites pass with zero regressions.

### Step 3: Rebase or Merge Target Branch
Merge latest changes from `main`/`master` into the feature branch:
```bash
git fetch origin main
git merge origin/main
```

### Step 4: Diff Purification & Verification
Verify that merging `origin/main` cleanly isolated the PR's true intended changes and pruned already-merged overlapping diffs:
```bash
git diff origin/main..HEAD --stat
```
Confirm that:
1. Unrelated files already integrated into `main` (e.g. earlier PRs' UI or test tweaks) have dropped out of the diff.
2. Only the PR's core domain features and corresponding test suites remain.

#### Pre-Commit Conflict Marker Verification
Always run an automated scan across tracked files before committing any conflict resolution:
```bash
if git grep -n -I -E '^(<{7}|={7}|>{7}|\|{7})([[:space:]]|$)'; then
  echo "❌ ERROR: Residual conflict markers detected!"
  exit 1
fi
```

### Step 5: Handling Stash Collisions & Agent Directive Reconciliations
When pulling upstream changes while local modifications or stash entries exist on `.jules/*.md`:
1. If `git stash pop` flags a merge conflict in `.jules/bolt.md` or `.jules/sentinel.md`:
   - Inspect the conflict block: upstream usually adds global prevention directives (e.g. `## Prevention Directives for Automated Refactoring`) while the stashed changes contain a newly minted task learning (`## YYYY-MM-DD - ...`).
   - **Do not overwrite or drop either section.**
   - Retain the new learning note under its timestamp, and keep the upstream prevention directives at the bottom.
2. Re-verify that all markers (`<<<<<<<`, `=======`, `>>>>>>>`) are removed.
3. Stage and commit:
   ```bash
   git add .jules/*.md
   ```

### Step 6: Commit and Push to Remote Feature Branch
Commit the clean configurations and push directly to the remote PR branch:
```bash
git commit -m "fix(ci): synchronize lockfile, jules notes, and schema configurations with main"
git push origin <FEATURE_BRANCH_NAME>
```

### Step 7: Sequential PR Merging & Mid-Batch Re-syncing

When processing multiple PRs in a batch:
1. Merging PR #1 advances `main`/`master`, which immediately causes PR #2 to become conflicting or unmergeable on GitHub (`the merge commit cannot be cleanly created`).
2. For each successive PR:
   ```bash
   git checkout <NEXT_FEATURE_BRANCH>
   git fetch origin main
   git merge origin/main
   # Run repo test suite
   mix precommit # or pnpm test / phpunit
   git push origin <NEXT_FEATURE_BRANCH>
   gh pr merge <NEXT_PR_NUMBER> --merge --delete-branch
   ```


## Dependencies
- **exact-merge-conflict-resolver**: When resolving syntax artifacts (<<<<<<< HEAD), always use `uv run python C:\Users\johns\.gemini\config\skills\exact-merge-conflict-resolver\scripts\conflict-splicer.py splice` instead of standard text replacement, as standard replacement often fails on corrupted syntax.
