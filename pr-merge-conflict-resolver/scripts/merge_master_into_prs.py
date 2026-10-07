#!/usr/bin/env python3
import subprocess
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    return res.returncode, res.stdout, res.stderr

def get_git_root():
    code, stdout, _ = run("git rev-parse --show-toplevel")
    if code == 0:
        return stdout.strip()
    return os.getcwd()

def resolve_text_conflict(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return False

    if "<<<<<<<" not in content:
        return False

    lines = content.splitlines()
    new_lines = []
    in_conflict = False
    side_a = []
    side_b = []
    current_side = None

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("<<<<<<<"):
            in_conflict = True
            current_side = "a"
            side_a = []
            side_b = []
            i += 1
            continue
        elif line.startswith("======="):
            current_side = "b"
            i += 1
            continue
        elif line.startswith(">>>>>>>"):
            in_conflict = False
            all_lines = side_a + side_b
            use_lines = [l for l in all_lines if l.strip().startswith("use ") or l.strip().startswith("import ")]

            if use_lines and len(use_lines) == len(all_lines):
                seen = set()
                dedup_uses = []
                for u in use_lines:
                    if u not in seen:
                        seen.add(u)
                        dedup_uses.append(u)
                new_lines.extend(dedup_uses)
            else:
                res_block = []
                seen = set()
                for l in side_a + side_b:
                    if l not in seen or l.strip() == "" or l.strip() in ["{", "}"]:
                        if l.strip() not in ["{", "}"]:
                            seen.add(l)
                        res_block.append(l)
                new_lines.extend(res_block)

            i += 1
            continue

        if in_conflict:
            if current_side == "a":
                side_a.append(line)
            else:
                side_b.append(line)
        else:
            new_lines.append(line)
        i += 1

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")
    return True

def main():
    repo_dir = get_git_root()
    base_branch = sys.argv[1] if len(sys.argv) > 1 else "master"

    # Detect if master or main exists
    c_m, _, _ = run(f"git rev-parse --verify {base_branch}", cwd=repo_dir)
    if c_m != 0 and base_branch == "master":
        c_main, _, _ = run("git rev-parse --verify main", cwd=repo_dir)
        if c_main == 0:
            base_branch = "main"

    print(f"Updating local target branch '{base_branch}' in {repo_dir}...")
    run("git fetch origin", cwd=repo_dir)
    run(f"git checkout {base_branch}", cwd=repo_dir)
    run(f"git pull origin {base_branch}", cwd=repo_dir)

    code, stdout, stderr = run("gh pr list --state open --json number,title,headRefName", cwd=repo_dir)
    if code != 0:
        print("Error getting open PRs:", stderr)
        sys.exit(1)

    prs = json.loads(stdout)
    if not prs:
        print("No open PRs found.")
        sys.exit(0)

    print(f"Processing {len(prs)} open PRs...")
    results = []

    for pr in prs:
        branch = pr["headRefName"]
        num = pr["number"]
        print(f"\n--- PR #{num}: {branch} ---")

        run(f"git fetch origin {branch}", cwd=repo_dir)
        run(f"git checkout -B {branch} origin/{branch}", cwd=repo_dir)

        # Abort any prior merge state and reset to origin branch
        run("git merge --abort", cwd=repo_dir)
        run(f"git reset --hard origin/{branch}", cwd=repo_dir)

        code_m, _, _ = run(f"git merge origin/{base_branch} --no-edit", cwd=repo_dir)
        if code_m == 0:
            print(f"  Clean merge into #{num}")
            p_code, _, _ = run(f"git push origin {branch} -f", cwd=repo_dir)
            results.append((num, branch, "Clean"))
        else:
            print(f"  Conflicts detected in #{num}, resolving...")
            _, status_out, _ = run("git status --porcelain", cwd=repo_dir)

            for line in status_out.splitlines():
                if len(line) < 4:
                    continue
                filepath = line[3:].strip()
                abs_p = os.path.join(repo_dir, filepath)

                if filepath.endswith((".gz", ".sql", ".png", ".jpg", ".zip", ".tar", ".lock", ".bin", ".db", "package-lock.json", "composer.lock", "pnpm-lock.yaml")) or ".jules" in filepath.lower():
                    run(f'git checkout origin/{base_branch} -- "{filepath}"', cwd=repo_dir)
                    run(f'git add "{filepath}"', cwd=repo_dir)
                elif os.path.exists(abs_p):
                    res = resolve_text_conflict(abs_p)
                    if not res:
                        run(f'git checkout origin/{base_branch} -- "{filepath}"', cwd=repo_dir)
                    run(f'git add "{filepath}"', cwd=repo_dir)
                else:
                    run(f'git rm "{filepath}"', cwd=repo_dir)

            run(f'git commit -m "Merge origin/{base_branch} into branch and resolve conflicts"', cwd=repo_dir)
            p_code, _, p_err = run(f"git push origin {branch} -f", cwd=repo_dir)

            if p_code == 0:
                print(f"  Successfully merged origin/{base_branch} into #{num} and pushed!")
                results.append((num, branch, "Resolved & Pushed"))
            else:
                print(f"  Push failed for #{num}: {p_err[:100]}")
                results.append((num, branch, f"Push Failed"))

    run(f"git checkout {base_branch}", cwd=repo_dir)

    print("\n================ FINAL STATUS ================")
    for num, branch, status in results:
        print(f"PR #{num} ({branch}): {status}")

if __name__ == "__main__":
    main()
