#!/usr/bin/env python3
"""Tests for Bug B2: Installed skills tracking in lock file and verification scoping."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "bin" / "build-forge.js"
VERIFY_SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "verify_integrity.py"
FIXTURE_BUILDER = REPO_ROOT / "tests" / "fixtures" / "create_old_install_fixture.py"

sys.path.insert(0, str(REPO_ROOT / "tests" / "fixtures"))
from create_old_install_fixture import generate_old_install_fixture


class TestInstalledSkillsB2(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bf-test-b2-"))
        # Initialize git repo with main branch
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.tmp), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.tmp), check=True)

        # 1. Install all skills first
        subprocess.run(["node", str(CLI_PATH), "install"], cwd=str(self.tmp), capture_output=True, check=True)

        # 2. Keep only core skills to simulate a core-only project
        tiers_data = json.loads((REPO_ROOT / "tiers.json").read_text(encoding="utf-8"))
        core_skills = set(tiers_data["core"])
        skills_dir = self.tmp / ".agents" / "skills"
        for s_dir in skills_dir.iterdir():
            if s_dir.is_dir() and s_dir.name not in core_skills:
                shutil.rmtree(s_dir)

        # 3. Write lockfile strictly for core skills
        lock_file = self.tmp / ".agents" / "build-forge.lock.json"
        integrity = json.loads((REPO_ROOT / "integrity.json").read_text(encoding="utf-8"))
        core_manifest = {}
        for skill in core_skills:
            for k, v in integrity.items():
                if k.startswith(f"skills/{skill}/"):
                    core_manifest[k] = v
        core_manifest["_version"] = "0.2.0"
        core_manifest["_installed"] = sorted(list(core_skills))
        lock_file.write_text(json.dumps(core_manifest, indent=2) + "\n", encoding="utf-8")

        # 4. Valid AGENTS.md, src, docs, and schema_version 2 profile
        (self.tmp / "AGENTS.md").write_text("# Agent Guidelines\n\nFollow all skills.\n", encoding="utf-8")
        (self.tmp / "src").mkdir(parents=True, exist_ok=True)
        (self.tmp / "docs").mkdir(parents=True, exist_ok=True)
        (self.tmp / "docs" / "repo-map.md").write_text("# Repo Map\n", encoding="utf-8")

        profile_content = (
            "schema_version: 2\n"
            "project:\n"
            "  name: CoreOnlyApp\n"
            "  summary: Core only test app\n"
            "  mode: existing\n"
            "stack:\n"
            "  language: typescript\n"
            "  framework: React\n"
            "  package_manager: npm\n"
            "commands:\n"
            "  check: npm test\n"
            "structure:\n"
            "  layers:\n"
            "    - path: src\n"
            "      purpose: Application source code\n"
            "  tests: colocated\n"
            "git:\n"
            "  commit_format: 'type(scope): summary'\n"
            "  push: ask\n"
            "docs:\n"
            "  skills_dir: .agents/skills\n"
            "  agents_file: AGENTS.md\n"
            "  repo_map: docs/repo-map.md\n"
            "blueprints: {}\n"
        )
        (self.tmp / ".agents" / "project-profile.yaml").write_text(profile_content, encoding="utf-8")

        # 5. Link agent pointers
        subprocess.run(["node", str(CLI_PATH), "link", "--agents", "all"], cwd=str(self.tmp), capture_output=True, check=True)

        # 6. Mark upgrade actions completed so doctor sees no pending actions
        upgrade_notes_file = REPO_ROOT / "upgrade-notes.json"
        if upgrade_notes_file.is_file():
            unotes = json.loads(upgrade_notes_file.read_text(encoding="utf-8"))
            all_action_ids = []
            for entry in unotes:
                for act in entry.get("actions", []):
                    all_action_ids.append(act["id"])
            (self.tmp / ".agents" / "upgrade-state.json").write_text(
                json.dumps({"completed": all_action_ids}, indent=2) + "\n", encoding="utf-8"
            )

        # Commit everything to keep git clean
        subprocess.run(["git", "add", "."], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "commit", "-m", "Initial clean commit"], cwd=str(self.tmp), check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_core_only_install_passes_verify_and_doctor(self):
        """A project without uninstalled optional skill passes verify and doctor."""
        res_v = subprocess.run(["node", str(CLI_PATH), "verify"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_v.returncode, 0, f"Verify failed:\n{res_v.stderr}\n{res_v.stdout}")

        res_py = subprocess.run([sys.executable, str(VERIFY_SCRIPT), "--root", str(self.tmp)], capture_output=True, text=True)
        self.assertEqual(res_py.returncode, 0, f"Python verify failed:\n{res_py.stderr}\n{res_py.stdout}")

        res_d = subprocess.run(["node", str(CLI_PATH), "doctor", "--json"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_d.returncode, 0, f"Doctor failed:\n{res_d.stdout}\n{res_d.stderr}")

    def test_02_add_extends_installed_list(self):
        """CLI add installs skill and adds it to _installed in the lock."""
        res_add = subprocess.run(["node", str(CLI_PATH), "add", "legal-and-settings-pages"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_add.returncode, 0, f"Add failed: {res_add.stderr}")

        lock = json.loads((self.tmp / ".agents" / "build-forge.lock.json").read_text(encoding="utf-8"))
        self.assertIn("_installed", lock)
        self.assertIn("legal-and-settings-pages", lock["_installed"])
        self.assertTrue((self.tmp / ".agents" / "skills" / "legal-and-settings-pages" / "SKILL.md").is_file())

    def test_03_remove_shrinks_installed_list(self):
        """CLI remove deletes skill from disk, from lock, and shrinks _installed."""
        # First ensure a skill is installed
        subprocess.run(["node", str(CLI_PATH), "add", "legal-and-settings-pages"], cwd=str(self.tmp), capture_output=True, text=True)
        res_rm = subprocess.run(["node", str(CLI_PATH), "remove", "legal-and-settings-pages"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_rm.returncode, 0, f"Remove failed: {res_rm.stderr}")

        lock = json.loads((self.tmp / ".agents" / "build-forge.lock.json").read_text(encoding="utf-8"))
        if "_installed" in lock:
            self.assertNotIn("legal-and-settings-pages", lock["_installed"])
        self.assertNotIn("skills/legal-and-settings-pages/SKILL.md", lock)
        self.assertFalse((self.tmp / ".agents" / "skills" / "legal-and-settings-pages").exists())

        # Removing uninstalled skill exits 1
        res_un = subprocess.run(["node", str(CLI_PATH), "remove", "legal-and-settings-pages"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_un.returncode, 1)

        # Removing core skill without --force exits 1
        res_core = subprocess.run(["node", str(CLI_PATH), "remove", "atomic-commits"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_core.returncode, 1)

        # Removing core skill with --force succeeds
        res_core_force = subprocess.run(["node", str(CLI_PATH), "remove", "atomic-commits", "--force"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_core_force.returncode, 0)
        self.assertFalse((self.tmp / ".agents" / "skills" / "atomic-commits").exists())

    def test_04_tampered_installed_skill_still_fails(self):
        """Tampering with an installed skill causes verify to fail."""
        atomic = self.tmp / ".agents" / "skills" / "atomic-commits" / "SKILL.md"
        atomic.write_text(atomic.read_text(encoding="utf-8") + "\n# Tampered line\n", encoding="utf-8")

        res_v = subprocess.run(["node", str(CLI_PATH), "verify"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertNotEqual(res_v.returncode, 0)
        self.assertIn("modified", res_v.stderr + res_v.stdout)

    def test_05_update_dry_run_needs_no_flags_for_uninstalled_skills(self):
        """update --dry-run on a core only project needs no flags for uninstalled skills."""
        res_u = subprocess.run(["node", str(CLI_PATH), "update", "--dry-run"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_u.returncode, 0, f"update --dry-run failed:\n{res_u.stdout}\n{res_u.stderr}")
        self.assertNotIn("Blocked by", res_u.stdout + res_u.stderr)
        self.assertNotIn("Unapproved local modifications", res_u.stdout + res_u.stderr)


if __name__ == "__main__":
    unittest.main()
