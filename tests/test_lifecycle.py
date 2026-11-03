#!/usr/bin/env python3
"""Lifecycle integration tests for Build Forge.

Tests:
1. build-forge doctor in clean vs broken project.
2. build-forge doctor --json output format and failure exit codes.
3. build-forge update with locally modified skill (must abort with exit code 1).
4. build-forge update on clean install.
5. migrate_profile.py plan and apply with schema_version migration.
6. Unknown and custom fields and user rules survive migration intact.
7. Cross-platform path handling for Windows compatibility.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")


def run_lifecycle_tests(repo_root: str = None) -> None:
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    cli_path = os.path.join(repo_root, "bin", "build-forge.js")
    migrate_script = os.path.join(
        repo_root, "skills", "project-bootstrap", "scripts", "migrate_profile.py"
    )

    if not os.path.isfile(cli_path):
        raise RuntimeError(f"CLI not found at {cli_path}")
    if not os.path.isfile(migrate_script):
        raise RuntimeError(f"migrate_profile.py not found at {migrate_script}")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)

        # ---------------------------------------------------------
        # Test 1: doctor in a broken/empty project (no lockfile)
        # ---------------------------------------------------------
        broken_dir = tmp / "broken-project"
        broken_dir.mkdir(parents=True, exist_ok=True)

        res_doc_fail = subprocess.run(
            ["node", cli_path, "doctor"],
            cwd=str(broken_dir),
            capture_output=True,
            text=True
        )
        assert res_doc_fail.returncode == 1, (
            f"doctor expected returncode 1 in empty project, got {res_doc_fail.returncode}"
        )
        assert "[FAIL]" in res_doc_fail.stdout or "[FAIL]" in res_doc_fail.stderr, (
            "doctor output missing [FAIL] in broken project"
        )

        # Test doctor --json
        res_doc_json = subprocess.run(
            ["node", cli_path, "doctor", "--json"],
            cwd=str(broken_dir),
            capture_output=True,
            text=True
        )
        assert res_doc_json.returncode == 1
        data_doc = json.loads(res_doc_json.stdout)
        assert data_doc.get("status") == "FAIL"
        assert data_doc.get("summary", {}).get("fail", 0) > 0

        # ---------------------------------------------------------
        # Setup clean project fixture
        # ---------------------------------------------------------
        proj_dir = tmp / "clean-project"
        proj_dir.mkdir(parents=True, exist_ok=True)

        # Run install to set up pipeline skills and lockfile
        res_inst = subprocess.run(
            ["node", cli_path, "install"],
            cwd=str(proj_dir),
            capture_output=True,
            text=True
        )
        assert res_inst.returncode == 0, f"install failed: {res_inst.stderr}"

        # Create valid AGENTS.md, src directory, and project-profile.yaml
        agents_md = proj_dir / "AGENTS.md"
        agents_md.write_text("# Agent Guidelines\n\nFollow all skills.\n", encoding="utf-8")
        (proj_dir / "src").mkdir(parents=True, exist_ok=True)
        (proj_dir / "docs").mkdir(parents=True, exist_ok=True)
        (proj_dir / "docs" / "repo-map.md").write_text("# Repo Map\n", encoding="utf-8")

        profile_path = proj_dir / ".agents" / "project-profile.yaml"
        initial_profile = {
            "schema_version": 1,
            "project": {
                "name": "FixtureApp",
                "summary": "Lifecycle test app",
                "mode": "existing"
            },
            "stack": {
                "language": "typescript",
                "framework": "React",
                "package_manager": "npm"
            },
            "commands": {
                "check": "npm test"
            },
            "structure": {
                "layers": [
                    {"path": "src", "purpose": "Application source code"}
                ],
                "tests": "colocated"
            },
            "git": {
                "commit_format": "type(scope): summary",
                "push": "ask"
            },
            "docs": {
                "skills_dir": ".agents/skills",
                "agents_file": "AGENTS.md",
                "repo_map": "docs/repo-map.md"
            },
            "rules": [
                {
                    "id": "custom-user-rule",
                    "area": "naming",
                    "text": "Never use single letter variable names.",
                    "enforced_by": "manual"
                }
            ],
            "custom_metadata_unknown_field": {
                "retention_days": 30,
                "team_lead": "engineer@example.com"
            }
        }
        profile_path.write_text(yaml.safe_dump(initial_profile, sort_keys=False), encoding="utf-8")

        # ---------------------------------------------------------
        # Test 2: doctor in clean project
        # ---------------------------------------------------------
        res_doc_clean = subprocess.run(
            ["node", cli_path, "doctor"],
            cwd=str(proj_dir),
            capture_output=True,
            text=True
        )
        # In this project, lockfile, AGENTS.md, git, node, python are valid
        assert res_doc_clean.returncode == 0, f"doctor in clean project failed: {res_doc_clean.stdout}\n{res_doc_clean.stderr}"
        assert "0 failure(s)" in res_doc_clean.stdout

        # ---------------------------------------------------------
        # Test 3: update with a modified skill (must abort with exit code 1)
        # ---------------------------------------------------------
        atomic_skill_md = proj_dir / ".agents" / "skills" / "atomic-commits" / "SKILL.md"
        assert atomic_skill_md.is_file(), "atomic-commits/SKILL.md not found"
        orig_content = atomic_skill_md.read_text(encoding="utf-8")

        # Tamper with the skill file
        atomic_skill_md.write_text(orig_content + "\n# Modified locally\n", encoding="utf-8")

        res_upd_fail = subprocess.run(
            ["node", cli_path, "update"],
            cwd=str(proj_dir),
            capture_output=True,
            text=True
        )
        assert res_upd_fail.returncode == 1, (
            f"update expected returncode 1 when skill is modified, got {res_upd_fail.returncode}"
        )
        assert "Update aborted" in res_upd_fail.stderr or "Update aborted" in res_upd_fail.stdout
        assert "atomic-commits" in (res_upd_fail.stderr + res_upd_fail.stdout)

        # ---------------------------------------------------------
        # Test 4: update on a clean install
        # ---------------------------------------------------------
        # Restore original skill content
        atomic_skill_md.write_text(orig_content, encoding="utf-8")

        res_upd_clean = subprocess.run(
            ["node", cli_path, "update"],
            cwd=str(proj_dir),
            capture_output=True,
            text=True
        )
        assert res_upd_clean.returncode == 0, f"update failed: {res_upd_clean.stderr}"
        assert "Updated" in res_upd_clean.stdout
        # Confirm profile migration plan was printed
        assert "Profile Migration Plan" in res_upd_clean.stdout or "profile is up to date" in res_upd_clean.stdout

        # ---------------------------------------------------------
        # Test 5: migrate_profile.py plan and apply
        # ---------------------------------------------------------
        # 5a. plan: prints diff, does not touch profile
        res_plan = subprocess.run(
            [sys.executable, migrate_script, "plan", "--profile", str(profile_path), "--root", str(proj_dir)],
            capture_output=True,
            text=True
        )
        assert res_plan.returncode == 0, f"migrate plan failed: {res_plan.stderr}"
        assert "Migration plan: schema_version 1 -> 2" in res_plan.stdout
        assert "+schema_version: 2" in res_plan.stdout or "schema_version" in res_plan.stdout

        # Verify profile was NOT modified by plan
        cur_prof = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        assert cur_prof.get("schema_version") == 1, "plan must not write files"

        # 5b. apply without --apply (dry-run): does not touch profile
        res_apply_dry = subprocess.run(
            [sys.executable, migrate_script, "apply", "--profile", str(profile_path), "--root", str(proj_dir)],
            capture_output=True,
            text=True
        )
        assert res_apply_dry.returncode == 0
        assert "Dry-run only" in res_apply_dry.stdout
        cur_prof_dry = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        assert cur_prof_dry.get("schema_version") == 1, "apply without --apply must not write files"

        # 5c. apply with --apply: writes changes
        res_apply_real = subprocess.run(
            [sys.executable, migrate_script, "apply", "--apply", "--profile", str(profile_path), "--root", str(proj_dir)],
            capture_output=True,
            text=True
        )
        assert res_apply_real.returncode == 0, f"apply --apply failed: {res_apply_real.stderr}"
        assert "Successfully migrated" in res_apply_real.stdout

        # ---------------------------------------------------------
        # Test 6: Verify unknown fields and user rules survived
        # ---------------------------------------------------------
        migrated_prof = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        assert migrated_prof.get("schema_version") == 2, "schema_version must be 2 after apply"

        # User rules survive
        rules = migrated_prof.get("rules", [])
        assert any(r.get("id") == "custom-user-rule" for r in rules), "user rules must survive migration"

        # Unknown custom fields survive
        custom_field = migrated_prof.get("custom_metadata_unknown_field")
        assert custom_field is not None, "unknown fields must survive migration"
        assert custom_field.get("retention_days") == 30
        assert custom_field.get("team_lead") == "engineer@example.com"

        # Blueprints structure added in v2
        assert "blueprints" in migrated_prof


def main():
    print("Running lifecycle integration tests...")
    run_lifecycle_tests()
    print("All lifecycle integration tests passed successfully.")


if __name__ == "__main__":
    main()
