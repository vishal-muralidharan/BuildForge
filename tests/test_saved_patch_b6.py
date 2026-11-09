#!/usr/bin/env python3
"""Tests for Bug B6: Saved patch relative headers and skip unmodified upgrades."""
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


class TestSavedPatchB6(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bf-test-b6-"))
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.tmp), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.tmp), check=True)

        # Install skills
        subprocess.run(["node", str(CLI_PATH), "install"], cwd=str(self.tmp), capture_output=True, check=True)

        subprocess.run(["git", "add", "."], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "commit", "-m", "Initial install"], cwd=str(self.tmp), check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_saved_patch_format_and_trigger(self):
        """Saved patch headers must use relative paths, git apply --check must succeed, and plain upgrade saves 0 patches."""
        work_dir = self.tmp / ".agents" / "work"
        if work_dir.exists():
            shutil.rmtree(work_dir)

        # 1. Plain update where skills differ from package but user made no local edits (simulate 0.1.0 clean skill)
        # Modify the lockfile hash for atomic-commits to simulate an old version hash, but leave file unmodified
        lock_file = self.tmp / ".agents" / "build-forge.lock.json"
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
        skill_file = self.tmp / ".agents" / "skills" / "atomic-commits" / "SKILL.md"
        actual_hash = lock_data["skills/atomic-commits/SKILL.md"]

        # Run update --restore atomic-commits when actual file matches lock (no local modifications)
        res_plain = subprocess.run(
            ["node", str(CLI_PATH), "update", "--restore", "atomic-commits"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True
        )
        self.assertEqual(res_plain.returncode, 0, f"Plain update failed:\n{res_plain.stdout}\n{res_plain.stderr}")
        # Plain upgrade of unmodified skill must create 0 patch files
        self.assertFalse(
            (work_dir / "overwritten-atomic-commits.patch").exists(),
            "Plain upgrade of unmodified skill should NOT create overwritten-atomic-commits.patch"
        )

        # 2. Upgrade of modified skill
        # Hand-edit atomic-commits
        content = skill_file.read_text(encoding="utf-8")
        edited = content + "\n## Local Custom Edit\nAlways add ticket ID.\n"
        skill_file.write_text(edited, encoding="utf-8")

        res_mod = subprocess.run(
            ["node", str(CLI_PATH), "update", "--restore", "atomic-commits"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True
        )
        self.assertEqual(res_mod.returncode, 0, f"Update with restore failed:\n{res_mod.stdout}\n{res_mod.stderr}")

        patch_file = work_dir / "overwritten-atomic-commits.patch"
        self.assertTrue(patch_file.is_file(), "overwritten-atomic-commits.patch was not created")

        patch_text = patch_file.read_text(encoding="utf-8")
        # Check header format
        self.assertIn("--- a/SKILL.md", patch_text)
        self.assertIn("+++ b/SKILL.md", patch_text)
        self.assertNotIn("/Users/", patch_text)
        self.assertNotIn("/tmp/", patch_text)
        self.assertIn("Local Custom Edit", patch_text)

        # git apply --check against a clean copy of the skill
        clean_skill_dir = REPO_ROOT / "skills" / "atomic-commits"
        res_apply = subprocess.run(
            ["git", "apply", "--check", str(patch_file.resolve())],
            cwd=str(clean_skill_dir),
            capture_output=True,
            text=True
        )
        self.assertEqual(res_apply.returncode, 0, f"git apply --check failed:\n{res_apply.stderr}")


if __name__ == "__main__":
    unittest.main()
