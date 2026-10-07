#!/usr/bin/env python3
import os
import sys
import subprocess
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    return res.returncode, res.stdout, res.stderr

def get_git_root():
    code, stdout, _ = run("git rev-parse --show-toplevel")
    if code == 0:
        return stdout.strip()
    return os.getcwd()

def find_php_bin():
    # Detect default php command or WinGet PHP path on Windows
    winget_php = r"C:\Users\johns\AppData\Local\Microsoft\WinGet\Packages\PHP.PHP.8.1_Microsoft.Winget.Source_8wekyb3d8bbwe\php.exe"
    ext_dir = r"C:\Users\johns\AppData\Local\Microsoft\WinGet\Packages\PHP.PHP.8.1_Microsoft.Winget.Source_8wekyb3d8bbwe\ext"

    if os.path.exists(winget_php) and os.path.exists(ext_dir):
        return f'"{winget_php}" -d extension_dir="{ext_dir}" -d extension=mbstring -d extension=pdo_sqlite'

    return "php"

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else get_git_root()
    php_cmd = find_php_bin()

    print(f"Scanning for PHP syntax errors in: {target}...")

    php_files = []
    if os.path.isfile(target) and target.endswith(".php"):
        php_files.append(target)
    elif os.path.isdir(target):
        for root, dirs, files in os.walk(target):
            # Exclude vendor and node_modules directories for speed
            dirs[:] = [d for d in dirs if d not in ["vendor", "node_modules", ".git", "storage", "bootstrap/cache"]]
            for f in files:
                if f.endswith(".php"):
                    php_files.append(os.path.join(root, f))

    if not php_files:
        print("No PHP files found to check.")
        sys.exit(0)

    print(f"Found {len(php_files)} PHP files. Linting...")

    syntax_errors = []
    clean_count = 0

    for filepath in php_files:
        cmd = f'{php_cmd} -l "{filepath}"'
        code, stdout, stderr = run(cmd)
        if code != 0 or "Errors parsing" in stdout or "Parse error" in stdout or "Fatal error" in stdout:
            syntax_errors.append({
                "filepath": filepath,
                "output": (stdout + stderr).strip()
            })
        else:
            clean_count += 1

    print("\n================ SYNTAX CHECK SUMMARY ================")
    print(f"Total Files Scanned: {len(php_files)}")
    print(f"Clean Files: {clean_count}")
    print(f"Syntax Errors ({len(syntax_errors)}):")

    for err in syntax_errors:
        print(f"\n❌ {err['filepath']}")
        print(f"   {err['output']}")

    if syntax_errors:
        sys.exit(1)
    else:
        print("\n✅ All PHP files passed syntax check successfully!")

if __name__ == "__main__":
    main()
