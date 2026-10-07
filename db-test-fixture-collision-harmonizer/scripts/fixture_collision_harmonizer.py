#!/usr/bin/env python3
"""
Database Test Fixture Collision Harmonizer CLI
Audits, detects, and resolves database unique constraint and enum collisions
between test setup seed fixtures (setUp, beforeEach) and test method payloads
across polyglot test suites (PHPUnit, Jest, pytest).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Force UTF-8 console output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Candidate fields prone to unique constraint violations in multi-tenant DDD applications
UNIQUE_KEY_CANDIDATES = [
    r'trigger[eE]vent',
    r'trigger_event',
    r'sku',
    r'email',
    r'code',
    r'slug',
    r'username',
    r'name',
    r'serial_number',
    r'serialNumber',
    r'batch_number',
    r'batchNumber'
]

ALTERNATIVE_ENUMS = {
    "triggerEvent": ["STOCK_ADJUSTED", "STOCK_TRANSFERRED", "CYCLE_COUNT_COMPLETED", "INVENTORY_COUNT_COMPLETED", "SHIPMENT_RECEIVED"],
    "trigger_event": ["STOCK_ADJUSTED", "STOCK_TRANSFERRED", "CYCLE_COUNT_COMPLETED", "INVENTORY_COUNT_COMPLETED", "SHIPMENT_RECEIVED"],
}

def extract_setup_and_tests_php(content):
    """Parses PHPUnit test file into setUp body and individual test method bodies."""
    # Find setUp
    setup_match = re.search(r'function\s+setUp\s*\([^)]*\)[^{]*\{((?:[^{}]*|\{(?:[^{}]*|\{[^{}]*\})*\})*)\}', content)
    setup_body = setup_match.group(1) if setup_match else ""

    # Find test methods
    test_methods = []
    pattern = re.compile(r'public\s+function\s+(test[A-Za-z0-9_]+)\s*\([^)]*\)[^{]*\{((?:[^{}]*|\{(?:[^{}]*|\{[^{}]*\})*\})*)\}')
    for m in pattern.finditer(content):
        test_methods.append({
            "name": m.group(1),
            "body": m.group(2),
            "start": m.start(2),
            "end": m.end(2)
        })
    return setup_body, test_methods

def extract_setup_and_tests_js_ts(content):
    """Parses Jest/Vitest test file into beforeEach body and test blocks (it/test)."""
    setup_match = re.search(r'beforeEach\s*\(\s*(?:async\s*)?\(\s*\)\s*=>\s*\{((?:[^{}]*|\{(?:[^{}]*|\{[^{}]*\})*\})*)\}', content)
    setup_body = setup_match.group(1) if setup_match else ""

    test_methods = []
    pattern = re.compile(r'(?:it|test)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]\s*,\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{((?:[^{}]*|\{(?:[^{}]*|\{[^{}]*\})*\})*)\}')
    for m in pattern.finditer(content):
        test_methods.append({
            "name": m.group(1),
            "body": m.group(2),
            "start": m.start(2),
            "end": m.end(2)
        })
    return setup_body, test_methods

def extract_setup_and_tests_python(content):
    """Parses pytest / unittest test file into setup_method/setUp and test functions."""
    setup_match = re.search(r'def\s+(?:setUp|setup_method)\s*\([^)]*\):((?:\n(?:[ \t]+[^\n]*|\s*))*)', content)
    setup_body = setup_match.group(1) if setup_match else ""

    test_methods = []
    pattern = re.compile(r'def\s+(test_[a-zA-Z0-9_]+)\s*\([^)]*\):((?:\n(?:[ \t]+[^\n]*|\s*))*)')
    for m in pattern.finditer(content):
        test_methods.append({
            "name": m.group(1),
            "body": m.group(2),
            "start": m.start(2),
            "end": m.end(2)
        })
    return setup_body, test_methods

def find_field_assignments(code_chunk):
    """Extracts key-value assignments for unique field candidates."""
    assignments = {}
    for key_pattern in UNIQUE_KEY_CANDIDATES:
        # PHP array: 'field' => 'value' or "field" => "value"
        php_re = re.compile(rf'[\'"]({key_pattern})[\'"]\s*=>\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
        for m in php_re.finditer(code_chunk):
            assignments[m.group(1)] = m.group(2)

        # JS/TS object: field: 'value' or 'field': 'value'
        js_re = re.compile(rf'(?:[\'"]?({key_pattern})[\'"]?)\s*:\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
        for m in js_re.finditer(code_chunk):
            assignments[m.group(1)] = m.group(2)

        # Python kwargs/dict: field="value" or 'field': "value"
        py_re = re.compile(rf'({key_pattern})\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
        for m in py_re.finditer(code_chunk):
            assignments[m.group(1)] = m.group(2)
    return assignments

def audit_test_file(filepath):
    """Audits a single test file for setup vs test payload collisions."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return []

    ext = Path(filepath).suffix.lower()
    if ext == ".php":
        setup_body, tests = extract_setup_and_tests_php(content)
    elif ext in [".ts", ".js", ".tsx", ".jsx"]:
        setup_body, tests = extract_setup_and_tests_js_ts(content)
    elif ext == ".py":
        setup_body, tests = extract_setup_and_tests_python(content)
    else:
        return []

    if not setup_body or not tests:
        return []

    setup_fields = find_field_assignments(setup_body)
    if not setup_fields:
        return []

    collisions = []
    for test in tests:
        test_fields = find_field_assignments(test["body"])
        for k, v in test_fields.items():
            # Check if matching key in setup has the exact same value
            for sk, sv in setup_fields.items():
                if k.lower() == sk.lower() and v == sv:
                    collisions.append({
                        "file": filepath,
                        "test_name": test["name"],
                        "field": k,
                        "colliding_value": v,
                        "setup_value": sv
                    })
    return collisions

def scan_directory(target_dir):
    """Recursively scans directories for test files and detects fixture collisions."""
    target_path = Path(target_dir)
    results = []
    test_extensions = {".php", ".ts", ".js", ".py"}

    for root, _, files in os.walk(target_path):
        # Skip vendor, node_modules, .git, venv
        if any(skip in root.lower() for skip in ["node_modules", "vendor", ".git", ".venv", "venv"]):
            continue
        for file in files:
            p = Path(os.path.join(root, file))
            if p.suffix.lower() in test_extensions:
                fname = p.name.lower()
                if "test" in fname or "spec" in fname:
                    collisions = audit_test_file(str(p))
                    if collisions:
                        results.extend(collisions)
    return results

def repair_collision(filepath, field, colliding_value):
    """Replaces colliding value in test methods with a safe disjoint alternative."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find alternatives
    alternatives = ALTERNATIVE_ENUMS.get(field, [])
    replacement = None
    for alt in alternatives:
        if alt != colliding_value and alt not in content:
            replacement = alt
            break

    if not replacement:
        replacement = f"{colliding_value}_ALT"

    # Only replace in test methods, strictly after setUp / beforeEach ends
    ext = Path(filepath).suffix.lower()
    setup_end = 0
    if ext == ".php":
        sm = re.search(r'function\s+setUp\s*\([^)]*\)[^{]*\{((?:[^{}]*|\{(?:[^{}]*|\{[^{}]*\})*\})*)\}', content)
        if sm:
            setup_end = sm.end()
    elif ext in [".ts", ".js", ".tsx", ".jsx"]:
        sm = re.search(r'beforeEach\s*\(\s*(?:async\s*)?\(\s*\)\s*=>\s*\{((?:[^{}]*|\{(?:[^{}]*|\{[^{}]*\})*\})*)\}', content)
        if sm:
            setup_end = sm.end()
    elif ext == ".py":
        sm = re.search(r'def\s+(?:setUp|setup_method)\s*\([^)]*\):((?:\n(?:[ \t]+[^\n]*|\s*))*)', content)
        if sm:
            setup_end = sm.end()

    if setup_end == 0:
        sm = re.search(r'(?:function\s+setUp|beforeEach|def\s+setUp)[^{:]*[{:]', content)
        setup_end = sm.end() if sm else 0

    # Match target pattern in test bodies
    pattern_php = re.compile(rf'([\'"]{re.escape(field)}[\'"]\s*=>\s*[\'"]){re.escape(colliding_value)}([\'"])')
    pattern_js = re.compile(rf'([\'"]?{re.escape(field)}[\'"]?\s*:\s*[\'"]){re.escape(colliding_value)}([\'"])')
    pattern_py = re.compile(rf'({re.escape(field)}\s*=\s*[\'"]){re.escape(colliding_value)}([\'"])')

    new_content = content
    # Replace in second half after setUp
    after_setup = content[setup_end:]
    # Replace occurrences in test methods
    count = 0
    if pattern_php.search(after_setup):
        after_setup, count = pattern_php.subn(rf'\g<1>{replacement}\g<2>', after_setup)
    elif pattern_js.search(after_setup):
        after_setup, count = pattern_js.subn(rf'\g<1>{replacement}\g<2>', after_setup)
    elif pattern_py.search(after_setup):
        after_setup, count = pattern_py.subn(rf'\g<1>{replacement}\g<2>', after_setup)

    if count > 0:
        new_content = content[:setup_end] + after_setup
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return replacement, count
    return None, 0

def cmd_scan(args):
    target = os.path.abspath(args.path)
    print(f"🔍 Scanning for test fixture unique constraint collisions in: {target}...")
    if os.path.isfile(target):
        collisions = audit_test_file(target)
    else:
        collisions = scan_directory(target)

    if not collisions:
        print("✅ No test fixture collisions detected.")
        return

    print(f"⚠️ Detected {len(collisions)} fixture collision(s):\n")
    for c in collisions:
        rel_file = os.path.relpath(c['file'], target) if os.path.isdir(target) else os.path.basename(c['file'])
        print(f"  • {rel_file} -> {c['test_name']}: Field '{c['field']}' collides with setUp ('{c['colliding_value']}')")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(collisions, f, indent=2)
        print(f"\n📊 JSON report written to: {args.output}")

def cmd_repair(args):
    target = os.path.abspath(args.path)
    print(f"🔧 Scanning and repairing test fixture collisions in: {target}...")
    if os.path.isfile(target):
        collisions = audit_test_file(target)
    else:
        collisions = scan_directory(target)

    if not collisions:
        print("✅ No test fixture collisions to repair.")
        return

    repaired_count = 0
    for c in collisions:
        rep, count = repair_collision(c["file"], c["field"], c["colliding_value"])
        if count > 0:
            rel_file = os.path.relpath(c['file'], target) if os.path.isdir(target) else os.path.basename(c['file'])
            print(f"  ✅ Repaired {rel_file} ({c['test_name']}): '{c['colliding_value']}' -> '{rep}'")
            repaired_count += 1

    print(f"\n🎉 Successfully repaired {repaired_count} fixture collision(s).")

def main():
    parser = argparse.ArgumentParser(description="Database Test Fixture Collision Harmonizer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_scan = subparsers.add_parser("scan", help="Scan test suites for fixture collisions")
    p_scan.add_argument("--path", required=True, help="Target file or directory path")
    p_scan.add_argument("--output", default=None, help="Optional output JSON file")
    p_scan.set_defaults(func=cmd_scan)

    p_repair = subparsers.add_parser("repair", help="Auto-repair test fixture collisions")
    p_repair.add_argument("--path", required=True, help="Target file or directory path")
    p_repair.set_defaults(func=cmd_repair)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
