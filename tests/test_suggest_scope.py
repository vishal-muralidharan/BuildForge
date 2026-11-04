#!/usr/bin/env python3
"""Tests for suggest_scope.py.

Covers:
1. Known files matching scope paths.
2. Staged files with --staged.
3. No match fallback to alphabetical list with purposes.
4. Deterministic tie breaking.
5. Windows path normalization.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SUGGEST_SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "atomic-commits" / "scripts" / "suggest_scope.py"


class TestSuggestScope(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)

        # Base profile with diverse scopes
        self.profile_path = self.root / ".agents" / "project-profile.yaml"
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_content = """schema_version: 1
project:
  name: test-app
  summary: test app
  mode: existing
git:
  commit_format: "<type>(<scope>): <subject>"
  scopes:
    - name: ui
      purpose: UI components and styling
      paths:
        - src/components/**
        - src/styles/**
    - name: api
      purpose: Backend API routes
      paths:
        - src/api/**
        - server/**
    - name: data
      purpose: Database and storage models
      paths:
        - src/models/**
        - src/schema/**
    - name: docs
      purpose: Documentation updates
      paths:
        - docs/**
        - "*.md"
    - misc
"""
        self.profile_path.write_text(self.profile_content, encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def run_suggest(self, args, cwd=None):
        cmd = [sys.executable, str(SUGGEST_SCRIPT), "--profile", str(self.profile_path)] + args
        res = subprocess.run(cmd, cwd=cwd or self.root, capture_output=True, text=True)
        return res

    def test_known_files_matching(self):
        res = self.run_suggest(["--files", "src/components/Button.jsx", "src/styles/theme.css"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Suggested scopes:", res.stdout)
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        self.assertTrue(any(line.startswith("ui - UI components") for line in lines))
        # Ensure only top matches appear
        self.assertNotIn("api -", res.stdout)

    def test_staged_files(self):
        # Initialize a temporary git repo
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)

        api_file = self.root / "src" / "api" / "users.js"
        api_file.parent.mkdir(parents=True, exist_ok=True)
        api_file.write_text("export const users = [];", encoding="utf-8")

        subprocess.run(["git", "add", "src/api/users.js"], cwd=self.root, check=True)

        res = self.run_suggest(["--staged", "--root", str(self.root)])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Suggested scopes:", res.stdout)
        self.assertIn("api - Backend API routes", res.stdout)

    def test_no_match_fallback(self):
        res = self.run_suggest(["--files", "unmatched_file.xyz", "unknown/folder/file.bin"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("No specific scope matched. Available scopes:", res.stdout)
        # Check that all scopes are listed alphabetically
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip().startswith(("api", "data", "docs", "misc", "ui"))]
        self.assertEqual(len(lines), 5)
        names = [l.split()[0] for l in lines]
        self.assertEqual(names, sorted(names))
        # Scope with no purpose is listed cleanly
        self.assertTrue(any(l == "misc" for l in lines))

    def test_tie_breaking(self):
        # Both ui and docs match 1 file each
        res = self.run_suggest(["--files", "src/components/Card.jsx", "README.md"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Suggested scopes:", res.stdout)
        lines = [l.strip() for l in res.stdout.splitlines() if " - " in l]
        # In case of tie, alphabetical order (docs before ui)
        names = [l.split()[0] for l in lines]
        self.assertEqual(names[:2], ["docs", "ui"])

    def test_windows_paths(self):
        # Pass Windows-style backslashes
        win_path = "src\\components\\modal\\Dialog.jsx"
        res = self.run_suggest(["--files", win_path])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Suggested scopes:", res.stdout)
        self.assertIn("ui - UI components and styling", res.stdout)


if __name__ == "__main__":
    unittest.main()
