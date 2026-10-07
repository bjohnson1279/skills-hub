#!/usr/bin/env python3
"""
Submodule Isolation & Dependency Boundary Auditor
Scans TypeScript files in submodules to detect:
1. Relative imports that escape the submodule's directory root.
2. Third-party package imports not listed in the submodule's package.json.
"""

import argparse
import json
import os
import re
import sys

def audit_submodule(sub_path):
    issues = []
    pkg_json_path = os.path.join(sub_path, "package.json")
    declared_pkgs = set()
    if os.path.exists(pkg_json_path):
        try:
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                declared_pkgs.update(data.get("dependencies", {}).keys())
                declared_pkgs.update(data.get("devDependencies", {}).keys())
        except Exception as e:
            issues.append(f"Error reading {pkg_json_path}: {e}")

    # Builtin Node modules
    builtins = {
        "fs", "path", "os", "crypto", "http", "https", "events", "stream",
        "util", "url", "buffer", "child_process", "net", "tls", "assert",
        "async_hooks", "dns", "perf_hooks", "worker_threads", "zlib", "constants",
        "node:fs", "node:path", "node:os", "node:crypto", "node:http", "node:https",
        "node:events", "node:stream", "node:util", "node:url", "node:buffer",
        "node:async_hooks", "node:dns", "node:perf_hooks", "node:worker_threads"
    }

    import_regex = re.compile(r"""(?:import|from|require\()\s*['"]([a-zA-Z0-9@_./-]+)['"]""")

    src_dir = os.path.join(sub_path, "src")
    if not os.path.exists(src_dir):
        return issues

    for root, _, files in os.walk(src_dir):
        for file in files:
            if not (file.endswith(".ts") or file.endswith(".tsx")):
                continue
            fpath = os.path.join(root, file)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            for match in import_regex.finditer(content):
                target = match.group(1)
                if target.startswith("."):
                    resolved = os.path.abspath(os.path.join(root, target))
                    sub_abs = os.path.abspath(sub_path)
                    if not resolved.startswith(sub_abs):
                        issues.append({
                            "type": "OUT_OF_BOUNDS_IMPORT",
                            "file": os.path.relpath(fpath, sub_path),
                            "target": target,
                            "resolved": resolved
                        })
                elif not target.startswith("@/") and not target.startswith("~/"):
                    # Check package name
                    pkg_name = target.split("/")[0]
                    if target.startswith("@") and "/" in target:
                        parts = target.split("/")
                        pkg_name = f"{parts[0]}/{parts[1]}"
                    if pkg_name not in declared_pkgs and pkg_name not in builtins:
                        issues.append({
                            "type": "UNDECLARED_DEPENDENCY",
                            "file": os.path.relpath(fpath, sub_path),
                            "package": pkg_name
                        })
    return issues

def main():
    parser = argparse.ArgumentParser(description="Audit submodule boundaries and dependencies")
    parser.add_argument("--repo-dir", default=".", help="Root repository directory containing submodules")
    args = parser.parse_args()

    repo_dir = os.path.abspath(args.repo_dir)
    print(f"Auditing submodules in: {repo_dir}")

    submodules = ["gql-ddd-inventory", "js-ddd-inventory"]
    total_issues = 0
    for sub in submodules:
        sub_path = os.path.join(repo_dir, sub)
        if not os.path.exists(sub_path):
            continue
        print(f"\n--- Checking [{sub}] ---")
        issues = audit_submodule(sub_path)
        if not issues:
            print("  [OK] No boundary or dependency violations found.")
        else:
            for iss in issues:
                total_issues += 1
                if iss["type"] == "OUT_OF_BOUNDS_IMPORT":
                    print(f"  [OUT_OF_BOUNDS] {iss['file']}: imports '{iss['target']}' outside submodule root")
                elif iss["type"] == "UNDECLARED_DEPENDENCY":
                    print(f"  [UNDECLARED_DEP] {iss['file']}: imports '{iss['package']}' not in package.json")

    sys.exit(1 if total_issues > 0 else 0)

if __name__ == "__main__":
    main()
