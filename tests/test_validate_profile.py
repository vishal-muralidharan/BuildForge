#!/usr/bin/env python3
"""Negative and schema tests for validate_profile.py git.scopes."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
VAL_PY = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "validate_profile.py"

BASE_PROFILE = """schema_version: 1
project:
  name: demo
  summary: demo application
  mode: new
  platforms: [web]
stack:
  language: javascript
  framework: vanilla
  package_manager: npm
commands:
  check: npm test
structure:
  layers:
    - path: src
      purpose: src
  tests: tests-dir
docs:
  skills_dir: .agents/skills
  agents_file: AGENTS.md
  repo_map: .agents/repo-map.md
git:
  commit_format: '<type>: <subject>'
  push: never
"""


class TestValidateProfileScopes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bf-test-val-")
        self.profile = Path(self.tmp) / "profile.yaml"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_val(self, content: str):
        self.profile.write_text(content, encoding="utf-8")
        return subprocess.run([sys.executable, str(VAL_PY), "--profile", str(self.profile)], capture_output=True, text=True)

    def test_valid_mixed_scopes_pass(self):
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - simple-scope\n"
            "    - name: ui\n"
            "      purpose: UI components and styles\n"
            "      paths:\n"
            "        - src/ui/**\n"
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("0 error(s)", res.stdout)

    def test_negative_duplicate_names_fail(self):
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - ui\n"
            "    - name: ui\n"
            "      purpose: Duplicate ui scope\n"
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 1)
        self.assertIn("duplicate scope name: ui", res.stdout)

    def test_negative_long_purpose_fails(self):
        long_purpose = "A" * 105
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - name: ui\n"
            f"      purpose: {long_purpose}\n"
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 1)
        self.assertIn("exceeds 100 characters", res.stdout)

    def test_negative_bad_glob_fails(self):
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - name: ui\n"
            "      paths:\n"
            '        - "src/[invalid"\n'
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 1)
        self.assertIn("is not a valid glob", res.stdout)

    def test_negative_non_string_name_fails(self):
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - name: 12345\n"
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 1)
        self.assertIn("git.scopes[0].name must be a non-empty string", res.stdout)


def run_all_validation_scope_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestValidateProfileScopes)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_all_validation_scope_tests()

