#!/usr/bin/env python3
"""Check git commit subjects against conventional commit rules."""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

VALID_TYPES = {
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
}

FORBIDDEN_STARTS = (
    "wip",
    "fixup!",
    "squash!",
    "tmp",
    "address review",
)


def is_shallow(repo_root: Path) -> bool:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        return res.returncode == 0 and res.stdout.strip().lower() == "true"
    except Exception:
        return False


def get_commits(repo_root: Path, base_ref: str, head_ref: str) -> list:
    git_range = f"{base_ref}..{head_ref}"
    cmd = ["git", "log", "--format=%H|%h|%P|%s", git_range]
    res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"Error reading commits for range '{git_range}': {res.stderr.strip()}")
    commits = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            full_sha, short_sha, parents_str, subject = parts
            parents = parents_str.split() if parents_str else []
            commits.append({
                "full_sha": full_sha,
                "short_sha": short_sha,
                "parents": parents,
                "subject": subject,
            })
    return commits


def validate_commit(commit: dict) -> list:
    # Skip merge commits (commits with more than 1 parent)
    if len(commit["parents"]) > 1:
        return []

    subject = commit["subject"].strip()
    errors = []

    if not subject:
        errors.append("Commit subject is empty.")
        return errors

    if len(subject) > 100:
        errors.append(f"Subject exceeds 100 characters (length: {len(subject)}).")

    subject_lower = subject.lower()
    for bad in FORBIDDEN_STARTS:
        if subject_lower.startswith(bad):
            errors.append(f"Subject starts with forbidden prefix '{bad}'.")

    # Match conventional commit pattern: <type>(<scope>)?: <subject>
    pattern = r"^([a-zA-Z]+)(?:\([a-zA-Z0-9_./-]+\))?!?: (.+)$"
    m = re.match(pattern, subject)
    if not m:
        errors.append("Subject does not follow conventional commit pattern '<type>(<scope>): <subject>'.")
    else:
        ctype = m.group(1).lower()
        subtext = m.group(2).strip()
        if ctype not in VALID_TYPES:
            errors.append(f"Commit type '{ctype}' is not in approved list ({sorted(VALID_TYPES)}).")
        if not subtext:
            errors.append("Subject description after type/scope is empty.")
        sub_lower = subtext.lower()
        for bad in FORBIDDEN_STARTS:
            if sub_lower.startswith(bad):
                errors.append(f"Subject description starts with forbidden prefix '{bad}'.")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Check conventional commit messages in git range.")
    parser.add_argument("--base", required=True, help="Base git reference")
    parser.add_argument("--head", required=True, help="Head git reference")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    if is_shallow(repo_root):
        print("Notice: shallow repository detected, skipping commit check.")
        sys.exit(0)

    commits = get_commits(repo_root, args.base, args.head)
    if not commits:
        print(f"PASS: No commits found in range {args.base}..{args.head}.")
        sys.exit(0)

    all_errors = []
    for c in commits:
        errs = validate_commit(c)
        if errs:
            all_errors.append((c, errs))

    if all_errors:
        print(f"FAIL: {len(all_errors)} commit(s) violated commit message rules:")
        for c, errs in all_errors:
            print(f"  Commit {c['short_sha']}: \"{c['subject']}\"")
            for e in errs:
                print(f"    - {e}")
        sys.exit(1)

    print(f"PASS: All {len(commits)} commit(s) in {args.base}..{args.head} satisfy commit rules.")


if __name__ == "__main__":
    main()
