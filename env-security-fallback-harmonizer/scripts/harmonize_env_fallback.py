#!/usr/bin/env python3
"""
harmonize_env_fallback.py

Automated scanner and patcher to detect and harmonize aggressive environment secret removals
that break test environments while ensuring production remains strictly secure.
"""

import argparse
import json
import os
import re
import subprocess
import sys

# Force UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def run_cmd(cmd, cwd=None):
    try:
        is_shell = isinstance(cmd, str)
        res = subprocess.run(cmd, shell=is_shell, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=cwd)
        return res.stdout.strip(), res.stderr.strip(), res.returncode
    except Exception as e:
        return "", str(e), 1

def detect_language(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.ts', '.js', '.tsx', '.jsx']:
        return 'typescript'
    elif ext in ['.php']:
        return 'php'
    elif ext in ['.py']:
        return 'python'
    elif ext in ['.go']:
        return 'go'
    return 'unknown'

def scan_content_for_unprotected_env_throws(content, lang):
    """
    Detects if missing env variable throws without checking test environment.
    """
    issues = []
    
    if lang == 'typescript':
        # 1. Direct check: if (!process.env.VAR) { throw ... }
        for m in re.finditer(r'if\s*\(\s*!process\.env\.([A-Z0-9_]+)\s*\)\s*\{\s*throw\s+new\s+Error\([^)]+\)', content):
            var_name = m.group(1)
            start = max(0, m.start() - 300)
            end = min(len(content), m.end() + 300)
            context = content[start:end]
            if 'NODE_ENV' not in context and 'test' not in context:
                issues.append({
                    'var': var_name,
                    'lang': 'typescript',
                    'snippet': m.group(0),
                    'recommended_replacement': f"process.env.{var_name} || (process.env.NODE_ENV === 'test' ? 'test-{var_name.lower()}' : undefined)"
                })
        # 2. Assigned check: const VAR = process.env.VAR; if (!VAR) { throw ... }
        for m in re.finditer(r'(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*process\.env\.([A-Z0-9_]+)[^;\n]*;[\s\S]{0,150}?if\s*\(\s*!\1\s*\)\s*\{\s*throw\s+new\s+Error\([^)]+\)', content):
            var_name = m.group(2)
            start = max(0, m.start() - 300)
            end = min(len(content), m.end() + 300)
            context = content[start:end]
            if 'NODE_ENV' not in context and 'test' not in context:
                issues.append({
                    'var': var_name,
                    'lang': 'typescript',
                    'snippet': m.group(0),
                    'recommended_replacement': f"const {m.group(1)} = process.env.{var_name} || (process.env.NODE_ENV === 'test' ? 'test-{var_name.lower()}' : undefined);"
                })

    elif lang == 'php':
        for m in re.finditer(r'if\s*\(\s*!(?:getenv\([\'"]([A-Z0-9_]+)[\'"]\)|empty\(getenv\([\'"]([A-Z0-9_]+)[\'"]\)\))\s*\)\s*\{\s*throw\s+new\s+\\?(?:RuntimeException|Exception)\([^)]+\)', content):
            var_name = m.group(1) or m.group(2)
            start = max(0, m.start() - 300)
            end = min(len(content), m.end() + 300)
            context = content[start:end]
            if 'APP_ENV' not in context and 'testing' not in context:
                issues.append({
                    'var': var_name,
                    'lang': 'php',
                    'snippet': m.group(0),
                    'recommended_replacement': f"getenv('{var_name}') ?: (getenv('APP_ENV') === 'testing' ? 'test-{var_name.lower()}' : null)"
                })
        for m in re.finditer(r'\$([A-Za-z0-9_]+)\s*=\s*getenv\([\'"]([A-Z0-9_]+)[\'"]\)[^;\n]*;[\s\S]{0,150}?if\s*\(\s*!\$\1\s*\)\s*\{\s*throw\s+new\s+\\?(?:RuntimeException|Exception)\([^)]+\)', content):
            var_name = m.group(2)
            start = max(0, m.start() - 300)
            end = min(len(content), m.end() + 300)
            context = content[start:end]
            if 'APP_ENV' not in context and 'testing' not in context:
                issues.append({
                    'var': var_name,
                    'lang': 'php',
                    'snippet': m.group(0),
                    'recommended_replacement': f"${m.group(1)} = getenv('{var_name}') ?: (getenv('APP_ENV') === 'testing' ? 'test-{var_name.lower()}' : null);"
                })

    elif lang == 'python':
        for m in re.finditer(r'if\s+not\s+os\.(?:getenv|environ\.get)\([\'"]([A-Z0-9_]+)[\'"]\)\s*:\s*raise\s+(?:ValueError|RuntimeError)\([^)]+\)', content):
            var_name = m.group(1)
            start = max(0, m.start() - 300)
            end = min(len(content), m.end() + 300)
            context = content[start:end]
            if 'APP_ENV' not in context and 'pytest' not in context:
                issues.append({
                    'var': var_name,
                    'lang': 'python',
                    'snippet': m.group(0),
                    'recommended_replacement': f'os.getenv("{var_name}") or ("test-{var_name.lower()}" if os.getenv("APP_ENV") == "test" else None)'
                })
        for m in re.finditer(r'([a-zA-Z0-9_]+)\s*=\s*os\.(?:getenv|environ\.get)\([\'"]([A-Z0-9_]+)[\'"]\)[^\n]*\n[\s\S]{0,150}?if\s+not\s+\1\s*:\s*raise\s+(?:ValueError|RuntimeError)\([^)]+\)', content):
            var_name = m.group(2)
            start = max(0, m.start() - 300)
            end = min(len(content), m.end() + 300)
            context = content[start:end]
            if 'APP_ENV' not in context and 'pytest' not in context:
                issues.append({
                    'var': var_name,
                    'lang': 'python',
                    'snippet': m.group(0),
                    'recommended_replacement': f'{m.group(1)} = os.getenv("{var_name}") or ("test-{var_name.lower()}" if os.getenv("APP_ENV") == "test" else None)'
                })


    return issues

def audit_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    lang = detect_language(file_path)
    return scan_content_for_unprotected_env_throws(content, lang)

def audit_pr(repo, pr_num):
    diff_out, err, code = run_cmd(f"gh pr diff {pr_num} -R {repo}")
    if code != 0 or not diff_out:
        return {"error": f"Failed to get diff for PR {repo}#{pr_num}: {err}"}

    issues = []
    current_file = None
    file_diff_lines = {}
    for line in diff_out.splitlines():
        if line.startswith('diff --git '):
            parts = line.split(' b/')
            if len(parts) == 2:
                current_file = parts[1]
                file_diff_lines[current_file] = []
        elif current_file:
            file_diff_lines[current_file].append(line)

    for file_path, lines in file_diff_lines.items():
        lang = detect_language(file_path)
        if lang != 'unknown':
            added_content = "\n".join([l[1:] for l in lines if l.startswith('+') and not l.startswith('+++')])
            found = scan_content_for_unprotected_env_throws(added_content, lang)
            for item in found:
                item['file'] = file_path
                issues.append(item)

    return {
        "repo": repo,
        "pr": pr_num,
        "total_issues": len(issues),
        "issues": issues
    }

def main():
    parser = argparse.ArgumentParser(description="Env Security Fallback Harmonizer")
    parser.add_argument("--repo", help="GitHub repository (owner/repo)")
    parser.add_argument("--pr", type=int, help="PR number to scan")
    parser.add_argument("--file", help="Local file path to scan")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    if args.repo and args.pr:
        res = audit_pr(args.repo, args.pr)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Audit for {args.repo}#{args.pr}:")
            if res.get("issues"):
                print(f"  Found {len(res['issues'])} unprotected secret throw(s) that may break test suites:")
                for item in res["issues"]:
                    print(f"  - File: {item.get('file')}")
                    print(f"    Variable: {item['var']} ({item['lang']})")
                    print(f"    Recommended Guard: {item['recommended_replacement']}")
            else:
                print("  ✅ No aggressive/unprotected env secret throws detected.")

    elif args.file:
        issues = audit_file(args.file)
        if args.json:
            print(json.dumps(issues, indent=2))
        else:
            print(f"Audit for {args.file}:")
            if issues:
                print(f"  Found {len(issues)} unprotected secret throw(s):")
                for item in issues:
                    print(f"  - Variable: {item['var']} ({item['lang']})")
                    print(f"    Recommended Guard: {item['recommended_replacement']}")
            else:
                print("  ✅ Clean: environment variables have test fallback guards.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
