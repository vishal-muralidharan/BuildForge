#!/usr/bin/env python3
"""Tests for doctor published root check (Bug B5)."""
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


class TestDoctorPublishedRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bf-test-pubroot-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_doctor(self):
        cmd = ["node", str(CLI_PATH), "doctor", "--json"]
        res = subprocess.run(cmd, cwd=str(self.tmp), capture_output=True, text=True)
        try:
            data = json.loads(res.stdout)
        except Exception as e:
            self.fail(f"doctor did not output valid JSON: {res.stdout}\n{res.stderr}\nError: {e}")
        chk = next((c for c in data.get("checks", []) if c.get("name") == "Published root"), None)
        return res, data, chk

    def test_static_site_fixture_with_root_index_html_and_no_build_script_warns(self):
        """A static site fixture with root index.html and no build script warns."""
        (self.tmp / "index.html").write_text("<!DOCTYPE html><html><body>Hello</body></html>\n", encoding="utf-8")
        (self.tmp / "package.json").write_text('{"name": "static-site", "scripts": {"test": "echo test"}}\n', encoding="utf-8")
        (self.tmp / "AGENTS.md").write_text("# Agents Guidelines\n", encoding="utf-8")
        agents_dir = self.tmp / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        (agents_dir / "project-profile.yaml").write_text("schema_version: 2\n", encoding="utf-8")

        res, data, chk = self.run_doctor()
        self.assertIsNotNone(chk, "Published root check not found in doctor output")
        self.assertEqual(chk["status"], "WARN", f"Expected WARN, got: {chk}")
        self.assertIn("The repo root may be published. Files such as .agents/ and AGENTS.md could become public.", chk["message"])
        self.assertIn("AGENTS.md", chk["message"])
        self.assertIn(".agents/project-profile.yaml", chk["message"])
        self.assertNotEqual(chk["status"], "FAIL")

    def test_vite_app_fixture_with_output_directory_dist_does_not_warn(self):
        """A Vite app fixture with outputDirectory dist does not warn (status OK)."""
        (self.tmp / "index.html").write_text("<!DOCTYPE html><html><body>App</body></html>\n", encoding="utf-8")
        (self.tmp / "package.json").write_text('{"name": "vite-app", "scripts": {"build": "vite build"}}\n', encoding="utf-8")
        (self.tmp / "vercel.json").write_text('{"outputDirectory": "dist"}\n', encoding="utf-8")
        (self.tmp / "AGENTS.md").write_text("# Agents Guidelines\n", encoding="utf-8")

        res, data, chk = self.run_doctor()
        self.assertIsNotNone(chk, "Published root check not found in doctor output")
        self.assertEqual(chk["status"], "OK", f"Expected OK, got: {chk}")

    def test_netlify_root_publish_warns(self):
        """Netlify toml with publish = '.' warns."""
        (self.tmp / "index.html").write_text("<!DOCTYPE html><html><body>Site</body></html>\n", encoding="utf-8")
        (self.tmp / "package.json").write_text('{"name": "my-site", "scripts": {"build": "build.sh"}}\n', encoding="utf-8")
        (self.tmp / "netlify.toml").write_text('[build]\npublish = "."\n', encoding="utf-8")
        (self.tmp / "AGENTS.md").write_text("# Agents Guidelines\n", encoding="utf-8")

        res, data, chk = self.run_doctor()
        self.assertIsNotNone(chk)
        self.assertEqual(chk["status"], "WARN")

    def test_no_index_html_is_ok(self):
        """When index.html is absent from root, status is OK."""
        (self.tmp / "AGENTS.md").write_text("# Agents Guidelines\n", encoding="utf-8")
        res, data, chk = self.run_doctor()
        self.assertIsNotNone(chk)
        self.assertEqual(chk["status"], "OK")


def run_all_published_root_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestDoctorPublishedRoot)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    return res.wasSuccessful()


if __name__ == "__main__":
    unittest.main()

