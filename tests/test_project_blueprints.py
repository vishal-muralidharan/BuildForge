"""Integration tests for project-blueprints extraction, verification, staleness, and budgeting."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BP_SCRIPT_DIR = REPO_ROOT / "skills" / "project-blueprints" / "scripts"
if str(BP_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(BP_SCRIPT_DIR))

BP_SCRIPT = BP_SCRIPT_DIR / "blueprint.py"
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


if __name__ == "__main__":
    unittest.main()
