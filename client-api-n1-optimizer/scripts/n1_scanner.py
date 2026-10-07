#!/usr/bin/env python3
"""
client-api-n1-optimizer: Static Analyzer for Serial Client-Side Request Loops
Scans TypeScript/JavaScript files for 'await' inside iterative loops ('for', 'for...of', 'while', 'forEach').
"""

import os
import sys
import re
import argparse
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

LOOP_PATTERNS = [
    (re.compile(r'^\s*for\s*\([^)]+\)\s*\{'), 'for-loop'),
    (re.compile(r'^\s*for\s+await\s*\([^)]+\)\s*\{'), 'for-await-loop'),
    (re.compile(r'^\s*while\s*\([^)]+\)\s*\{'), 'while-loop'),
    (re.compile(r'\.(?:forEach|map)\s*\(\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{'), 'array-method-loop'),
]

AWAIT_REQUEST_PATTERN = re.compile(
    r'await\s+(?:this\.request|fetch|axios|this\.client|api\.\w+|client\.\w+)\s*\('
)

def scan_file_for_n1(file_path):
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        return issues

    open_blocks = [] # stack of (line_num, loop_type, brace_depth)
    current_brace_depth = 0

    for idx, line in enumerate(lines, 1):
        # Count brace changes
        open_braces = line.count('{')
        close_braces = line.count('}')

        # Check for loop start
        for pattern, loop_type in LOOP_PATTERNS:
            if pattern.search(line):
                open_blocks.append({
                    'start_line': idx,
                    'loop_type': loop_type,
                    'brace_depth_at_start': current_brace_depth,
                    'line_snippet': line.strip()
                })
                break

        # Check for await request inside loop
        if open_blocks and AWAIT_REQUEST_PATTERN.search(line):
            innermost_loop = open_blocks[-1]
            issues.append({
                'file': file_path,
                'await_line': idx,
                'await_snippet': line.strip(),
                'loop_start_line': innermost_loop['start_line'],
                'loop_type': innermost_loop['loop_type'],
                'loop_snippet': innermost_loop['line_snippet']
            })

        # Update brace depth
        current_brace_depth += (open_braces - close_braces)

        # Pop finished loops
        while open_blocks and current_brace_depth <= open_blocks[-1]['brace_depth_at_start']:
            open_blocks.pop()

    return issues

def scan_directory(target_dir, extensions=('.ts', '.tsx', '.js', '.jsx')):
    all_issues = []
    for root, _, files in os.walk(target_dir):
        if 'node_modules' in root or '.git' in root or 'dist' in root or 'build' in root:
            continue
        for file in files:
            if file.endswith(extensions) and not file.endswith(('.test.ts', '.test.tsx', '.spec.ts', '.spec.tsx')):
                full_path = os.path.join(root, file)
                issues = scan_file_for_n1(full_path)
                all_issues.extend(issues)
    return all_issues

def main():
    parser = argparse.ArgumentParser(description="Scan TypeScript/JavaScript files for serial N+1 HTTP request loops.")
    parser.add_argument("path", help="File or directory path to scan")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--output", help="Save results to specified filepath")
    args = parser.parse_args()

    target_path = os.path.abspath(args.path)
    if os.path.isfile(target_path):
        results = scan_file_for_n1(target_path)
    elif os.path.isdir(target_path):
        results = scan_directory(target_path)
    else:
        print(f"❌ Error: Path does not exist: {target_path}", file=sys.stderr)
        sys.exit(1)

    if args.json or args.output:
        formatted = json.dumps(results, indent=2)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted)
            print(f"📄 Results saved to: {args.output}")
        if args.json:
            print(formatted)
    else:
        print(f"🔍 Scanned {target_path} — Found {len(results)} potential N+1 loop(s):\n")
        for i, issue in enumerate(results, 1):
            rel_file = os.path.relpath(issue['file'], os.getcwd()) if os.path.isabs(issue['file']) else issue['file']
            print(f"[{i}] {rel_file}:{issue['await_line']}")
            print(f"    Loop ({issue['loop_type']} at line {issue['loop_start_line']}): {issue['loop_snippet']}")
            print(f"    Await call: {issue['await_snippet']}\n")

if __name__ == "__main__":
    main()
