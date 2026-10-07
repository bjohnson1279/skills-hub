import argparse
import sys
import yaml

def load_yaml(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def compare_specs(spec1, spec2, strict=False):
    diffs = []
    
    paths1 = set(spec1.get('paths', {}).keys())
    paths2 = set(spec2.get('paths', {}).keys())
    
    missing_in_2 = paths1 - paths2
    missing_in_1 = paths2 - paths1
    
    for p in missing_in_2:
        diffs.append(f"❌ Missing endpoint in spec 2: {p}")
    for p in missing_in_1:
        diffs.append(f"❌ Missing endpoint in spec 1: {p}")
        
    for p in paths1.intersection(paths2):
        methods1 = set(spec1['paths'][p].keys())
        methods2 = set(spec2['paths'][p].keys())
        if methods1 != methods2:
            diffs.append(f"⚠️ Methods differ for path {p}: {methods1} vs {methods2}")
            
    schemas1 = set(spec1.get('components', {}).get('schemas', {}).keys())
    schemas2 = set(spec2.get('components', {}).get('schemas', {}).keys())
    if schemas1 != schemas2:
        diffs.append(f"⚠️ Schemas differ: {schemas1.symmetric_difference(schemas2)}")
        
    return diffs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('specs', nargs='+', help='Paths to OpenAPI YAML specs to compare')
    parser.add_argument('--strict', action='store_true', help='Zero-tolerance mode')
    args = parser.parse_args()
    
    if len(args.specs) < 2:
        print("Need at least two specs to compare.")
        sys.exit(1)
        
    has_errors = False
    base_spec = load_yaml(args.specs[0])
    
    for i in range(1, len(args.specs)):
        compare_spec = load_yaml(args.specs[i])
        print(f"Comparing {args.specs[0]} and {args.specs[i]}...")
        diffs = compare_specs(base_spec, compare_spec, args.strict)
        
        if diffs:
            for d in diffs:
                print(d)
                if '❌' in d or args.strict:
                    has_errors = True
        else:
            print(f"✅ Specs {args.specs[0]} and {args.specs[i]} are in sync")
            
    if has_errors:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
