---
name: submodule-parent-tree-syncer
description: >
  Standardizes and automates submodule pointer fast-forwarding, detached HEAD reconciliation, dirty worktree cleanup, and atomic parent repository tree synchronization across multi-submodule projects. Activate when submodules drift out of sync after merging PRs or when updating parent repository submodule pointers.
---

# Submodule Parent Tree Syncer

This skill provides an automated workflow to audit, synchronize, fast-forward, and commit submodule tracking pointers (`gitlinks`) in parent repositories after remote Pull Request merges.

---

## When to Use

1. **Post-Merge Submodule Drift**: Pull Requests were merged across multiple submodule repositories (e.g. `gql-ddd-inventory`, `js-ddd-inventory`, `php-ddd-inventory`), leaving parent repo gitlinks pointed at older commits.
2. **Detached HEAD Reconciliation**: Submodules are checked out on detached PR branches or temporary commit hashes instead of their default tracking branches (`main` or `master`).
3. **Atomic Submodule Pointer Updates**: Staging and committing all updated submodule SHA pointers in the parent repository with a single unified commit.

---

## Workflow Procedure

### Step 1: Audit Submodule Tree Status
Inspect the parent repository and all registered submodules to check branch alignment, dirty worktrees, and pointer states:

```bash
python C:/Users/johns/.gemini/config/skills/submodule-parent-tree-syncer/scripts/submodule_tree_syncer.py status \
  --base-dir C:/Users/johns/DEV/inventory \
  --check-remote \
  --output submodule_status.json
```

### Step 2: Synchronize and Fast-Forward Submodules
Fast-forward each submodule to its latest remote tracking branch (`origin/main` or `origin/master`), discard local scratch files with `--clean` if needed, and stage updated gitlinks in the parent repo:

```bash
# Sync submodules without committing to parent repo
python C:/Users/johns/.gemini/config/skills/submodule-parent-tree-syncer/scripts/submodule_tree_syncer.py sync \
  --base-dir C:/Users/johns/DEV/inventory \
  --clean
```

### Step 3: Atomic Parent Commit & Push
Synchronize submodules, commit updated gitlinks on the parent repository, and push upstream:

```bash
python C:/Users/johns/.gemini/config/skills/submodule-parent-tree-syncer/scripts/submodule_tree_syncer.py sync \
  --base-dir C:/Users/johns/DEV/inventory \
  --clean \
  --commit \
  --push \
  --message "chore(submodules): synchronize submodule trees to latest upstream commits"
```

---

## Command Reference

| Subcommand | Flag | Description |
| :--- | :--- | :--- |
| `status` | `--base-dir` | Path to parent repository root (default: current directory). |
| `status` | `--check-remote` | Queries remote default branches (`ls-remote`) to detect upstream SHA drift. |
| `status` | `--output` | File path to write JSON status report. |
| `sync` | `--clean` | Discards untracked / dirty files before checkout and pull. |
| `sync` | `--commit` | Stages and commits changed submodule pointers in parent repository (automatically validates that each submodule commit exists on `origin` before staging). |
| `sync` | `--push` | Pushes the parent repository commit upstream. |
| `sync` | `--message` | Custom commit message for the parent repository. |

---

## Safety Guardrails
- **Unpushed Commit Guard**: Before staging any submodule gitlink in the parent repository, `submodule_tree_syncer.py` verifies that the commit hash has been pushed to the remote origin (`git branch -r --contains <SHA>` or `git ls-remote`). If unpushed local commits are detected, it skips staging that submodule to prevent GitHub Actions checkout failure (`fatal: remote error: upload-pack: not our ref`).
- **Transient Artifact & Dump Purging**: When syncing with `--clean`, automatically removes volatile database backup dumps (`infra/db/backups`), test run caches (`.pytest_cache`, `coverage`), and temporary logs to prevent false dirty worktree warnings.
- **Heterogeneous Default Branch Resolution**: Dynamically checks upstream symbolic refs (`refs/remotes/origin/HEAD`) and GitHub repository metadata (`gh repo view`) to accurately resolve mixed `main` and `master` default branches without hardcoding.

---

## Alternative: Native Bash Batch Fast-Forward

If the python scripts are unavailable, you can use this native bash snippet to parse `.gitmodules`, determine the correct branch for each submodule, pull the changes in parallel, and stage them:

```bash
git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}' | while read path; do
  branch=$(git config -f .gitmodules --get "submodule.$path.branch" || echo "main")
  echo "Syncing $path on branch $branch..."
  git -C "$path" checkout "$branch" && git -C "$path" pull origin "$branch" &
done
wait
echo "Staging updated submodule pointers..."
git add $(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')
```

