#!/usr/bin/env python3
"""Tests for Bug B4: update prunes removed upstream files without deleting user additions."""
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


def hash_content(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


class TestPruneObsoleteB4(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bf-test-b4-"))
        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.tmp), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.tmp), check=True)

        # Install skills
        subprocess.run(["node", str(CLI_PATH), "install"], cwd=str(self.tmp), capture_output=True, check=True)

        # Setup obsolete files in project-bootstrap
        pb_dir = self.tmp / ".agents" / "skills" / "project-bootstrap"
        lock_file = self.tmp / ".agents" / "build-forge.lock.json"
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))

        # 1. Clean removed file in subfolder (references/example-nemo.project-profile.yaml)
        clean_obsolete = pb_dir / "references" / "example-nemo.project-profile.yaml"
        clean_obsolete_content = "schema_version: 1\n# Old nemo example\n"
        clean_obsolete.write_text(clean_obsolete_content, encoding="utf-8")
        lock_data["skills/project-bootstrap/references/example-nemo.project-profile.yaml"] = hash_content(clean_obsolete_content)

        # 2. Obsolete file in a dedicated empty subfolder (subfolder should be deleted when file is pruned)
        obsolete_subdir = pb_dir / "obsolete-subfolder"
        obsolete_subdir.mkdir(parents=True, exist_ok=True)
        obsolete_subfile = obsolete_subdir / "deprecated.txt"
        obsolete_subfile_content = "deprecated content\n"
        obsolete_subfile.write_text(obsolete_subfile_content, encoding="utf-8")
        lock_data["skills/project-bootstrap/obsolete-subfolder/deprecated.txt"] = hash_content(obsolete_subfile_content)

        # 3. Modified removed file (was in lock, but user modified it)
        mod_obsolete = pb_dir / "references" / "obsolete-modified.md"
        mod_obsolete_orig = "# Old Spec\nOriginal content.\n"
        mod_obsolete_user = "# Old Spec\nUser modified content.\n"
        mod_obsolete.write_text(mod_obsolete_user, encoding="utf-8")
        lock_data["skills/project-bootstrap/references/obsolete-modified.md"] = hash_content(mod_obsolete_orig)

        # 4. User-added file (never in lock)
        user_file = pb_dir / "references" / "my-custom-notes.md"
        user_file.write_text("# My Custom Notes\n", encoding="utf-8")

        lock_file.write_text(json.dumps(lock_data, indent=2) + "\n", encoding="utf-8")

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=str(self.tmp), check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit with obsolete files"], cwd=str(self.tmp), check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_update_prunes_removed_upstream_files(self):
        """Update prunes clean removed files, keeps modified with warning/patch, keeps user additions, cleans empty dirs."""
        pb_dir = self.tmp / ".agents" / "skills" / "project-bootstrap"
        clean_obsolete = pb_dir / "references" / "example-nemo.project-profile.yaml"
        obsolete_subdir = pb_dir / "obsolete-subfolder"
        obsolete_subfile = obsolete_subdir / "deprecated.txt"
        mod_obsolete = pb_dir / "references" / "obsolete-modified.md"
        user_file = pb_dir / "references" / "my-custom-notes.md"

        # Run update --restore project-bootstrap (or plain update)
        res_u = subprocess.run(
            ["node", str(CLI_PATH), "update", "--restore", "project-bootstrap"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True
        )
        self.assertEqual(res_u.returncode, 0, f"Update failed:\n{res_u.stdout}\n{res_u.stderr}")

        # 1. Clean obsolete files are pruned
        self.assertFalse(clean_obsolete.exists(), "Clean obsolete file was not pruned")
        self.assertFalse(obsolete_subfile.exists(), "Obsolete file in subfolder was not pruned")

        # 2. Empty directory was cleaned up
        self.assertFalse(obsolete_subdir.exists(), "Empty subfolder was not cleaned up")

        # 3. Modified removed file is kept on disk and backup/patch saved to .agents/work/
        self.assertTrue(mod_obsolete.is_file(), "Modified obsolete file was deleted")
        self.assertIn("warning", res_u.stderr.lower() + res_u.stdout.lower())

        work_dir = self.tmp / ".agents" / "work"
        work_files = list(work_dir.glob("*")) if work_dir.exists() else []
        self.assertTrue(any("obsolete-modified" in f.name for f in work_files), f"No backup/patch found in {work_files}")

        # 4. User-added file is kept
        self.assertTrue(user_file.is_file(), "User-added file was deleted")

        # 5. Lock file no longer contains the pruned clean files
        lock_data = json.loads((self.tmp / ".agents" / "build-forge.lock.json").read_text(encoding="utf-8"))
        self.assertNotIn("skills/project-bootstrap/references/example-nemo.project-profile.yaml", lock_data)
        self.assertNotIn("skills/project-bootstrap/obsolete-subfolder/deprecated.txt", lock_data)


if __name__ == "__main__":
    unittest.main()
