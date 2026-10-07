---
name: multi-submodule-hygiene-and-pointer-syncer
description: >
  Audits submodule working trees for untracked content, local file modifications, git lockfiles, and remote drift. Automatically cleans transient artifacts, updates gitignores, pulls default branches, and atomically synchronizes parent repository tree pointers.
---

# Multi-Submodule Hygiene & Pointer Syncer

This skill audits, cleans, and harmonizes multi-submodule Git repository architectures. It identifies untracked configuration files (e.g. `pytest.ini`), discards unwanted test artifact modifications, cleans orphaned Windows Git locks, and fast-forwards parent submodule pointers in an atomic commit.

---

## Quick Start

### 1. Scan Submodule Hygiene & Pointer Status
```bash
python C:/Users/johns/.gemini/config/skills/multi-submodule-hygiene-and-pointer-syncer/scripts/submodule_syncer.py scan   --workspace-dir C:/Users/johns/DEV/inventory   --markdown-output submodule_hygiene_report.md
```

### 2. Clean Git Locks, Reset Modified Working Trees & Prune Transient Dumps
```bash
python C:/Users/johns/.gemini/config/skills/multi-submodule-hygiene-and-pointer-syncer/scripts/submodule_syncer.py clean \
  --workspace-dir C:/Users/johns/DEV/inventory \
  --restore-tracked \
  --clean-transient
```

### 3. Sync Remote Default Branches & Commit Parent Tree Pointers
```bash
python C:/Users/johns/.gemini/config/skills/multi-submodule-hygiene-and-pointer-syncer/scripts/submodule_syncer.py sync   --workspace-dir C:/Users/johns/DEV/inventory   --push
```

---

## Utility Commands

| Command | Purpose | Key Arguments |
| :--- | :--- | :--- |
| `scan` | Detects `UNTRACKED_CONTENT`, `MODIFIED_CONTENT`, detached HEADs, and remote drift | `--workspace-dir`, `--output`, `--markdown-output` |
| `clean` | Removes Windows `.git/*.lock` files, restores tracked files, and prunes transient dumps | `--workspace-dir`, `--restore-tracked`, `--clean-transient` |
| `sync` | Checks out default branch, pulls latest remote, stages pointers in parent, and commits | `--workspace-dir`, `--push`, `--dry-run` |

---

## Common Edge Cases & Handling

1. **Untracked Critical Files (e.g. `pytest.ini`)**: `scan` will report `UNTRACKED_CONTENT`. These should be committed to the submodule before running `sync`.
2. **Local Backup Dumps / Transient Logs**: Pass `--clean-transient` to prune volatile database dumps (`infra/db/backups/*.sql.gz`), test caches (`.pytest_cache`), and log files without touching uncommitted source code.
3. **Detached HEAD State**: `sync` automatically determines the upstream default branch (`main` or `master`) and checks it out cleanly.
