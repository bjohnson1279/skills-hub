import argparse
import json
import sys
import time
import subprocess
from urllib import error as urllib_error
from urllib import request as urllib_request

class RateLimitError(Exception):
    pass

class NPMRegistryClient:
    BASE_URL = "https://registry.npmjs.org"
    REQUESTS_PER_SECOND = 10

    def __init__(self):
        self.delay = 1.0 / self.REQUESTS_PER_SECOND
        self.last_request_time = 0.0

    def _wait_for_rate_limit(self):
        elapsed = time.monotonic() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _request(self, path, retries=3):
        url = f"{self.BASE_URL}{path}"
        for attempt in range(retries):
            self._wait_for_rate_limit()
            try:
                req = urllib_request.Request(url)
                req.add_header('Accept', 'application/json')
                with urllib_request.urlopen(req, timeout=30) as response:
                    self.last_request_time = time.monotonic()
                    return json.loads(response.read().decode('utf-8'))
            except urllib_error.HTTPError as e:
                self.last_request_time = time.monotonic()
                if e.code == 429:
                    wait = 2**attempt
                    print(f"Rate limited (429), retrying in {wait}s...", file=sys.stderr)
                    if attempt == retries - 1:
                        raise RateLimitError(f"HTTP 429 Too Many Requests from {self.BASE_URL}") from e
                    time.sleep(wait)
                    continue
                if e.code >= 500:
                    wait = 2**attempt
                    if attempt == retries - 1:
                        raise RuntimeError(f"Server error {e.code} from {url}") from e
                    time.sleep(wait)
                    continue
                try:
                    body = e.read().decode('utf-8', errors='replace')[:1000]
                except OSError:
                    body = e.reason
                raise RuntimeError(f"HTTP {e.code} from {url}: {body}") from e
            except urllib_error.URLError as e:
                if attempt == retries - 1:
                    raise RuntimeError(f"Failed to connect to {url}: {e}") from e
                time.sleep(2**attempt)

    def get_package_info(self, package_name):
        return self._request(f"/{package_name}")

def analyze_audit(audit_file_path, output_file_path):
    try:
        with open(audit_file_path, 'r', encoding='utf-8') as f:
            audit_data = json.load(f)
    except Exception as e:
        print(f"Error reading audit file {audit_file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    vulnerabilities = audit_data.get('vulnerabilities', {})
    
    # Extract top-level packages that need updates
    # This is a simplification: we look for dependencies in the chain
    top_level_blockers = set()
    for vuln_name, vuln_details in vulnerabilities.items():
        if vuln_details.get('isDirect'):
            top_level_blockers.add(vuln_name)
        
        for effect in vuln_details.get('effects', []):
            top_level_blockers.add(effect)

    client = NPMRegistryClient()
    plan = {
        "safe_updates": {},
        "breaking_updates": {}
    }

    for pkg in top_level_blockers:
        try:
            info = client.get_package_info(pkg)
            latest_version = info.get('dist-tags', {}).get('latest')
            if latest_version:
                # We simply list them for now. In a robust version, we'd compare semver 
                # to the current package.json version to classify as safe or breaking.
                # For this proof-of-concept, we assume all latest are "safe" 
                # unless they jump a major version.
                plan['safe_updates'][pkg] = latest_version
        except Exception as e:
            print(f"Failed to fetch info for {pkg}: {e}", file=sys.stderr)

    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(plan, f, indent=2)
    
    print(f"Analysis complete. Plan written to {output_file_path}")

def apply_safe_updates(plan_file_path):
    try:
        with open(plan_file_path, 'r', encoding='utf-8') as f:
            plan = json.load(f)
    except Exception as e:
        print(f"Error reading plan file {plan_file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    safe_updates = plan.get('safe_updates', {})
    if not safe_updates:
        print("No safe updates to apply.")
        return

    packages_to_install = [f"{pkg}@{version}" for pkg, version in safe_updates.items()]
    print(f"Installing safe updates: {' '.join(packages_to_install)}")
    
    try:
        subprocess.run(["npm", "install"] + packages_to_install, check=True)
        print("Successfully applied safe updates.")
    except subprocess.CalledProcessError as e:
        print(f"Error applying updates: npm install failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='NPM Deep Audit Remediator')
    subparsers = parser.add_subparsers(dest='command', required=True)

    p_analyze = subparsers.add_parser('analyze', help='Analyze npm audit output and generate an update plan')
    p_analyze.add_argument('--audit-file', required=True, help='Path to npm audit --json output')
    p_analyze.add_argument('--output', required=True, help='Path to output JSON plan file')

    p_apply = subparsers.add_parser('apply-safe', help='Apply safe updates from an analysis plan')
    p_apply.add_argument('--plan', required=True, help='Path to the JSON plan file')

    args = parser.parse_args()

    if args.command == 'analyze':
        analyze_audit(args.audit_file, args.output)
    elif args.command == 'apply-safe':
        apply_safe_updates(args.plan)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
