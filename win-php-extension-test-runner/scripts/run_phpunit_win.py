#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

# Force UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def discover_php_extension_dir():
    candidates = []
    
    # 1. WinGet standard package location
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_pkgs = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
        if os.path.exists(winget_pkgs):
            for entry in os.listdir(winget_pkgs):
                if entry.startswith("PHP.PHP"):
                    ext_dir = os.path.join(winget_pkgs, entry, "ext")
                    if os.path.exists(ext_dir):
                        candidates.append(ext_dir)

    # 2. Chocolatey & XAMPP standard locations
    for common_path in [
        r"C:\tools\php\ext",
        r"C:\xampp\php\ext",
        r"C:\ProgramData\chocolatey\lib\php\tools\ext"
    ]:
        if os.path.exists(common_path) and common_path not in candidates:
            candidates.append(common_path)

    # 3. Path from active where.exe php
    try:
        res = subprocess.run(["where.exe", "php"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                p = line.strip()
                if p:
                    ext_dir = os.path.join(os.path.dirname(p), "ext")
                    if os.path.exists(ext_dir) and ext_dir not in candidates:
                        candidates.append(ext_dir)
    except Exception:
        pass

    for c in candidates:
        has_mb = os.path.exists(os.path.join(c, "php_mbstring.dll"))
        has_sqlite = os.path.exists(os.path.join(c, "php_pdo_sqlite.dll")) or os.path.exists(os.path.join(c, "php_sqlite3.dll"))
        if has_mb or has_sqlite:
            return c
    return None

def build_php_flags(ext_dir):
    if not ext_dir:
        return []
    flags = [f"-d extension_dir={ext_dir}"]
    extensions = ["php_mbstring.dll", "php_pdo_sqlite.dll", "php_sqlite3.dll", "php_curl.dll", "php_openssl.dll"]
    for ext in extensions:
        if os.path.exists(os.path.join(ext_dir, ext)):
            flags.append(f"-d extension={ext}")
    return flags

def main():
    parser = argparse.ArgumentParser(description="Windows PHPUnit Dynamic Extension Runner")
    parser.add_argument("--cwd", default=".", help="Working directory containing composer.json / vendor")
    parser.add_argument("--discover-only", action="store_true", help="Print discovered extension flags without running phpunit")
    args, forwarded = parser.parse_known_args()

    ext_dir = discover_php_extension_dir()
    if not ext_dir:
        print("⚠️ No Windows PHP extension directory discovered with mbstring/sqlite DLLs.", file=sys.stderr)
        php_flags = []
    else:
        php_flags = build_php_flags(ext_dir)
        print(f"🔍 Discovered PHP extensions at: {ext_dir}")

    if args.discover_only:
        print(" ".join(php_flags))
        return

    phpunit_bin = os.path.join(args.cwd, "vendor", "bin", "phpunit")
    if not os.path.exists(phpunit_bin) and os.path.exists(os.path.join(args.cwd, "vendor", "bin", "phpunit.bat")):
        phpunit_bin = os.path.join(args.cwd, "vendor", "bin", "phpunit.bat")

    cmd = ["php"] + php_flags + [phpunit_bin] + forwarded
    print(f"🚀 Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=args.cwd)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
