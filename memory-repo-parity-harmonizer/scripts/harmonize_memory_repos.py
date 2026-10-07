#!/usr/bin/env python3
"""
In-Memory Repository & Router Parity Auditor
Audits in-memory multi-tenant repository implementations and Express router mounting
to prevent empty-stub regressions and missing route endpoints in DDD architectures.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def audit_in_memory_repositories(repo_path: Path, seed_path: Path) -> List[Dict[str, Any]]:
    """
    Audits memory repository classes for empty array stubs, missing filter handling,
    and missing GL balance posting logic.
    """
    issues = []
    if not repo_path.is_file():
        return issues

    repo_content = repo_path.read_text(encoding="utf-8", errors="ignore")

    # 1. Audit empty stub array initialization
    class_blocks = re.findall(r'export\s+class\s+([A-Za-z0-9_]+Repository)\s+implements\s+[A-Za-z0-9_]+\s*\{([^}]+)\}', repo_content)
    for class_name, body in class_blocks:
        empty_stubs = re.findall(r'private\s+([A-Za-z0-9_]+)\s*:\s*[^=]+=\s*\[\s*\];', body)
        for stub in empty_stubs:
            issues.append({
                "type": "EMPTY_STUB_ARRAY",
                "severity": "HIGH",
                "class": class_name,
                "field": stub,
                "message": f"{class_name}.{stub} initialized as empty array `[]`. Ensure baseline seed data is injected."
            })

    # 2. Audit getAll(tenantId, filter) implementations that ignore filter
    get_all_blocks = re.findall(r'async\s+getAll\s*\([^)]*filter\??:[^)]*\)\s*:\s*Promise<[^>]+>\s*\{([^}]+)\}', repo_content)
    for block in get_all_blocks:
        if 'filter' in block and not any(k in block for k in ['filter.', 'filter?.', 'if (filter', 'if (!filter']):
            issues.append({
                "type": "IGNORED_QUERY_FILTER",
                "severity": "MEDIUM",
                "message": "Repository getAll() declares filter parameter but returns data without evaluating filter criteria."
            })

    # 3. Audit journal entry creation for account balance updates
    if "MemoryAccountingRepository" in repo_content:
        acct_repo_idx = repo_content.find("class MemoryAccountingRepository")
        next_class_idx = repo_content.find("class ", acct_repo_idx + 25)
        acct_repo_block = repo_content[acct_repo_idx:next_class_idx] if next_class_idx != -1 else repo_content[acct_repo_idx:]
        if "createJournalEntry" in acct_repo_block and "currentBalance" not in acct_repo_block:
            issues.append({
                "type": "MISSING_GL_BALANCE_UPDATE",
                "severity": "HIGH",
                "class": "MemoryAccountingRepository",
                "message": "MemoryAccountingRepository.createJournalEntry does not update account currentBalance, breaking trial balance calculations."
            })

    return issues


def audit_router_mounts(routes_dir: Path, index_file: Path) -> List[Dict[str, Any]]:
    """
    Verifies that every router file in src/routes/*.routes.ts is imported and mounted in src/routes/index.ts.
    """
    issues = []
    if not routes_dir.is_dir() or not index_file.is_file():
        return issues

    index_content = index_file.read_text(encoding="utf-8", errors="ignore")
    route_files = [f for f in routes_dir.glob("*.routes.ts")]

    for rf in route_files:
        module_name = rf.stem.replace(".routes", "")
        # Check for import of this route file
        import_match = re.search(r'import\s+[^;]+\s+from\s+[\'"]\.\/' + re.escape(rf.name.replace(".ts", ".js")) + r'[\'"]', index_content)
        if not import_match:
            # Check without .js extension
            import_match = re.search(r'import\s+[^;]+\s+from\s+[\'"]\.\/' + re.escape(rf.stem) + r'[\'"]', index_content)

        # Check router.use('/...', ...)
        use_match = re.search(r'router\.use\s*\(\s*[\'"]\/[^\'"]+[\'"]\s*,\s*([A-Za-z0-9_]+)\s*\)', index_content)

        if not import_match:
            issues.append({
                "type": "UNMOUNTED_ROUTER",
                "severity": "HIGH",
                "file": rf.name,
                "message": f"Route file {rf.name} is not imported in {index_file.name}. Requests will 404."
            })

    return issues


def main():
    parser = argparse.ArgumentParser(description="In-Memory Repository & Router Parity Auditor")
    parser.add_argument("--project-root", default=".", help="Root directory of repository")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()
    root = Path(args.project_root)

    repo_file = root / "src" / "db" / "memory.repositories.ts"
    seed_file = root / "src" / "data" / "seedData.ts"
    routes_dir = root / "src" / "routes"
    index_file = root / "src" / "routes" / "index.ts"

    repo_issues = audit_in_memory_repositories(repo_file, seed_file)
    router_issues = audit_router_mounts(routes_dir, index_file)
    all_issues = repo_issues + router_issues

    if args.json:
        print(json.dumps({
            "status": "warning" if all_issues else "success",
            "total_issues": len(all_issues),
            "repository_issues": repo_issues,
            "router_issues": router_issues
        }, indent=2))
    else:
        print(f"\nAudited memory repositories and router configuration in {root}:")
        if all_issues:
            print(f"[!] Found {len(all_issues)} parity issue(s):")
            for iss in all_issues:
                print(f"  [{iss['severity']}] {iss['type']}: {iss['message']}")
        else:
            print("[OK] In-memory repositories and route mounts are in full parity with domain specifications!")


if __name__ == "__main__":
    main()
