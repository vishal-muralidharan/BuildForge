"""Integration test for field adoption: 10-step sequence, salvage, adopt, and non-generated line survival."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SRC = REPO_ROOT / "tests" / "fixtures" / "field-adoption"
VALIDATE_SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "validate_profile.py"
LEGACY_SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "legacy_import.py"
REFS_SCRIPT = REPO_ROOT / "skills" / "extend-pipeline" / "scripts" / "refs.py"
RENDER_SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "render.py"
BLUEPRINT_SCRIPT = REPO_ROOT / "skills" / "project-blueprints" / "scripts" / "blueprint.py"
CHECK_SYNC_SCRIPT = REPO_ROOT / "skills" / "sync-skills-and-docs" / "scripts" / "check_sync.py"
CLI_SCRIPT = REPO_ROOT / "bin" / "build-forge.js"


def extract_non_generated_lines(file_path: Path) -> list:
    """Extract non-generated content lines outside standard boilerplate/generated markers."""
    if not file_path.is_file():
        return []
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    custom_lines = []
    in_frontmatter = False
    in_generated = False
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if idx == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if "<!-- GENERATED" in stripped:
            in_generated = True
            continue
        if "<!-- END GENERATED" in stripped:
            in_generated = False
            continue
        if in_generated:
            continue
        if stripped.startswith("<!-- BEGIN CUSTOM") or stripped.startswith("<!-- END CUSTOM"):
            continue
        if not stripped or stripped.startswith("#"):
            continue
        custom_lines.append(stripped)
    return custom_lines


class TestFieldAdoption(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        # Copy fixture into temporary test workspace
        shutil.copytree(FIXTURE_SRC, self.root, dirs_exist_ok=True)

    def tearDown(self):
        self.td.cleanup()

    def run_py(self, script: Path, *args, cwd=None):
        cmd = [sys.executable, "-B", str(script), *args]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            cmd,
            cwd=str(cwd or self.root),
            capture_output=True,
            text=True,
            env=env
        )

    def run_node(self, script: Path, *args, cwd=None):
        cmd = ["node", str(script), *args]
        return subprocess.run(
            cmd,
            cwd=str(cwd or self.root),
            capture_output=True,
            text=True
        )

    def test_ten_step_field_adoption_sequence(self):
        """Execute the 10-step field adoption sequence and verify strict invariants."""
        # Collect baseline non-generated lines from original files
        old_custom_lines = []
        for sf in [
            self.root / ".agents" / "skills" / "app-ui" / "SKILL.md",
            self.root / ".agents" / "skills" / "app-tokens" / "SKILL.md",
            self.root / ".agents" / "skills" / "app-data" / "SKILL.md"
        ]:
            old_custom_lines.extend(extract_non_generated_lines(sf))
        self.assertTrue(len(old_custom_lines) > 200, f"Expected > 200 custom lines, got {len(old_custom_lines)}")

        # Step 1: validate_profile --strict-paths (flags the unmatched glob and exits 1)
        res_v = self.run_py(
            VALIDATE_SCRIPT,
            "--profile", ".agents/project-profile.yaml",
            "--root", ".",
            "--strict-paths"
        )
        self.assertEqual(res_v.returncode, 1, "validate_profile --strict-paths must exit 1 on unmatched glob")
        self.assertIn("src/legacy_nonexistent", res_v.stdout + res_v.stderr)

        # Step 2: legacy inventory (exits 0)
        res_inv = self.run_py(LEGACY_SCRIPT, "inventory", "--root", ".")
        self.assertEqual(res_inv.returncode, 0, res_inv.stderr)
        ledger_path = self.root / ".agents" / "legacy-parity.md"
        self.assertTrue(ledger_path.is_file())
        ledger_text = ledger_path.read_text(encoding="utf-8")
        self.assertIn("## Skipped Sources", ledger_text)

        # Assert: the legacy status shows no vendor statements
        res_stat = self.run_py(LEGACY_SCRIPT, "status", "--root", ".")
        self.assertNotIn("(vendor-dup)", res_stat.stdout)
        self.assertNotIn("(reference)", res_stat.stdout)
        self.assertNotIn(".agents/skills/vendor-listed", res_stat.stdout)

        # Step 3: refs dedupe plan (exits 0)
        res_dedupe = self.run_py(REFS_SCRIPT, "dedupe", "--root", ".")
        self.assertEqual(res_dedupe.returncode, 0, res_dedupe.stderr)
        self.assertIn("Dual-homed skill collisions detected", res_dedupe.stdout)

        # Step 4: render --update (skips unstamped, exits 3 per D7)
        res_upd = self.run_py(
            RENDER_SCRIPT,
            "--profile", ".agents/project-profile.yaml",
            "--root", ".",
            "--update",
            "--allow-dirty"
        )
        self.assertIn(res_upd.returncode, (1, 3), "render --update must refuse or skip on unstamped or hand-edited files")
        self.assertTrue("refused" in res_upd.stdout.lower() or "skipped" in res_upd.stdout.lower())

        # Step 5: render --salvage (exits 0)
        res_salvage = self.run_py(
            RENDER_SCRIPT,
            "--profile", ".agents/project-profile.yaml",
            "--root", ".",
            "--salvage",
            "--allow-dirty"
        )
        self.assertEqual(res_salvage.returncode, 0, res_salvage.stderr)

        # Step 6: blueprint adopt (exits 0)
        res_adopt = self.run_py(
            BLUEPRINT_SCRIPT,
            "adopt",
            "--from", ".agents/skills/app-ui/SKILL.md",
            "--block", "oversized_contracts",
            "--area", "ui",
            "--root", "."
        )
        self.assertEqual(res_adopt.returncode, 0, res_adopt.stderr)
        self.assertIn("Adopted custom block", res_adopt.stdout)

        # Also extract blueprints so manifest and derived facts are up to date
        self.run_py(BLUEPRINT_SCRIPT, "extract", "--root", ".")

        # Step 7: check_sync (reports 0 false warnings and exactly 1 true path warning)
        res_sync = self.run_py(
            CHECK_SYNC_SCRIPT,
            "--profile", ".agents/project-profile.yaml",
            "--root", "."
        )
        sync_out = res_sync.stdout + res_sync.stderr
        # Assert: 0 false warnings (e.g. no spurious missing skill warnings for Scope guide rows: skills, docs, ui)
        self.assertNotIn("skill file not found: skills", sync_out)
        self.assertNotIn("skill file not found: docs", sync_out)
        self.assertNotIn("skill file not found: ui", sync_out)
        # Assert: exactly 1 true path warning for src/legacy_nonexistent
        self.assertIn("src/legacy_nonexistent", sync_out)
        self.assertEqual(sync_out.count("src/legacy_nonexistent"), 1)

        # Step 8: blueprint drift (exits 0)
        res_drift = self.run_py(BLUEPRINT_SCRIPT, "drift", "--root", ".")
        self.assertEqual(res_drift.returncode, 0, f"drift failed: {res_drift.stdout}\n{res_drift.stderr}")
        self.assertIn("drift check passed", res_drift.stdout.lower())

        # Step 9: doctor if it exists (exits 0)
        res_doc = self.run_node(CLI_SCRIPT, "doctor", cwd=self.root)
        self.assertEqual(res_doc.returncode, 0, f"doctor failed: {res_doc.stdout}")
        self.assertIn("Build Forge Doctor", res_doc.stdout)

        # Step 10: verify (exits 0)
        res_ver = self.run_node(CLI_SCRIPT, "verify", cwd=self.root)
        self.assertEqual(res_ver.returncode, 0, f"verify failed: {res_ver.stdout}\n{res_ver.stderr}")
        self.assertIn("Verify ok", res_ver.stdout)

        # Property test: no non-generated line from the old files is missing from the new files
        all_new_text = []
        for p in self.root.rglob("*"):
            if p.is_file() and not p.name.startswith(".git"):
                try:
                    all_new_text.append(p.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    pass
        combined_new_text = "\n".join(all_new_text)

        missing_lines = []
        for line in old_custom_lines:
            if line not in combined_new_text:
                missing_lines.append(line)

        self.assertEqual(
            missing_lines,
            [],
            f"{len(missing_lines)} non-generated line(s) lost during adoption: {missing_lines[:5]}"
        )


if __name__ == "__main__":
    unittest.main()
