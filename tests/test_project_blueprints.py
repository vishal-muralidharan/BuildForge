"""Integration tests for project-blueprints extraction, verification, staleness, and budgeting."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
BP_SCRIPT_DIR = REPO_ROOT / "skills" / "project-blueprints" / "scripts"
if str(BP_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(BP_SCRIPT_DIR))

BP_SCRIPT = BP_SCRIPT_DIR / "blueprint.py"
BOOTSTRAP_SCRIPT_DIR = REPO_ROOT / "skills" / "project-bootstrap" / "scripts"
if str(BOOTSTRAP_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_SCRIPT_DIR))
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "blueprints"


class TestProjectBlueprints(unittest.TestCase):
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

    def test_determinism_extract_twice(self):
        """Extract run twice produces byte-for-byte identical output."""
        shutil.copytree(FIXTURES_DIR / "js-tokens-storage", self.root / "app")
        app_dir = self.root / "app"

        res1 = self.run_bp("extract", "--root", ".", cwd=app_dir)
        self.assertEqual(res1.returncode, 0, res1.stderr)

        bp_dir = app_dir / ".agents" / "blueprints"
        files1 = {f.name: f.read_bytes() for f in bp_dir.glob("*")}

        res2 = self.run_bp("extract", "--root", ".", cwd=app_dir)
        self.assertEqual(res2.returncode, 0, res2.stderr)
        files2 = {f.name: f.read_bytes() for f in bp_dir.glob("*")}

        self.assertEqual(files1.keys(), files2.keys())
        for k in files1:
            self.assertEqual(files1[k], files2[k], f"Difference detected in {k}")

    def test_verify_passes_and_fails_after_source_edit(self):
        """Verify passes initially and fails after a referenced line changes."""
        shutil.copytree(FIXTURES_DIR / "sql-ts-types", self.root / "app")
        app_dir = self.root / "app"

        res = self.run_bp("extract", "--root", ".", cwd=app_dir)
        self.assertEqual(res.returncode, 0, res.stderr)

        # Initial verify should pass
        res_v1 = self.run_bp("verify", "--root", ".", cwd=app_dir)
        self.assertEqual(res_v1.returncode, 0, res_v1.stderr)
        self.assertIn("Verified", res_v1.stdout)

        # Truncate source file to break line boundary
        (app_dir / "schema.sql").write_text("", encoding="utf-8")
        res_v2 = self.run_bp("verify", "--root", ".", cwd=app_dir)
        self.assertEqual(res_v2.returncode, 1)

    def test_stale_reports_changed_area(self):
        """Stale command lists the area whose sources were modified."""
        shutil.copytree(FIXTURES_DIR / "js-tokens-storage", self.root / "app")
        app_dir = self.root / "app"

        self.run_bp("extract", "--root", ".", cwd=app_dir)

        # Clean check
        res_clean = self.run_bp("stale", "--root", ".", cwd=app_dir)
        self.assertEqual(res_clean.returncode, 0)
        self.assertIn("All blueprints are up to date", res_clean.stdout)

        # Modify token CSS file
        css_file = app_dir / "src" / "theme.css"
        css_file.write_text(css_file.read_text(encoding="utf-8") + "\n.extra { --color-extra: #123456; }", encoding="utf-8")

        res_stale = self.run_bp("stale", "--root", ".", cwd=app_dir)
        self.assertEqual(res_stale.returncode, 0)
        self.assertIn("tokens", res_stale.stdout)

        # --fail flag returns 1 on stale
        res_fail = self.run_bp("stale", "--fail", "--root", ".", cwd=app_dir)
        self.assertEqual(res_fail.returncode, 1)

    def test_show_respects_budget_and_names_skipped(self):
        """Show command truncates to budget and reports skipped lines."""
        shutil.copytree(FIXTURES_DIR / "js-tokens-storage", self.root / "app")
        app_dir = self.root / "app"

        self.run_bp("extract", "--root", ".", cwd=app_dir)

        res = self.run_bp("show", "--area", "tokens", "--budget", "5", cwd=app_dir)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("[Budget limit 5 reached. Skipped", res.stdout)

    def test_custom_block_survives_extract(self):
        """Custom contracts block survives re-extraction byte for byte."""
        shutil.copytree(FIXTURES_DIR / "sql-ts-types", self.root / "app")
        app_dir = self.root / "app"

        self.run_bp("extract", "--root", ".", cwd=app_dir)

        data_bp = app_dir / ".agents" / "blueprints" / "data.md"
        custom_block = (
            "<!-- BEGIN CUSTOM: contracts -->\n"
            "Human written facts about ledger state machines.\n"
            "<!-- END CUSTOM: contracts -->"
        )
        content = data_bp.read_text(encoding="utf-8")
        # Replace empty contracts block with custom block
        updated = content.replace("<!-- BEGIN CUSTOM: contracts -->\n<!-- END CUSTOM: contracts -->", custom_block)
        data_bp.write_text(updated, encoding="utf-8")

        # Re-run extract
        self.run_bp("extract", "--root", ".", cwd=app_dir)

        reloaded = data_bp.read_text(encoding="utf-8")
        self.assertIn(custom_block, reloaded)

    def test_fake_secret_never_appears_in_output(self):
        """Secret values in .env never appear in output blueprints."""
        shutil.copytree(FIXTURES_DIR / "secret-env", self.root / "app")
        app_dir = self.root / "app"

        res = self.run_bp("extract", "--root", ".", cwd=app_dir)
        self.assertEqual(res.returncode, 0, res.stderr)

        bp_dir = app_dir / ".agents" / "blueprints"
        for bp_file in bp_dir.glob("*.md"):
            txt = bp_file.read_text(encoding="utf-8")
            self.assertNotIn("sk-fake1234567890abcdef1234567890", txt)
            self.assertNotIn("fakepass123", txt)

        # Verify config.md lists variable names without values
        cfg_txt = (bp_dir / "config.md").read_text(encoding="utf-8")
        self.assertIn("API_SECRET", cfg_txt)
        self.assertIn("DATABASE_URL", cfg_txt)

    def test_tailwind_v4_theme_extracted(self):
        """Tailwind v4 @theme tokens are parsed into token tables."""
        shutil.copytree(FIXTURES_DIR / "tailwind-theme", self.root / "app")
        app_dir = self.root / "app"

        res = self.run_bp("extract", "--root", ".", cwd=app_dir)
        self.assertEqual(res.returncode, 0, res.stderr)

        tokens_txt = (app_dir / ".agents" / "blueprints" / "tokens.md").read_text(encoding="utf-8")
        self.assertIn("--color-brand", tokens_txt)
        self.assertIn("--font-sans", tokens_txt)

    def test_overflow_and_index_budget(self):
        """Splitting large areas into part files maintains line budgets."""
        from analyzers import common
        from blueprint import split_into_parts

        lines = [f"line {i}" for i in range(550)]
        parts = split_into_parts(lines, "data", max_lines=250)
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0][0], "data.md")
        self.assertEqual(parts[1][0], "data-part-2.md")
        self.assertEqual(parts[2][0], "data-part-3.md")

    def test_form_controls_gap_violation_and_candidates(self):
        """A fixture with Calendar and native date inputs and no DatePicker shows gap and violation and creates both candidates."""
        app_dir = self.root / "app_gap_violation"
        (app_dir / "src" / "components" / "ui").mkdir(parents=True, exist_ok=True)
        (app_dir / "src" / "views").mkdir(parents=True, exist_ok=True)

        # Low level widget Calendar, no DatePicker
        (app_dir / "src" / "components" / "ui" / "Calendar.tsx").write_text(
            "export function Calendar() { return <div>Calendar Grid</div>; }\n",
            encoding="utf-8"
        )
        # Native date input outside primitive folder
        (app_dir / "src" / "views" / "BookingForm.tsx").write_text(
            "export function BookingForm() { return <form><input type=\"date\" name=\"booking\" /></form>; }\n",
            encoding="utf-8"
        )
        (app_dir / "package.json").write_text('{"name": "test-app"}\n', encoding="utf-8")

        res_extract = self.run_bp("extract", "--areas", "ui", cwd=app_dir)
        self.assertEqual(res_extract.returncode, 0, res_extract.stderr)

        ui_md = (app_dir / ".agents" / "blueprints" / "ui.md").read_text(encoding="utf-8")
        self.assertIn("## Form controls", ui_md)
        self.assertIn("gap, violation", ui_md)

        candidates_md = (app_dir / ".agents" / "blueprints" / "candidates.md").read_text(encoding="utf-8")
        self.assertIn("ui-no-native-pickers", candidates_md)
        self.assertIn("Create the primitive first, in its own commit, before using the control.", candidates_md)

        # Output is deterministic and verify passes
        res_verify = self.run_bp("verify", cwd=app_dir)
        self.assertEqual(res_verify.returncode, 0, f"Verify failed:\n{res_verify.stderr}\n{res_verify.stdout}")

    def test_form_controls_datepicker_shows_ok(self):
        """A fixture with a DatePicker shows ok."""
        app_dir = self.root / "app_ok"
        (app_dir / "src" / "components" / "ui").mkdir(parents=True, exist_ok=True)
        (app_dir / "src" / "views").mkdir(parents=True, exist_ok=True)

        # Themed primitive DatePicker exists
        (app_dir / "src" / "components" / "ui" / "DatePicker.tsx").write_text(
            "export function DatePicker() { return <div>Themed Date Picker</div>; }\n",
            encoding="utf-8"
        )
        # Usage uses the primitive, no native date input
        (app_dir / "src" / "views" / "BookingForm.tsx").write_text(
            "import { DatePicker } from '../components/ui/DatePicker';\n"
            "export function BookingForm() { return <form><DatePicker /></form>; }\n",
            encoding="utf-8"
        )
        (app_dir / "package.json").write_text('{"name": "test-app"}\n', encoding="utf-8")

        res_extract = self.run_bp("extract", "--areas", "ui", cwd=app_dir)
        self.assertEqual(res_extract.returncode, 0, res_extract.stderr)

        ui_md = (app_dir / ".agents" / "blueprints" / "ui.md").read_text(encoding="utf-8")
        self.assertIn("## Form controls", ui_md)
        # Date row has DatePicker and ok status
        self.assertIn("DatePicker.tsx", ui_md)
        self.assertIn("| date | src/components/ui/DatePicker.tsx | 0 | ok |", ui_md)

    def test_form_controls_dynamic_type_shows_review(self):
        """A dynamic type (type={x}) shows review."""
        app_dir = self.root / "app_dyn"
        (app_dir / "src" / "views").mkdir(parents=True, exist_ok=True)
        (app_dir / "src" / "views" / "DynamicForm.tsx").write_text(
            "export function DynamicForm({ kind }) { return <input type={kind} />; }\n",
            encoding="utf-8"
        )
        (app_dir / "package.json").write_text('{"name": "test-app"}\n', encoding="utf-8")

        res_extract = self.run_bp("extract", "--areas", "ui", cwd=app_dir)
        self.assertEqual(res_extract.returncode, 0, res_extract.stderr)

        ui_md = (app_dir / ".agents" / "blueprints" / "ui.md").read_text(encoding="utf-8")
        self.assertIn("review", ui_md)

    def test_build_ui_contains_form_controls_section(self):
        """The rendered build-ui text contains the Form controls section."""
        from render import skill_build_ui

        profile = {
            "project": {"name": "TestApp"},
            "design": {
                "enabled": True,
                "tokens_file": "src/tokens.css",
                "component_dirs": ["src/components/ui"]
            }
        }
        sname, desc, lines = skill_build_ui(profile, "TestApp")
        text = "\n".join(lines)
        self.assertIn("## Form controls", text)
        self.assertIn("1. Use the themed primitive.", text)
        self.assertIn("2. If none exists, build it first in `src/components/ui`", text)
        self.assertIn("3. Never use a native browser control that a themed primitive covers.", text)
        self.assertIn("4. Read the Form controls table with the blueprint show command", text)


if __name__ == "__main__":
    unittest.main()
