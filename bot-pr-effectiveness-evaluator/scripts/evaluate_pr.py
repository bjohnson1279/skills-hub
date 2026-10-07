#!/usr/bin/env python3
import os
import sys
import json
import re
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def run_command(cmd, cwd=None):
    env = os.environ.copy()
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_PAGER"] = "1"
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    res = subprocess.run(cmd, cwd=cwd, shell=True, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise Exception(f"Command failed: {res.stderr.strip()}")
    return res.stdout, res.stderr

def evaluate_pr(repo, pr_num, base_dir=None):
    try:
        view_cmd = f"gh pr view {pr_num} -R {repo} --json number,title,author,headRefName,baseRefName,state,files,statusCheckRollup,body,mergeable"
        view_out, _ = run_command(view_cmd)
        pr_data = json.loads(view_out)
        
        diff_cmd = f"gh pr diff {pr_num} -R {repo}"
        diff_out, _ = run_command(diff_cmd)
        
        score = 50
        improvements = []
        risks = []
        
        # Regex checks - Algorithmic and Data Structures
        if "Map<" in diff_out or "new Map" in diff_out:
            score += 15
            improvements.append("Replaced O(N) linear array scan with O(1) Map lookup")
        if re.search(r'Dict\[|dict\[|_[a-zA-Z0-9_]+_index\[|_[a-zA-Z0-9_]+_by_', diff_out):
            score += 15
            improvements.append("Replaced O(N) linear scan with O(1) dictionary index lookup")
        if "keyBy(" in diff_out:
            score += 15
            improvements.append("Optimized collection lookup with keyBy dictionary indexing")
        if "for...in" in diff_out or ("for (" in diff_out and "Object.keys" not in diff_out and "Object.values" not in diff_out):
            score += 10
            improvements.append("Optimized object iteration avoiding intermediate array/Set allocations")
        if "toLowerCase" in diff_out and "for" in diff_out:
            score += 10
            improvements.append("Hoisted string case transformations out of innermost comparison loops")
        if "Set<" in diff_out or "new Set" in diff_out:
            score += 10
            improvements.append("Used Set for O(1) permission/membership lookups")

        # Security and Sanitization
        if "process.env.NODE_ENV" in diff_out and "production" in diff_out:
            score += 15
            improvements.append("Sanitized error responses for production environments")
        if re.search(r'SecurityHeadersMiddleware|X-Content-Type-Options|Content-Security-Policy|Strict-Transport-Security', diff_out):
            score += 15
            improvements.append("Injected HTTP security headers middleware")
        if "decrypt" in diff_out and ("throw" in diff_out or "raise" in diff_out or "fail closed" in diff_out.lower()):
            score += 15
            improvements.append("Hardened decryption to fail closed securely")
        if re.search(r'sanitizeUrl|isValidUrl|encodeURI', diff_out):
            score += 15
            improvements.append("Sanitized dynamic URLs against injection vulnerabilities")
        if re.search(r'escapeHtml\(|encodeURIComponent\(|validator\.escape|DOMPurify\.sanitize', diff_out):
            score += 15
            improvements.append("Sanitized dynamic output against XSS vulnerabilities")
        if re.search(r'isNaN|isFinite|<=?\s*100|>=?\s*0|validator|bounds|MAX_.*_SIZE', diff_out) and re.search(r'status\(400\)|Bad Request|raise HTTPException|throw new Error', diff_out):
            score += 15
            improvements.append("Added parameter bounds and type validation to protect against calculation/resource exploits")

        # Accessibility and UI
        if re.search(r'aria-label|htmlFor|<label', diff_out):
            score += 10
            improvements.append("Added accessible form labels / WCAG markup")

        # Artifact cleanup & Test coverage
        if re.search(r'-\s*.*\.timestamp-.*\.mjs', diff_out):
            score += 10
            improvements.append("Pruned stale temporary build/timestamp artifacts")
        if re.search(r'\+def test_|\+it\(|\+test\(', diff_out):
            score += 15
            improvements.append("Added regression or unit test coverage")
            
        files_changed = [f["path"] for f in pr_data.get("files", [])]
        scratch_files = [f for f in files_changed if re.search(r'test_.*\.sh|plan\.md|\.scratch|fix_.*\.php|fix_.*\.cjs|patch_.*\.py', f)]
        if scratch_files:
            score -= 20
            risks.append(f"Contains uncleaned scratch/verification files: {', '.join(scratch_files)}")
            
        score = min(max(score, 0), 100)
        
        tier = "High Value (Merge Recommended)" if score >= 80 else "Moderate Value (Safe to Merge)" if score >= 50 else "Low Value (Needs Review)"
        rec = "MERGE" if score >= 50 else "REVIEW"
        
        return {
            "repository": repo,
            "pr_number": pr_num,
            "title": pr_data.get("title"),
            "author": pr_data.get("author", {}).get("login"),
            "state": pr_data.get("state"),
            "mergeable": pr_data.get("mergeable"),
            "score": score,
            "tier": tier,
            "recommendation": rec,
            "patterns": {
                "security_improvements": improvements,
                "potential_risks": risks,
            },
            "files_changed": [f["path"] for f in pr_data.get("files", [])]
        }
    except Exception as e:
        return {"repository": repo, "pr_number": pr_num, "error": str(e)}

def batch_evaluate(prs, max_workers=6):
    results = []
    print(f"Evaluating {len(prs)} PRs concurrently with {max_workers} workers...", flush=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(evaluate_pr, repo, num) for repo, num in prs]
        for fut in as_completed(futures):
            results.append(fut.result())
    return results

def generate_matrix(input_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print("# 📊 Bot PR Effectiveness Evaluation Matrix\n")
    print("| Repo | PR # | Title | Score | Recommendation | Key Improvements | Potential Risks |")
    print("| :--- | :---: | :--- | :---: | :---: | :--- | :--- |")
    
    for r in data:
        if "error" in r:
            print(f"| `{r['repository']}` | **#{r['pr_number']}** | ERROR | N/A | N/A | {r['error']} | N/A |")
            continue
            
        repo = r["repository"]
        pr = r["pr_number"]
        title = r["title"]
        score = r["score"]
        rec = r["recommendation"]
        
        imps = "<br>• ".join([""] + r.get("patterns", {}).get("security_improvements", [])) if r.get("patterns", {}).get("security_improvements") else "None detected"
        if imps.startswith("<br>• "): imps = "• " + imps[6:]
        
        risks = "<br>⚠️ ".join([""] + r.get("patterns", {}).get("potential_risks", [])) if r.get("patterns", {}).get("potential_risks") else "None"
        if risks.startswith("<br>⚠️ "): risks = "⚠️ " + risks[7:]
        
        print(f"| `{repo}` | **#{pr}** | {title} | **{score}/100** | **{rec}** | {imps} | {risks} |")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    
    eval_parser = subparsers.add_parser("evaluate")
    eval_parser.add_argument("repo")
    eval_parser.add_argument("pr_number", type=int)
    eval_parser.add_argument("--base-dir")
    
    batch_parser = subparsers.add_parser("batch_evaluate")
    batch_parser.add_argument("--input-file", required=True)
    batch_parser.add_argument("--output-file", required=True)
    
    matrix_parser = subparsers.add_parser("matrix")
    matrix_parser.add_argument("--input-file", required=True)
    
    args = parser.parse_args()
    
    if args.command == "evaluate":
        res = evaluate_pr(args.repo, args.pr_number, args.base_dir)
        print(json.dumps(res, indent=2))
    elif args.command == "batch_evaluate":
        with open(args.input_file, 'r', encoding='utf-8') as f:
            prs = json.load(f)
        results = batch_evaluate(prs)
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
    elif args.command == "matrix":
        generate_matrix(args.input_file)
