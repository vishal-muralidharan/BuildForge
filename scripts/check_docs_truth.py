#!/usr/bin/env python3
"""Documentation truth verification check for Build Forge.

Extracts:
1. Every build-forge command referenced in documentation and skill definitions.
2. Every python3 .agents/skills/... script execution command.

Asserts:
- Every build-forge command maps to a recognized CLI command or flag.
- Every python script referenced exists in the skills/ package distribution.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

RECOGNIZED_CLI_COMMANDS = {
    "install",
    "link",
    "unlink",
    "verify",
    "status",
    "diff",
    "doctor",
    "outdated",
    "update",
    "upgrade",
    "add",
    "list",
    "help",
    "--force",  # shorthand for install --force in README.md
}


def find_doc_files(repo_root: Path) -> list:
    """Collect all markdown documentation and skill files in the repository."""
    doc_files = []
    top_docs = ["README.md", "UPGRADING.md", "MAINTAINING.md", "maintainers/README.md"]
    for rel_doc in top_docs:
        p = repo_root / rel_doc
        if p.is_file():
            doc_files.append(p)

    skills_dir = repo_root / "skills"
    if skills_dir.is_dir():
        for p in sorted(skills_dir.rglob("*.md")):
            doc_files.append(p)

    return doc_files


def check_docs_truth(repo_root: Path) -> tuple:
    """Extract commands from documentation and verify each exists.

    Returns (bf_results, py_results, missing_count).
    """
    doc_files = find_doc_files(repo_root)

    bf_pattern = re.compile(
        r"(?:npx\s+(?:@v1006/)?build-forge|build-forge)\s+([a-z0-9-]+)", re.IGNORECASE
    )
    py_pattern = re.compile(
        r"python3?\s+\.?/?\.agents/skills/([a-z0-9_-]+/(?:scripts/|references/)?[a-z0-9_-]+\.py)",
        re.IGNORECASE,
    )

    bf_cmd_locations = {}
    py_script_locations = {}

    for df in doc_files:
        rel_path = df.relative_to(repo_root).as_posix()
        try:
            content = df.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for m in bf_pattern.finditer(content):
            cmd_token = m.group(1).lower()
            bf_cmd_locations.setdefault(cmd_token, []).append(rel_path)

        for m in py_pattern.finditer(content):
            script_path = m.group(1)
            py_script_locations.setdefault(script_path, []).append(rel_path)

    bf_results = []
    missing_count = 0

    for cmd in sorted(bf_cmd_locations.keys()):
        locs = sorted(set(bf_cmd_locations[cmd]))
        if cmd in RECOGNIZED_CLI_COMMANDS:
            bf_results.append((cmd, "PASS", locs))
        else:
            bf_results.append((cmd, "FAIL", locs))
            missing_count += 1

    py_results = []
    for script_rel in sorted(py_script_locations.keys()):
        locs = sorted(set(py_script_locations[script_rel]))
        target_file = repo_root / "skills" / script_rel
        if target_file.is_file():
            py_results.append((script_rel, "PASS", locs))
        else:
            py_results.append((script_rel, "FAIL", locs))
            missing_count += 1

    return bf_results, py_results, missing_count


def main():
    parser = argparse.ArgumentParser(description="Verify documentation truth for Build Forge commands.")
    parser.add_argument("--root", default=None, help="Repository root path")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent

    print(f"Checking documentation truth on {repo_root}...\n")
    bf_results, py_results, missing_count = check_docs_truth(repo_root)

    print(f"{'Build Forge CLI Command':<28} {'Status':<10} {'Referenced In'}")
    print("-" * 80)
    for cmd, status, locs in bf_results:
        loc_str = locs[0] if len(locs) == 1 else f"{locs[0]} (+{len(locs) - 1} more)"
        print(f"{cmd:<28} [{status:<4}]     {loc_str}")

    print("\n" + f"{'Python Script Execution':<55} {'Status':<10} {'Referenced In'}")
    print("-" * 90)
    for script, status, locs in py_results:
        loc_str = locs[0] if len(locs) == 1 else f"{locs[0]} (+{len(locs) - 1} more)"
        print(f"{script:<55} [{status:<4}]     {loc_str}")

    print("-" * 90)
    if missing_count > 0:
        print(f"\nDocumentation truth check: FAILED ({missing_count} missing item(s)).")
        sys.exit(1)
    else:
        print("\nDocumentation truth check: PASSED (all documented commands exist).")
        sys.exit(0)


if __name__ == "__main__":
    main()

