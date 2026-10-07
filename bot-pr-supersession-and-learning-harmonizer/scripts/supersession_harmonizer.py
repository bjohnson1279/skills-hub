#!/usr/bin/env python3
"""
Bot PR Supersession & Learning Harmonizer CLI
Audits duplicate/competing bot PRs, additively reconciles .jules/*.md learning entries,
and safely closes superseded pull requests with audit trails.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure UTF-8 console output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def run_cmd(cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


def detect_duplicate_prs(repo: Optional[str] = None) -> Dict:
    """
    Scans open PRs in a repository for duplicate or competing bot implementations.
    """
    cmd = ["gh", "pr", "list", "--state", "open", "--json", "number,title,headRefName,baseRefName,mergeable,createdAt,body"]
    if repo:
        cmd.extend(["--repo", repo])

    code, stdout, stderr = run_cmd(cmd)
    if code != 0:
        return {"status": "error", "message": stderr}

    try:
        prs = json.loads(stdout)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    pr_files = {}
    for pr in prs:
        num = pr.get("number")
        diff_cmd = ["gh", "pr", "diff", str(num), "--name-only"]
        if repo:
            diff_cmd.extend(["--repo", repo])
        d_code, d_out, _ = run_cmd(diff_cmd)
        if d_code == 0:
            files = [f.strip() for f in d_out.splitlines() if f.strip() and not f.strip().startswith(".jules/") and not f.strip().endswith(".md")]
            pr_files[num] = set(files)
        else:
            pr_files[num] = set()

    duplicate_groups = []
    handled = set()

    for i, p1 in enumerate(prs):
        n1 = p1.get("number")
        if n1 in handled:
            continue
        group = [p1]
        f1 = pr_files.get(n1, set())

        for j, p2 in enumerate(prs[i + 1:], start=i + 1):
            n2 = p2.get("number")
            if n2 in handled:
                continue
            f2 = pr_files.get(n2, set())

            has_file_overlap = bool(f1 and f2 and (f1 & f2))
            title1_words = set(p1.get("title", "").lower().split())
            title2_words = set(p2.get("title", "").lower().split())
            title_overlap = len(title1_words & title2_words) >= 4

            if has_file_overlap or title_overlap:
                group.append(p2)
                handled.add(n2)

        if len(group) > 1:
            handled.add(n1)
            # Rank candidates: select newest by createdAt, check test subsumption if touching test files
            group_sorted = sorted(group, key=lambda p: p.get("createdAt", ""), reverse=True)
            primary = group_sorted[0]
            superseded = group_sorted[1:]
            subsumption_details = None

            test_files = [f for f in f1 if any(t in f.lower() for t in [".test.", ".spec.", "_test.", "test_"])]
            if test_files and len(group) == 2:
                # Perform deep test subsumption comparison
                p_a, p_b = group[0], group[1]
                num_a, num_b = p_a.get("number"), p_b.get("number")
                cmd_a = ["gh", "pr", "diff", str(num_a)]
                cmd_b = ["gh", "pr", "diff", str(num_b)]
                if repo:
                    cmd_a.extend(["--repo", repo])
                    cmd_b.extend(["--repo", repo])
                _, diff_a, _ = run_cmd(cmd_a)
                _, diff_b, _ = run_cmd(cmd_b)
                sub_res = analyze_test_subsumption(diff_a, diff_b)
                if sub_res.get("winner") == "B":
                    primary = p_b
                    superseded = [p_a]
                    subsumption_details = sub_res
                elif sub_res.get("winner") == "A":
                    primary = p_a
                    superseded = [p_b]
                    subsumption_details = sub_res

            entry = {
                "target_files": list(f1),
                "primary_candidate": primary.get("number"),
                "primary_title": primary.get("title"),
                "superseded_candidates": [s.get("number") for s in superseded],
                "prs": group,
            }
            if subsumption_details:
                entry["test_subsumption"] = subsumption_details
            duplicate_groups.append(entry)

    return {
        "status": "success",
        "total_prs_audited": len(prs),
        "duplicate_groups_count": len(duplicate_groups),
        "duplicate_groups": duplicate_groups,
    }


def extract_test_cases(content: str) -> Dict[str, Any]:
    """
    Extracts test blocks (it, test, describe) and assertions (expect, assert) from test files or diffs.
    """
    test_title_pattern = re.compile(r"""(?:it|test)\s*\(\s*['"`]([^'"`]+)['"`]""")
    describe_pattern = re.compile(r"""describe\s*\(\s*['"`]([^'"`]+)['"`]""")
    expect_pattern = re.compile(r"""expect\s*\([^)]+\)""")

    tests = [m.strip() for m in test_title_pattern.findall(content)]
    describes = [m.strip() for m in describe_pattern.findall(content)]
    expect_count = len(expect_pattern.findall(content))
    non_empty_lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("//") and not l.strip().startswith("#")]

    return {
        "test_count": len(tests),
        "tests": tests,
        "describe_count": len(describes),
        "describes": describes,
        "expect_count": expect_count,
        "line_count": len(non_empty_lines),
    }


def analyze_test_subsumption(content_a: str, content_b: str) -> Dict[str, Any]:
    """
    Evaluates whether Test Suite B subsumes Test Suite A (or vice versa).
    """
    info_a = extract_test_cases(content_a)
    info_b = extract_test_cases(content_b)

    set_a = {re.sub(r'[^a-z0-9]', '', t.lower()) for t in info_a["tests"]}
    set_b = {re.sub(r'[^a-z0-9]', '', t.lower()) for t in info_b["tests"]}

    common_tests = set_a & set_b
    subsumes_a_in_b = len(common_tests) / max(1, len(set_a))
    subsumes_b_in_a = len(common_tests) / max(1, len(set_b))

    winner = None
    reason = "Undetermined"

    if info_b["test_count"] > info_a["test_count"] and info_b["expect_count"] >= info_a["expect_count"]:
        winner = "B"
        reason = f"Candidate B contains {info_b['test_count']} tests vs {info_a['test_count']} tests in A, and subsumes {subsumes_a_in_b*100:.1f}% of A's coverage."
    elif info_a["test_count"] > info_b["test_count"] and info_a["expect_count"] >= info_b["expect_count"]:
        winner = "A"
        reason = f"Candidate A contains {info_a['test_count']} tests vs {info_b['test_count']} tests in B, and subsumes {subsumes_b_in_a*100:.1f}% of B's coverage."
    elif info_b["line_count"] > info_a["line_count"] * 1.5:
        winner = "B"
        reason = f"Candidate B contains significantly more assertions and test fixtures ({info_b['line_count']} vs {info_a['line_count']} lines)."
    elif info_a["line_count"] > info_b["line_count"] * 1.5:
        winner = "A"
        reason = f"Candidate A contains significantly more assertions and test fixtures ({info_a['line_count']} vs {info_b['line_count']} lines)."
    else:
        winner = "B"  # fallback default
        reason = "Candidates have similar test volume; elected newer candidate."

    return {
        "winner": winner,
        "reason": reason,
        "suite_a": info_a,
        "suite_b": info_b,
        "a_subsumed_by_b_ratio": round(subsumes_a_in_b, 3),
        "b_subsumed_by_a_ratio": round(subsumes_b_in_a, 3),
    }


def parse_jules_sections(content: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Parses .jules markdown content into header preamble and individual learning sections.
    """
    lines = content.splitlines(keepends=True)
    header_lines = []
    sections = []
    current_section = None

    section_header_regex = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*-\s*(.+)$")

    for line in lines:
        match = section_header_regex.match(line)
        if match:
            if current_section:
                sections.append(current_section)
            current_section = {
                "date": match.group(1).strip(),
                "title": match.group(2).strip(),
                "full_header": line.strip(),
                "body_lines": [],
            }
        else:
            if current_section is None:
                header_lines.append(line)
            else:
                current_section["body_lines"].append(line)

    if current_section:
        sections.append(current_section)

    return "".join(header_lines), sections


def union_jules_files(base_file: str, feature_content: str) -> str:
    """
    Additively unions learning entries from feature branch into base_file without losing any entries.
    """
    base_path = Path(base_file)
    base_content = base_path.read_text(encoding="utf-8", errors="ignore") if base_path.is_file() else ""

    base_preamble, base_sections = parse_jules_sections(base_content)
    _, feat_sections = parse_jules_sections(feature_content)

    existing_keys = set()
    for s in base_sections:
        # Key by date + normalized title
        key = f"{s['date']}:{re.sub(r'[^a-zA-Z0-9]', '', s['title'].lower())}"
        existing_keys.add(key)

    new_sections = []
    for s in feat_sections:
        key = f"{s['date']}:{re.sub(r'[^a-zA-Z0-9]', '', s['title'].lower())}"
        if key not in existing_keys:
            new_sections.append(s)
            existing_keys.add(key)

    combined_lines = [base_preamble.rstrip("\n")]
    if combined_lines and combined_lines[0]:
        combined_lines.append("\n\n")

    for s in base_sections:
        combined_lines.append(s["full_header"] + "\n")
        combined_lines.append("".join(s["body_lines"]).rstrip("\n") + "\n\n")

    for s in new_sections:
        combined_lines.append(s["full_header"] + "\n")
        combined_lines.append("".join(s["body_lines"]).rstrip("\n") + "\n\n")

    return "".join(combined_lines).rstrip() + "\n"


def close_superseded_pr(pr_number: int, primary_pr: int, repo: Optional[str] = None, dry_run: bool = False) -> Dict:
    """
    Closes a superseded PR with a canonical reference to the primary merged PR.
    """
    comment = f"Closing as superseded: equivalent changes merged via PR #{primary_pr}."
    cmd = ["gh", "pr", "close", str(pr_number), "--comment", comment, "--delete-branch"]
    if repo:
        cmd.extend(["--repo", repo])

    if dry_run:
        return {
            "status": "dry_run",
            "pr_number": pr_number,
            "primary_pr": primary_pr,
            "comment": comment,
        }

    code, stdout, stderr = run_cmd(cmd)
    return {
        "status": "success" if code == 0 else "error",
        "pr_number": pr_number,
        "primary_pr": primary_pr,
        "stdout": stdout,
        "stderr": stderr,
    }


def audit_post_merge(repo: Optional[str] = None, base_ref: str = "main", limit: int = 5, base_dir: Optional[str] = None) -> Dict:
    """
    Audits open PRs immediately after a PR merge to detect newly conflicting or superseded sibling PRs.
    """
    # 1. Fetch recently merged PRs
    merged_cmd = ["gh", "pr", "list", "--state", "merged", "--limit", str(limit), "--json", "number,title,headRefName,baseRefName,mergedAt"]
    if repo:
        merged_cmd.extend(["--repo", repo])
    m_code, m_out, m_err = run_cmd(merged_cmd)
    if m_code != 0:
        return {"status": "error", "message": f"Failed to fetch merged PRs: {m_err}"}

    try:
        merged_prs = json.loads(m_out)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    # 2. Fetch open PRs
    open_cmd = ["gh", "pr", "list", "--state", "open", "--json", "number,title,headRefName,baseRefName,mergeable,createdAt"]
    if repo:
        open_cmd.extend(["--repo", repo])
    o_code, o_out, o_err = run_cmd(open_cmd)
    if o_code != 0:
        return {"status": "error", "message": f"Failed to fetch open PRs: {o_err}"}

    try:
        open_prs = json.loads(o_out)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    # Map files modified in recently merged PRs
    merged_files = {}
    for m in merged_prs:
        num = m.get("number")
        diff_cmd = ["gh", "pr", "diff", str(num), "--name-only"]
        if repo:
            diff_cmd.extend(["--repo", repo])
        d_code, d_out, _ = run_cmd(diff_cmd)
        if d_code == 0:
            files = [f.strip() for f in d_out.splitlines() if f.strip() and not f.strip().startswith(".jules/")]
            merged_files[num] = set(files)

    sibling_issues = []
    for op in open_prs:
        op_num = op.get("number")
        head_ref = op.get("headRefName")
        diff_cmd = ["gh", "pr", "diff", str(op_num), "--name-only"]
        if repo:
            diff_cmd.extend(["--repo", repo])
        d_code, d_out, _ = run_cmd(diff_cmd)
        op_files = set([f.strip() for f in d_out.splitlines() if f.strip() and not f.strip().startswith(".jules/")]) if d_code == 0 else set()

        conflicting = False
        conflict_details = ""
        # Check in-memory merge simulation if local git working directory provided
        if base_dir and os.path.exists(os.path.join(base_dir, ".git")):
            mt_code, mt_out, _ = run_cmd(["git", "merge-tree", f"origin/{base_ref}", f"origin/{head_ref}"], cwd=base_dir)
            if "CONFLICT" in mt_out or mt_code != 0:
                conflicting = True
                conflict_details = "\n".join([line for line in mt_out.splitlines() if "CONFLICT" in line])

        overlapping_merged = []
        for m_num, m_files in merged_files.items():
            overlap = op_files & m_files
            if overlap:
                overlapping_merged.append({
                    "merged_pr": m_num,
                    "overlapping_files": list(overlap)
                })

        if conflicting or overlapping_merged:
            sibling_issues.append({
                "open_pr": op_num,
                "title": op.get("title"),
                "head_ref": head_ref,
                "conflicting": conflicting,
                "conflict_details": conflict_details,
                "overlapping_merged_prs": overlapping_merged,
                "recommendation": "CLOSE_SUPERSEDED" if (conflicting and overlapping_merged) else ("REBASE" if conflicting else "REVIEW")
            })

    return {
        "status": "success",
        "recently_merged_count": len(merged_prs),
        "open_prs_audited": len(open_prs),
        "impacted_sibling_prs_count": len(sibling_issues),
        "impacted_sibling_prs": sibling_issues
    }


def output_json_report(data: any, output_path: Optional[str] = None):
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    else:
        print(json.dumps(data, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Bot PR Supersession & Learning Harmonizer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # detect-duplicates
    dup_parser = subparsers.add_parser("detect-duplicates", help="Detect duplicate and competing bot PRs")
    dup_parser.add_argument("--repo", default=None, help="Optional GitHub repository (owner/repo)")
    dup_parser.add_argument("--output", default=None, help="Optional path to write JSON report")

    # union-jules
    union_parser = subparsers.add_parser("union-jules", help="Additively union Jules learning notes across branches")
    union_parser.add_argument("--target-file", required=True, help="Path to local .jules/*.md file")
    union_parser.add_argument("--source-file", default=None, help="Path to feature branch .jules/*.md file or string")
    union_parser.add_argument("--in-place", action="store_true", help="Write unioned result directly to target-file")
    union_parser.add_argument("--output", default=None, help="Optional path to write output")

    # close-superseded
    close_parser = subparsers.add_parser("close-superseded", help="Close superseded PRs with clean audit references")
    close_parser.add_argument("--pr", type=int, required=True, help="PR number to close")
    close_parser.add_argument("--primary-pr", type=int, required=True, help="Primary PR number that was merged")
    close_parser.add_argument("--repo", default=None, help="Optional GitHub repository (owner/repo)")
    close_parser.add_argument("--dry-run", action="store_true", help="Simulate closure without mutating GitHub state")
    close_parser.add_argument("--output", default=None, help="Optional path to write JSON report")

    # detect-test-subsumption
    sub_parser = subparsers.add_parser("detect-test-subsumption", help="Analyze test case overlap and subsumption between two PRs or files")
    sub_parser.add_argument("--pr-a", type=int, default=None, help="PR number for Candidate A")
    sub_parser.add_argument("--pr-b", type=int, default=None, help="PR number for Candidate B")
    sub_parser.add_argument("--file-a", default=None, help="File path for Candidate A test content")
    sub_parser.add_argument("--file-b", default=None, help="File path for Candidate B test content")
    sub_parser.add_argument("--repo", default=None, help="Optional GitHub repository (owner/repo)")
    # audit-post-merge
    post_parser = subparsers.add_parser("audit-post-merge", help="Audit open PRs immediately after a PR merge to detect newly conflicting or superseded sibling PRs")
    post_parser.add_argument("--repo", default=None, help="Optional GitHub repository (owner/repo)")
    post_parser.add_argument("--base-ref", default="main", help="Target base branch (default: main)")
    post_parser.add_argument("--limit", type=int, default=5, help="Number of recently merged PRs to inspect (default: 5)")
    post_parser.add_argument("--base-dir", default=None, help="Optional local directory of git repository for in-memory merge simulation")
    post_parser.add_argument("--output", default=None, help="Optional path to write JSON report")

    args = parser.parse_args()

    if args.command == "audit-post-merge":
        report = audit_post_merge(repo=args.repo, base_ref=args.base_ref, limit=args.limit, base_dir=args.base_dir)
        output_json_report(report, args.output)
        if args.output:
            print(f"Post-merge audit completed: {report.get('impacted_sibling_prs_count', 0)} impacted sibling PR(s) detected. Written to {args.output}")

    elif args.command == "detect-duplicates":
        report = detect_duplicate_prs(repo=args.repo)
        output_json_report(report, args.output)
        if args.output:
            print(f"Duplicate audit completed: {report.get('duplicate_groups_count', 0)} duplicate group(s) found. Written to {args.output}")

    elif args.command == "union-jules":
        source_content = ""
        if args.source_file and Path(args.source_file).is_file():
            source_content = Path(args.source_file).read_text(encoding="utf-8", errors="ignore")
        unioned = union_jules_files(args.target_file, source_content)
        if args.in_place:
            Path(args.target_file).write_text(unioned, encoding="utf-8")
            print(f"Successfully unioned learning notes in-place to {args.target_file}")
        elif args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(unioned)
            print(f"Unioned output written to {args.output}")
        else:
            print(unioned)

    elif args.command == "close-superseded":
        report = close_superseded_pr(pr_number=args.pr, primary_pr=args.primary_pr, repo=args.repo, dry_run=args.dry_run)
        output_json_report(report, args.output)
        if args.output:
            print(f"PR closure report written to {args.output}")

    elif args.command == "detect-test-subsumption":
        content_a = ""
        content_b = ""

        if args.file_a and Path(args.file_a).is_file():
            content_a = Path(args.file_a).read_text(encoding="utf-8", errors="ignore")
        elif args.pr_a:
            cmd_a = ["gh", "pr", "diff", str(args.pr_a)]
            if args.repo:
                cmd_a.extend(["--repo", args.repo])
            _, content_a, _ = run_cmd(cmd_a)

        if args.file_b and Path(args.file_b).is_file():
            content_b = Path(args.file_b).read_text(encoding="utf-8", errors="ignore")
        elif args.pr_b:
            cmd_b = ["gh", "pr", "diff", str(args.pr_b)]
            if args.repo:
                cmd_b.extend(["--repo", args.repo])
            _, content_b, _ = run_cmd(cmd_b)

        result = analyze_test_subsumption(content_a, content_b)
        result["candidate_a"] = args.pr_a or args.file_a
        result["candidate_b"] = args.pr_b or args.file_b
        output_json_report(result, args.output)
        if args.output:
            print(f"Subsumption analysis written to {args.output}")


if __name__ == "__main__":
    main()
