#!/usr/bin/env python3
"""
DOM-based XSS innerHTML Auditor and Test Modernizer CLI
Audits TypeScript and JavaScript repositories for unsafe dynamic `innerHTML` interpolations
and modernizes associated unit test assertions from innerHTML string checks to safe DOM queries.
"""

import argparse
import json
import os
import re
import sys

# Force UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def audit_file_for_innerhtml(file_path):
    """Audits a single file for innerHTML usages and dynamic string interpolations."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    findings = []
    for idx, line in enumerate(lines, 1):
        if "innerHTML" in line and not line.strip().startswith("//") and not line.strip().startswith("*"):
            # Check if it's an assignment vs test assertion
            is_assignment = re.search(r'\.innerHTML\s*=', line)
            is_dynamic = bool(re.search(r'\$\{.*\}|\+\s*\w+', line))
            is_test_assertion = bool(re.search(r'expect\(.*\.innerHTML\)', line))

            findings.append({
                "line": idx,
                "code": line.strip(),
                "is_assignment": bool(is_assignment),
                "is_dynamic": is_dynamic,
                "is_test_assertion": is_test_assertion,
                "severity": "HIGH" if (is_assignment and is_dynamic) else ("MEDIUM" if is_assignment else "LOW")
            })
    return findings

def cmd_audit(args):
    target_dir = os.path.abspath(args.target_dir or os.getcwd())
    print(f"🛡️ Scanning {target_dir} for innerHTML patterns and DOM XSS vulnerabilities...")

    report = {}
    total_findings = 0
    high_severity = 0

    for root, _, files in os.walk(target_dir):
        # Skip node_modules, .git, dist, build
        if any(ignored in root for ignored in ["node_modules", ".git", "dist", "build", ".gemini"]):
            continue
        for f in files:
            if f.endswith((".ts", ".js", ".tsx", ".jsx")) and not f.endswith(".d.ts"):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, target_dir)
                findings = audit_file_for_innerhtml(full_path)
                if findings:
                    report[rel_path] = findings
                    total_findings += len(findings)
                    high_severity += sum(1 for item in findings if item["severity"] == "HIGH")

    print(f"\n📊 Audit Summary:")
    print(f"  - Files with innerHTML: {len(report)}")
    print(f"  - Total innerHTML occurrences: {total_findings}")
    print(f"  - High Severity (Dynamic innerHTML assignments): {high_severity}")

    for file_rel, items in report.items():
        print(f"\n📄 {file_rel}:")
        for item in items:
            badge = f"[{item['severity']}]"
            print(f"   Line {item['line']:4d} {badge:8s} {item['code']}")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Full audit report saved to: {args.output}")

def modernize_test_file(file_path):
    """Modernizes expect(btn.innerHTML).toContain('<tag') to expect(btn.querySelector('tag')).not.toBeNull()."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return 0

    original = content
    # Pattern: expect(element.innerHTML).toContain('<tag')
    def replacer(match):
        element_expr = match.group(1)
        tag_name = match.group(2)
        return f"expect({element_expr}.querySelector('{tag_name}')).not.toBeNull()"

    # Regex matching: expect(btn?.innerHTML).toContain('<kbd') -> expect(btn?.querySelector('kbd')).not.toBeNull()
    updated = re.sub(
        r'expect\(([^)]+?)\.innerHTML\)\.toContain\([\'"]<([a-zA-Z0-9_-]+)[\'"]\)',
        replacer,
        content
    )

    if updated != original:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated)
        return 1
    return 0

def cmd_modernize_tests(args):
    target_dir = os.path.abspath(args.target_dir or os.getcwd())
    print(f"🔧 Modernizing unit test assertions in {target_dir}...")
    updated_files = 0

    for root, _, files in os.walk(target_dir):
        if any(ignored in root for ignored in ["node_modules", ".git", "dist", "build"]):
            continue
        for f in files:
            if re.search(r'\.(test|spec)\.(ts|js|tsx|jsx)$', f):
                full_path = os.path.join(root, f)
                if modernize_test_file(full_path):
                    rel_path = os.path.relpath(full_path, target_dir)
                    print(f"  ✨ Modernized assertions in: {rel_path}")
                    updated_files += 1

    print(f"\n✅ Modernized test assertions across {updated_files} file(s).")

def main():
    parser = argparse.ArgumentParser(description="DOM-based XSS innerHTML Auditor and Test Modernizer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_audit = subparsers.add_parser("audit", help="Audit repository for dynamic innerHTML usage and DOM XSS")
    p_audit.add_argument("--target-dir", help="Directory to scan (default: current directory)")
    p_audit.add_argument("--output", help="Optional JSON output filepath")
    p_audit.set_defaults(func=cmd_audit)

    p_mod = subparsers.add_parser("modernize-tests", help="Modernize test assertions checking innerHTML to DOM queries")
    p_mod.add_argument("--target-dir", help="Directory containing test files (default: current directory)")
    p_mod.set_defaults(func=cmd_modernize_tests)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
