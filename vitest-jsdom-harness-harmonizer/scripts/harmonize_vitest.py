#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys

# Force UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STORAGE_MOCK_CODE = """
// Polyfill in-memory localStorage and sessionStorage for JSDOM
if (typeof window !== 'undefined') {
  const createStorageMock = () => {
    let store: Record<string, string> = {};
    return {
      getItem: (key: string) => store[key] || null,
      setItem: (key: string, value: string) => {
        store[key] = String(value);
      },
      removeItem: (key: string) => {
        delete store[key];
      },
      clear: () => {
        store = {};
      },
      key: (index: number) => Object.keys(store)[index] || null,
      get length() {
        return Object.keys(store).length;
      }
    };
  };

  if (!window.localStorage || typeof window.localStorage.getItem !== 'function') {
    Object.defineProperty(window, 'localStorage', {
      value: createStorageMock(),
      writable: true,
      configurable: true
    });
  }

  if (!window.sessionStorage || typeof window.sessionStorage.getItem !== 'function') {
    Object.defineProperty(window, 'sessionStorage', {
      value: createStorageMock(),
      writable: true,
      configurable: true
    });
  }
}
"""

def detect_vitest_version(project_dir):
    """Detects installed or configured Vitest major version from package.json."""
    pkg_path = os.path.join(project_dir, "package.json")
    if not os.path.exists(pkg_path):
        return 2
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        ver_str = deps.get("vitest") or dev_deps.get("vitest", "")
        m = re.search(r"(\d+)", ver_str)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return 2

def harmonize_storage_mock(setup_file_path):
    if not os.path.exists(setup_file_path):
        print(f"Creating new setup file: {setup_file_path}")
        with open(setup_file_path, "w", encoding="utf-8") as f:
            f.write("import '@testing-library/jest-dom';\n" + STORAGE_MOCK_CODE)
        return True

    with open(setup_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "createStorageMock" in content or ("localStorage" in content and "getItem" in content):
        print(f"Storage mock already present in {setup_file_path}")
        return False

    print(f"Injecting in-memory storage mock into {setup_file_path}...")
    with open(setup_file_path, "w", encoding="utf-8") as f:
        f.write(content + "\n" + STORAGE_MOCK_CODE)
    return True

def strip_nested_block(content, key_pattern):
    match = re.search(key_pattern, content)
    if not match:
        return content, False

    start = match.start()
    brace_idx = content.find('{', match.end() - 1)
    if brace_idx == -1:
        return content, False

    depth = 1
    idx = brace_idx + 1
    in_single_quote = False
    in_double_quote = False
    in_backtick = False
    escape = False

    while idx < len(content) and depth > 0:
        ch = content[idx]
        if escape:
            escape = False
        elif ch == '\\':
            escape = True
        elif ch == "'" and not in_double_quote and not in_backtick:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote and not in_backtick:
            in_double_quote = not in_double_quote
        elif ch == '`' and not in_single_quote and not in_double_quote:
            in_backtick = not in_backtick
        elif not in_single_quote and not in_double_quote and not in_backtick:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
        idx += 1

    if depth == 0:
        # Also consume optional trailing comma and whitespace
        while idx < len(content) and content[idx] in ' \t,':
            idx += 1
        if idx < len(content) and content[idx] == '\n':
            idx += 1
        new_content = content[:start] + content[idx:]
        return new_content, True
    return content, False

def harmonize_vitest_config(config_path, vitest_version=2):
    if not os.path.exists(config_path):
        return False

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    modified = False

    # 1. Check for and cleanly remove deprecated poolOptions
    if "poolOptions" in content:
        print(f"Migrating deprecated test.poolOptions in {config_path}...")
        content, stripped = strip_nested_block(content, r"poolOptions\s*:\s*\{")
        if stripped:
            modified = True

    # 2. Deduplicate any existing pool property in test block
    if re.search(r"""pool\s*:\s*['"][^'"]+['"],?""", content):
        content = re.sub(r"""[ \t]*pool\s*:\s*['"][^'"]+['"],?\r?\n?""", "", content)
        modified = True

    # 3. Add top-level pool: 'forks' cleanly inside test: { ... }
    # In Vitest 4+, also configure fileParallelism: false if Windows worker timeout is risk
    pool_setting = "pool: 'forks',"
    if vitest_version >= 4 and os.name == 'nt' and "fileParallelism" not in content:
        pool_setting = "pool: 'forks',\n    fileParallelism: false,"

    if "test:" in content or "test :" in content:
        print(f"Configuring top-level {pool_setting.splitlines()[0]} in {config_path}...")
        content = re.sub(r"((?:test)\s*:\s*\{)", f"\\1\n    {pool_setting}", content, count=1)
        modified = True

    if modified:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated {config_path} with safe pool configuration")
        return True
    else:
        print(f"Vitest config {config_path} already configured with safe pool settings.")
        return False

def harmonize_tsconfig(project_dir):
    tsconfig_path = os.path.join(project_dir, "tsconfig.json")
    if not os.path.exists(tsconfig_path):
        return False

    with open(tsconfig_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if test files are already excluded from build
    if "src/**/*.test." in content or "**/*.test." in content:
        print(f"tsconfig.json in {project_dir} already excludes test files.")
        return False

    print(f"Harmonizing tsconfig.json test exclusions in {project_dir}...")
    if '"exclude"' in content:
        # Append test patterns to existing exclude
        content = re.sub(
            r'("exclude"\s*:\s*\[)',
            r'\1"src/**/*.test.ts", "src/**/*.test.tsx", "tests", ',
            content
        )
    elif '"include"' in content:
        # Add exclude after include
        content = re.sub(
            r'("include"\s*:\s*\[[^\]]*\])',
            r'\1,\n  "exclude": ["src/**/*.test.ts", "src/**/*.test.tsx", "tests"]',
            content
        )
    else:
        content = re.sub(
            r'(\}\s*)$',
            r',\n  "exclude": ["src/**/*.test.ts", "src/**/*.test.tsx", "tests"]\n}',
            content
        )

    with open(tsconfig_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated {tsconfig_path} to exclude test files from production tsc builds.")
    return True

def upgrade_to_vitest_v4(project_dir):
    """Upgrades Vite and Vitest dependencies atomically to resolve CVE-2026-47429 and modernize test runner."""
    pkg_path = os.path.join(project_dir, "package.json")
    if not os.path.exists(pkg_path):
        return False

    with open(pkg_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    modified = False
    for section in ["devDependencies", "dependencies"]:
        if section in data:
            if "vitest" in data[section]:
                data[section]["vitest"] = "^4.1.11"
                modified = True
            if "vite" in data[section]:
                data[section]["vite"] = "^8.2.2"
                modified = True
            if "@vitest/coverage-v8" in data[section]:
                data[section]["@vitest/coverage-v8"] = "^4.1.11"
                modified = True

    # Also update package scripts if test:unit passes deprecated flags
    scripts = data.get("scripts", {})
    if "test" in scripts and "--poolOptions" in scripts["test"]:
        scripts["test"] = scripts["test"].replace("--poolOptions.forks.singleFork=true", "--no-file-parallelism")
        modified = True
    if "test:unit" in scripts and "--poolOptions" in scripts["test:unit"]:
        scripts["test:unit"] = scripts["test:unit"].replace("--poolOptions.forks.singleFork=true", "--no-file-parallelism")
        modified = True

    if modified:
        with open(pkg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        print(f"Upgraded package.json dependencies to Vite 8 / Vitest 4 in {project_dir}")
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Harmonize Vitest & JSDOM test harness")
    parser.add_argument("--dir", default=".", help="Target project directory")
    parser.add_argument("--upgrade-v4", action="store_true", help="Upgrade Vite and Vitest to v4/v8 stack")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.dir)
    print(f"Checking test configuration in: {project_dir}")

    if args.upgrade_v4:
        upgrade_to_vitest_v4(project_dir)

    vitest_version = detect_vitest_version(project_dir)
    print(f"Detected Vitest target version: v{vitest_version}")

    # 1. Setup files
    setup_candidates = [
        os.path.join(project_dir, "tests", "unit", "setup.ts"),
        os.path.join(project_dir, "src", "setupTests.ts"),
        os.path.join(project_dir, "tests", "setup.ts")
    ]
    for s in setup_candidates:
        if os.path.exists(s):
            harmonize_storage_mock(s)
            break
    else:
        default_setup = os.path.join(project_dir, "tests", "unit", "setup.ts")
        os.makedirs(os.path.dirname(default_setup), exist_ok=True)
        harmonize_storage_mock(default_setup)

    # 2. Config files
    config_candidates = [
        os.path.join(project_dir, "vitest.config.ts"),
        os.path.join(project_dir, "vite.config.ts")
    ]
    for c in config_candidates:
        harmonize_vitest_config(c, vitest_version=vitest_version)

    # 3. TypeScript build scope
    harmonize_tsconfig(project_dir)

    print("Vitest & JSDOM harness harmonization complete!")

if __name__ == "__main__":
    main()
