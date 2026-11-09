#!/usr/bin/env python3
"""Tests for Bug B5: doctor and verify must agree across clean, missing, modified, and extra states."""
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


class TestDoctorAndVerifyAgreeB5(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bf-test-b5-"))
        # Initialize git repo with main branch
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.tmp), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.tmp), check=True)

        # Install skills
        subprocess.run(["node", str(CLI_PATH), "install"], cwd=str(self.tmp), capture_output=True, check=True)

        # AGENTS.md, src, docs, and valid profile
        (self.tmp / "AGENTS.md").write_text("# Agent Guidelines\n", encoding="utf-8")
        (self.tmp / "src").mkdir(parents=True, exist_ok=True)
        (self.tmp / "docs").mkdir(parents=True, exist_ok=True)
        (self.tmp / "docs" / "repo-map.md").write_text("# Repo Map\n", encoding="utf-8")
        profile = (
            "schema_version: 2\n"
            "project:\n"
            "  name: TestApp\n"
            "  summary: Test app\n"
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
        (self.tmp / ".agents" / "project-profile.yaml").write_text(profile, encoding="utf-8")
        subprocess.run(["node", str(CLI_PATH), "link", "--agents", "all"], cwd=str(self.tmp), capture_output=True, check=True)

        # Mark upgrade actions completed
        upgrade_notes = REPO_ROOT / "upgrade-notes.json"
        if upgrade_notes.is_file():
            unotes = json.loads(upgrade_notes.read_text(encoding="utf-8"))
            all_ids = [act["id"] for entry in unotes for act in entry.get("actions", [])]
            (self.tmp / ".agents" / "upgrade-state.json").write_text(
                json.dumps({"completed": all_ids}, indent=2) + "\n", encoding="utf-8"
            )

        subprocess.run(["git", "add", "."], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "commit", "-m", "Clean base"], cwd=str(self.tmp), check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_clean_state_both_pass(self):
        """Clean state: verify exits 0, doctor Lock file check is OK."""
        res_v = subprocess.run(["node", str(CLI_PATH), "verify"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_v.returncode, 0, f"verify failed: {res_v.stderr}")

        res_d = subprocess.run(["node", str(CLI_PATH), "doctor", "--json"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_d.returncode, 0, f"doctor failed: {res_d.stdout}\n{res_d.stderr}")
        doc = json.loads(res_d.stdout)
        lock_check = next(c for c in doc["checks"] if c["name"] == "Lock file")
        self.assertEqual(lock_check["status"], "OK")

    def test_02_missing_file_both_fail(self):
        """Missing file: verify exits 1 listing file as missing, doctor Lock file check is FAIL with missing."""
        target = self.tmp / ".agents" / "skills" / "atomic-commits" / "scripts" / "check_commit_message.py"
        target.unlink()

        res_v = subprocess.run(["node", str(CLI_PATH), "verify"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_v.returncode, 1)
        self.assertIn("missing", res_v.stderr + res_v.stdout)
        self.assertIn("check_commit_message.py", res_v.stderr + res_v.stdout)

        res_d = subprocess.run(["node", str(CLI_PATH), "doctor", "--json"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_d.returncode, 1)
        doc = json.loads(res_d.stdout)
        lock_check = next(c for c in doc["checks"] if c["name"] == "Lock file")
        self.assertEqual(lock_check["status"], "FAIL")
        self.assertIn("missing", lock_check["message"])

    def test_03_modified_file_both_fail(self):
        """Modified file: verify exits 1 listing file as modified, doctor Lock file check is FAIL with modified."""
        target = self.tmp / ".agents" / "skills" / "atomic-commits" / "SKILL.md"
        target.write_text(target.read_text(encoding="utf-8") + "\n# Modified\n", encoding="utf-8")

        res_v = subprocess.run(["node", str(CLI_PATH), "verify"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_v.returncode, 1)
        self.assertIn("modified", res_v.stderr + res_v.stdout)
        self.assertIn("atomic-commits/SKILL.md", res_v.stderr + res_v.stdout)

        res_d = subprocess.run(["node", str(CLI_PATH), "doctor", "--json"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_d.returncode, 1)
        doc = json.loads(res_d.stdout)
        lock_check = next(c for c in doc["checks"] if c["name"] == "Lock file")
        self.assertEqual(lock_check["status"], "FAIL")
        self.assertIn("modified", lock_check["message"])

    def test_04_extra_file_both_fail(self):
        """Extra file: verify exits 1 listing file as extra, doctor Lock file check is FAIL with extra."""
        target = self.tmp / ".agents" / "skills" / "atomic-commits" / "extra-file.txt"
        target.write_text("extra uncommitted file\n", encoding="utf-8")

        res_v = subprocess.run(["node", str(CLI_PATH), "verify"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_v.returncode, 1)
        self.assertIn("extra", res_v.stderr + res_v.stdout)
        self.assertIn("extra-file.txt", res_v.stderr + res_v.stdout)

        res_d = subprocess.run(["node", str(CLI_PATH), "doctor", "--json"], cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(res_d.returncode, 1)
        doc = json.loads(res_d.stdout)
        lock_check = next(c for c in doc["checks"] if c["name"] == "Lock file")
        self.assertEqual(lock_check["status"], "FAIL")
        self.assertIn("extra", lock_check["message"])


if __name__ == "__main__":
    unittest.main()
