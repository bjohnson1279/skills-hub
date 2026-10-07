#!/usr/bin/env python3
"""
Service Repository Batch Query Optimizer CLI
Audits domain services and controller handlers across TypeScript, PHP, and Python
for N+1 repository queries (Promise.all over single item lookups, loop queries),
and provides architectural patterns for batched repository retrieval.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Ensure UTF-8 output streams on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def audit_service_file(file_path: str, content: str) -> Dict[str, Any]:
    findings = {
        "file": file_path,
        "n1_promise_all_instances": [],
        "n1_loop_query_instances": [],
        "batched_methods_found": [],
        "recommendations": []
    }

    lines = content.splitlines()

    # 1. Detect Promise.all N+1 pattern: Promise.all(items.map(i => repo.get*(i)))
    promise_all_regex = re.compile(
        r'Promise\.all\s*\(\s*(?:\w+\.)?map\s*\(\s*(?:\w+|\([^)]+\))\s*=>\s*(?:this\.|this\.repos\.\w+\.|repo\.)?(?:get|find|fetch)\w+\(',
        re.IGNORECASE
    )

    # 2. Detect sequential loop query: for (...) { await repo.get*(...) }
    for_loop_regex = re.compile(r'for\s*(?:await)?\s*\([^)]+\)\s*\{', re.IGNORECASE)

    # 3. Detect existing batched methods (e.g. getByIds, getAccountsByNumbers, findMany)
    batched_method_regex = re.compile(
        r'(?:get|find|fetch)\w+By(?:Ids|Numbers|Codes|Keys|Uuids)\s*\(',
        re.IGNORECASE
    )

    for match in batched_method_regex.finditer(content):
        findings["batched_methods_found"].append(match.group(0).rstrip('('))

    for idx, line in enumerate(lines, 1):
        if promise_all_regex.search(line):
            findings["n1_promise_all_instances"].append({
                "line": idx,
                "snippet": line.strip()[:140]
            })

    # Multi-line scan for Promise.all
    full_content = "\n".join(lines)
    multi_matches = re.finditer(
        r'(const|let|var)?\s*\w+\s*=\s*await\s+Promise\.all\s*\(\s*[^)]*?\.map\s*\([^)]*?(?:get|find|fetch)\w+\([^)]*?\)\s*\)',
        full_content,
        re.DOTALL
    )
    for m in multi_matches:
        # Find start line
        start_pos = m.start()
        line_no = full_content[:start_pos].count('\n') + 1
        snippet = " ".join(m.group(0).split())[:140]
        # Avoid duplicate if single-line regex already captured
        if not any(inst["line"] == line_no for inst in findings["n1_promise_all_instances"]):
            findings["n1_promise_all_instances"].append({
                "line": line_no,
                "snippet": snippet
            })

    # Scan for loop queries
    for idx, line in enumerate(lines, 1):
        if re.search(r'for\s*\([^)]+\)', line):
            # Check next 5 lines for await repo.get/find
            window = "\n".join(lines[idx:min(len(lines), idx + 6)])
            if re.search(r'await\s+(?:this\.|repo\.)?(?:get|find|fetch)\w+\(', window):
                findings["n1_loop_query_instances"].append({
                    "line": idx,
                    "snippet": line.strip()[:140]
                })

    if findings["n1_promise_all_instances"]:
        findings["recommendations"].append(
            f"Found {len(findings['n1_promise_all_instances'])} Promise.all N+1 query loop(s). "
            "Refactor repository with a batched query method (e.g. getByIds / getByNumbers) and use Map indexing."
        )

    if findings["n1_loop_query_instances"]:
        findings["recommendations"].append(
            f"Found {len(findings['n1_loop_query_instances'])} sequential loop query instance(s). "
            "Extract unique keys into a Set/Array and batch fetch prior to loop iteration."
        )

    return findings


def scan_target(target_path: str) -> List[Dict[str, Any]]:
    results = []
    p = Path(target_path)
    extensions = {'.ts', '.js', '.php', '.py'}

    if p.is_file():
        if p.suffix.lower() in extensions:
            content = p.read_text(encoding='utf-8', errors='ignore')
            results.append(audit_service_file(str(p), content))
    elif p.is_dir():
        for root, _, files in os.walk(p):
            if any(ignored in root for ignored in ['node_modules', '.git', 'dist', 'build', 'vendor', '__pycache__']):
                continue
            for f in files:
                fpath = Path(root) / f
                if fpath.suffix.lower() in extensions and any(term in f.lower() for term in ['service', 'controller', 'repository', 'handler']):
                    try:
                        content = fpath.read_text(encoding='utf-8', errors='ignore')
                        res = audit_service_file(str(fpath), content)
                        if res["n1_promise_all_instances"] or res["n1_loop_query_instances"]:
                            results.append(res)
                    except Exception:
                        pass
    return results


def get_refactoring_patterns() -> Dict[str, Any]:
    return {
        "repository_interface": """export interface IEntityRepository {
  getById(tenantId: string, id: string): Promise<Entity | null>;
  // ⚡ Batch method: Retrieves all matching records in a single query
  getByIds(tenantId: string, ids: string[]): Promise<Entity[]>;
}""",
        "memory_repository": """export class MemoryEntityRepository implements IEntityRepository {
  private entities: Entity[] = [];

  async getByIds(tenantId: string, ids: string[]): Promise<Entity[]> {
    const idSet = new Set(ids);
    return Promise.resolve(this.entities.filter(e => idSet.has(e.id)));
  }
}""",
        "sql_repository_postgres": """export class PgEntityRepository implements IEntityRepository {
  async getByIds(tenantId: string, ids: string[]): Promise<Entity[]> {
    if (ids.length === 0) return [];
    return withTenantTransaction(tenantId, async (client) => {
      // Use parameterized ANY($2) or WHERE id IN (...)
      const res = await client.query(
        'SELECT * FROM entities WHERE tenant_id = $1 AND id = ANY($2)',
        [tenantId, ids]
      );
      return res.rows.map(mapRowToEntity);
    });
  }
}""",
        "service_layer_caller": """// ❌ BEFORE: N+1 concurrent queries exhausting DB connection pool
const uniqueIds = Array.from(new Set(payload.lines.map(l => l.id)));
const fetched = await Promise.all(
  uniqueIds.map(id => this.entityRepo.getById(tenantId, id))
);

// ✅ AFTER: Single batched query with O(1) Map lookup
const uniqueIds = Array.from(new Set(payload.lines.map(l => l.id)));
const fetched = await this.entityRepo.getByIds(tenantId, uniqueIds);
const entityMap = new Map(fetched.map(e => [e.id, e]));

for (const line of payload.lines) {
  const entity = entityMap.get(line.id);
  if (!entity) throw new Error(`Entity '${line.id}' not found`);
  // Process entity...
}"""
    }


def main():
    parser = argparse.ArgumentParser(description="Service Repository Batch Query Optimizer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan service and repository files for N+1 query patterns")
    p_scan.add_argument("--target", required=True, help="Target file or directory to scan")
    p_scan.add_argument("--output", default=None, help="Optional output JSON filepath")

    # pattern
    p_pat = subparsers.add_parser("pattern", help="Output canonical batched query architecture patterns")
    p_pat.add_argument("--output", default=None, help="Optional output JSON filepath")

    args = parser.parse_args()

    if args.command == "scan":
        results = scan_target(args.target)
        if args.output:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            print(f"✅ Scan complete: {len(results)} file(s) with N+1 bottlenecks found. Saved to: {args.output}")
        else:
            print(json.dumps(results, indent=2))

    elif args.command == "pattern":
        patterns = get_refactoring_patterns()
        if args.output:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(patterns, f, indent=2)
            print(f"✅ Architecture patterns saved to: {args.output}")
        else:
            print(json.dumps(patterns, indent=2))


if __name__ == '__main__':
    main()
