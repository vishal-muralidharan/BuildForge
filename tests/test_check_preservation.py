#!/usr/bin/env python3
"""Tests for check_preservation.py."""
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
SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "check_preservation.py"


def run_git(cwd: Path, args: list) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "author@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Committer"
    env["GIT_COMMITTER_EMAIL"] = "committer@example.com"
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )


class TestCheckPreservation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_preservation_")
        self.root = Path(self.tmpdir)
        run_git(self.root, ["init"])
        run_git(self.root, ["config", "user.name", "Test Committer"])
        run_git(self.root, ["config", "user.email", "committer@example.com"])
        run_git(self.root, ["config", "commit.gpgsign", "false"])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def run_check(self, base="HEAD~1", head="HEAD", extra_args=None):
        cmd = [sys.executable, "-B", str(SCRIPT), "--root", str(self.root), "--base", base, "--head", head]
        if extra_args:
            cmd.extend(extra_args)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(cmd, capture_output=True, text=True, env=env)

    def test_line_moved_into_custom_block_passes(self):
        agents = self.root / "AGENTS.md"
        agents.write_text(
            "# Rules\n\nAlways verify user tokens before routing any request.\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "AGENTS.md"])
        run_git(self.root, ["commit", "-m", "base commit"])

        # Head replaces file with generated template, but moves the rule into custom block
        agents.write_text(
            "<!-- Generated from .agents/project-profile.yaml by project-bootstrap. -->\n"
            "<!-- build-forge:generated v1 body=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef -->\n"
            "# Agent Guidelines for demo-app\n\n"
            "## Areas\n\n"
            "<!-- BEGIN CUSTOM: notes -->\n"
            "Always verify user tokens before routing any request.\n"
            "<!-- END CUSTOM: notes -->\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "AGENTS.md"])
        run_git(self.root, ["commit", "-m", "head commit"])

        res = self.run_check()
        self.assertEqual(res.returncode, 0, f"Expected 0 but got {res.returncode}: {res.stderr}\n{res.stdout}")
        self.assertIn("Preservation check passed", res.stdout)

    def test_line_moved_into_blueprint_passes(self):
        agents = self.root / "AGENTS.md"
        agents.write_text(
            "# Rules\n\nBilling endpoints require mutual TLS authentication.\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "AGENTS.md"])
        run_git(self.root, ["commit", "-m", "base commit"])

        # Head removes from AGENTS.md, but places into .agents/blueprints/auth.md
        agents.write_text(
            "<!-- build-forge:generated v1 body=abcdef -->\n# Agent Guidelines\n",
            encoding="utf-8",
        )
        bp_dir = self.root / ".agents" / "blueprints"
        bp_dir.mkdir(parents=True, exist_ok=True)
        (bp_dir / "auth.md").write_text(
            "# Auth Blueprint\n\nBilling endpoints require mutual TLS authentication.\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "."])
        run_git(self.root, ["commit", "-m", "head commit"])

        res = self.run_check()
        self.assertEqual(res.returncode, 0, f"Expected 0 but got {res.returncode}: {res.stderr}\n{res.stdout}")
        self.assertIn("Preservation check passed", res.stdout)

    def test_line_dropped_fails(self):
        agents = self.root / "AGENTS.md"
        agents.write_text(
            "# Rules\n\nSpecial constraint: never delete records directly from audit_logs table.\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "AGENTS.md"])
        run_git(self.root, ["commit", "-m", "base commit"])

        agents.write_text(
            "<!-- build-forge:generated v1 body=abcdef -->\n# Agent Guidelines\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "AGENTS.md"])
        run_git(self.root, ["commit", "-m", "head commit"])

        res = self.run_check()
        self.assertEqual(res.returncode, 1)
        self.assertIn("Preservation check failed: 1 line(s) missing", res.stdout)
        self.assertIn("Special constraint: never delete records directly from audit_logs table.", res.stdout)

    def test_pure_addition_passes(self):
        agents = self.root / "AGENTS.md"
        agents.write_text(
            "# Existing lines in AGENTS.md\n\nLine number one of documentation.\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "AGENTS.md"])
        run_git(self.root, ["commit", "-m", "base commit"])

        agents.write_text(
            "# Existing lines in AGENTS.md\n\nLine number one of documentation.\n\nNewly added instructions that expand guidelines.\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "AGENTS.md"])
        run_git(self.root, ["commit", "-m", "head commit"])

        res = self.run_check()
        self.assertEqual(res.returncode, 0, f"Expected 0 but got {res.returncode}: {res.stderr}\n{res.stdout}")
        self.assertIn("Preservation check passed", res.stdout)

    def test_table_row_or_fact_replaced_by_generated_table_reported_as_missing(self):
        agents = self.root / "AGENTS.md"
        agents.write_text(
            "# Rules\n\n"
            "| auth | JWT token validation and password reset |\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "AGENTS.md"])
        run_git(self.root, ["commit", "-m", "base commit"])

        agents.write_text(
            "<!-- build-forge:generated v1 body=abcdef -->\n"
            "# Generated Guidelines\n\n"
            "| Area | Skill |\n"
            "|---|---|\n"
            "| ui | .agents/skills/build-ui/SKILL.md |\n",
            encoding="utf-8",
        )
        run_git(self.root, ["add", "AGENTS.md"])
        run_git(self.root, ["commit", "-m", "head commit"])

        res = self.run_check(extra_args=["--json"])
        self.assertEqual(res.returncode, 1)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "FAIL")
        self.assertEqual(data["missing_count"], 1)
        self.assertIn("| auth | JWT token validation and password reset |", data["missing"])
        self.assertIn("Table rows or facts replaced by generated tables are reported as missing so a human can review and decide.", data["message"])


def run_all_preservation_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCheckPreservation)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    return res.wasSuccessful()


if __name__ == "__main__":
    unittest.main()
