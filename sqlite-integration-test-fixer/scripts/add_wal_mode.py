#!/usr/bin/env python3
import os
import sys

def run_cmd(cmd):
    import subprocess
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout.strip()

def get_git_root():
    root = run_cmd("git rev-parse --show-toplevel")
    return root if root else os.getcwd()

def main():
    root_dir = get_git_root()
    bootstrap_file = os.path.join(root_dir, "src", "Infrastructure", "Persistence", "bootstrap_database.php")
    
    if not os.path.exists(bootstrap_file):
        # Try searching for bootstrap_database.php
        for r, d, files in os.walk(root_dir):
            if "bootstrap_database.php" in files:
                bootstrap_file = os.path.join(r, "bootstrap_database.php")
                break

    if not os.path.exists(bootstrap_file):
        print(f"Error: Could not find bootstrap_database.php in {root_dir}")
        sys.exit(1)

    with open(bootstrap_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if "journal_mode=WAL" in content:
        print("WAL mode is already configured in bootstrap_database.php")
        return

    target = "if ($driver === 'sqlite') {\n    require_once __DIR__ . '/sqlite_setup.php';"
    replacement = "if ($driver === 'sqlite') {\n    try {\n        $capsule->getConnection()->statement('PRAGMA journal_mode=WAL;');\n        $capsule->getConnection()->statement('PRAGMA busy_timeout=10000;');\n    } catch (\\Exception $e) {}\n    require_once __DIR__ . '/sqlite_setup.php';"

    if target in content:
        content = content.replace(target, replacement)
    else:
        # Generic insert after sqlite driver check
        if "if ($driver === 'sqlite')" in content:
            content = content.replace("if ($driver === 'sqlite') {", "if ($driver === 'sqlite') {\n    try {\n        $capsule->getConnection()->statement('PRAGMA journal_mode=WAL;');\n        $capsule->getConnection()->statement('PRAGMA busy_timeout=10000;');\n    } catch (\\Exception $e) {}")

    with open(bootstrap_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully added SQLite WAL mode to {bootstrap_file}")

if __name__ == "__main__":
    main()
