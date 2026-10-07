#!/usr/bin/env python3
import os
import sys

def get_git_root():
    import subprocess
    res = subprocess.run("git rev-parse --show-toplevel", shell=True, capture_output=True, text=True)
    root = res.stdout.strip()
    return root if root else os.getcwd()

def main():
    root_dir = get_git_root()
    http_dir = os.path.join(root_dir, "tests", "Integration", "Http")

    if not os.path.exists(http_dir):
        print(f"Error: Could not find Http test directory in {root_dir}")
        sys.exit(1)

    for filename in os.listdir(http_dir):
        if not filename.endswith(".php"):
            continue
        filepath = os.path.join(http_dir, filename)
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if "setUpBeforeClass" not in content or "proc_open" not in content:
            continue

        if "Manager::getInstance();" in content:
            content = content.replace("Manager::getInstance();", "new \\Illuminate\\Database\\Capsule\\Manager();")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Isolated Capsule instance in {filename}")

if __name__ == "__main__":
    main()
