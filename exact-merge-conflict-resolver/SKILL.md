---
name: exact-merge-conflict-resolver
description: >-
  Resolves git merge conflicts safely by strictly splicing replacement code into exact line indices, avoiding the brittleness of fuzzy string replacement on corrupted ASTs. Fails loudly if conflict markers are not found at the expected lines.
---

# Exact-Line Merge Conflict Resolver

## Overview
Resolves git merge conflicts safely by strictly splicing replacement code into exact line indices. Because standard `replace_file_content` tools rely on fuzzy string matching, they frequently fail or incorrectly modify code when syntax is corrupted by `<<<<<<< HEAD` markers. This skill guarantees exact placement and will abort if the targeted lines do not contain merge conflict markers.

## Dependencies
None. (This skill is meant to be called by `pr-merge-conflict-resolver` and `sentinel-bot-syntax-auditor`).

## Quick Start
Create a JSON file containing the splice operations you want to perform:
```json
[
  {
    "file": "src/app.ts",
    "startLine": 120,
    "endLine": 128,
    "replacement": "app.use(cors(corsOptions));\n"
  }
]
```
Then execute the splice command using `uv run python`:
```bash
uv run python C:\Users\johns\.gemini\config\skills\exact-merge-conflict-resolver\scripts\conflict-splicer.py splice --input path/to/ops.json
```

## Utility Scripts

### `splice`
Splices a file using exact line boundaries. 

**Arguments:**
- `--input`: Path to a JSON file containing an array of splice operations.

**Behavior:**
Parses the JSON operations. For each operation, validates that the lines being removed actually contain `<<<<<<<`, `=======`, or `>>>>>>>`. If valid, removes the exact line range and inserts the provided replacement string. Writes the updated content back to the file.

## Common Mistakes
- **Incorrect Line Numbers**: If the file has changed since you calculated the line numbers, the script will reject the splice. Recalculate your indices.
- **Missing Markers**: Ensure the `startLine` and `endLine` fully encapsulate at least one merge conflict marker. If they do not, the script intentionally aborts to prevent accidental code deletion.
