#!/usr/bin/env python3
"""Tests for CLI flags in bin/build-forge.js (--help, -h, --all)."""
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


class TestCLIFlags(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bf-test-cli-flags-"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_help_flag_prints_help_and_does_not_install(self):
        """node bin/build-forge.js --help prints help text and does not create .agents/skills."""
        res = subprocess.run(
            ["node", str(CLI_PATH), "--help"],
            cwd=str(self.temp_dir),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Build Forge CLI", res.stdout)
        self.assertIn("Usage: npx @v1006/build-forge <command>", res.stdout)
        self.assertFalse((self.temp_dir / ".agents" / "skills").exists())

    def test_short_help_flag_prints_help(self):
        """node bin/build-forge.js -h prints help text and does not create .agents/skills."""
        res = subprocess.run(
            ["node", str(CLI_PATH), "-h"],
            cwd=str(self.temp_dir),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Build Forge CLI", res.stdout)
        self.assertFalse((self.temp_dir / ".agents" / "skills").exists())

    def test_install_with_all_flag(self):
        """node bin/build-forge.js install --all successfully installs all skills."""
        # Initialize git in temp project so gitignore write doesn't fail
        subprocess.run(["git", "init"], cwd=str(self.temp_dir), capture_output=True)
        res = subprocess.run(
            ["node", str(CLI_PATH), "install", "--all"],
            cwd=str(self.temp_dir),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("installed in .agents/skills", res.stdout)
        self.assertTrue((self.temp_dir / ".agents" / "skills").is_dir())


if __name__ == "__main__":
    unittest.main()
