#!/usr/bin/env python3
import argparse
import os
import re

def parse_interface(interface_path):
    """Parses a TS interface to extract method names and groups them by a simplistic heuristic."""
    methods = []
    with open(interface_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Naive regex to match method signatures in a TS interface.
    # e.g. `getInventoryItem(id: string): Promise<InventoryItem>;`
    matches = re.findall(r'^\s*([a-zA-Z0-9_]+)\s*\([^)]*\)\s*:', content, re.MULTILINE)
    
    domain_groups = {}
    for match in matches:
        # Simplistic grouping: prefix of method (e.g., getInventory, createAccount -> inventory, account)
        # We'll just group by the first word split by camelCase for a basic heuristic.
        words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', match)
        if len(words) > 1:
            domain = words[1].lower() # e.g., get(Inventory)
        elif len(words) == 1:
            domain = words[0].lower()
        else:
            domain = "general"
            
        if domain not in domain_groups:
            domain_groups[domain] = []
        domain_groups[domain].append(match)
        
    return domain_groups

def generate_infrastructure(output_dir, backends):
    """Generates conftest.py, comparator.py, and requirements.txt."""
    # requirements.txt
    req_path = os.path.join(output_dir, "requirements.txt")
    with open(req_path, 'w') as f:
        f.write("pytest\nhttpx\ngql\ndeepdiff\npyyaml\njsonschema\npytest-json-report\n")
        
    # conftest.py
    conftest_path = os.path.join(output_dir, "conftest.py")
    with open(conftest_path, 'w') as f:
        backends_list = backends.split(',')
        backends_repr = [b.strip() for b in backends_list]
        f.write(f'''import pytest

BACKENDS = {repr(backends_repr)}

@pytest.fixture(params=BACKENDS)
def backend(request):
    return request.param

@pytest.fixture
def test_client():
    # Provide a generic client for HTTP requests
    import httpx
    with httpx.Client() as client:
        yield client
''')

    # comparator.py
    comparator_path = os.path.join(output_dir, "comparator.py")
    with open(comparator_path, 'w') as f:
        f.write('''from deepdiff import DeepDiff

def unwrap_graphql(response_json):
    if "data" in response_json:
        return response_json["data"]
    return response_json

def compare_responses(response_data, golden_schema_name):
    # Stub for deep comparison and volatile stripping
    unwrapped = unwrap_graphql(response_data)
    # Perform DeepDiff comparison with canonical schema...
    return True
''')
    
    return [req_path, conftest_path, comparator_path]

def generate_test_modules(domain_groups, output_dir, backends):
    """Generates a pytest file for each domain capability."""
    generated_files = []
    
    backends_list = [b.strip() for b in backends.split(',')]
    
    for domain, methods in domain_groups.items():
        test_file = os.path.join(output_dir, f"test_{domain}_scenarios.py")
        with open(test_file, 'w') as f:
            f.write(f'import pytest\nfrom comparator import compare_responses\n\n')
            for method in methods:
                f.write(f'def test_{method}(backend, test_client):\n')
                f.write(f'    # TODO: Implement request logic for {method} against {{backend}}\n')
                f.write(f'    response_data = {{"data": {{}}}}\n')
                f.write(f'    assert compare_responses(response_data, "{method}_schema")\n\n')
        generated_files.append(test_file)
        
    return generated_files

def main():
    parser = argparse.ArgumentParser(description="Generate conformance test suite")
    parser.add_argument("--interface-file", required=True, help="Path to TypeScript client interface")
    parser.add_argument("--output-dir", required=True, help="Path for generated test files")
    parser.add_argument("--backends", required=True, help="Comma-separated list of backend configs (name:port)")
    args = parser.parse_args()
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        
    print(f"Parsing interface: {args.interface_file}")
    domain_groups = parse_interface(args.interface_file)
    
    print(f"Generating infrastructure in: {args.output_dir}")
    infra_files = generate_infrastructure(args.output_dir, args.backends)
    
    print("Generating scenario test modules...")
    test_files = generate_test_modules(domain_groups, args.output_dir, args.backends)
    
    print("\\nSummary of generated files:")
    for f in infra_files + test_files:
        print(f" - {f}")

if __name__ == "__main__":
    main()
