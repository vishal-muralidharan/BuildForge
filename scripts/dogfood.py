#!/usr/bin/env python3
"""Dogfood verification and synchronization tool for Build Forge.

Keeps the installed core pipeline skills in .agents/skills in sync with skills/.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

DOGFOOD_SET = [
    "atomic-commits",
    "audit-and-planning",
    "extend-pipeline",
    "feature-delivery",
    "project-blueprints",
    "project-bootstrap",
    "repo-search",
    "rules-to-tests",
    "sync-skills-and-docs",
    "targeted-module-testing",
]

DOGFOOD_EXCLUDED = [
    "legal-and-settings-pages",
    "product-spec",
    "project-readme",
    "scaffold-app",
]

IGNORED_NAMES = {"__pycache__", ".DS_Store"}


def get_repo_root(custom_root: str = None) -> Path:
    if custom_root:
        return Path(custom_root).resolve()
    return Path(__file__).resolve().parent.parent


def normalize_content(content: bytes) -> bytes:
    """Normalize CRLF to LF."""
    return content.replace(b"\r\n", b"\n")


def check_adoption_state(repo_root: Path) -> str:
    lock_file = repo_root / ".agents" / "build-forge.lock.json"
    profile_file = repo_root / ".agents" / "project-profile.yaml"
    has_lock = lock_file.is_file()
    has_profile = profile_file.is_file()
    if not has_lock and not has_profile:
        return "not_adopted"
    if has_profile and not has_lock:
        return "profile_no_lock"
    return "adopted"


def collect_skill_files(skill_dir: Path) -> dict:
    """Collect relative paths to contents normalized."""
    files = {}
    if not skill_dir.is_dir():
        return files
    for root, dirs, filenames in os.walk(skill_dir):
        # Exclude ignored dirs in place
        dirs[:] = [d for d in dirs if d not in IGNORED_NAMES]
        for f in filenames:
            if f in IGNORED_NAMES or f.endswith(".pyc"):
                continue
            full_path = Path(root) / f
            rel = full_path.relative_to(skill_dir).as_posix()
            try:
                data = full_path.read_bytes()
                files[rel] = normalize_content(data)
            except Exception as e:
                files[rel] = b""
    return files


def check_dogfood(repo_root: Path) -> list:
    """Perform read-only check of installed skills against DOGFOOD_SET and source skills."""
    errors = []
    skills_dir = repo_root / "skills"
    agents_skills_dir = repo_root / ".agents" / "skills"
    lock_file = repo_root / ".agents" / "build-forge.lock.json"
    integrity_file = repo_root / "integrity.json"

    # 1. Check skills/ directory contents against DOGFOOD_SET and DOGFOOD_EXCLUDED
    if not skills_dir.is_dir():
        errors.append(f"Source skills directory missing: {skills_dir}")
        return errors

    source_skill_dirs = set()
    for entry in skills_dir.iterdir():
        if entry.is_dir() and entry.name not in IGNORED_NAMES:
            source_skill_dirs.add(entry.name)

    expected_total = set(DOGFOOD_SET) | set(DOGFOOD_EXCLUDED)

    # Check for new skills in skills/ not in either set
    for name in sorted(source_skill_dirs):
        if name not in expected_total:
            errors.append(
                f"new skill {name}: add it to DOGFOOD_SET or DOGFOOD_EXCLUDED in scripts/dogfood.py"
            )

    # Check for names in either constant that do not exist in skills/
    for name in sorted(expected_total):
        if name not in source_skill_dirs:
            errors.append(
                f"skill '{name}' in DOGFOOD_SET or DOGFOOD_EXCLUDED does not exist in skills/"
            )

    # 2. Check lock file
    if not lock_file.is_file():
        errors.append("Lock file missing: .agents/build-forge.lock.json")
        return errors

    try:
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Invalid JSON in .agents/build-forge.lock.json: {e}")
        return errors

    installed_in_lock = lock_data.get("_installed", [])
    if sorted(installed_in_lock) != sorted(DOGFOOD_SET):
        missing = sorted(set(DOGFOOD_SET) - set(installed_in_lock))
        extra = sorted(set(installed_in_lock) - set(DOGFOOD_SET))
        if missing:
            errors.append(f"Lockfile _installed missing skills: {', '.join(missing)}")
        if extra:
            errors.append(f"Lockfile _installed contains unexpected skills: {', '.join(extra)}")

    # 3. Check disk installed skills set
    if not agents_skills_dir.is_dir():
        errors.append("Installed skills directory missing: .agents/skills")
        return errors

    installed_on_disk = set()
    for entry in agents_skills_dir.iterdir():
        if entry.is_dir() and entry.name not in IGNORED_NAMES:
            if entry.name in source_skill_dirs:
                installed_on_disk.add(entry.name)
            else:
                # Check if this is a generated convention skill from project profile
                skill_md = entry / "SKILL.md"
                if skill_md.is_file():
                    try:
                        head = skill_md.read_text(encoding="utf-8", errors="ignore")[:400]
                        if "<!-- build-forge:generated" in head or "by project-bootstrap" in head:
                            continue
                    except Exception:
                        pass
                installed_on_disk.add(entry.name)

    if sorted(installed_on_disk) != sorted(DOGFOOD_SET):
        missing = sorted(set(DOGFOOD_SET) - set(installed_on_disk))
        extra = sorted(set(installed_on_disk) - set(DOGFOOD_SET))
        if missing:
            errors.append(f"Installed skills on disk missing: {', '.join(missing)}")
        if extra:
            errors.append(f"Installed skills on disk contains unexpected skills: {', '.join(extra)}")

    # 4. Check file contents match between skills/<name> and .agents/skills/<name>
    for skill_name in sorted(DOGFOOD_SET):
        src_dir = skills_dir / skill_name
        dest_dir = agents_skills_dir / skill_name
        if not src_dir.is_dir() or not dest_dir.is_dir():
            continue

        src_files = collect_skill_files(src_dir)
        dest_files = collect_skill_files(dest_dir)

        # Check for extra files in installed skill
        extra_files = sorted(set(dest_files.keys()) - set(src_files.keys()))
        for ef in extra_files:
            errors.append(f"Extra file in installed skill '{skill_name}': {ef}")

        # Check for missing files in installed skill
        missing_files = sorted(set(src_files.keys()) - set(dest_files.keys()))
        for mf in missing_files:
            errors.append(f"Missing file in installed skill '{skill_name}': {mf}")

        # Check content match for common files
        common_files = sorted(set(src_files.keys()) & set(dest_files.keys()))
        for cf in common_files:
            if src_files[cf] != dest_files[cf]:
                errors.append(f"File content differs in '{skill_name}': {cf}")

    # 5. Check lock hashes match integrity.json
    if integrity_file.is_file():
        try:
            integrity_data = json.loads(integrity_file.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"Invalid JSON in integrity.json: {e}")
            integrity_data = {}

        if integrity_data:
            # Every hash in lockData for installed skills must equal integrity.json
            for k, expected_hash in integrity_data.items():
                parts = k.split("/")
                if len(parts) >= 2 and parts[0] == "skills" and parts[1] in DOGFOOD_SET:
                    lock_hash = lock_data.get(k)
                    if not lock_hash:
                        errors.append(f"Lockfile missing entry for installed skill file: {k}")
                    elif lock_hash != expected_hash:
                        errors.append(
                            f"Lockfile hash mismatch for '{k}': expected {expected_hash[:10]}..., got {lock_hash[:10]}..."
                        )

            # Ensure lockfile does not contain hashes for excluded skills
            for k in lock_data:
                if k.startswith("_") or k == "version":
                    continue
                parts = k.split("/")
                if len(parts) >= 2 and parts[0] == "skills" and parts[1] not in DOGFOOD_SET:
                    errors.append(f"Lockfile contains entry for uninstalled skill: {k}")

    return errors


def cmd_status(args, repo_root: Path) -> int:
    state = check_adoption_state(repo_root)
    if state == "not_adopted":
        if args.json:
            print(json.dumps({"adopted": False, "status": "not adopted"}, indent=2))
        else:
            print("Status: not adopted (no lockfile or project profile)")
        return 0

    lock_file = repo_root / ".agents" / "build-forge.lock.json"
    if not lock_file.is_file():
        if args.json:
            print(json.dumps({"adopted": False, "status": "profile exists but lock file missing"}, indent=2))
        else:
            print("Status: profile exists but lock file is missing")
        return 1

    try:
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
    except Exception as e:
        if args.json:
            print(json.dumps({"error": f"Invalid lockfile: {e}"}, indent=2))
        else:
            print(f"Error reading lockfile: {e}")
        return 1

    installed = lock_data.get("_installed", [])
    version = lock_data.get("_version", "unknown")
    errors = check_dogfood(repo_root)

    if args.json:
        data = {
            "adopted": True,
            "version": version,
            "installed": installed,
            "dogfood_set": DOGFOOD_SET,
            "dogfood_excluded": DOGFOOD_EXCLUDED,
            "drift": len(errors) > 0,
            "differences": errors,
        }
        print(json.dumps(data, indent=2))
    else:
        print(f"Build Forge Dogfood Status:")
        print(f"  Version:   {version}")
        print(f"  Installed: {len(installed)} skills ({', '.join(sorted(installed))})")
        print(f"  Drift:     {'DRIFT DETECTED' if errors else 'IN SYNC'}")
        if errors:
            print("\nDifferences:")
            for err in errors:
                print(f"  - {err}")
    return 0 if not errors else 1


def cmd_check(args, repo_root: Path) -> int:
    state = check_adoption_state(repo_root)
    if state == "not_adopted":
        print("not adopted")
        return 0
    if state == "profile_no_lock":
        print("Error: .agents/project-profile.yaml exists but .agents/build-forge.lock.json is missing.", file=sys.stderr)
        print("run: python3 scripts/dev.py dogfood sync", file=sys.stderr)
        return 1

    errors = check_dogfood(repo_root)
    if errors:
        for err in errors:
            print(f"DOGFOOD DRIFT: {err}")
        print("run: python3 scripts/dev.py dogfood sync")
        return 1

    print("OK: Dogfood check passed. Installed skills match DOGFOOD_SET.")
    return 0


def cmd_sync(args, repo_root: Path) -> int:
    # 1. Must run from repository root
    cwd = Path.cwd().resolve()
    if cwd != repo_root.resolve():
        print(f"Error: dogfood sync must run from repo root ({repo_root}), but current directory is {cwd}", file=sys.stderr)
        return 1

    cli_path = repo_root / "bin" / "build-forge.js"
    if not cli_path.is_file():
        print(f"Error: CLI file not found at {cli_path}", file=sys.stderr)
        return 1

    # 2. Run install --force --no-gitignore
    cmd_install = ["node", str(cli_path), "install", "--force", "--no-gitignore"]
    res_inst = subprocess.run(cmd_install, cwd=str(repo_root), capture_output=True, text=True)
    if res_inst.returncode != 0:
        print(f"Error during install:\n{res_inst.stderr or res_inst.stdout}", file=sys.stderr)
        return 1

    # 3. Remove each excluded skill using the CLI remove command
    for excluded_skill in DOGFOOD_EXCLUDED:
        cmd_rm = ["node", str(cli_path), "remove", excluded_skill]
        res_rm = subprocess.run(cmd_rm, cwd=str(repo_root), capture_output=True, text=True)
        if res_rm.returncode != 0:
            print(f"Error during remove {excluded_skill}:\n{res_rm.stderr or res_rm.stdout}", file=sys.stderr)
            return 1

    # 4. Run check
    errors = check_dogfood(repo_root)
    if errors:
        for err in errors:
            print(f"DOGFOOD DRIFT after sync: {err}", file=sys.stderr)
        print("run: python3 scripts/dev.py dogfood sync", file=sys.stderr)
        return 1

    # 5. Print git status for .agents
    res_status = subprocess.run(
        ["git", "status", "--short", "--", ".agents"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if res_status.stdout:
        print(res_status.stdout, end="")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Build Forge Dogfood Tool")
    parser.add_argument("--root", type=str, default=None, help="Repository root path")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Show dogfood adoption and drift status")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")

    # check
    subparsers.add_parser("check", help="Check installed skills against source skills")

    # sync
    subparsers.add_parser("sync", help="Sync installed skills to match source skills")

    args = parser.parse_args()
    repo_root = get_repo_root(args.root)

    if args.subcommand == "status":
        sys.exit(cmd_status(args, repo_root))
    elif args.subcommand == "check":
        sys.exit(cmd_check(args, repo_root))
    elif args.subcommand == "sync":
        sys.exit(cmd_sync(args, repo_root))


if __name__ == "__main__":
    main()

