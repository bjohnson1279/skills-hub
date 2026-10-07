#!/usr/bin/env python3
"""
Accessibility DOM Feature Test Augmenter
Scans git diffs or source files for newly introduced WCAG accessibility features
(skip-links, aria-live, modal dialog roles, aria-hidden emojis, tabindex attributes)
and automatically generates or augments test assertions in frontend test suites.
"""

import argparse
import os
import re
import sys

# Windows UTF-8 safety
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def scan_a11y_features(html_or_diff):
    features = []

    # 1. Skip to Content Link
    if re.search(r'href=["\']#main(?:-content)?["\']', html_or_diff, re.IGNORECASE) and 'skip' in html_or_diff.lower():
        features.append({
            "type": "skip_link",
            "description": "Skip to main content anchor and target container tabindex=-1",
            "regex": [
                r'<a[^>]*href=["\']#main(?:-content)?["\'][^>]*class=["\'][^"\']*skip-link[^"\']*["\'][^>]*>Skip to main content</a>',
                r'<main[^>]*id=["\']main(?:-content)?["\'][^>]*tabindex=["\']-1["\']'
            ],
            "assertion_name": "should contain a functional skip-to-content link for keyboard accessibility"
        })

    # 2. Persistent Screen Reader Announcer
    if 'id="sr-announcer"' in html_or_diff or 'aria-live=' in html_or_diff:
        features.append({
            "type": "sr_announcer",
            "description": "Persistent screen reader live region",
            "regex": [
                r'<div[^>]*id=["\']sr-announcer["\'][^>]*aria-live=["\'](?:polite|assertive)["\']'
            ],
            "assertion_name": "should contain a persistent screen reader announcer region"
        })

    # 3. Hidden Decorative Emojis
    if re.search(r'<span[^>]*aria-hidden=["\']true["\'][^>]*>[\U00010000-\U0010ffff]', html_or_diff):
        features.append({
            "type": "aria_hidden_emoji",
            "description": "Decorative emojis hidden from assistive technology",
            "regex": [
                r'<span[^>]*aria-hidden=["\']true["\']'
            ],
            "assertion_name": "should hide decorative visual emojis with aria-hidden"
        })

    return features

def generate_test_snippet(features):
    lines = []
    for f in features:
        lines.append(f"  it('{f['assertion_name']}', () => {{")
        lines.append(f"    // 🎨 Palette / A11y Guardrail: {f['description']}")
        for r in f['regex']:
            escaped = r.replace('\\', '\\\\')
            lines.append(f"    expect(htmlContent).toMatch(/{escaped}/);")
        lines.append("  });\n")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Accessibility DOM Feature Test Augmenter")
    parser.add_argument("--scan-file", help="HTML or component source file to inspect")
    parser.add_argument("--scan-diff", help="Unified diff text file to inspect")
    parser.add_argument("--target-test", help="Target test suite file to augment")
    parser.add_argument("--dry-run", action="store_true", help="Print generated test assertions without writing")
    args = parser.parse_args()

    content = ""
    if args.scan_file and os.path.exists(args.scan_file):
        with open(args.scan_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    elif args.scan_diff and os.path.exists(args.scan_diff):
        with open(args.scan_diff, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    else:
        print("Error: Must provide --scan-file or --scan-diff", file=sys.stderr)
        sys.exit(1)

    features = scan_a11y_features(content)
    if not features:
        print("No new accessibility DOM features detected.")
        sys.exit(0)

    print(f"Detected {len(features)} accessibility feature(s):")
    for f in features:
        print(f"  - {f['type']}: {f['description']}")

    test_code = generate_test_snippet(features)

    if args.target_test and not args.dry_run:
        if os.path.exists(args.target_test):
            with open(args.target_test, 'r', encoding='utf-8') as f:
                existing = f.read()
            # Insert before last closing });
            idx = existing.rfind("});")
            if idx != -1:
                updated = existing[:idx] + test_code + existing[idx:]
                with open(args.target_test, 'w', encoding='utf-8') as f:
                    f.write(updated)
                print(f"✅ Successfully augmented {args.target_test}")
            else:
                print("Could not find closing '});' in test file", file=sys.stderr)
        else:
            print(f"Target test file {args.target_test} not found", file=sys.stderr)
    else:
        print("\nGenerated Test Snippet:")
        print(test_code)

if __name__ == '__main__':
    main()
