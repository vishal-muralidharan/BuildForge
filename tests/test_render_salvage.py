#!/usr/bin/env python3
"""Comprehensive test suite for render.py content salvage, migration, and safeguards."""
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
  name: pocketlog
  summary: Pocketlog application for salvage tests.
  mode: existing
  platforms: [web]

stack:
  language: typescript
  framework: react

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
  scopes: [ui, tokens, data, layout]
  push: never

data:
  storage: sqlite
  invariants:
    - Sessions have unique ids

docs:
  skills_dir: .agents/skills
  agents_file: AGENTS.md
  repo_map: .agents/repo-map.md
"""


class TestRenderSalvage(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="bf-test-salvage-")
        self.root = Path(self.tmp_dir)
        self.profile_path = self.root / ".agents" / "project-profile.yaml"
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(BASE_PROFILE, encoding="utf-8")

        # Copy blueprint skill for adopt tests
        bp_src = REPO_ROOT / "skills" / "project-blueprints"
        bp_dest = self.root / ".agents" / "skills" / "project-blueprints"
        bp_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bp_src, bp_dest)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def run_render(self, *extra_args, check=False):
        cmd = [sys.executable, "-B", str(RENDER_PY), "--profile", str(self.profile_path), "--root", str(self.root)] + list(extra_args)
        res = subprocess.run(cmd, cwd=str(self.root), capture_output=True, text=True, check=check)
        if res.stdout:
            res.stdout = res.stdout.replace("\\", "/")
        if res.stderr:
            res.stderr = res.stderr.replace("\\", "/")
        return res

    def run_check_sync(self):
        cmd = [sys.executable, "-B", str(CHECK_SYNC_PY), "--profile", str(self.profile_path), "--root", str(self.root)]
        res = subprocess.run(cmd, cwd=str(self.root), capture_output=True, text=True)
        return res

    def test_01_stamped_matching_hash_regenerates_and_keeps_blocks(self):
        """Point 1: Stamped file with matching hash keeps blocks and updates generated text."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        content = bui.read_text(encoding="utf-8")
        custom_note = "- Human written note about UI patterns\n"
        bui.write_text(
            content.replace(
                "<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->",
                f"<!-- BEGIN CUSTOM: notes -->\n{custom_note}<!-- END CUSTOM: notes -->"
            ),
            encoding="utf-8"
        )

        res = self.run_render("--update")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("UPDATED .agents/skills/build-ui/SKILL.md (preserved 1 block(s))", res.stdout)
        updated_txt = bui.read_text(encoding="utf-8")
        self.assertIn(custom_note, updated_txt)

    def test_02_stamped_edited_outside_blocks_update_refuses_and_salvage_preserves(self):
        """Point 2: --update refuses hand edits outside blocks; --salvage moves absent lines to salvaged block."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        orig_text = bui.read_text(encoding="utf-8")

        # Hand edit outside custom blocks (e.g. 10 line table)
        table_lines = ["| Component | Status |", "| :--- | :--- |"] + [f"| Button{i} | ready |" for i in range(8)]
        table_text = "\n".join(table_lines) + "\n"
        edited_text = orig_text.replace("## Finish", f"## Hand Added Section\n\n{table_text}\n## Finish")
        bui.write_text(edited_text, encoding="utf-8")

        # --update alone must refuse with exit 1
        res_refuse = self.run_render("--update")
        self.assertEqual(res_refuse.returncode, 1)
        self.assertIn("REFUSED .agents/skills/build-ui/SKILL.md (hand edits outside custom blocks)", res_refuse.stdout)
        self.assertIn("+++ .agents/skills/build-ui/SKILL.md (expected clean)", res_refuse.stdout)

        # --salvage regenerates and saves hand edit into salvaged block
        res_salvage = self.run_render("--salvage")
        self.assertEqual(res_salvage.returncode, 0, res_salvage.stderr)
        self.assertIn("SALVAGED", res_salvage.stdout)
        self.assertIn("salvaged", res_salvage.stdout)

        salvaged_txt = bui.read_text(encoding="utf-8")
        self.assertIn("<!-- BEGIN CUSTOM: salvaged -->", salvaged_txt)
        self.assertIn("<!-- Salvaged hand edits outside custom blocks -->", salvaged_txt)
        self.assertIn("| Button0 | ready |", salvaged_txt)
        self.assertIn("## Finish", salvaged_txt)

    def test_02b_overflow_salvage_routes_through_blueprint_adopt(self):
        """Point 2: Salvaged hand edits over limit route through blueprint adopt to area contracts."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        orig_text = bui.read_text(encoding="utf-8")

        # Create 200 lines of hand edits outside blocks (> 160 line limit)
        token_lines = [f"const TOKEN_{i:03d} = 'value_{i}';" for i in range(180)]
        token_body = "\n".join(token_lines) + "\n"
        bui.write_text(orig_text.replace("## Finish", f"## Token Block\n\n{token_body}\n## Finish"), encoding="utf-8")

        res_salvage = self.run_render("--salvage")
        self.assertEqual(res_salvage.returncode, 0, res_salvage.stderr)
        self.assertIn("ROUTED  Custom block 'salvaged' from .agents/skills/build-ui/SKILL.md into blueprint 'ui.md'", res_salvage.stdout)

        # Confirm target blueprint ui.md contracts holds the adopted lines
        bp_ui = self.root / ".agents" / "blueprints" / "ui.md"
        self.assertTrue(bp_ui.is_file())
        bp_txt = bp_ui.read_text(encoding="utf-8")
        self.assertIn("<!-- BEGIN CUSTOM: contracts -->", bp_txt)
        self.assertIn("const TOKEN_000 = 'value_0';", bp_txt)

        # Confirm build-ui now has a pointer
        bui_txt = bui.read_text(encoding="utf-8")
        self.assertIn("python3 .agents/skills/project-blueprints/scripts/blueprint.py show --area ui", bui_txt)

    def test_02c_overflow_salvage_non_mapped_skill_routes_to_notes(self):
        """Point 2: Salvaged hand edits in non-blueprint skill route to .agents/notes/<skill>.md."""
        self.run_render(check=True)

        fn = self.root / ".agents" / "skills" / "file-folder-naming" / "SKILL.md"
        orig_text = fn.read_text(encoding="utf-8")

        large_lines = [f"- Naming rule {i}: specific constraint" for i in range(175)]
        fn.write_text(orig_text + "\n## Large Naming Rules\n\n" + "\n".join(large_lines) + "\n", encoding="utf-8")

        res = self.run_render("--salvage")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("ROUTED  Custom block 'salvaged' from .agents/skills/file-folder-naming/SKILL.md to .agents/notes/file-folder-naming.md", res.stdout)

        notes_file = self.root / ".agents" / "notes" / "file-folder-naming.md"
        self.assertTrue(notes_file.is_file())
        notes_txt = notes_file.read_text(encoding="utf-8")
        self.assertIn("Naming rule 0: specific constraint", notes_txt)

        fn_txt = fn.read_text(encoding="utf-8")
        self.assertIn("Moved to .agents/notes/file-folder-naming.md", fn_txt)

    def test_03_force_behaves_like_salvage_and_discard_requires_both_flags(self):
        """Point 3: --force behaves like --salvage; discarding needs --discard-edits and --yes-discard."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        orig = bui.read_text(encoding="utf-8")
        hand_edit = "Special hand edit line that must not be lost."
        bui.write_text(orig.replace("## Finish", f"## Extra Section\n{hand_edit}\n\n## Finish"), encoding="utf-8")

        # --force alone behaves like --salvage
        res_force = self.run_render("--force")
        self.assertEqual(res_force.returncode, 0, res_force.stderr)
        self.assertIn("SALVAGED", res_force.stdout)
        self.assertIn("salvaged", res_force.stdout)
        self.assertIn(hand_edit, bui.read_text(encoding="utf-8"))

        # Re-introduce hand edit
        bui.write_text(orig.replace("## Finish", "## Extra Section\nDiscardable test line\n## Finish"), encoding="utf-8")

        # --discard-edits without --yes-discard must fail
        res_no_yes = self.run_render("--force", "--discard-edits")
        self.assertEqual(res_no_yes.returncode, 1)
        self.assertIn("--discard-edits requires --yes-discard", res_no_yes.stderr or res_no_yes.stdout)

        # --discard-edits with --yes-discard succeeds and prints discarded lines
        res_discard = self.run_render("--force", "--discard-edits", "--yes-discard")
        self.assertEqual(res_discard.returncode, 0, res_discard.stderr)
        self.assertIn("DISCARDED", res_discard.stdout)
        self.assertIn("Discardable test line", res_discard.stdout)
        self.assertNotIn("Discardable test line", bui.read_text(encoding="utf-8"))

    def test_04_unstamped_file_migrate_custom_and_table_route(self):
        """Point 4: Unstamped file skips by default; --migrate-custom wraps in legacy; > 20 line table routes."""
        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        bui.parent.mkdir(parents=True, exist_ok=True)

        # Table longer than 20 lines
        table = ["| Element | Role |", "| :--- | :--- |"] + [f"| Item{i} | role_{i} |" for i in range(25)]
        unstamped_content = "# Unstamped Build UI\n\n" + "\n".join(table) + "\n"
        bui.write_text(unstamped_content, encoding="utf-8")

        # Default skip
        res_skip = self.run_render()
        self.assertEqual(res_skip.returncode, 0)
        self.assertIn("SKIPPED .agents/skills/build-ui/SKILL.md (unstamped; use --migrate-custom to wrap in legacy block)", res_skip.stdout)
        self.assertEqual(bui.read_text(encoding="utf-8"), unstamped_content)

        # With --migrate-custom, table > 20 lines routes through adopt
        res_mig = self.run_render("--migrate-custom")
        self.assertEqual(res_mig.returncode, 0, res_mig.stderr)
        self.assertIn("MIGRATED .agents/skills/build-ui/SKILL.md", res_mig.stdout)
        self.assertIn("ROUTED  Custom block 'legacy' from .agents/skills/build-ui/SKILL.md into blueprint 'ui.md'", res_mig.stdout)

        bp_ui = self.root / ".agents" / "blueprints" / "ui.md"
        self.assertTrue(bp_ui.is_file())
        self.assertIn("| Item0 | role_0 |", bp_ui.read_text(encoding="utf-8"))

    def test_05_dirty_tree_guard_refuses_unless_allow_dirty(self):
        """Point 5: Git dirty tree guard refuses uncommitted changes unless --allow-dirty."""
        subprocess.run(["git", "init"], cwd=str(self.root), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(self.root), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.root), check=True)

        self.run_render(check=True)

        subprocess.run(["git", "add", "."], cwd=str(self.root), check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=str(self.root), check=True)

        # Modify stamped file to create uncommitted change
        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        bui.write_text(bui.read_text(encoding="utf-8") + "\n- Uncommitted line\n", encoding="utf-8")

        # Render without --allow-dirty should refuse
        res_refuse = self.run_render("--salvage")
        self.assertEqual(res_refuse.returncode, 1)
        self.assertIn("Target file(s) have uncommitted changes", res_refuse.stderr or res_refuse.stdout)

        # Render with --allow-dirty should succeed
        res_allow = self.run_render("--salvage", "--allow-dirty")
        self.assertEqual(res_allow.returncode, 0, res_allow.stderr)

    def test_06_render_log_records_salvage_and_migration_deterministically(self):
        """Point 6: Salvage and migration append to .agents/render-log.md without timestamps."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        bui.write_text(bui.read_text(encoding="utf-8").replace("## Finish", "## Section\n- Salvage me\n## Finish"), encoding="utf-8")

        self.run_render("--salvage")

        log_file = self.root / ".agents" / "render-log.md"
        self.assertTrue(log_file.is_file())
        log_txt = log_file.read_text(encoding="utf-8")
        self.assertIn("# Render Log", log_txt)
        self.assertIn("path: .agents/skills/build-ui/SKILL.md", log_txt)
        self.assertIn("action: salvage", log_txt)

    def test_07_secret_scan_refuses_salvage_and_migration(self):
        """Point 7: Secret pattern in hand edits or unstamped files causes immediate refusal."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        orig = bui.read_text(encoding="utf-8")
        secret_line = 'API_KEY = "sk-live-0123456789abcdef0123456789abcdef"'
        bui.write_text(orig.replace("## Finish", f"## Config\n{secret_line}\n## Finish"), encoding="utf-8")

        res = self.run_render("--salvage")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Secret pattern detected", res.stderr or res.stdout)

    def test_08_check_sync_warns_on_salvaged_or_legacy_blocks(self):
        """Point 8: check_sync.py warns when salvaged or legacy blocks exist."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        bui.write_text(bui.read_text(encoding="utf-8").replace("## Finish", "## Section\n- Temp hand edit\n## Finish"), encoding="utf-8")
        self.run_render("--salvage")

        res_sync = self.run_check_sync()
        self.assertIn("custom block 'salvaged' in '.agents/skills/build-ui/SKILL.md' needs review", res_sync.stdout)

    def test_09_idempotency_second_run_salvages_nothing(self):
        """Point 9: Second run of --salvage produces 0 salvaged lines and leaves files unchanged."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        bui.write_text(bui.read_text(encoding="utf-8").replace("## Finish", "## Section\n- Line 1\n- Line 2\n## Finish"), encoding="utf-8")

        res1 = self.run_render("--salvage")
        self.assertEqual(res1.returncode, 0)
        self.assertIn("SALVAGED", res1.stdout)
        txt1 = bui.read_text(encoding="utf-8")

        # Second run
        res2 = self.run_render("--salvage")
        self.assertEqual(res2.returncode, 0)
        self.assertNotIn("SALVAGED", res2.stdout)
        self.assertIn("(preserved 2 block(s))", res2.stdout)
        txt2 = bui.read_text(encoding="utf-8")
        self.assertEqual(txt1, txt2)

    def test_10_crlf_normalization(self):
        """CRLF line endings in stamped files are salvaged cleanly as LF without trailing CR."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        orig = bui.read_text(encoding="utf-8")
        crlf_edit = orig.replace("## Finish", "## CRLF Section\r\n- Windows Line 1\r\n- Windows Line 2\r\n## Finish")
        bui.write_bytes(crlf_edit.encode("utf-8"))

        res = self.run_render("--salvage")
        self.assertEqual(res.returncode, 0, res.stderr)
        final_bytes = bui.read_bytes()
        self.assertNotIn(b"\r\n", final_bytes)
        self.assertIn("Windows Line 1", bui.read_text(encoding="utf-8"))

    def test_11_property_every_non_generated_line_survives_unless_discarded(self):
        """Property test: Every normalized non-generated line of old files appears in new files unless discarded."""
        self.run_render(check=True)

        bui = self.root / ".agents" / "skills" / "build-ui" / "SKILL.md"
        orig = bui.read_text(encoding="utf-8")

        # Inject 15 distinct hand-written lines across custom block and outside blocks
        hand_lines = [f"Unique hand line {i:02d} with special business requirement" for i in range(15)]
        outside_lines = hand_lines[:8]
        inside_lines = hand_lines[8:]

        edited = orig.replace(
            "<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->",
            "<!-- BEGIN CUSTOM: notes -->\n" + "\n".join(inside_lines) + "\n<!-- END CUSTOM: notes -->"
        )
        edited = edited.replace("## Finish", "## Hand Section\n" + "\n".join(outside_lines) + "\n\n## Finish")
        bui.write_text(edited, encoding="utf-8")

        # Run salvage
        res = self.run_render("--salvage")
        self.assertEqual(res.returncode, 0, res.stderr)

        # Read all generated files in .agents (skills, blueprints, notes)
        all_new_text = ""
        for p in self.root.rglob("*.md"):
            all_new_text += p.read_text(encoding="utf-8", errors="replace") + "\n"

        for line in hand_lines:
            self.assertIn(line, all_new_text, f"Hand line lost: {line}")


if __name__ == "__main__":
    unittest.main()
