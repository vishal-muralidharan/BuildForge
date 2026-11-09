#!/usr/bin/env python3
"""Integration tests for render.py custom blocks, update, force, and stamping."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
RENDER_PY = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "render.py"
CHECK_SYNC_PY = REPO_ROOT / "skills" / "sync-skills-and-docs" / "scripts" / "check_sync.py"

BASE_PROFILE = """schema_version: 1

project:
  name: demo-app
  summary: Demo application for custom block tests.
  mode: new
  platforms: [web]

stack:
  language: javascript
  framework: vanilla

commands:
  check: npm test
  test: npm test

design:
  enabled: true
  tokens_file: src/tokens.css

structure:
  layers:
    - path: src
      purpose: Application source
  tests: tests-dir

git:
  commit_format: "<type>(<scope>): <subject>"
  single_line: true
  types: [feat, fix, docs, chore]
  scopes: [ui, data]
  push: never

data:
  storage: localStorage
  invariants:
    - Notes have unique ids

docs:
  skills_dir: .agents/skills
  agents_file: AGENTS.md
  repo_map: .agents/repo-map.md
"""


class TestRenderCustomBlocks(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="bf-test-render-")
        self.root = Path(self.tmp_dir)
        self.profile_path = self.root / ".agents" / "project-profile.yaml"
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(BASE_PROFILE, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def run_render(self, *extra_args, check=False):
        cmd = [sys.executable, str(RENDER_PY), "--profile", str(self.profile_path), "--root", str(self.root)] + list(extra_args)
        res = subprocess.run(cmd, cwd=str(self.root), capture_output=True, text=True, check=check)
        if res.stdout:
            res.stdout = res.stdout.replace("\\", "/")
        if res.stderr:
            res.stderr = res.stderr.replace("\\", "/")
        return res

    def test_01_fresh_render_adds_notes_block_and_stamp(self):
        """Fresh render adds the stamp line and an empty notes block to generated files."""
        res = self.run_render()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("WROTE   AGENTS.md", res.stdout)
        self.assertIn("created:", res.stdout)

        agents_file = self.root / "AGENTS.md"
        self.assertTrue(agents_file.is_file())
        content = agents_file.read_text(encoding="utf-8")

        self.assertIn("<!-- build-forge:generated v1 body=", content)
        self.assertIn("<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->", content)

        skill_file = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        self.assertTrue(skill_file.is_file())
        scontent = skill_file.read_text(encoding="utf-8")
        self.assertIn("<!-- build-forge:generated v1 body=", scontent)
        self.assertIn("<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->", scontent)

    def test_02_update_after_profile_change_keeps_custom_block_byte_for_byte(self):
        """--update after profile change preserves custom blocks byte for byte."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        original_text = bui.read_text(encoding="utf-8")
        custom_note = "Special hand-written note line 1.\n  indented line 2\n"
        bui.write_text(
            original_text.replace(
                "<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->",
                f"<!-- BEGIN CUSTOM: notes -->\n{custom_note}<!-- END CUSTOM: notes -->"
            ),
            encoding="utf-8"
        )

        # Modify profile summary
        updated_profile = BASE_PROFILE.replace("Demo application for custom block tests.", "Updated application description.")
        self.profile_path.write_text(updated_profile, encoding="utf-8")

        res_update = self.run_render("--update")
        self.assertEqual(res_update.returncode, 0, res_update.stderr)
        self.assertIn("UPDATED .agents/skills/build-ui/SKILL.md (preserved 1 block(s))", res_update.stdout)

        # Verify custom block survived byte for byte
        updated_bui = bui.read_text(encoding="utf-8")
        self.assertIn(f"<!-- BEGIN CUSTOM: notes -->\n{custom_note}<!-- END CUSTOM: notes -->", updated_bui)

        # Verify AGENTS.md also reflected updated profile
        agents_txt = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Updated application description.", agents_txt)

    def test_03_hand_edit_outside_blocks_makes_update_refuse_with_exit_1_and_no_file_changed(self):
        """A hand edit outside custom blocks causes --update to refuse with exit 1 and change nothing."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        bui_orig = bui.read_text(encoding="utf-8")
        agents = self.root / "AGENTS.md"
        agents_orig = agents.read_text(encoding="utf-8")

        # Hand-edit build-ui outside custom blocks
        bui_edited = bui_orig.replace("# How to build UI in demo-app", "# Hand-edited Title")
        bui.write_text(bui_edited, encoding="utf-8")

        res = self.run_render("--update")
        self.assertEqual(res.returncode, 1)
        self.assertIn("REFUSED .agents/skills/build-ui/SKILL.md (hand edits outside custom blocks)", res.stdout)
        self.assertIn("--- .agents/skills/build-ui/SKILL.md (current)", res.stdout)
        self.assertIn("+++ .agents/skills/build-ui/SKILL.md (expected clean)", res.stdout)

        # Confirm no file was changed on disk
        self.assertEqual(bui.read_text(encoding="utf-8"), bui_edited)
        self.assertEqual(agents.read_text(encoding="utf-8"), agents_orig)

    def test_04_force_keeps_blocks_and_reports_lost_lines(self):
        """--force on a stamped file behaves like --salvage unless --discard-edits and --yes-discard are passed."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        content = bui.read_text(encoding="utf-8")
        custom_note = "- Important UI invariant written by engineer\n"
        content = content.replace(
            "<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->",
            f"<!-- BEGIN CUSTOM: notes -->\n{custom_note}<!-- END CUSTOM: notes -->"
        )
        # Edit text outside blocks
        content = content.replace("## Finish", "## Custom Hand Modified Finish Header")
        bui.write_text(content, encoding="utf-8")

        # --force alone behaves like --salvage (no content discarded)
        res = self.run_render("--force")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("SALVAGED 1 line(s) from .agents/skills/build-ui/SKILL.md", res.stdout)
        self.assertIn("salvaged 1 line(s)", res.stdout)

        # Check file content: custom note preserved and hand-edit salvaged
        new_bui = bui.read_text(encoding="utf-8")
        self.assertIn(f"<!-- BEGIN CUSTOM: notes -->\n{custom_note}<!-- END CUSTOM: notes -->", new_bui)
        self.assertIn("Custom Hand Modified Finish Header", new_bui)
        self.assertIn("<!-- BEGIN CUSTOM: salvaged -->", new_bui)

        # Re-introduce hand edit outside blocks and test --discard-edits --yes-discard
        content2 = new_bui.replace("## Finish", "## Discardable Header")
        bui.write_text(content2, encoding="utf-8")

        res_discard = self.run_render("--force", "--discard-edits", "--yes-discard")
        self.assertEqual(res_discard.returncode, 0, res_discard.stderr)
        self.assertIn("DISCARDED 1 line(s) from .agents/skills/build-ui/SKILL.md:", res_discard.stdout)
        self.assertIn("Discardable Header", res_discard.stdout)

        final_bui = bui.read_text(encoding="utf-8")
        self.assertNotIn("Discardable Header", final_bui)

    def test_05_unstamped_file_survives_force_unless_overwrite_unstamped(self):
        """Unstamped file survives --force alone and requires --overwrite-unstamped to overwrite."""
        # Pre-create unstamped file
        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        bui.parent.mkdir(parents=True, exist_ok=True)
        unstamped_text = "# Unstamped legacy build UI file\nNo stamp here.\n"
        bui.write_text(unstamped_text, encoding="utf-8")

        res1 = self.run_render("--force")
        self.assertEqual(res1.returncode, 0)
        self.assertIn("SKIPPED .agents/skills/build-ui/SKILL.md (unstamped; use --migrate-custom to wrap in legacy block)", res1.stdout)
        self.assertEqual(bui.read_text(encoding="utf-8"), unstamped_text)

        # With --overwrite-unstamped (requires --discard-edits and --yes-discard per D8)
        res2 = self.run_render("--force", "--overwrite-unstamped", "--discard-edits", "--yes-discard")
        self.assertEqual(res2.returncode, 0)
        self.assertIn("OVERWROTE .agents/skills/build-ui/SKILL.md (unstamped; forced with --overwrite-unstamped)", res2.stdout)
        self.assertIn("<!-- build-forge:generated v1 body=", bui.read_text(encoding="utf-8"))

    def test_06_orphan_custom_blocks_saved_to_ledger(self):
        """Custom blocks whose block name or file is no longer generated go to .agents/custom-orphans.md."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        content = bui.read_text(encoding="utf-8")
        orphan_block = "<!-- BEGIN CUSTOM: extra-rule -->\nExtra rule content\n<!-- END CUSTOM: extra-rule -->\n"
        bui.write_text(content + "\n" + orphan_block, encoding="utf-8")

        res = self.run_render("--force")
        self.assertEqual(res.returncode, 0)
        self.assertIn("ORPHAN  Preserved custom block 'extra-rule' from .agents/skills/build-ui/SKILL.md in .agents/custom-orphans.md", res.stdout)

        orphans_file = self.root / ".agents" / "custom-orphans.md"
        self.assertTrue(orphans_file.is_file())
        otxt = orphans_file.read_text(encoding="utf-8")
        self.assertIn("Extra rule content", otxt)
        self.assertIn("block: extra-rule", otxt)

    def test_07_custom_block_line_limits_warn_and_fail(self):
        """Block line limits warn above 80/300 and fail above 160/600 with message pointing to blueprints."""
        self.run_render(check=True)
        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        content = bui.read_text(encoding="utf-8")

        # 85 lines in a block -> warning
        lines_85 = "\n".join(f"Note {i}" for i in range(85))
        bui.write_text(
            content.replace(
                "<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->",
                f"<!-- BEGIN CUSTOM: notes -->\n{lines_85}\n<!-- END CUSTOM: notes -->"
            ),
            encoding="utf-8"
        )
        res_warn = self.run_render("--update")
        self.assertEqual(res_warn.returncode, 0)
        self.assertIn("WARN  Custom block 'notes' in .agents/skills/build-ui/SKILL.md has 85 lines (> 80).", res_warn.stdout)
        self.assertIn("Facts belong in blueprints (.agents/blueprints/) or the profile (.agents/project-profile.yaml).", res_warn.stdout)

        # 165 lines in a block -> failure
        lines_165 = "\n".join(f"Note {i}" for i in range(165))
        bui.write_text(
            content.replace(
                "<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->",
                f"<!-- BEGIN CUSTOM: notes -->\n{lines_165}\n<!-- END CUSTOM: notes -->"
            ),
            encoding="utf-8"
        )
        res_fail = self.run_render("--update")
        self.assertEqual(res_fail.returncode, 1)
        self.assertIn("ERROR: Custom block 'notes' in .agents/skills/build-ui/SKILL.md has 165 lines (> 160).", res_fail.stderr)
        self.assertIn("Facts belong in blueprints (.agents/blueprints/) or the profile (.agents/project-profile.yaml).", res_fail.stderr)

    def test_08_fake_secret_in_block_fails(self):
        """Fake secret patterns inside custom blocks fail render with clear error."""
        self.run_render(check=True)
        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        content = bui.read_text(encoding="utf-8")

        secret_block = "api_key = 'abcdef1234567890abcdef1234567890'"
        bui.write_text(
            content.replace(
                "<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->",
                f"<!-- BEGIN CUSTOM: notes -->\n{secret_block}\n<!-- END CUSTOM: notes -->"
            ),
            encoding="utf-8"
        )
        res = self.run_render("--update")
        self.assertEqual(res.returncode, 1)
        self.assertIn("ERROR: Secret pattern detected in custom block 'notes'", res.stderr)

    def test_09_crlf_input_handled_cleanly(self):
        """Files formatted with Windows CRLF newlines are parsed and updated without false refusal."""
        self.run_render(check=True)
        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        content = bui.read_text(encoding="utf-8")

        # Convert to CRLF with a custom note
        crlf_content = content.replace("\n", "\r\n").replace(
            "<!-- BEGIN CUSTOM: notes -->\r\n<!-- END CUSTOM: notes -->",
            "<!-- BEGIN CUSTOM: notes -->\r\nWindows CRLF note line 1\r\n<!-- END CUSTOM: notes -->"
        )
        bui.write_bytes(crlf_content.encode("utf-8"))

        res = self.run_render("--update")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("UPDATED .agents/skills/build-ui/SKILL.md (preserved 1 block(s))", res.stdout)
        self.assertIn("Windows CRLF note line 1", bui.read_text(encoding="utf-8"))

    def test_10_duplicate_block_names_fail_with_clear_message(self):
        """Duplicate custom block names in a file fail with clear error."""
        self.run_render(check=True)
        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        content = bui.read_text(encoding="utf-8")
        duplicate_blocks = (
            "<!-- BEGIN CUSTOM: notes -->\nFirst notes\n<!-- END CUSTOM: notes -->\n"
            "<!-- BEGIN CUSTOM: notes -->\nSecond notes\n<!-- END CUSTOM: notes -->\n"
        )
        bui.write_text(content + "\n" + duplicate_blocks, encoding="utf-8")

        res = self.run_render("--update")
        self.assertEqual(res.returncode, 1)
        self.assertIn("ERROR: Duplicate custom block name 'notes' in .agents/skills/build-ui/SKILL.md.", res.stderr)


def run_all_render_custom_block_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestRenderCustomBlocks)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_all_render_custom_block_tests()

