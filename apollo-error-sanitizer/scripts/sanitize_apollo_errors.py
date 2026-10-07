#!/usr/bin/env python3
import argparse
import os
import re
import sys

# Force UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SANITIZER_SNIPPET = """    formatError: (formattedError: any) => {
      if (process.env.NODE_ENV === 'production') {
        if (formattedError.extensions) {
          if (formattedError.extensions.exception) {
            delete formattedError.extensions.exception;
          }
          delete formattedError.extensions.stacktrace;
        }
        return formattedError;
      }
      if (formattedError.extensions && formattedError.extensions.exception) {
        delete formattedError.extensions.exception.stacktrace;
      }
      return formattedError;
    },"""

def audit_file(file_path, apply_fix=False):
    if not os.path.exists(file_path):
        return {"status": "NOT_FOUND", "file": file_path}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "new ApolloServer" not in content:
        return {"status": "NO_APOLLO_SERVER", "file": file_path}

    has_format_error = "formatError" in content
    has_prod_masking = "NODE_ENV === 'production'" in content or 'NODE_ENV === "production"' in content
    has_stacktrace_strip = "delete formattedError.extensions.stacktrace" in content or "delete formattedError.extensions?.stacktrace" in content

    if has_format_error and has_prod_masking and has_stacktrace_strip:
        return {"status": "SECURE", "file": file_path}

    if apply_fix:
        print(f"Applying Apollo formatError production sanitizer to: {file_path}...")
        if has_format_error:
            # Replace existing formatError
            pattern = r'formatError:\s*\([^)]*\)\s*=>\s*\{[^}]*(\{[^}]*\}[^}]*)*\},?'
            new_content = re.sub(pattern, SANITIZER_SNIPPET, content)
        else:
            # Inject into ApolloServer config object
            new_content = content.replace("new ApolloServer({", f"new ApolloServer({{\n{SANITIZER_SNIPPET}")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return {"status": "FIXED", "file": file_path}

    return {"status": "VULNERABLE", "file": file_path, "issue": "Missing production exception/stacktrace stripping"}

def main():
    parser = argparse.ArgumentParser(description="Apollo Server GraphQL Error Sanitizer")
    parser.add_argument("--path", required=True, help="Target repository directory or file path")
    parser.add_argument("--fix", action="store_true", help="Automatically inject production error sanitizer")
    args = parser.parse_args()

    target = os.path.abspath(args.path)
    files_to_check = []
    if os.path.isfile(target):
        files_to_check.append(target)
    else:
        for root, _, files in os.walk(target):
            for f in files:
                if f.endswith((".ts", ".js")) and ("index" in f or "server" in f or "gateway" in f):
                    files_to_check.append(os.path.join(root, f))

    print(f"Auditing {len(files_to_check)} candidate GraphQL server file(s)...")
    for f in files_to_check:
        res = audit_file(f, apply_fix=args.fix)
        if res["status"] == "VULNERABLE":
            print(f"⚠️ [VULNERABLE] {res['file']}: {res['issue']}")
        elif res["status"] == "FIXED":
            print(f"✅ [FIXED] {res['file']}: Injected production error sanitizer")
        elif res["status"] == "SECURE":
            print(f"🔒 [SECURE] {res['file']}: Production error masking verified")

if __name__ == "__main__":
    main()
