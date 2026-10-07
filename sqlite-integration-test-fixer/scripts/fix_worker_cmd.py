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
    queue_dir = os.path.join(root_dir, "tests", "Integration", "Queue")

    if not os.path.exists(queue_dir):
        print(f"Error: Could not find Queue test directory in {root_dir}")
        sys.exit(1)

    target1 = 'exec($cmd, $output, $resultCode);'
    replacement1 = 'DB::disconnect();\n        exec($cmd, $output, $resultCode);\n        DB::reconnect();'

    for filename in os.listdir(queue_dir):
        if filename.endswith(".php"):
            filepath = os.path.join(queue_dir, filename)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if target1 in content and "DB::disconnect()" not in content:
                content = content.replace(target1, replacement1)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Added DB disconnect/reconnect wrapping around exec() in {filename}")

if __name__ == "__main__":
    main()
