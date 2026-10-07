---
name: in-memory-pr-merge-simulator
description: >
  Simulates git 3-way branch and pull request merges entirely in-memory using git merge-tree, evaluates pairwise file overlap across batch candidate PRs, and verifies clean mergeability without checking out branches or mutating the local working tree.
---

# In-Memory PR Merge Simulator

This skill provides diagnostic procedures and Python CLI utilities to test Git 3-way mergeability entirely in-memory using `git merge-tree` and `git merge-base`. It eliminates the risk of working-tree corruption, dirty state, or build-watcher triggers when auditing open Pull Requests and evaluating batch merge candidates.

---

## When to Activate

Activate this skill when:
- Auditing multiple open Pull Requests to verify whether they can merge cleanly into `main` / `master`.
- Planning sequential batch merges across $N$ candidate PRs to verify that their modified file sets are disjoint (zero mid-batch merge conflicts).
- Checking mergeability in continuous integration or local development without checking out branches or touching files on disk.

---

## In-Memory 3-Way Merge Mechanics

Instead of executing `git checkout <branch>` and `git merge <base>`, Git provides `git merge-tree` to compute the exact 3-way merge result directly from Git object storage:

```bash
# 1. Compute common ancestor merge base commit
MERGE_BASE=$(git merge-base main origin/<feature-branch>)

# 2. Simulate 3-way merge in-memory (exit code 1 indicates conflicts)
git merge-tree "$MERGE_BASE" main origin/<feature-branch>
```

### Interpretation:
- **Clean Merge**: The command returns **exit code 0**. The output contains the merged tree object hash and diffs.
- **Merge Conflict**: The command returns **exit code 1**. Standard output will contain `CONFLICT (content): Merge conflict in <file>` detailing exactly which files and lines collide. Do not solely rely on searching for `<<<<<<<` markers, as `merge-tree` signals conflicts structurally via the exit code and `CONFLICT` text.

> [!WARNING] Python Subprocess Encoding on Windows
> When wrapping `git merge-tree` or GitHub CLI (`gh`) commands in Python scripts on Windows, always explicitly specify `encoding='utf-8', errors='replace'` in `subprocess.run(text=True)`. CLI outputs (like PR titles or commit messages) frequently contain UTF-8 emojis (⚡, 🛡️) that will cause a fatal `UnicodeDecodeError` under the default Windows `cp1252` encoding.

---

## CLI Utility Runner

The bundled helper script automates multi-branch simulation and pairwise disjoint diff analysis:

```bash
# Simulate all candidate PR branches in-memory against main
python C:/Users/johns/.gemini/config/skills/in-memory-pr-merge-simulator/scripts/merge_simulator.py simulate \
  --base main \
  --branches "origin/sentinel-fix-sql-injection-rls-session,origin/bolt/optimize-ams-filters,origin/palette-ux-improvements" \
  --repo-dir C:/Users/johns/DEV/ams-proto \
  --output simulation_results.json
```

### CLI Output Capabilities:
1. **Per-Branch Merge Cleanliness**: Reports `✅ CLEAN` or `❌ CONFLICTS` with specific line numbers and conflict snippets.
2. **Pairwise Disjoint File Sets**: Identifies whether candidate PRs modify non-overlapping files (ignoring additive agent notes like `.jules/*.md`), proving that merging PR 1 will not invalidate PR 2.
3. **Disjoint Cluster Partitioning**: Groups $N$ PRs into mathematically independent batches (connected components) to parallelize review or fast-path batch merging.
4. **Structured JSON Output**: Saves complete machine-readable audit reports for agent consumption.

---

## Sequential Batch Merging Guidelines

When merging $N$ PRs in a batch:
1. **Disjoint Sets**: If pairwise analysis shows 100% disjoint code paths, PRs can be merged sequentially via `gh pr merge <NUM> --merge --delete-branch` without intermediate branch rebasing.
2. **Overlapping Sets**: If PRs touch the same source files (e.g. `ams.service.ts`), merge PR 1 first, fetch `origin/main`, re-run `merge_simulator.py` on PR 2 against the advanced `main` commit, and only proceed if clean.

---

## Common Pitfalls

1. **Stale Remote References**: Always run `git fetch origin` prior to simulation to ensure all remote tracking branch heads (`origin/<branch>`) reflect their latest commits.
2. **Agent Learning Logs (`.jules/*.md`)**: Learning logs often collide if multiple PRs add entries on the same date. Filter out `.jules/` when assessing code mergeability, and union log entries additively during final merge reconciliation.
