#!/usr/bin/env python3
"""Tests for check_package.py permanent packaging verifier."""
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
CHECK_PACKAGE_SCRIPT = REPO_ROOT / "scripts" / "check_package.py"

IGNORE_PATTERNS = shutil.ignore_patterns(
    "node_modules", ".git", ".next", ".venv", "venv", "__pycache__", "dist", "*.pyc", ".DS_Store"
)


class TestCheckPackage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bf-test-check-pkg-"))
        # Copy repo to temp folder
        self.copy_root = self.temp_dir / "repo"
        shutil.copytree(str(REPO_ROOT), str(self.copy_root), ignore=IGNORE_PATTERNS)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clean_copy_passes(self):
        """A clean copy of the repository passes all packaging checks."""
        res = subprocess.run(
            [sys.executable, str(CHECK_PACKAGE_SCRIPT), "--root", str(self.copy_root)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"Expected clean copy to pass, but failed:\n{res.stdout}\n{res.stderr}",
        )
        self.assertIn("Clean-room package check: PASSED.", res.stdout)

    def test_omits_integrity_json_fails(self):
        """A package whose files list omits integrity.json fails and names the file."""
        pkg_json_path = self.copy_root / "package.json"
        data = json.loads(pkg_json_path.read_text(encoding="utf-8"))
        if "integrity.json" in data.get("files", []):
            data["files"].remove("integrity.json")
        pkg_json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        res = subprocess.run(
            [sys.executable, str(CHECK_PACKAGE_SCRIPT), "--root", str(self.copy_root)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        output = res.stdout + res.stderr
        self.assertIn("integrity.json", output)

    def test_stale_bin_file_fails(self):
        """A stale bin file present in bin/ causes check_package to fail and identify it."""
        stale_bin = self.copy_root / "bin" / "stale_script.js"
        stale_bin.write_text("console.log('stale');\n", encoding="utf-8")

        res = subprocess.run(
            [sys.executable, str(CHECK_PACKAGE_SCRIPT), "--root", str(self.copy_root)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        output = res.stdout + res.stderr
        self.assertTrue(
            "stale_script.js" in output or "stale bin file" in output.lower(),
            f"Expected stale bin failure in output:\n{output}",
        )

    def test_skill_missing_from_tiers_fails(self):
        """A skill missing from tiers.json causes check_package to fail and name the missing skill."""
        tiers_path = self.copy_root / "tiers.json"
        data = json.loads(tiers_path.read_text(encoding="utf-8"))
        removed_skill = None
        for tier in ("core", "new-app", "module"):
            if data.get(tier):
                removed_skill = data[tier].pop(0)
                break

        tiers_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        res = subprocess.run(
            [sys.executable, str(CHECK_PACKAGE_SCRIPT), "--root", str(self.copy_root)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        output = res.stdout + res.stderr
        self.assertIn(removed_skill, output)


if __name__ == "__main__":
    unittest.main()

