#!/usr/bin/env python3
import os
import re
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
        # Search for Http test directory
        for r, d, files in os.walk(root_dir):
            if r.endswith(os.path.join("tests", "Integration", "Http")) or r.endswith("Http"):
                http_dir = r
                break

    if not os.path.exists(http_dir):
        print(f"Error: Could not find Http test directory in {root_dir}")
        sys.exit(1)

    test_files = [f for f in os.listdir(http_dir) if f.endswith(".php")]
    start_port = 8085

    for idx, filename in enumerate(test_files):
        filepath = os.path.join(http_dir, filename)
        port = start_port + idx

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Replace local server port binding strings
        new_content = re.sub(r'127\.0\.0\.1:\d+', f'127.0.0.1:{port}', content)

        if new_content != content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Assigned port {port} to {filename}")

if __name__ == "__main__":
    main()
