#!/usr/bin/env python3
"""
Multi-Tenant Method Signature Drift Harmonizer
Audits and harmonizes parameter arity (tenantId: string) and async Promise drift across
PR test fixtures and legacy calling code.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def discover_multitenant_methods(service_files: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Parses TypeScript service/repository files to detect methods requiring tenantId or returning Promise.
    """
    signatures = {}

    method_pattern = re.compile(
        r'(?:public\s+)?(?:async\s+)?([a-zA-Z0-9_$]+)\s*\(\s*([^)]*)\)\s*(?::\s*([^{;]+))?'
    )

    for file_path in service_files:
        if not os.path.exists(file_path):
            continue
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        for match in method_pattern.finditer(content):
            name = match.group(1)
            params = match.group(2).strip()
            ret_type = match.group(3).strip() if match.group(3) else ""

            # Ignore constructor, control keywords, and private methods
            control_keywords = {'if', 'for', 'while', 'switch', 'catch', 'with', 'function', 'class'}
            if name in ('constructor', 'getInstance') or name in control_keywords or name.startswith('_'):
                continue

            param_list = [p.strip() for p in params.split(',') if p.strip()]
            requires_tenant = bool(param_list and ('tenantId' in param_list[0] or 'tenant_id' in param_list[0]))
            is_async = 'Promise' in ret_type or 'async' in match.group(0)

            if requires_tenant or is_async:
                signatures[name] = {
                    "method": name,
                    "file": file_path,
                    "requires_tenant_id": requires_tenant,
                    "is_async": is_async,
                    "total_params": len(param_list),
                    "first_param": param_list[0] if param_list else None
                }
    return signatures


def scan_test_file_for_drift(test_file: str, signatures: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Scans a test file for calls to multi-tenant / async methods that lack tenantId or await.
    """
    if not os.path.exists(test_file):
        return []

    issues = []
    with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        for method_name, sig in signatures.items():
            # Pattern matching calls: service.methodName(...)
            call_pattern = re.compile(r'(?<!function\s)(?<!async\s)\b' + re.escape(method_name) + r'\s*\(\s*([^)]*)\)')
            for match in call_pattern.finditer(line):
                args_str = match.group(1).strip()
                args = [a.strip() for a in args_str.split(',') if a.strip()]

                # Check tenantId drift
                has_tenant_arg = bool(args and ('tenant' in args[0].lower() or args[0].startswith("'") or args[0].startswith('"')))
                missing_tenant = sig["requires_tenant_id"] and not has_tenant_arg

                # Check missing await
                has_await = 'await ' in line[:match.start()] or 'return ' in line[:match.start()]
                missing_await = sig["is_async"] and not has_await and not 'jest.spyOn' in line and not '.mock' in line

                if missing_tenant or missing_await:
                    issues.append({
                        "file": test_file,
                        "line": i,
                        "method": method_name,
                        "missing_tenant_id": missing_tenant,
                        "missing_await": missing_await,
                        "raw_line": line.strip()
                    })

    return issues


def fix_signature_drift(test_file: str, default_tenant: str = "'tenant-001'") -> int:
    """
    Auto-fixes common single-tenant synchronous method calls in test files.
    """
    if not os.path.exists(test_file):
        return 0

    with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    fixed_count = 0
    # Auto-prefix tenantId to known methods when single payload object is passed
    target_methods = ['createPolicy', 'createCustomer', 'getPolicies', 'getCustomers', 'generateInvoiceForPolicy', 'getBatches']
    for m in target_methods:
        pattern = re.compile(r'(\b' + re.escape(m) + r'\s*\(\s*)(\{)')
        content, count = pattern.subn(r'\1' + default_tenant + r', \2', content)
        fixed_count += count

    if fixed_count > 0:
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(content)

    return fixed_count


def main():
    parser = argparse.ArgumentParser(description="Multi-Tenant Method Signature Drift Harmonizer")
    parser.add_argument("--project-root", default=".", help="Root directory of repository")
    parser.add_argument("--tenant-id", default="'tenant-001'", help="Default tenant ID literal to inject in test calls")
    parser.add_argument("--fix", action="store_true", help="Auto-inject tenantId into test calling conventions")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()
    root = Path(args.project_root)

    services = list(root.glob("src/services/*.service.ts")) + list(root.glob("src/db/*.interfaces.ts"))
    signatures = discover_multitenant_methods([str(s) for s in services])

    test_files = list(root.glob("tests/*.test.ts"))
    all_issues = []

    for tf in test_files:
        issues = scan_test_file_for_drift(str(tf), signatures)
        all_issues.extend(issues)
        if args.fix:
            fix_count = fix_signature_drift(str(tf), default_tenant=args.tenant_id)
            if fix_count > 0 and not args.json:
                print(f"[Fixed] {tf.name}: injected tenant ID into {fix_count} calls.")

    if args.json:
        print(json.dumps({
            "total_issues": len(all_issues),
            "discovered_signatures": len(signatures),
            "issues": all_issues
        }, indent=2))
    else:
        print(f"\nDiscovered {len(signatures)} multi-tenant/async method signatures across services.")
        if all_issues:
            print(f"[!] Found {len(all_issues)} signature drift issue(s) across test suites:")
            for iss in all_issues[:15]:
                print(f"  {os.path.basename(iss['file'])}:{iss['line']} -> {iss['method']}() (Missing tenantId: {iss['missing_tenant_id']}, Missing await: {iss['missing_await']})")
        else:
            print("[OK] All test suites match active multi-tenant and async method signatures!")


if __name__ == "__main__":
    main()
