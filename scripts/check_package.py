#!/usr/bin/env python3
"""Permanent clean-room packaging check for Build Forge.

Verifies:
1. npm pack succeeds and extracts cleanly into a temp directory.
2. Every bin target declared in package.json exists in the tarball, and bin/ holds no stale/unreferenced files.
3. Every package root file statically read by bin/build-forge.js and skill scripts exists in the tarball.
4. The tarball holds no maintainers/, scripts/, tests/, fixtures/, or dotfiles.
5. Skills in the tarball match tiers.json, and integrity.json file keys match all skill files in the tarball.
6. The packed CLI successfully runs install, verify, doctor, and verify_integrity.py across 3 clean-room project shapes.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

FORBIDDEN_PREFIXES = ("maintainers/", "scripts/", "tests/", "fixtures/")


def scan_package_root_references(repo_root: Path) -> set:
    """Statically scan bin/build-forge.js and skills/ scripts for package root file accesses."""
    root_refs = set()

    # 1. Scan bin/build-forge.js
    cli_file = repo_root / "bin" / "build-forge.js"
    if cli_file.is_file():
        text = cli_file.read_text(encoding="utf-8", errors="ignore")
        # path.join(__dirname, '..', '<filename>')
        matches = re.findall(
            r"path\.join\(__dirname,\s*['\"]\.\.['\"],\s*['\"]([^'\"]+)['\"]\)", text
        )
        for m in matches:
            root_refs.add(m)

    # 2. Scan python scripts in skills/
    skills_dir = repo_root / "skills"
    if skills_dir.is_dir():
        for py_path in skills_dir.rglob("*.py"):
            text = py_path.read_text(encoding="utf-8", errors="ignore")
            # matches path traversal from scripts/ up 3 levels to package root
            matches = re.findall(
                r"parents\[3\]\s*/\s*['\"]([^'\"/]+)['\"]",
                text,
            )
            for m in matches:
                root_refs.add(m)

    return root_refs


def check_package(repo_root: Path) -> list:
    """Run comprehensive packaging checks and return list of (check_name, status, details)."""
    results = []
    temp_dirs_to_clean = []

    try:
        # Step 1: Pack tarball into a temp folder
        pack_temp = Path(tempfile.mkdtemp(prefix="bf-pack-check-"))
        temp_dirs_to_clean.append(pack_temp)

        pack_res = subprocess.run(
            ["npm", "pack", "--pack-destination", str(pack_temp)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if pack_res.returncode != 0:
            results.append((
                "npm pack",
                "FAIL",
                f"npm pack failed with exit {pack_res.returncode}: {pack_res.stderr.strip()}",
            ))
            return results
        results.append(("npm pack", "PASS", "Tarball created successfully"))

        # Find tgz file
        tgz_files = list(pack_temp.glob("*.tgz"))
        if not tgz_files:
            results.append(("tarball find", "FAIL", "No .tgz file found in output"))
            return results
        tarball_path = tgz_files[0]

        # Extract tarball
        extract_dir = pack_temp / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tarball_path, "r:gz") as tar:
            tar.extractall(path=extract_dir)

        pkg_dir = extract_dir / "package"
        if not pkg_dir.is_dir():
            results.append(("tarball structure", "FAIL", "Expected package/ root in tarball"))
            return results
        results.append(("tarball extract", "PASS", "Extracted package/ root"))

        # Step 2: Bin targets and stale bin files
        pkg_json_file = repo_root / "package.json"
        if not pkg_json_file.is_file():
            results.append(("package.json", "FAIL", "Missing package.json in root"))
            return results

        try:
            pkg_data = json.loads(pkg_json_file.read_text(encoding="utf-8"))
        except Exception as e:
            results.append(("package.json parse", "FAIL", f"Invalid JSON: {e}"))
            return results

        bin_decl = pkg_data.get("bin", {})
        bin_targets = {}
        if isinstance(bin_decl, str):
            bin_targets[pkg_data.get("name", "build-forge")] = bin_decl
        elif isinstance(bin_decl, dict):
            bin_targets = bin_decl

        # Assert every bin target exists in the tarball
        bin_fail = False
        for name, rel_target in bin_targets.items():
            norm_target = rel_target.replace("\\", "/").lstrip("/")
            target_path = pkg_dir / norm_target
            if not target_path.is_file():
                results.append((
                    "bin targets in tarball",
                    "FAIL",
                    f"Bin target '{rel_target}' for command '{name}' missing in tarball",
                ))
                bin_fail = True
                break
        if not bin_fail:
            results.append(("bin targets in tarball", "PASS", f"All {len(bin_targets)} target(s) present"))

        # Assert bin/ holds no stale file (in tarball and in source)
        stale_files = []
        target_norm_set = {v.replace("\\", "/").lstrip("/") for v in bin_targets.values()}

        # Check in tarball package/bin
        tarball_bin_dir = pkg_dir / "bin"
        if tarball_bin_dir.is_dir():
            for f in tarball_bin_dir.rglob("*"):
                if f.is_file():
                    rel_f = "bin/" + f.relative_to(tarball_bin_dir).as_posix()
                    if rel_f not in target_norm_set:
                        stale_files.append(f"tarball:{rel_f}")

        # Check in repo root/bin
        repo_bin_dir = repo_root / "bin"
        if repo_bin_dir.is_dir():
            for f in repo_bin_dir.rglob("*"):
                if f.is_file():
                    rel_f = "bin/" + f.relative_to(repo_bin_dir).as_posix()
                    if rel_f not in target_norm_set:
                        stale_files.append(f"repo:{rel_f}")

        if stale_files:
            results.append((
                "no stale bin files",
                "FAIL",
                f"Stale bin file(s) found not declared in package.json: {', '.join(sorted(stale_files))}",
            ))
        else:
            results.append(("no stale bin files", "PASS", "No stale files in bin/"))

        # Step 3: Statically scan bin/build-forge.js and skills/ scripts for package root files
        root_refs = scan_package_root_references(repo_root)
        missing_root_refs = []
        for ref_item in sorted(root_refs):
            ref_path = pkg_dir / ref_item
            if not ref_path.exists():
                missing_root_refs.append(ref_item)

        if missing_root_refs:
            results.append((
                "root files in tarball",
                "FAIL",
                f"Missing package root file(s) referenced in code: {', '.join(missing_root_refs)}",
            ))
        else:
            results.append((
                "root files in tarball",
                "PASS",
                f"All {len(root_refs)} referenced root item(s) present in tarball",
            ))

        # Step 4: Tarball holds no maintainers/, scripts/, tests/, fixtures/ or dotfiles
        forbidden_found = []
        for item in pkg_dir.rglob("*"):
            if item.is_file():
                rel_item = item.relative_to(pkg_dir).as_posix()
                # Check forbidden directory prefixes
                for prefix in FORBIDDEN_PREFIXES:
                    if rel_item.startswith(prefix):
                        forbidden_found.append(rel_item)
                        break
                # Check dotfiles anywhere in path
                for part in Path(rel_item).parts:
                    if part.startswith(".") and part != ".":
                        forbidden_found.append(rel_item)
                        break

        if forbidden_found:
            results.append((
                "forbidden files excluded",
                "FAIL",
                f"Forbidden file(s) found in tarball: {', '.join(sorted(forbidden_found)[:10])}",
            ))
        else:
            results.append(("forbidden files excluded", "PASS", "No maintainers, scripts, tests, fixtures, or dotfiles"))

        # Step 5: Tiers and integrity
        tiers_path = repo_root / "tiers.json"
        if not tiers_path.is_file():
            results.append(("tiers check", "FAIL", "Missing tiers.json"))
        else:
            try:
                tiers_data = json.loads(tiers_path.read_text(encoding="utf-8"))
                tiers_skills = set(
                    tiers_data.get("core", [])
                    + tiers_data.get("new-app", [])
                    + tiers_data.get("module", [])
                )
            except Exception as e:
                tiers_skills = set()
                results.append(("tiers check", "FAIL", f"Invalid tiers.json: {e}"))

            tarball_skills_dir = pkg_dir / "skills"
            tarball_skills = set()
            if tarball_skills_dir.is_dir():
                for d in tarball_skills_dir.iterdir():
                    if d.is_dir() and not d.name.startswith("."):
                        tarball_skills.add(d.name)

            if tiers_skills != tarball_skills:
                diff_missing = tiers_skills - tarball_skills
                diff_extra = tarball_skills - tiers_skills
                details = []
                if diff_missing:
                    details.append(f"missing from tarball: {diff_missing}")
                if diff_extra:
                    details.append(f"in tarball but not tiers: {diff_extra}")
                results.append(("tiers match skills", "FAIL", "; ".join(details)))
            else:
                results.append(("tiers match skills", "PASS", f"All {len(tiers_skills)} skills match tiers.json"))

        # Integrity check
        integrity_path = repo_root / "integrity.json"
        if not integrity_path.is_file():
            results.append(("integrity check", "FAIL", "Missing integrity.json"))
        else:
            try:
                integrity_data = json.loads(integrity_path.read_text(encoding="utf-8"))
                integrity_keys = set(integrity_data.keys())
            except Exception as e:
                integrity_keys = set()
                results.append(("integrity check", "FAIL", f"Invalid integrity.json: {e}"))

            tarball_skill_files = set()
            if tarball_skills_dir.is_dir():
                for f in tarball_skills_dir.rglob("*"):
                    if f.is_file():
                        rel_file = f.relative_to(pkg_dir).as_posix()
                        tarball_skill_files.add(rel_file)

            if integrity_keys != tarball_skill_files:
                missing_in_tarball = integrity_keys - tarball_skill_files
                missing_in_integrity = tarball_skill_files - integrity_keys
                details = []
                if missing_in_tarball:
                    details.append(f"in integrity but not tarball: {len(missing_in_tarball)}")
                if missing_in_integrity:
                    details.append(f"in tarball but not integrity: {len(missing_in_integrity)}")
                results.append(("integrity keys match skills", "FAIL", "; ".join(details)))
            else:
                results.append((
                    "integrity keys match skills",
                    "PASS",
                    f"All {len(integrity_keys)} files in skills/ match integrity.json keys",
                ))

        # Step 6: Clean-room CLI execution across 3 temp project shapes
        cli_entry = pkg_dir / "bin" / "build-forge.js"
        if not cli_entry.is_file():
            results.append(("packed CLI executable", "FAIL", "bin/build-forge.js not found in package"))
            return results

        project_shapes = {
            "empty": "Empty folder",
            "small_js": "Small JS app with package.json and 4 source files",
            "old_agents": "Folder with old AGENTS.md",
        }

        for shape_id, shape_desc in project_shapes.items():
            proj_dir = Path(tempfile.mkdtemp(prefix=f"bf-cleanroom-{shape_id}-"))
            temp_dirs_to_clean.append(proj_dir)

            # Shape-specific setup
            if shape_id == "small_js":
                (proj_dir / "package.json").write_text(
                    json.dumps({"name": "small-app", "version": "1.0.0"}, indent=2),
                    encoding="utf-8",
                )
                src_dir = proj_dir / "src"
                src_dir.mkdir(parents=True, exist_ok=True)
                for f_idx in range(4):
                    (src_dir / f"module_{f_idx}.js").write_text(
                        f"console.log('module {f_idx}');\n", encoding="utf-8"
                    )
            elif shape_id == "old_agents":
                (proj_dir / "AGENTS.md").write_text(
                    "# Existing AGENTS.md\nOriginal instructions\n", encoding="utf-8"
                )

            # Initialize git repository
            subprocess.run(["git", "init"], cwd=str(proj_dir), capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(proj_dir), capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(proj_dir), capture_output=True)
            subprocess.run(["git", "add", "."], cwd=str(proj_dir), capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(proj_dir), capture_output=True)

            # 1. install
            r_install = subprocess.run(
                ["node", str(cli_entry), "install"],
                cwd=str(proj_dir),
                capture_output=True,
                text=True,
            )
            if r_install.returncode != 0:
                results.append((
                    f"project [{shape_id}] CLI install",
                    "FAIL",
                    f"exit {r_install.returncode}: {r_install.stderr.strip() or r_install.stdout.strip()}",
                ))
            else:
                results.append((f"project [{shape_id}] CLI install", "PASS", "exit 0"))

            # 2. verify
            r_verify = subprocess.run(
                ["node", str(cli_entry), "verify"],
                cwd=str(proj_dir),
                capture_output=True,
                text=True,
            )
            if r_verify.returncode != 0:
                results.append((
                    f"project [{shape_id}] CLI verify",
                    "FAIL",
                    f"exit {r_verify.returncode}: {r_verify.stderr.strip() or r_verify.stdout.strip()}",
                ))
            else:
                results.append((f"project [{shape_id}] CLI verify", "PASS", "exit 0"))

            # 3. doctor
            r_doctor = subprocess.run(
                ["node", str(cli_entry), "doctor"],
                cwd=str(proj_dir),
                capture_output=True,
                text=True,
            )
            if r_doctor.returncode != 0:
                results.append((
                    f"project [{shape_id}] CLI doctor",
                    "FAIL",
                    f"exit {r_doctor.returncode}: {r_doctor.stderr.strip() or r_doctor.stdout.strip()}",
                ))
            else:
                results.append((f"project [{shape_id}] CLI doctor", "PASS", "exit 0"))

            # 4. offline verifier
            offline_verifier = (
                proj_dir
                / ".agents"
                / "skills"
                / "project-bootstrap"
                / "scripts"
                / "verify_integrity.py"
            )
            if not offline_verifier.is_file():
                results.append((
                    f"project [{shape_id}] offline verifier",
                    "FAIL",
                    f"Offline verifier script not found at {offline_verifier}",
                ))
            else:
                r_offline = subprocess.run(
                    [sys.executable, str(offline_verifier), "--root", "."],
                    cwd=str(proj_dir),
                    capture_output=True,
                    text=True,
                )
                if r_offline.returncode != 0:
                    results.append((
                        f"project [{shape_id}] offline verifier",
                        "FAIL",
                        f"exit {r_offline.returncode}: {r_offline.stderr.strip() or r_offline.stdout.strip()}",
                    ))
                else:
                    results.append((f"project [{shape_id}] offline verifier", "PASS", "exit 0"))

    finally:
        for p in temp_dirs_to_clean:
            shutil.rmtree(p, ignore_errors=True)

    return results


def main():
    parser = argparse.ArgumentParser(description="Clean-room package verification for Build Forge.")
    parser.add_argument("--root", default=None, help="Root directory of Build Forge repository")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent

    print(f"Running clean-room packaging checks on {repo_root}...\n")
    results = check_package(repo_root)

    header = f"{'Check':<36} {'Status':<10} {'Details'}"
    print(header)
    print("-" * 80)
    has_failure = False
    for name, status, details in results:
        if status != "PASS":
            has_failure = True
        status_str = f"[{status}]"
        print(f"{name:<36} {status_str:<10} {details}")

    print("-" * 80)
    if has_failure:
        print("\nClean-room package check: FAILED.")
        sys.exit(1)
    else:
        print("\nClean-room package check: PASSED.")
        sys.exit(0)


if __name__ == "__main__":
    main()
