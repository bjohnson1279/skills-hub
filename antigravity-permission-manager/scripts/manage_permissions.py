#!/usr/bin/env python3
"""
Antigravity Permission Manager CLI
Audits, adds, and standardizes allowed command profiles in Antigravity settings.
"""

import argparse
import json
import os
import re
import shutil
import sys

# Force UTF-8 encoding across Windows console streams
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

DEFAULT_CONFIG_FILES = [
    os.path.expanduser("~/.gemini/config/config.json"),
    os.path.expanduser("~/.gemini/antigravity-cli/settings.json")
]

PROFILES = {
    "gh-readonly": [
        "command(gh)",
        "command(gh api)",
        "command(gh auth status)",
        "command(gh repo list)",
        "command(gh repo view)",
        "command(gh pr list)",
        "command(gh pr view)",
        "command(gh pr diff)",
        "command(gh pr checks)",
        "command(gh pr status)",
        "command(gh search prs)",
        "command(gh search issues)",
        "command(gh search code)",
        "command(gh search commits)",
        "command(gh run list)",
        "command(gh run view)",
        "command(gh run watch)"
    ],
    "github-cli": [
        "command(gh)",
        "command(gh api)",
        "command(gh auth status)",
        "command(gh repo list)",
        "command(gh repo view)",
        "command(gh pr list)",
        "command(gh pr view)",
        "command(gh pr diff)",
        "command(gh pr checks)",
        "command(gh pr status)",
        "command(gh pr merge)",
        "command(gh pr close)",
        "command(gh search prs)",
        "command(gh search issues)",
        "command(gh search code)",
        "command(gh search commits)",
        "command(gh run list)",
        "command(gh run view)",
        "command(gh run watch)"
    ],
    "git-readonly": [
        "command(git)",
        "command(git status)",
        "command(git diff)",
        "command(git log)",
        "command(git show)",
        "command(git branch)",
        "command(git fetch)",
        "command(git ls-files)",
        "command(git ls-tree)",
        "command(git rev-parse)",
        "command(git rev-list)",
        "command(git merge-base)",
        "command(git merge-tree)",
        "command(git submodule)",
        "command(git remote)",
        "command(git grep)",
        "command(git blame)",
        "command(git cat-file)",
        "command(git describe)",
        "command(git check-ignore)",
        "command(git check-ref-format)",
        "command(git config)",
        "command(git fsck)",
        "command(git tag)",
        "command(git shortlog)",
        "command(git show-branch)",
        "command(git ls-remote)",
        "command(git var)",
        "command(git version)",
        "command(git help)",
        "command(git archive)",
        "command(git show-ref)",
        "command(git reflog)",
        "command(git count-objects)",
        "command(git verify-commit)",
        "command(git verify-tag)"
    ],
    "git-core": [
        "command(git)",
        "command(git status)",
        "command(git diff)",
        "command(git log)",
        "command(git show)",
        "command(git branch)",
        "command(git fetch)",
        "command(git pull)",
        "command(git checkout)",
        "command(git merge)",
        "command(git commit)",
        "command(git add)",
        "command(git stash)",
        "command(git rev-parse)",
        "command(git rev-list)",
        "command(git merge-base)",
        "command(git merge-tree)",
        "command(git submodule)",
        "command(git remote)",
        "command(git grep)",
        "command(git blame)",
        "command(git ls-files)",
        "command(git ls-tree)"
    ],
    "powershell-readonly": [
        "command(powershell)",
        "command(Get-ChildItem)",
        "command(Get-Content)",
        "command(Select-String)",
        "command(Test-Path)",
        "command(Get-Command)",
        "command(Get-Process)",
        "command(Get-Service)",
        "command(Select-Object)",
        "command(Where-Object)",
        "command(Measure-Object)",
        "command(Resolve-Path)",
        "command(Format-Table)",
        "command(Format-List)"
    ],
    "windows-powershell": [
        "command(powershell)",
        "command(Get-ChildItem)",
        "command(Get-Content)",
        "command(Select-String)",
        "command(Test-Path)",
        "command(Get-Command)",
        "command(Get-Process)",
        "command(Get-Service)",
        "command(Select-Object)",
        "command(Where-Object)",
        "command(Measure-Object)",
        "command(Resolve-Path)",
        "command(Format-Table)",
        "command(Format-List)",
        "command(Set-Content)",
        "command(New-Item)",
        "command(Copy-Item)",
        "command(Remove-Item)"
    ],
    "node-testing": [
        "command(node)",
        "command(npm)",
        "command(npx)",
        "command(pnpm)",
        "command(npm test)",
        "command(npm run)",
        "command(npm audit)",
        "command(npm view)",
        "command(npm list)",
        "command(npm install)",
        "command(npx jest)",
        "command(npx vitest)",
        "command(npx tsc)",
        "command(pnpm test)",
        "command(pnpm install)"
    ],
    "python-tools": [
        "command(python)",
        "command(python3)",
        "command(pytest)",
        "command(python -m pytest)",
        "command(uv)"
    ],
    "php-testing": [
        "command(php)",
        "command(php -v)",
        "command(php -m)",
        "command(php --ini)",
        "command(vendor/bin/phpunit)",
        "command(vendor\\bin\\phpunit)",
        "command(php vendor/bin/phpunit)"
    ],
    "docker": [
        "command(docker)",
        "command(docker ps)",
        "command(docker compose)",
        "command(docker --version)",
        "command(docker version)",
        "command(docker info)"
    ]
}

# Unified readonly profile combining all safe inspection profiles
PROFILES["readonly-all"] = list(dict.fromkeys(
    PROFILES["gh-readonly"] +
    PROFILES["git-readonly"] +
    PROFILES["powershell-readonly"] +
    [
        "command(docker ps)",
        "command(docker version)",
        "command(docker --version)",
        "command(docker info)",
        "command(php -v)",
        "command(php -m)",
        "command(php --ini)",
        "command(npm -v)",
        "command(npm view)",
        "command(npm list)",
        "command(node -v)",
        "command(python --version)",
        "command(python3 --version)",
        "command(pytest --version)",
        "command(where.exe)"
    ]
))


def get_allow_list(data):
    """Retrieves the allow list and its parent reference based on schema."""
    if "userSettings" in data and isinstance(data["userSettings"], dict):
        grants = data["userSettings"].setdefault("globalPermissionGrants", {})
        allow = grants.setdefault("allow", [])
        return allow, grants, "allow"
    if "permissions" in data and isinstance(data["permissions"], dict):
        allow = data["permissions"].setdefault("allow", [])
        return allow, data["permissions"], "allow"
    perms = data.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    return allow, perms, "allow"


def load_settings(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
        return None


def save_settings(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_target_files(custom_settings=None):
    if custom_settings:
        return [custom_settings]
    return [p for p in DEFAULT_CONFIG_FILES if os.path.exists(p)]


def cmd_list(args):
    targets = get_target_files(args.settings)
    for target in targets:
        data = load_settings(target)
        if not data:
            print(f"Target not found: {target}")
            continue
        allow, _, _ = get_allow_list(data)
        print(f"\n=======================================================")
        print(f"Configured permissions in: {target} ({len(allow)} total rules):")
        print(f"=======================================================")
        for r in allow[:args.limit]:
            first_line = r.splitlines()[0]
            print(f"  • {first_line[:90]}{'...' if len(first_line) > 90 or '\\n' in r else ''}")
        if len(allow) > args.limit:
            print(f"  ... and {len(allow) - args.limit} more.")


def cmd_add(args):
    targets = get_target_files(args.settings)
    to_add = []

    if args.profile:
        for p in args.profile:
            if p in PROFILES:
                to_add.extend(PROFILES[p])
            else:
                print(f"Unknown profile: {p}. Available: {list(PROFILES.keys())}", file=sys.stderr)

    if args.command:
        for c in args.command:
            rule = f"command({c})" if not (c.startswith("command(") or c.startswith("read_file(") or c.startswith("write_file(")) else c
            to_add.append(rule)

    for target in targets:
        data = load_settings(target)
        if data is None:
            continue
        allow, parent, key = get_allow_list(data)
        added = []
        for item in to_add:
            if item not in allow:
                allow.insert(0, item)
                added.append(item)

        parent[key] = allow
        save_settings(target, data)
        print(f"Added {len(added)} new rule(s) to: {target}")
        for a in added[:10]:
            print(f"  + {a[:80]}")
        if len(added) > 10:
            print(f"  ... and {len(added) - 10} more.")


def is_stale_or_one_off_rule(rule):
    """Identifies dead scratch scripts, inline PowerShell scripts, and one-off branch/PR rules."""
    # 1. Multi-line inline scripts
    if "\n" in rule or rule.startswith("command(@'") or "@|" in rule:
        return True, "Inline multi-line script"

    # 2. Dead scratch files across brain sessions
    if re.search(r'brain[\\\/][a-f0-9\-]+[\\\/]scratch', rule, re.IGNORECASE):
        return True, "Temporary scratch script path"
    if re.search(r'scratch_test|fix_\d+\.py|triage_all_\d+_prs|execute_all_\d+_prs', rule, re.IGNORECASE):
        return True, "One-off triage scratch script"

    # 3. Hyper-specific branch operations or commit hashes
    if re.search(r'git push origin [a-zA-Z0-9_\-\./]+:[a-zA-Z0-9_\-\.]+', rule):
        return True, "One-off branch push"
    if re.search(r'git push origin (fix-|jules-|sentinel-|bolt-|dependabot/|test-)[a-zA-Z0-9_\-\.]+', rule):
        return True, "Specific feature branch push"
    if re.search(r'git checkout (fix-|jules-|sentinel-|bolt-|dependabot/|test/|tests/|test-)[a-zA-Z0-9_\-\.]+', rule):
        return True, "Specific feature branch checkout"

    # 4. Specific numbered PR commands (compound PR commands)
    if re.search(r'gh pr (checks|view|diff|merge|close) \d+\s*(;|&&)', rule):
        return True, "Compound PR number command"
    if re.search(r'gh run (view|rerun) \d+', rule):
        return True, "Specific GitHub Action run ID"

    # 5. One-off specific file adds with long commit messages
    if re.search(r'git commit -m "[^"]{40,}"', rule):
        return True, "One-off detailed commit message"

    return False, ""


def cmd_clean(args):
    targets = get_target_files(args.settings)
    
    # Base consolidated rules to ensure always exist
    core_rules = list(dict.fromkeys(
        PROFILES["readonly-all"] +
        PROFILES["github-cli"] +
        PROFILES["git-core"] +
        PROFILES["windows-powershell"] +
        PROFILES["node-testing"] +
        PROFILES["python-tools"] +
        PROFILES["php-testing"] +
        PROFILES["docker"]
    ))

    for target in targets:
        data = load_settings(target)
        if data is None:
            continue
            
        # Create backup
        bak = target + ".bak"
        shutil.copyfile(target, bak)
        print(f"\n📦 Backed up {target} -> {bak}")

        allow, parent, key = get_allow_list(data)
        original_count = len(allow)
        pruned_rules = []
        retained_rules = []

        for rule in allow:
            stale, reason = is_stale_or_one_off_rule(rule)
            if stale:
                pruned_rules.append((rule, reason))
            else:
                retained_rules.append(rule)

        # Merge core rules first, followed by clean retained rules, deduplicated
        consolidated = []
        seen = set()

        for r in core_rules + retained_rules:
            if r not in seen:
                seen.add(r)
                consolidated.append(r)

        parent[key] = consolidated
        save_settings(target, data)

        print(f"✨ Consolidated {target}:")
        print(f"   Original rules: {original_count}")
        print(f"   Pruned one-off/stale rules: {len(pruned_rules)}")
        print(f"   Consolidated active rules: {len(consolidated)}")
        if pruned_rules:
            print("   Sample pruned rules:")
            for pr, rsn in pruned_rules[:5]:
                first_line = pr.splitlines()[0]
                print(f"     - [{rsn}] {first_line[:80]}...")


def main():
    parser = argparse.ArgumentParser(description="Antigravity Permission Manager CLI")
    parser.add_argument("--settings", help="Custom path to settings/config file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List allowed command permissions")
    p_list.add_argument("--limit", type=int, default=35, help="Max rules to print")
    p_list.set_defaults(func=cmd_list)

    # add
    p_add = subparsers.add_parser("add", help="Add permissions by profile or exact command")
    p_add.add_argument("--profile", nargs="+", choices=list(PROFILES.keys()), help="Preset permission profiles")
    p_add.add_argument("--command", nargs="+", help="Specific command strings (e.g. 'gh pr view', 'docker compose')")
    p_add.set_defaults(func=cmd_add)

    # clean / consolidate
    p_clean = subparsers.add_parser("clean", help="Clean and consolidate permissions, pruning stale scratch and one-off commands")
    p_clean.set_defaults(func=cmd_clean)

    p_cons = subparsers.add_parser("consolidate", help="Alias for clean")
    p_cons.set_defaults(func=cmd_clean)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
