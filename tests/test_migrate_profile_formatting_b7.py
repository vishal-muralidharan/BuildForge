#!/usr/bin/env python3
"""Tests for Bug B7: migrate_profile.py preserves comments, quotes, key order, line wrapping."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATE_SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "migrate_profile.py"
VALIDATE_SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "validate_profile.py"


SAMPLE_PROFILE_V1 = """# Top-level comment that must survive
schema_version: 1 # version inline comment

project:
  name: "Quoted Project Name" # project name comment
  summary: 'Single-quoted summary that should keep single quotes'
  mode: existing

# Stack configuration
stack:
  language: "typescript"
  framework: "React"
  package_manager: "npm"

commands:
  check: "npm test"

structure:
  layers:
    - path: "src"
      purpose: "Application source code"
  tests: colocated

git:
  commit_format: 'type(scope): summary'
  push: ask

docs:
  skills_dir: .agents/skills
  agents_file: AGENTS.md
  repo_map: docs/repo-map.md

rules:
  - id: custom-rule-1
    area: naming
    text: "Do not use short variable names under any circumstances in production modules."
    enforced_by: manual
"""


class TestMigrateProfileFormattingB7(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bf-test-b7-"))
        (self.tmp / "src").mkdir(parents=True, exist_ok=True)
        (self.tmp / "docs").mkdir(parents=True, exist_ok=True)
        (self.tmp / "docs" / "repo-map.md").write_text("# Repo Map\n", encoding="utf-8")
        (self.tmp / "AGENTS.md").write_text("# Agent Guidelines\n", encoding="utf-8")
        self.profile = self.tmp / ".agents" / "project-profile.yaml"
        self.profile.parent.mkdir(parents=True, exist_ok=True)
        self.profile.write_text(SAMPLE_PROFILE_V1, encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migrate_profile_preserves_formatting(self):
        """Line-based migration preserves comments, quotes, key order, bumps version to 2, and adds blueprints."""
        # 1. Test plan command diff output
        res_plan = subprocess.run(
            [sys.executable, str(MIGRATE_SCRIPT), "plan", "--profile", str(self.profile), "--root", str(self.tmp)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_plan.returncode, 0, f"migrate plan failed:\n{res_plan.stderr}")
        self.assertIn("Migration plan: schema_version 1 -> 2", res_plan.stdout)
        self.assertIn("-schema_version: 1", res_plan.stdout)
        self.assertIn("+schema_version: 2", res_plan.stdout)
        self.assertIn("+blueprints:", res_plan.stdout)

        # 2. Test apply --apply
        res_apply = subprocess.run(
            [sys.executable, str(MIGRATE_SCRIPT), "apply", "--profile", str(self.profile), "--root", str(self.tmp), "--apply"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_apply.returncode, 0, f"migrate apply failed:\n{res_apply.stderr}")

        migrated_text = self.profile.read_text(encoding="utf-8")

        # 3. Assert schema_version bumped to 2
        self.assertIn("schema_version: 2", migrated_text)
        self.assertNotIn("schema_version: 1", migrated_text)

        # 4. Assert blueprints section added
        self.assertIn("blueprints:", migrated_text)

        # 5. Assert comments survived
        self.assertIn("# Top-level comment that must survive", migrated_text)
        self.assertIn("# version inline comment", migrated_text)
        self.assertIn("# project name comment", migrated_text)
        self.assertIn("# Stack configuration", migrated_text)

        # 6. Assert quoting survived exactly
        self.assertIn('"Quoted Project Name"', migrated_text)
        self.assertIn("'Single-quoted summary that should keep single quotes'", migrated_text)
        self.assertIn('"typescript"', migrated_text)
        self.assertIn('"React"', migrated_text)
        self.assertIn('"npm"', migrated_text)
        self.assertIn('"Do not use short variable names under any circumstances in production modules."', migrated_text)

        # 7. Assert key order unchanged
        proj_idx = migrated_text.find("project:")
        stack_idx = migrated_text.find("stack:")
        cmds_idx = migrated_text.find("commands:")
        struct_idx = migrated_text.find("structure:")
        git_idx = migrated_text.find("git:")
        docs_idx = migrated_text.find("docs:")
        rules_idx = migrated_text.find("rules:")
        self.assertTrue(proj_idx < stack_idx < cmds_idx < struct_idx < git_idx < docs_idx < rules_idx)

        # 8. Assert profile validates cleanly
        res_val = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), "--profile", str(self.profile), "--root", str(self.tmp)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_val.returncode, 0, f"Validator failed on migrated profile:\n{res_val.stdout}\n{res_val.stderr}")


if __name__ == "__main__":
    unittest.main()
