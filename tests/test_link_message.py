#!/usr/bin/env python3
"""build-forge link explains what it did, also when it did nothing."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "bin" / "build-forge.js"


def cli(args, cwd):
    return subprocess.run(["node", str(CLI_PATH)] + args, cwd=cwd, capture_output=True, text=True)


class TestLinkMessage(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="bf-link-msg-"))
        cli(["install"], self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_auto_without_agents_explains(self):
        res = cli(["link", "--agents", "auto"], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("No coding agent folders or pointer files were found", res.stdout)
        self.assertIn("--agents <id|all>", res.stdout)
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_unknown_agent_id_fails(self):
        res = cli(["link", "--agents", "claud"], self.root)
        self.assertEqual(res.returncode, 1)
        self.assertIn("Unknown agent id(s): claud", res.stderr)

    def test_second_link_reports_already_linked(self):
        first = cli(["link", "--agents", "claude"], self.root)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("CLAUDE.md created", first.stdout)
        second = cli(["link", "--agents", "claude"], self.root)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already linked", second.stdout)


if __name__ == "__main__":
    unittest.main()
