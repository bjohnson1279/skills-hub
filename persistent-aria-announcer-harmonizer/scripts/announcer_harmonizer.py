#!/usr/bin/env python3
"""
Persistent ARIA Announcer Harmonizer CLI
Audits frontend markup and scripts for dynamic aria-live injection anti-patterns (innerHTML,
template literals), provides scaffolding for persistent .sr-only announcer regions, and
generates automated accessibility regression tests.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Ensure UTF-8 output streams on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def audit_markup(file_path: str, content: str) -> Dict[str, Any]:
    findings = {
        "file": file_path,
        "has_persistent_announcer": False,
        "announcer_ids": [],
        "inline_dynamic_aria_live_instances": [],
        "announcement_calls": [],
        "recommendations": []
    }

    # Check for persistent announcer container in static HTML/DOM
    announcer_matches = re.findall(
        r'<div[^>]*?(?:id=["\'](sr-announcer|live-announcer|screen-reader-announcer)["\']|aria-live=["\'](?:polite|assertive)["\'][^>]*?class=["\'][^"\']*sr-only[^"\']*)[^>]*?>',
        content,
        re.IGNORECASE
    )
    if announcer_matches or 'id="sr-announcer"' in content or "id='sr-announcer'" in content:
        findings["has_persistent_announcer"] = True
        findings["announcer_ids"] = list(set([m for m in announcer_matches if isinstance(m, str) and m]))

    # Detect anti-pattern: aria-live inside innerHTML assignments or dynamic template strings
    inline_live_regexes = [
        r'innerHTML\s*=\s*`[\s\S]*?aria-live=["\'](?:polite|assertive)["\']',
        r'innerHTML\s*=\s*["\'][^"\']*aria-live=["\'](?:polite|assertive)["\']',
        r'aria-live=["\'](?:polite|assertive)["\'][^>]*>\s*No\s+\w+\s+found'
    ]
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        if 'aria-live' in line:
            # Check if this line looks like dynamic insertion or template string
            if re.search(r'innerHTML|\.html\(|`.*?aria-live|<tr|<td|<div[^>]*style=', line):
                if 'id="sr-announcer"' not in line and "class=\"sr-only\"" not in line and "class='sr-only'" not in line:
                    findings["inline_dynamic_aria_live_instances"].append({
                        "line": idx,
                        "snippet": line.strip()[:120]
                    })

    # Detect dispatcher function calls (e.g. announceToScreenReader, announce)
    announcement_calls = re.findall(r'(?:announceToScreenReader|announce|speakToScreenReader)\s*\(\s*([^)]+)\)', content)
    findings["announcement_calls"] = [c.strip() for c in announcement_calls]

    # Formulate recommendations
    if not findings["has_persistent_announcer"]:
        findings["recommendations"].append(
            "Add a persistent <div id=\"sr-announcer\" class=\"sr-only\" aria-live=\"polite\"></div> to static markup."
        )
    if findings["inline_dynamic_aria_live_instances"]:
        findings["recommendations"].append(
            f"Remove {len(findings['inline_dynamic_aria_live_instances'])} instance(s) of inline aria-live attributes from dynamic template strings and replace them with announceToScreenReader(message) calls."
        )

    return findings


def scan_path(target_path: str) -> List[Dict[str, Any]]:
    results = []
    p = Path(target_path)
    extensions = {'.html', '.htm', '.jsx', '.tsx', '.vue', '.js', '.ts'}

    if p.is_file():
        if p.suffix.lower() in extensions:
            content = p.read_text(encoding='utf-8', errors='ignore')
            results.append(audit_markup(str(p), content))
    elif p.is_dir():
        for root, _, files in os.walk(p):
            if any(ignored in root for ignored in ['node_modules', '.git', 'dist', 'build']):
                continue
            for f in files:
                fpath = Path(root) / f
                if fpath.suffix.lower() in extensions:
                    try:
                        content = fpath.read_text(encoding='utf-8', errors='ignore')
                        res = audit_markup(str(fpath), content)
                        if res["inline_dynamic_aria_live_instances"] or res["has_persistent_announcer"]:
                            results.append(res)
                    except Exception:
                        pass
    return results


def get_scaffold_snippets() -> Dict[str, str]:
    css = """.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}"""

    html = '<div id="sr-announcer" class="sr-only" aria-live="polite"></div>'

    js = """function announceToScreenReader(message) {
  const announcer = document.getElementById('sr-announcer');
  if (announcer) {
    announcer.textContent = message;
  }
}"""

    return {
        "css": css,
        "html": html,
        "javascript": js
    }


def generate_test_suite(target_file: str, output_path: str, sample_messages: Optional[List[str]] = None) -> str:
    norm_path = target_file.replace(os.sep, "/")
    messages = sample_messages or ["No items found", "Data updated successfully"]
    formatted_messages = json.dumps(messages, indent=4)

    test_content = f"""import fs from 'fs';
import path from 'path';

describe('Persistent Screen Reader Announcer Accessibility Guardrail', () => {{
  const targetPath = path.resolve(process.cwd(), '{norm_path}');
  let fileContent: string;

  beforeAll(() => {{
    expect(fs.existsSync(targetPath)).toBe(true);
    fileContent = fs.readFileSync(targetPath, 'utf-8');
  }});

  it('should declare a persistent screen reader live region in static markup', () => {{
    expect(fileContent).toMatch(/(?:id=["']sr-announcer["']|<div[^>]*aria-live=["']polite["'][^>]*class=["'][^"']*sr-only)/);
  }});

  it('should define .sr-only CSS class for accessible visual hiding', () => {{
    expect(fileContent).toContain('.sr-only');
    expect(fileContent).toMatch(/clip:\\s*rect\\(0,\\s*0,\\s*0,\\s*0\\)/);
  }});

  it('should implement an announcement dispatcher function', () => {{
    expect(fileContent).toMatch(/function\\s+announceToScreenReader|const\\s+announceToScreenReader/);
  }});

  it('should NOT inject aria-live attributes dynamically via innerHTML template strings', () => {{
    const dynamicLiveMatches = fileContent.match(/innerHTML\\s*=\\s*`[\\s\\S]*?aria-live=["'](?:polite|assertive)["']/g);
    expect(dynamicLiveMatches).toBeNull();
  }});

  const testMessages = {formatted_messages};

  test.each(testMessages)('dynamic state: "%s" should not contain inline aria-live attribute', (msg) => {{
    const inlineRegex = new RegExp(`aria-live=["'](?:polite|assertive)["']>\\\\s*${{msg}}`);
    expect(fileContent).not.toMatch(inlineRegex);
  }});
}});
"""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    return test_content


def main():
    parser = argparse.ArgumentParser(description="Persistent ARIA Announcer Harmonizer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan files for dynamic aria-live anti-patterns")
    p_scan.add_argument("--target", required=True, help="Target file or directory to scan")
    p_scan.add_argument("--output", default=None, help="Optional output JSON filepath")

    # scaffold
    p_scaffold = subparsers.add_parser("scaffold", help="Output boilerplate code snippets for persistent announcer")
    p_scaffold.add_argument("--output", default=None, help="Optional output JSON filepath")

    # generate-test
    p_test = subparsers.add_parser("generate-test", help="Generate Jest/Vitest accessibility test suite")
    p_test.add_argument("--target-file", required=True, help="Path to markup/component file")
    p_test.add_argument("--output", required=True, help="Path to write output test file (.test.ts)")
    p_test.add_argument("--messages", default=None, help="Comma-separated list of dynamic state messages to test")

    args = parser.parse_args()

    if args.command == "scan":
        results = scan_path(args.target)
        if args.output:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            print(f"✅ Scan complete: {len(results)} file(s) evaluated. Saved to: {args.output}")
        else:
            print(json.dumps(results, indent=2))

    elif args.command == "scaffold":
        snippets = get_scaffold_snippets()
        if args.output:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(snippets, f, indent=2)
            print(f"✅ Scaffolding snippets saved to: {args.output}")
        else:
            print(json.dumps(snippets, indent=2))

    elif args.command == "generate-test":
        msgs = [m.strip() for m in args.messages.split(',')] if args.messages else None
        generate_test_suite(args.target_file, args.output, msgs)
        print(f"✅ Accessibility test suite generated at: {args.output}")


if __name__ == '__main__':
    main()
