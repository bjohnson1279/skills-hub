import argparse
import json
import sys

def splice_file(operations):
    for op in operations:
        file_path = op.get('file')
        start_line = op.get('startLine')
        end_line = op.get('endLine')
        replacement = op.get('replacement')

        if not all([file_path, start_line, end_line, replacement is not None]):
            print(f"Error: Missing required fields in operation: {op}", file=sys.stderr)
            sys.exit(1)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except IOError as e:
            print(f"Error reading {file_path}: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Validate that the lines exist
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            print(f"Error: Invalid line range {start_line}-{end_line} for {file_path} (has {len(lines)} lines)", file=sys.stderr)
            sys.exit(1)
        
        # 1-indexed to 0-indexed slice
        start_idx = start_line - 1
        end_idx = end_line
        
        removed_lines = lines[start_idx:end_idx]
        removed_text = "".join(removed_lines)
        
        if '<<<<<<<' not in removed_text and '=======' not in removed_text and '>>>>>>>' not in removed_text:
            print(f"Error: Conflict markers (<<<<<<< or ======= or >>>>>>>) NOT found in the specified range ({start_line}-{end_line}) in {file_path}. Target lines are:\n{removed_text}", file=sys.stderr)
            sys.exit(1)
        
        # Perform exact splice
        lines = lines[:start_idx] + [replacement] + lines[end_idx:]
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except IOError as e:
            print(f"Error writing {file_path}: {e}", file=sys.stderr)
            sys.exit(1)
            
        print(f"Successfully spliced {file_path} (replaced lines {start_line}-{end_line}).")


def main():
    parser = argparse.ArgumentParser(description='Exact Line Splicing for Merge Conflicts')
    subparsers = parser.add_subparsers(dest='command', required=True)

    p_splice = subparsers.add_parser('splice', help='Splice file using exact line boundaries')
    p_splice.add_argument('--input', required=True, help='Path to a JSON file containing an array of splice operations.')

    args = parser.parse_args()

    if args.command == 'splice':
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                operations = json.load(f)
        except Exception as e:
            print(f"Error reading JSON input file {args.input}: {e}", file=sys.stderr)
            sys.exit(1)
            
        if not isinstance(operations, list):
            print("Error: Input JSON must be an array of operations.", file=sys.stderr)
            sys.exit(1)
            
        splice_file(operations)
        print("Success! All splices applied.")
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
