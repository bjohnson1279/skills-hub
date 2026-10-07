---
name: multi-repo-ci-step-harmonizer
description: Automates discovering, injecting, and synchronizing standardized CI pipeline steps (e.g. merge conflict scans, linter gates, security audits) across polyglot repositories and multi-submodule projects.
---

# Multi-Repo CI Step Harmonizer

This skill standardizes the process of querying all repositories in a GitHub account or organization, discovering their primary CI pipelines, idempotently injecting verification steps (such as merge conflict scans or linter checks), and committing/pushing across protected branches with submodule pointer synchronization.

---

## Capabilities & Architecture

1. **Repository & Pipeline Discovery**:
   - Queries GitHub CLI (`gh repo list`) for active, non-archived repositories.
   - Discovers default branch (`main` vs `master`) and active workflow definitions (`.github/workflows/*.yml`).

2. **Idempotent Step Injection**:
   - Checks if the rule/step is already present prior to modification to prevent duplicate execution blocks.
   - Injects the step immediately after the code checkout step (`actions/checkout@v4`).

3. **Branch Protection & Rebase Synchronization**:
   - Seamlessly handles admin push rule bypasses (`current_user_can_bypass`).
   - Automatically stashes uncommitted local development artifacts (database dumps, temporary logs) before rebasing against remote changes.

4. **Atomic Submodule Pointer Updates**:
   - When modifying submodule repositories (e.g. `gql-ddd-inventory`, `php-ddd-inventory`), tracks commit pointers and atomically updates the parent repository (`inventory`).

---

## Standard Step Templates

### 1. Merge Conflict Marker Scanner
Fails fast if git merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`) are present in tracked files:

```yaml
      - name: Check for Merge Conflict Markers
        run: |
          echo "Scanning codebase for git merge conflict markers..."
          if git grep -n -I -E '^(<{7}|={7}|>{7}|\|{7})([[:space:]]|$)'; then
            echo "::error::Merge conflict markers detected in tracked files! Please resolve conflicts before merging."
            exit 1
          fi
          echo "No conflict markers detected."
```

#### Regex Mechanics:
- `^(<{7}|={7}|>{7}|\|{7})`: Matches 7 consecutive conflict characters at line start.
- `([[:space:]]|$)`: Matches end-of-line or whitespace separator, eliminating false positives from documentation or comparison operators.
- `-I`: Excludes binary assets.
- `-n`: Emits line numbers for immediate diagnostic feedback in GitHub Actions logs.

### 2. Python Module Shadowing Detector
Prevents obscure `AttributeError` or `ImportError` bugs by failing fast if a stray local file (e.g., `inspect.py`, `test.py`, `json.py`) masks a Python standard library module in the working directory before test execution:

```yaml
      - name: Check for Python Standard Library Shadowing
        run: |
          echo "Scanning for stray files that shadow Python standard library modules..."
          SHADOW_FILES=("inspect.py" "json.py" "logging.py" "sys.py" "os.py" "test.py" "unittest.py" "datetime.py")
          FOUND_SHADOWS=0
          for file in "${SHADOW_FILES[@]}"; do
            if [ -f "$file" ]; then
              echo "::error::Found stray '$file' in the root directory! This will shadow the Python standard library and crash tests (e.g., breaking unittest.mock). Please rename or delete it."
              FOUND_SHADOWS=1
            fi
          done
          if [ $FOUND_SHADOWS -ne 0 ]; then
            exit 1
          fi
          echo "No shadowing files detected."
```

---

## Orchestration Workflow

### Step 1: Catalog Repositories and Default Branches
```bash
python -c "
import subprocess, json

repos = json.loads(subprocess.check_output([
    'gh', 'repo', 'list', '<OWNER>', '--limit', '100',
    '--json', 'name,isArchived,visibility,defaultBranchRef'
], text=True))

for r in repos:
    if not r.get('isArchived'):
        default_branch = r['defaultBranchRef']['name'] if r.get('defaultBranchRef') else 'main'
        print(f\"{r['name']} | default: {default_branch} | {r['visibility']}\")
"
```

### Step 2: Locate Primary CI Workflows
Map out each repository's CI entrypoints:
```bash
gh api repos/<OWNER>/<REPO>/actions/workflows --jq '.workflows[] | select(.state == "active") | {name: .name, path: .path}'
```
Common primary workflows:
- `.github/workflows/ci.yml`
- `.github/workflows/test.yml`
- `.github/workflows/phpunit.yml`
- `.github/workflows/conformance.yml`

### Step 3: Check & Inject Step Idempotently
Inspect existing workflow steps:
```bash
git grep "Check for Merge Conflict Markers" .github/workflows/
```
If missing, insert the step immediately after the checkout step:
```yaml
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Check for Merge Conflict Markers
        run: |
          echo "Scanning codebase for git merge conflict markers..."
          if git grep -n -I -E '^(<{7}|={7}|>{7}|\|{7})([[:space:]]|$)'; then
            echo "::error::Merge conflict markers detected in tracked files! Please resolve conflicts before merging."
            exit 1
          fi
          echo "No conflict markers detected."
```

### Step 4: Rebase & Push with Stash Protection
```bash
# 1. Stash any dirty local files or db dumps
git stash --include-untracked

# 2. Stage and commit workflow change
git add .github/workflows/<WORKFLOW_FILE>.yml
git commit -m "ci: add merge conflict markers check to CI pipeline"

# 3. Rebase against latest remote default branch
git pull --rebase origin <DEFAULT_BRANCH>

# 4. Push to remote
git push origin <DEFAULT_BRANCH>

# 5. Restore local working tree
git stash pop || true
```

### Step 5: Synchronize Parent Repository Submodules
If any child submodules were updated:
```bash
cd <PARENT_REPO_DIR>
git add <SUBMODULE_A> <SUBMODULE_B> .github/workflows/conformance.yml
git commit -m "ci: add merge conflict markers check to CI pipeline and sync submodule pointers"
git pull --rebase origin <DEFAULT_BRANCH>
git push origin <DEFAULT_BRANCH>
```
