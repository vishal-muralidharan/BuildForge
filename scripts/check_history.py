#!/usr/bin/env python3
"""Check first-parent git history against the merge trail policy."""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


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


def get_first_parent_commits(repo_root: Path, ref: str) -> list:
    cmd = ["git", "log", "--first-parent", "--format=%H|%h|%P|%s", ref]
    res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"Error reading git history for ref '{ref}': {res.stderr.strip()}")
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


def is_pr_merge(commit: dict) -> bool:
    if len(commit["parents"]) == 2:
        return bool(re.match(r"^Merge pull request #\d+ from ", commit["subject"]))
    return False


def load_baseline(baseline_path: Path) -> set:
    prefixes = set()
    if baseline_path.is_file():
        for line in baseline_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            token = line.split()[0]
            prefixes.add(token.lower())
    return prefixes


def init_baseline(baseline_path: Path, commits: list) -> None:
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    existing_prefixes = load_baseline(baseline_path)
    new_lines = []
    added = 0
    # Process from oldest to newest for clean file order
    for c in reversed(commits):
        if is_pr_merge(c):
            continue
        prefix = c["short_sha"].lower()
        if prefix in existing_prefixes:
            continue
        new_lines.append(f"{c['short_sha']} before merge policy: {c['subject']}\n")
        existing_prefixes.add(prefix)
        added += 1

    with baseline_path.open("a", encoding="utf-8") as f:
        for nl in new_lines:
            f.write(nl)
    print(f"Initialized baseline in {baseline_path} with {added} commit(s).")


def check_history(commits: list, baseline_prefixes: set, ref: str) -> bool:
    violations = []
    for c in commits:
        if is_pr_merge(c):
            continue
        # Check against baseline prefixes
        sha_lower = c["full_sha"].lower()
        short_lower = c["short_sha"].lower()
        matched = False
        for pref in baseline_prefixes:
            if sha_lower.startswith(pref) or pref.startswith(short_lower):
                matched = True
                break
        if not matched:
            violations.append(c)

    if violations:
        print(f"FAIL: History check found {len(violations)} non-PR commit(s) on '{ref}':")
        for v in violations:
            print(f"  {v['short_sha']} ({len(v['parents'])} parents) {v['subject']}")
        return False

    print(f"PASS: History check passed for '{ref}' ({len(commits)} commit(s) verified).")
    return True


def get_repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / ".git").exists():
        return cwd
    return Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="Check first-parent history against merge policy.")
    parser.add_argument("--ref", default="main", help="Git ref to check (default: main)")
    parser.add_argument("--baseline", default="maintainers/history-baseline.txt", help="Path to baseline file")
    parser.add_argument("--init-baseline", action="store_true", help="Initialize baseline from existing commits")
    args = parser.parse_args()

    repo_root = get_repo_root()

    if is_shallow(repo_root):
        print("Notice: shallow repository detected, skipping history check.")
        sys.exit(0)

    baseline_path = Path(args.baseline) if Path(args.baseline).is_absolute() else repo_root / args.baseline
    commits = get_first_parent_commits(repo_root, args.ref)

    if args.init_baseline:
        init_baseline(baseline_path, commits)
        sys.exit(0)

    baseline_prefixes = load_baseline(baseline_path)
    ok = check_history(commits, baseline_prefixes, args.ref)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
