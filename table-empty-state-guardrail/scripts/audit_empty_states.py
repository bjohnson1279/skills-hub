#!/usr/bin/env python3
"""
Table Empty State Guardrail CLI
Audits frontend templates (HTML, JSX, TSX, Vue) for accessible, actionable empty states
in data tables, validates colspan matching, detects lingering conflict markers,
and generates automated test fixtures.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Ensure UTF-8 console output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def audit_file_content(file_path: str, content: str) -> Dict[str, Any]:
    findings = {
        "file": file_path,
        "tables_found": 0,
        "empty_states_found": 0,
        "mismatched_colspans": [],
        "missing_empty_states": [],
        "actionable_buttons_count": 0,
        "conflict_markers": [],
        "warnings": []
    }

    # 1. Detect Git Conflict Markers
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        if re.search(r'<{7}\s|={7}$|>{7}\s', line):
            findings["conflict_markers"].append({"line": idx, "content": line.strip()})

    # 2. Match Tables
    table_blocks = re.findall(r'<table[\s\S]*?</table>', content, re.IGNORECASE)
    findings["tables_found"] = len(table_blocks)

    for block in table_blocks:
        # Count header columns
        th_count = len(re.findall(r'<th[\s>][\s\S]*?</th>', block, re.IGNORECASE))
        
        # Check for empty state row
        colspan_matches = re.findall(r'colspan=["\']?(\d+)', block, re.IGNORECASE)
        has_empty_state = bool(re.search(r'empty|no\s+\w+\s+found|no\s+data|none\s+found', block, re.IGNORECASE))
        
        if has_empty_state:
            findings["empty_states_found"] += 1
            for cs in colspan_matches:
                cs_val = int(cs)
                if th_count > 0 and cs_val != th_count:
                    findings["mismatched_colspans"].append({
                        "header_columns": th_count,
                        "colspan_used": cs_val
                    })
        elif th_count > 0:
            findings["missing_empty_states"].append({
                "header_columns": th_count,
                "reason": "Table contains headers but no static or inline empty state row detected"
            })

    # 3. Dynamic JS/TS rendering checks (e.g. innerHTML or tableBody.innerHTML)
    dynamic_empty_states = re.findall(r'colspan=["\']?(\d+)[^>]*>[\s\S]*?(?:no\s+\w+\s+found|empty|execute|populate)', content, re.IGNORECASE)
    for cs in dynamic_empty_states:
        findings["empty_states_found"] += 1

    # Count actionable call-to-action buttons inside empty states
    cta_matches = re.findall(r'<button[\s\S]*?(?:onclick|@click|onClick)=[\s\S]*?</button>', content, re.IGNORECASE)
    findings["actionable_buttons_count"] = len(cta_matches)

    # 4. Accessibility Check: Persistent Announcer vs Dynamic innerHTML aria-live
    has_persistent_announcer = bool(re.search(r'id=["\']sr-announcer["\']|<div[^>]*aria-live=["\'](?:polite|assertive)["\'][^>]*class=["\'][^"\']*sr-only', content, re.IGNORECASE))
    findings["persistent_announcer_present"] = has_persistent_announcer

    # Detect anti-pattern: aria-live injected dynamically inside innerHTML template strings
    inline_aria_live = re.findall(r'(?:innerHTML\s*=\s*`[\s\S]*?aria-live=["\'](?:polite|assertive)["\']|aria-live=["\'](?:polite|assertive)["\'][^>]*>\s*No\s+\w+\s+found)', content, re.IGNORECASE)
    if inline_aria_live:
        findings["warnings"].append(
            f"Detected {len(inline_aria_live)} instance(s) of inline aria-live injected dynamically in templates/innerHTML. "
            "Migrate to a persistent .sr-only announcer (e.g. #sr-announcer) to ensure screen readers reliably announce dynamic state changes."
        )

    return findings


def scan_target(target_path: str) -> List[Dict[str, Any]]:
    results = []
    p = Path(target_path)
    extensions = {'.html', '.htm', '.jsx', '.tsx', '.vue', '.js', '.ts'}

    if p.is_file():
        if p.suffix.lower() in extensions:
            content = p.read_text(encoding='utf-8', errors='ignore')
            results.append(audit_file_content(str(p), content))
    elif p.is_dir():
        for root, _, files in os.walk(p):
            if any(ignored in root for ignored in ['node_modules', '.git', 'dist', 'build']):
                continue
            for f in files:
                fpath = Path(root) / f
                if fpath.suffix.lower() in extensions:
                    try:
                        content = fpath.read_text(encoding='utf-8', errors='ignore')
                        res = audit_file_content(str(fpath), content)
                        if res["tables_found"] > 0 or res["conflict_markers"]:
                            results.append(res)
                    except Exception:
                        pass
    return results


def generate_test_fixture(target_file: str, output_test_path: str, required_empty_states: Optional[List[str]] = None) -> str:
    states = required_empty_states or [
        "No General Ledger entries found",
        "No agency bill invoices found",
        "No download batches found",
        "No crosswalk rules defined"
    ]
    formatted_states = json.dumps(states, indent=4)
    norm_target = target_file.replace(os.sep, "/")
    
    test_code = f"""import fs from 'fs';
import path from 'path';

describe('UI Empty States & DOM Structure Guardrail', () => {{
  const targetPath = path.resolve(process.cwd(), '{norm_target}');
  let htmlContent: string;

  beforeAll(() => {{
    expect(fs.existsSync(targetPath)).toBe(true);
    htmlContent = fs.readFileSync(targetPath, 'utf-8');
  }});

  it('should not contain any lingering Git merge conflict markers', () => {{
    expect(htmlContent).not.toMatch(/<{{7}}\\s/);
    expect(htmlContent).not.toMatch(/={{7}}/);
    expect(htmlContent).not.toMatch(/>{{7}}\\s/);
  }});

  it('should declare a persistent screen reader announcer live region', () => {{
    // Verify a persistent announcer exists (e.g. #sr-announcer with .sr-only and aria-live="polite")
    expect(htmlContent).toMatch(/(?:id=["']sr-announcer["']|<div[^>]*aria-live=["']polite["'][^>]*class=["'][^"']*sr-only)/);
  }});

  const requiredEmptyStates = {formatted_states};

  test.each(requiredEmptyStates)('should contain empty state: %s and NOT inject inline aria-live', (emptyStateText) => {{
    expect(htmlContent).toContain(emptyStateText);

    // Verify empty state title element does NOT inject inline aria-live (must use global announcer)
    const inlineRegex = new RegExp(`aria-live=["'](?:polite|assertive)["']>\\\\s*${{emptyStateText}}`);
    expect(htmlContent).not.toMatch(inlineRegex);
  }});

  it('should contain actionable Call-To-Action buttons in empty states', () => {{
    expect(htmlContent).toMatch(/<button[^>]*class=["']btn/);
  }});
}});
"""
    os.makedirs(os.path.dirname(os.path.abspath(output_test_path)), exist_ok=True)
    with open(output_test_path, 'w', encoding='utf-8') as f:
        f.write(test_code)
    return test_code


def main():
    parser = argparse.ArgumentParser(description="Table Empty State Guardrail CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan files or directories for table empty state compliance")
    p_scan.add_argument("--target", required=True, help="Target file or directory to scan")
    p_scan.add_argument("--output", default=None, help="Optional output JSON file")

    # generate-test
    p_gen = subparsers.add_parser("generate-test", help="Generate Jest/Vitest test fixture enforcing empty states")
    p_gen.add_argument("--target-file", required=True, help="Path to frontend HTML or template file")
    p_gen.add_argument("--output", required=True, help="Path to write output test file (.test.ts)")
    p_gen.add_argument("--empty-states", default=None, help="Comma-separated list of required empty state strings")

    args = parser.parse_args()

    if args.command == "scan":
        res = scan_target(args.target)
        if args.output:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(res, f, indent=2)
            print(f"✅ Scan complete: {len(res)} file(s) audited. Report saved to {args.output}")
        else:
            print(json.dumps(res, indent=2))

    elif args.command == "generate-test":
        states = [s.strip() for s in args.empty_states.split(',')] if args.empty_states else None
        generate_test_fixture(args.target_file, args.output, states)
        print(f"✅ Test fixture generated at: {args.output}")


if __name__ == '__main__':
    main()