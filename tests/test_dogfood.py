#!/usr/bin/env python3
"""Tests for Build Forge dogfood tooling (scripts/dogfood.py)."""
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
DOGFOOD_SCRIPT = REPO_ROOT / "scripts" / "dogfood.py"
CLI_PATH = REPO_ROOT / "bin" / "build-forge.js"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import dogfood


class TestDogfood(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bf-test-dogfood-"))
        # Initialize minimal repo copy
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.tmp), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.tmp), check=True)

        # Copy essential files: bin, skills, integrity.json, package.json, scripts
        shutil.copytree(REPO_ROOT / "bin", self.tmp / "bin")
        shutil.copytree(REPO_ROOT / "skills", self.tmp / "skills", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        shutil.copytree(REPO_ROOT / "scripts", self.tmp / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        shutil.copyfile(REPO_ROOT / "package.json", self.tmp / "package.json")
        shutil.copyfile(REPO_ROOT / "integrity.json", self.tmp / "integrity.json")
        shutil.copyfile(REPO_ROOT / "tiers.json", self.tmp / "tiers.json")

        subprocess.run(["git", "add", "."], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(self.tmp), check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_dogfood(self, args: list, cwd: Path = None) -> subprocess.CompletedProcess:
        target_cwd = cwd or self.tmp
        cmd = [sys.executable, str(self.tmp / "scripts" / "dogfood.py")] + args
        return subprocess.run(cmd, cwd=str(target_cwd), capture_output=True, text=True)

    def test_01_not_adopted_when_no_lock_and_no_profile(self):
        """When neither lock nor profile exists, check prints 'not adopted' and exits 0."""
        res = self.run_dogfood(["check"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("not adopted", res.stdout)

        res_st = self.run_dogfood(["status"])
        self.assertEqual(res_st.returncode, 0)
        self.assertIn("not adopted", res_st.stdout)

    def test_02_profile_without_lock_exits_1(self):
        """When profile exists but lock does not, check exits 1."""
        agents_dir = self.tmp / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        (agents_dir / "project-profile.yaml").write_text("schema_version: 2\n", encoding="utf-8")

        res = self.run_dogfood(["check"])
        self.assertEqual(res.returncode, 1)
        self.assertIn("missing", res.stderr + res.stdout)

    def test_03_sync_refuses_outside_repo_root(self):
        """Sync refuses to run when current directory is not repo root."""
        sub_dir = self.tmp / "bin"
        res = self.run_dogfood(["sync"], cwd=sub_dir)
        self.assertEqual(res.returncode, 1)
        self.assertIn("must run from repo root", res.stderr + res.stdout)

    def test_04_sync_and_check_pass(self):
        """Sync installs DOGFOOD_SET skills and check passes."""
        res_sync = self.run_dogfood(["sync"])
        self.assertEqual(res_sync.returncode, 0, f"Sync failed:\n{res_sync.stderr}\n{res_sync.stdout}")

        # Verify disk installed set matches DOGFOOD_SET
        installed_disk = sorted([
            d.name for d in (self.tmp / ".agents" / "skills").iterdir()
            if d.is_dir() and d.name not in dogfood.IGNORED_NAMES
        ])
        self.assertEqual(installed_disk, sorted(dogfood.DOGFOOD_SET))

        # Verify lock matches DOGFOOD_SET
        lock_data = json.loads((self.tmp / ".agents" / "build-forge.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(lock_data["_installed"]), sorted(dogfood.DOGFOOD_SET))

        # Check passes
        res_check = self.run_dogfood(["check"])
        self.assertEqual(res_check.returncode, 0, f"Check failed:\n{res_check.stderr}\n{res_check.stdout}")
        self.assertIn("Dogfood check passed", res_check.stdout)

    def test_05_check_never_writes(self):
        """Check is strictly read-only and never modifies files."""
        # First sync to populate .agents
        self.run_dogfood(["sync"])

        # Capture snapshot
        before_state = {}
        for r, _, files in os.walk(self.tmp):
            for f in files:
                p = Path(r) / f
                before_state[str(p)] = (p.stat().st_mtime, p.read_bytes())

        # Run check
        res = self.run_dogfood(["check"])
        self.assertEqual(res.returncode, 0)

        # Compare snapshot
        after_state = {}
        for r, _, files in os.walk(self.tmp):
            for f in files:
                p = Path(r) / f
                after_state[str(p)] = (p.stat().st_mtime, p.read_bytes())

        self.assertEqual(set(before_state.keys()), set(after_state.keys()))
        for k in before_state:
            self.assertEqual(before_state[k][1], after_state[k][1], f"File content changed: {k}")

    def test_06_check_fails_when_installed_file_edited(self):
        """Editing an installed skill file causes check to fail."""
        self.run_dogfood(["sync"])
        target_file = self.tmp / ".agents" / "skills" / "atomic-commits" / "SKILL.md"
        target_file.write_text(target_file.read_text(encoding="utf-8") + "\n# Modified\n", encoding="utf-8")

        res = self.run_dogfood(["check"])
        self.assertEqual(res.returncode, 1)
        self.assertIn("File content differs", res.stdout)
        self.assertIn("run: python3 scripts/dev.py dogfood sync", res.stdout)

    def test_07_check_fails_when_installed_file_deleted(self):
        """Deleting an installed file causes check to fail."""
        self.run_dogfood(["sync"])
        target_file = self.tmp / ".agents" / "skills" / "atomic-commits" / "scripts" / "suggest_scope.py"
        target_file.unlink()

        res = self.run_dogfood(["check"])
        self.assertEqual(res.returncode, 1)
        self.assertIn("Missing file in installed skill", res.stdout)

    def test_08_check_fails_when_installed_file_added(self):
        """Adding an untracked extra file inside an installed skill causes check to fail."""
        self.run_dogfood(["sync"])
        target_file = self.tmp / ".agents" / "skills" / "atomic-commits" / "extra_file.txt"
        target_file.write_text("extra", encoding="utf-8")

        res = self.run_dogfood(["check"])
        self.assertEqual(res.returncode, 1)
        self.assertIn("Extra file in installed skill", res.stdout)

    def test_09_check_fails_when_source_skill_edited_until_sync(self):
        """Editing a source skill causes check to fail until sync is run."""
        self.run_dogfood(["sync"])
        src_file = self.tmp / "skills" / "atomic-commits" / "SKILL.md"
        src_file.write_text(src_file.read_text(encoding="utf-8") + "\n# New source line\n", encoding="utf-8")

        res_before = self.run_dogfood(["check"])
        self.assertEqual(res_before.returncode, 1)
        self.assertIn("File content differs", res_before.stdout)

        # After sync, check passes
        res_sync = self.run_dogfood(["sync"])
        self.assertEqual(res_sync.returncode, 0)
        res_after = self.run_dogfood(["check"])
        self.assertEqual(res_after.returncode, 0)

    def test_10_crlf_differences_pass(self):
        """CRLF vs LF line ending differences are tolerated."""
        self.run_dogfood(["sync"])
        target_file = self.tmp / ".agents" / "skills" / "atomic-commits" / "SKILL.md"
        content = target_file.read_bytes().replace(b"\n", b"\r\n")
        target_file.write_bytes(content)

        res = self.run_dogfood(["check"])
        self.assertEqual(res.returncode, 0, f"Check failed on CRLF normalization:\n{res.stdout}\n{res.stderr}")

    def test_11_check_fails_when_new_skill_not_in_sets(self):
        """A new skill directory in skills/ that is in neither set fails check with specific message."""
        self.run_dogfood(["sync"])
        new_skill = self.tmp / "skills" / "brand-new-skill"
        new_skill.mkdir(parents=True)
        (new_skill / "SKILL.md").write_text("name: brand-new-skill\n", encoding="utf-8")

        res = self.run_dogfood(["check"])
        self.assertEqual(res.returncode, 1)
        self.assertIn("new skill brand-new-skill: add it to DOGFOOD_SET or DOGFOOD_EXCLUDED in scripts/dogfood.py", res.stdout)

    def test_12_check_fails_when_constant_name_missing_from_skills(self):
        """When a skill listed in DOGFOOD_SET does not exist in skills/, check fails."""
        self.run_dogfood(["sync"])
        shutil.rmtree(self.tmp / "skills" / "repo-search")

        res = self.run_dogfood(["check"])
        self.assertEqual(res.returncode, 1)
        self.assertIn("does not exist in skills/", res.stdout)

    def test_13_status_text_and_json(self):
        """Status prints human readable summary and JSON format."""
        self.run_dogfood(["sync"])

        res_text = self.run_dogfood(["status"])
        self.assertEqual(res_text.returncode, 0)
        self.assertIn("Build Forge Dogfood Status:", res_text.stdout)
        self.assertIn("IN SYNC", res_text.stdout)

        res_json = self.run_dogfood(["status", "--json"])
        self.assertEqual(res_json.returncode, 0)
        data = json.loads(res_json.stdout)
        self.assertTrue(data["adopted"])
        self.assertFalse(data["drift"])
        self.assertEqual(sorted(data["installed"]), sorted(dogfood.DOGFOOD_SET))

    def test_14_windows_paths(self):
        """Lock file keys with POSIX slashes work regardless of platform."""
        self.run_dogfood(["sync"])
        lock_file = self.tmp / ".agents" / "build-forge.lock.json"
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
        for k in lock_data:
            if not k.startswith("_") and k != "version":
                self.assertNotIn("\\", k, f"Found Windows backslash in lock key: {k}")


if __name__ == "__main__":
    unittest.main()

