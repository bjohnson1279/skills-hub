---
name: pr-supersession-detector
description: Audits open pull requests across repositories to detect superseded, redundant, or zero-diff bot PRs using in-memory diff comparison, dependency manifest inspection, and repository directive checks.
---

# PR Supersession Detector

This skill provides automated detection and safe batch closure of superseded, redundant, or zero-diff bot PRs across GitHub repositories.

## Purpose

When automated bots (Jules, Sentinel, Dependabot) submit multiple PRs for the same dependency or feature area, sibling PRs can become obsolete when:
1. An overlapping PR was already merged (e.g. `loofah 2.25.2` merged into `main` while PR #8 still asks for `loofah 2.25.2`).
2. A subsequent PR provides a strictly superior implementation (e.g. database-indexed queries vs unindexed in-memory filtering).
3. The PR introduces zero code modifications against the latest base branch (hallucinatory task acknowledgment).
4. The PR directly violates repository architectural directives in `.jules/*.md`.

## CLI Usage

Run the supersession detector CLI:

```bash
# Scan a single repository in dry-run mode
python C:/Users/johns/.gemini/config/skills/pr-supersession-detector/scripts/supersession_detector.py --repo bjohnson1279/ruby-crm --dry-run

# Scan all repositories for an owner
python C:/Users/johns/.gemini/config/skills/pr-supersession-detector/scripts/supersession_detector.py --owner bjohnson1279 --base-dir C:/Users/johns/DEV --dry-run

# Automatically close superseded PRs with rationale comments
python C:/Users/johns/.gemini/config/skills/pr-supersession-detector/scripts/supersession_detector.py --owner bjohnson1279 --base-dir C:/Users/johns/DEV --execute
```

## Detection Heuristics

1. **Pairwise Sibling Subset Analysis**:
   When multiple open PRs from automated bots (Jules, Bolt, Sentinel, Dependabot) target the same repository, pairwise comparison evaluates changed file sets. If the target files of PR A are an exact match or subset of PR B and PR B has a higher PR number or superior implementation, PR A is flagged as superseded with a direct reference to PR B.

2. **Journal-Only / Zero-Code Elimination**:
   PRs where diffs are restricted exclusively to `.jules/*.md` journal logs or CI workflow files without functional code changes are flagged as `INVALID` and rejected.

3. **Zero-Diff Elimination**:
   PRs where `git diff origin/<base>...HEAD` contains no code changes against the target branch (excluding `.jules/*.md` logs) are flagged for immediate closure.

4. **Dependency Manifest Subsumption**:
   PRs updating dependencies (Ruby Gemfile, PHP composer.json, Node package.json) are checked against `origin/<base>`. If the target package version is already satisfied on the base branch, the PR is marked superseded.

5. **Directive Compliance**:
   Scans modified lines against negative constraints documented in `.jules/*.md` (e.g. forbidden API replacements, scratch files, unresolved conflict markers).
