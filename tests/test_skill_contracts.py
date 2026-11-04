#!/usr/bin/env python3
"""Tests for scripts/skill_contracts.py verifying failure on broken fixtures."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skill_contracts import check_skill_contracts  # noqa: E402


class TestSkillContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bf-contracts-test-")
        self.root = Path(self.tmp)
        (self.root / "scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "skills").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rule_1_unmentioned_script_fails(self):
        """Rule 1: Script not mentioned in SKILL.md and not in allowlist fails."""
        skill_dir = self.root / "skills" / "my-skill"
        (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (skill_dir / "scripts" / "unmentioned.py").write_text("# script\n", encoding="utf-8")
        (skill_dir / "SKILL.md").write_text("# My Skill\nNo scripts mentioned here.\n", encoding="utf-8")

        errors = check_skill_contracts(self.root)
        self.assertTrue(any("is not mentioned in my-skill/SKILL.md" in e for e in errors), errors)

        # Passes when added to contracts-allow.txt
        (self.root / "scripts" / "contracts-allow.txt").write_text(
            "skills/my-skill/scripts/unmentioned.py: allowed test helper\n",
            encoding="utf-8"
        )
        errors_after = check_skill_contracts(self.root)
        self.assertFalse(any("unmentioned.py" in e for e in errors_after), errors_after)

    def test_rule_2_missing_script_path_fails(self):
        """Rule 2: .agents/skills/<skill>/scripts/<file> referencing non-existent file fails."""
        skill_dir = self.root / "skills" / "my-skill"
        (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "# My Skill\nRun `python3 .agents/skills/my-skill/scripts/missing_script.py`\n",
            encoding="utf-8"
        )

        errors = check_skill_contracts(self.root)
        self.assertTrue(any("references non-existent script: .agents/skills/my-skill/scripts/missing_script.py" in e for e in errors), errors)

    def test_rule_3_unknown_subcommand_fails(self):
        """Rule 3: Script with argparse subparsers fails when an unknown subcommand is referenced."""
        skill_dir = self.root / "skills" / "my-skill"
        (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)

        script_code = """#!/usr/bin/env python3
import argparse
p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="sub")
sub.add_parser("valid_cmd")
p.parse_args()
"""
        (skill_dir / "scripts" / "tool.py").write_text(script_code, encoding="utf-8")
        (skill_dir / "SKILL.md").write_text(
            "# My Skill\nUses `tool.py`:\n`python3 .agents/skills/my-skill/scripts/tool.py bogus_cmd`\n",
            encoding="utf-8"
        )

        errors = check_skill_contracts(self.root)
        self.assertTrue(any("Unknown subcommand 'bogus_cmd'" in e for e in errors), errors)

    def test_rule_4_missing_required_text_fails(self):
        """Rule 4: Missing REQUIRED_TEXT in a required skill fails."""
        skill_dir = self.root / "skills" / "atomic-commits"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("# Atomic Commits\nIncomplete text.\n", encoding="utf-8")

        errors = check_skill_contracts(self.root)
        self.assertTrue(any("does not contain required text contract" in e for e in errors), errors)

    def test_current_repo_passes_all_contracts(self):
        """All contracts must pass cleanly on the actual Build Forge repository."""
        errors = check_skill_contracts(REPO_ROOT)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
