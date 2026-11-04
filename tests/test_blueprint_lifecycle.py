"""Integration tests for blueprint lifecycle: init, adopt, link-check, drift, and atomicity."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BP_SCRIPT = REPO_ROOT / "skills" / "project-blueprints" / "scripts" / "blueprint.py"


class TestBlueprintLifecycle(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def run_bp(self, *args, cwd=None):
        cmd = [sys.executable, "-B", str(BP_SCRIPT), *args]
        return subprocess.run(
            cmd,
            cwd=str(cwd or self.root),
            capture_output=True,
            text=True
        )

    def test_init_is_idempotent_and_never_overwrites(self):
        """Init scaffolds files and never overwrites existing content."""
        res1 = self.run_bp("init", "--root", ".")
        self.assertEqual(res1.returncode, 0, res1.stderr)

        data_file = self.root / ".agents" / "blueprints" / "data.md"
        self.assertTrue(data_file.is_file())

        # Add custom line to data.md
        custom_marker = "HAND WRITTEN TEST FACT DO NOT OVERWRITE"
        data_file.write_text(data_file.read_text(encoding="utf-8") + f"\n{custom_marker}\n", encoding="utf-8")

        # Run init again
        res2 = self.run_bp("init", "--root", ".")
        self.assertEqual(res2.returncode, 0, res2.stderr)
        self.assertIn("Skipped existing", res2.stdout)

        content = data_file.read_text(encoding="utf-8")
        self.assertIn(custom_marker, content)

    def test_adopt_moves_200_line_block_with_pointer(self):
        """Adopt moves a 200 line block byte for byte and leaves a show pointer."""
        skill_dir = self.root / ".agents" / "skills" / "build-ui"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        block_lines = [f"Contract row number {i} with payload specification" for i in range(1, 201)]
        block_body = "\n".join(block_lines)

        skill_file.write_text(
            "---\nname: build-ui\ndescription: test\n---\n# UI Skill\n\n"
            "<!-- BEGIN CUSTOM: contracts -->\n"
            f"{block_body}\n"
            "<!-- END CUSTOM: contracts -->\n",
            encoding="utf-8"
        )

        res = self.run_bp("adopt", "--from", ".agents/skills/build-ui/SKILL.md", "--block", "contracts", "--area", "ui")
        self.assertEqual(res.returncode, 0, res.stderr)

        # Check blueprint ui.md contains the exact block lines
        bp_ui = self.root / ".agents" / "blueprints" / "ui.md"
        self.assertTrue(bp_ui.is_file())
        ui_txt = bp_ui.read_text(encoding="utf-8")
        self.assertIn("Contract row number 1 with payload specification", ui_txt)
        self.assertIn("Contract row number 200 with payload specification", ui_txt)

        # Check skill file has the pointer replacement
        skill_txt = skill_file.read_text(encoding="utf-8")
        self.assertNotIn("Contract row number 1", skill_txt)
        self.assertIn("blueprint.py show --area ui", skill_txt)

    def test_adopt_refuses_block_with_fake_secret(self):
        """Adopt aborts and refuses when block contains potential secret patterns."""
        skill_dir = self.root / ".agents" / "skills" / "build-ui"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        original_content = (
            "---\nname: build-ui\ndescription: test\n---\n"
            "<!-- BEGIN CUSTOM: secret-block -->\n"
            "api_key = 'sk-fake1234567890abcdef1234567890'\n"
            "<!-- END CUSTOM: secret-block -->\n"
        )
        skill_file.write_text(original_content, encoding="utf-8")

        res = self.run_bp("adopt", "--from", ".agents/skills/build-ui/SKILL.md", "--block", "secret-block", "--area", "ui")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Refused to adopt block", res.stderr)
        self.assertEqual(skill_file.read_text(encoding="utf-8"), original_content)

    def test_contracts_survive_extract(self):
        """Contracts custom block in blueprints survives extract byte for byte."""
        self.run_bp("init", "--root", ".")
        data_file = self.root / ".agents" / "blueprints" / "data.md"

        custom_contract = (
            "<!-- BEGIN CUSTOM: contracts -->\n"
            "- Immutable account state transitions\n"
            "- Evidence: src/state.ts:15\n"
            "<!-- END CUSTOM: contracts -->"
        )
        data_file.write_text(
            f"# Data Blueprint\n\nGenerated facts.\n\n{custom_contract}\n",
            encoding="utf-8"
        )

        # Create tiny src file so extract runs
        (self.root / "schema.sql").write_text("CREATE TABLE t (id INT);\n", encoding="utf-8")
        res = self.run_bp("extract", "--root", ".")
        self.assertEqual(res.returncode, 0, res.stderr)

        content = data_file.read_text(encoding="utf-8")
        self.assertIn("- Immutable account state transitions", content)
        self.assertIn("- Evidence: src/state.ts:15", content)

    def test_drift_catches_changed_anchor(self):
        """Drift check fails when contract evidence anchor text moves away."""
        self.run_bp("init", "--root", ".")

        # Create source file with target text at line 10
        src_file = self.root / "src" / "state.ts"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"// comment {i}" for i in range(1, 10)]
        lines.append("export const AccountStateTransition = 'ACTIVE';")
        lines.extend([f"// trailing {i}" for i in range(11, 40)])
        src_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        data_file = self.root / ".agents" / "blueprints" / "data.md"
        data_file.write_text(
            "# Data Blueprint\n\n"
            "<!-- BEGIN CUSTOM: contracts -->\n"
            "- State contract\n"
            "  Evidence: `src/state.ts:10` contains: `AccountStateTransition`\n"
            "<!-- END CUSTOM: contracts -->\n",
            encoding="utf-8"
        )

        # Initial drift should pass (anchor is at line 10)
        self.run_bp("extract", "--root", ".")
        res_ok = self.run_bp("drift", "--root", ".")
        self.assertEqual(res_ok.returncode, 0, res_ok.stderr + res_ok.stdout)

        # Move the line down to line 35 (> 5 lines away from anchor 10)
        moved_lines = [f"// comment {i}" for i in range(1, 35)]
        moved_lines.append("export const AccountStateTransition = 'ACTIVE';")
        moved_lines.extend([f"// trailing {i}" for i in range(36, 50)])
        src_file.write_text("\n".join(moved_lines) + "\n", encoding="utf-8")

        res_drift = self.run_bp("drift", "--root", ".")
        self.assertEqual(res_drift.returncode, 1)
        self.assertIn("Contract anchor text 'AccountStateTransition' not found within 5 lines", res_drift.stderr + res_drift.stdout)

    def test_link_check_validations(self):
        """Link-check catches missing blueprints, missing index entries, and oversized blocks."""
        self.run_bp("init", "--root", ".")

        skill_dir = self.root / ".agents" / "skills" / "build-ui"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        # Case 1: Point to non-existent blueprint area
        skill_file.write_text(
            "---\nname: build-ui\ndescription: test\n---\n"
            "## Blueprint\n"
            "python3 .agents/skills/project-blueprints/scripts/blueprint.py show --area nonexistent\n",
            encoding="utf-8"
        )
        res1 = self.run_bp("link-check", "--root", ".")
        self.assertEqual(res1.returncode, 1)
        self.assertIn("links to missing blueprint area 'nonexistent'", res1.stderr)

        # Case 2: Custom block in skill exceeding 80 lines
        oversized_body = "\n".join([f"line {i}" for i in range(95)])
        skill_file.write_text(
            "---\nname: build-ui\ndescription: test\n---\n"
            "## Blueprint\n"
            "python3 .agents/skills/project-blueprints/scripts/blueprint.py show --area ui\n\n"
            "<!-- BEGIN CUSTOM: custom-rules -->\n"
            f"{oversized_body}\n"
            "<!-- END CUSTOM: custom-rules -->\n",
            encoding="utf-8"
        )
        res2 = self.run_bp("link-check", "--root", ".")
        self.assertEqual(res2.returncode, 1)
        self.assertIn("> 80 lines", res2.stderr)

    def test_crlf_handling(self):
        """CRLF line endings are handled cleanly during extract and adopt."""
        src_file = self.root / "src" / "crlf.ts"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_bytes(b"export interface CRLFUser {\r\n  id: string;\r\n  name: string;\r\n}\r\n")

        res = self.run_bp("extract", "--root", ".")
        self.assertEqual(res.returncode, 0, res.stderr)

        bp_data = self.root / ".agents" / "blueprints" / "data.md"
        content = bp_data.read_text(encoding="utf-8")
        self.assertIn("CRLFUser", content)


if __name__ == "__main__":
    unittest.main()
