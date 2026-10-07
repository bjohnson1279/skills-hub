---
name: antigravity-permission-manager
description: >
  Audits, configures, and standardizes allowed tool and CLI command permissions in Antigravity settings (settings.json). Use to pre-authorize common tool profiles (github-cli, git-core, node-testing, php-testing, docker) and prevent repetitive command confirmation prompts.
---

# Antigravity Permission Manager

This skill provides an automated CLI utility to inspect and pre-authorize command execution permissions in Antigravity settings files, eliminating interactive approval friction during autonomous test and merge workflows.

---

## Supported Preset Profiles

| Profile Name | Pre-Authorized Commands |
| :--- | :--- |
| **`readonly-all`** | Unified read-only inspection grant combining all read-only commands for `git`, `gh`, `powershell`, and version diagnostics. |
| **`gh-readonly`** | `command(gh)`, `gh api`, `gh auth status`, `gh repo list`, `gh repo view`, `gh pr list`, `gh pr view`, `gh pr diff`, `gh pr checks`, `gh pr status`, `gh search prs`, `gh search issues`, `gh search code`, `gh search commits`, `gh run list`, `gh run view`, `gh run watch` |
| **`github-cli`** | `gh-readonly` plus `gh pr merge`, `gh pr close` |
| **`git-readonly`** | `command(git)` root prefix, `git status`, `git diff`, `git log`, `git show`, `git branch`, `git fetch`, `git ls-files`, `git ls-tree`, `git rev-parse`, `git rev-list`, `git merge-base`, `git merge-tree`, `git submodule`, `git remote`, `git grep`, `git blame`, `git cat-file`, `git describe`, `git check-ignore`, `git check-ref-format`, `git config`, `git fsck`, `git tag`, `git shortlog`, `git show-branch`, `git ls-remote`, `git var`, `git version`, `git help`, `git archive`, `git show-ref`, `git reflog`, `git count-objects`, `git verify-commit`, `git verify-tag` |
| **`git-core`** | `command(git)` root prefix, `git-readonly` plus `git pull`, `git checkout`, `git merge`, `git commit`, `git add`, `git stash` |
| **`powershell-readonly`** | `command(powershell)`, `Get-ChildItem`, `Get-Content`, `Select-String`, `Test-Path`, `Get-Command`, `Get-Process`, `Get-Service`, `Select-Object`, `Where-Object`, `Measure-Object`, `Resolve-Path`, `Format-Table`, `Format-List` |
| **`windows-powershell`** | `powershell-readonly` plus `Set-Content`, `New-Item`, `Copy-Item`, `Remove-Item` |
| **`node-testing`** | `command(node)`, `command(npm)`, `command(npx)`, `command(pnpm)`, `npm test`, `npm run`, `npm audit`, `npm view`, `npm list`, `npm install`, `npx jest`, `npx vitest`, `npx tsc`, `pnpm test`, `pnpm install` |
| **`python-tools`** | `command(python)`, `command(python3)`, `command(pytest)`, `python -m pytest`, `uv` |
| **`php-testing`** | `command(php)`, `php -v`, `php -m`, `php --ini`, `vendor/bin/phpunit`, `vendor\bin\phpunit`, `php vendor/bin/phpunit` |
| **`docker`** | `command(docker)`, `docker ps`, `docker compose`, `docker --version`, `docker version`, `docker info` |

---

## CLI Usage

### List Configured Permissions (Both Desktop and CLI Configs)
```bash
python C:/Users/johns/.gemini/config/skills/antigravity-permission-manager/scripts/manage_permissions.py list
```

### Pre-Authorize All Read-Only Commands
```bash
python C:/Users/johns/.gemini/config/skills/antigravity-permission-manager/scripts/manage_permissions.py add --profile readonly-all
```

### Clean & Consolidate Permissions (Prunes Stale Scratch & One-Off Branch Rules)
```bash
python C:/Users/johns/.gemini/config/skills/antigravity-permission-manager/scripts/manage_permissions.py clean
```

### Add Specific Command Permissions
```bash
python C:/Users/johns/.gemini/config/skills/antigravity-permission-manager/scripts/manage_permissions.py add --command "gh pr view" "gh pr diff" "npx vitest run --pool=forks"
```

