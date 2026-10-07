import os
import re
import sys
import subprocess

def scan_file_for_duplicate_keys(file_path):
    """
    Scans a TypeScript file for object literals with duplicate keys (TS1117).
    """
    if not os.path.exists(file_path):
        return []
        
    issues = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        prop_match = re.search(r'^\s*([a-zA-Z0-9_$]+)\s*:', line)
        if prop_match:
            prop_name = prop_match.group(1)
            # Check for duplicate key in surrounding context lines (simple window check)
            context_start = max(0, i - 15)
            context = lines[context_start:i-1]
            for c_idx, c_line in enumerate(context, start=context_start + 1):
                c_match = re.search(r'^\s*' + re.escape(prop_name) + r'\s*:', c_line)
                if c_match:
                    between = lines[c_idx:i-1]
                    brace_count = sum(l.count('{') - l.count('}') for ll in between for l in [ll.split('//')[0]])
                    if brace_count == 0:
                        issues.append((i, prop_name, c_idx))
                        break
    return issues

def scan_file_for_mock_leaks(file_path):
    """
    Scans a TypeScript test file for spyOn mock leakage without proper isolation.
    """
    if not os.path.exists(file_path):
        return []

    issues = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    has_after_each_restore = bool(re.search(r'afterEach\s*\(\s*(?:\(\s*\)\s*=>|function\s*\(\s*\))\s*\{[^}]*(?:restoreAllMocks|clearAllMocks)', content))

    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        # Match persistent spy mockImplementation or mockReturnValue
        spy_match = re.search(r'(?:jest|vi)\.spyOn\s*\([^)]+\)\s*\.(mockImplementation|mockReturnValue)\s*\(', line)
        if spy_match and not has_after_each_restore:
            method_type = spy_match.group(1)
            # Check if this line or next lines do mockImplementationOnce instead
            if not method_type.endswith('Once'):
                issues.append((i, method_type, line.strip()))
    return issues

def fix_file_mock_leaks(file_path):
    """
    Refactors persistent spyOn mockImplementation into mockImplementationOnce.
    """
    if not os.path.exists(file_path):
        return 0

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    new_content, count = re.subn(
        r'((?:jest|vi)\.spyOn\s*\([^)]+\)\s*\.mockImplementation)\s*\(',
        r'\1Once(',
        content
    )

    if count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
    return count

def run_tsc_check(target_dir):
    """
    Runs tsc --noEmit to find all TypeScript compilation errors across test files.
    """
    print(f"\nRunning TypeScript syntax check on {target_dir}...")
    try:
        res = subprocess.run(['npx', 'tsc', '--noEmit'], cwd=target_dir, capture_output=True, text=True, shell=True)
        if res.returncode == 0:
            print("[OK] TypeScript syntax check passed cleanly with 0 errors!")
            return True
        else:
            print("[!] Found TypeScript compilation errors:")
            for line in res.stdout.splitlines()[:25]:
                print("  ", line)
            return False
    except Exception as e:
        print(f"Error running tsc: {e}")
        return False

def main():
    args = sys.argv[1:]
    fix_leaks = '--fix-mock-leaks' in args
    target_args = [a for a in args if not a.startswith('--')]
    target_dir = target_args[0] if target_args else '.'
    test_dir = os.path.join(target_dir, 'tests') if os.path.exists(os.path.join(target_dir, 'tests')) else target_dir

    print(f"Scanning TypeScript test files in {test_dir}...")
    total_files = 0
    duplicate_key_count = 0
    mock_leak_count = 0

    for root, _, files in os.walk(test_dir):
        for file in files:
            if file.endswith('.ts') or file.endswith('.tsx'):
                full_path = os.path.join(root, file)
                if not os.path.exists(full_path):
                    continue
                total_files += 1
                issues = scan_file_for_duplicate_keys(full_path)
                if issues:
                    rel_path = os.path.relpath(full_path, target_dir)
                    print(f"\n[Duplicate Keys Found] {rel_path}:")
                    for line_num, prop, prev_line in issues[:10]: # Top 10 per file
                        print(f"  Line {line_num}: Property '{prop}' duplicates key from line {prev_line}")
                    duplicate_key_count += len(issues)

                leak_issues = scan_file_for_mock_leaks(full_path)
                if leak_issues:
                    rel_path = os.path.relpath(full_path, target_dir)
                    print(f"\n[Potential Mock Leakage] {rel_path}:")
                    for line_num, method_type, line_text in leak_issues[:5]:
                        print(f"  Line {line_num}: Persistent .{method_type}() without afterEach restore. Suggest using mockImplementationOnce()")
                    mock_leak_count += len(leak_issues)

                    if fix_leaks:
                        fixes = fix_file_mock_leaks(full_path)
                        if fixes > 0:
                            print(f"  --> Auto-refactored {fixes} spy call(s) to mockImplementationOnce()")

    print(f"\nScanned {total_files} files.")
    print(f"Total duplicate object key warnings: {duplicate_key_count}")
    print(f"Total un-isolated spy mock warnings: {mock_leak_count}")
    run_tsc_check(target_dir)

if __name__ == '__main__':
    main()
