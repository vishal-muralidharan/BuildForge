"""Integration tests for legacy import routing, volume guard, and status grouping."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "legacy_import.py"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestLegacyImportRouting(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def run_cmd(self, *args):
        extra = []
        if args and args[0] == "inventory" and "--write" not in args:
            extra = ["--write"]
        cmd = [sys.executable, "-B", str(LEGACY_SCRIPT), *args, *extra]
        return subprocess.run(
            cmd,
            cwd=str(self.root),
            capture_output=True,
            text=True
        )

    def test_vendor_dup_in_references_yaml_skipped_and_listed(self):
        """Vendor-dup folder of 22 files listed in references.yaml is skipped and listed."""
        agents_dir = self.root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        vendor_dir = agents_dir / "skills" / "vendor-kit"
        vendor_dir.mkdir(parents=True, exist_ok=True)

        for i in range(1, 23):
            file_lines = [f"# Vendor Guide {i}"]
            for j in range(1, 30):
                file_lines.append(f"- Vendor rule item {i}-{j}: always format output.")
            (vendor_dir / f"doc_{i}.md").write_text("\n".join(file_lines) + "\n", encoding="utf-8")

        ref_yaml = agents_dir / "references.yaml"
        ref_yaml.write_text(
            yaml.safe_dump({
                "references": [
                    {"name": "vendor-kit", "path": ".agents/skills/vendor-kit", "type": "skill"}
                ]
            }),
            encoding="utf-8"
        )

        res = self.run_cmd("inventory", "--root", ".")
        self.assertEqual(res.returncode, 0, res.stderr)

        ledger_path = agents_dir / "legacy-parity.md"
        self.assertTrue(ledger_path.is_file())
        ledger_text = ledger_path.read_text(encoding="utf-8")

        self.assertIn("## Skipped Sources", ledger_text)
        self.assertIn(".agents/skills/vendor-kit", ledger_text)

    def test_unlisted_large_folder_trips_volume_guard(self):
        """Folder of 22 files not in references.yaml trips volume guard (>100 statements)."""
        agents_dir = self.root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        large_dir = agents_dir / "skills" / "massive-kit"
        large_dir.mkdir(parents=True, exist_ok=True)

        for i in range(1, 23):
            file_lines = [f"# Massive Doc {i}"]
            for j in range(1, 30):
                file_lines.append(f"- Directive {i}-{j}: ensure field check.")
            (large_dir / f"file_{i}.md").write_text("\n".join(file_lines) + "\n", encoding="utf-8")

        res = self.run_cmd("inventory", "--root", ".")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Warning:", res.stdout)
        self.assertIn("massive-kit", res.stdout)

        ledger_path = agents_dir / "legacy-parity.md"
        ledger_text = ledger_path.read_text(encoding="utf-8")

        self.assertIn("## Needs a Decision", ledger_text)
        self.assertIn(".agents/skills/massive-kit", ledger_text)
        self.assertNotIn("Directive 1-1", ledger_text)

    def test_local_skill_interface_table_routes_as_unit(self):
        """Local skill with a 40-line interface table routes as 1 unit."""
        agents_dir = self.root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        local_skill = agents_dir / "skills" / "local-ui"
        local_skill.mkdir(parents=True, exist_ok=True)

        table_lines = [
            "# UI Component Specs",
            "",
            "| Prop | Type | Default | Description |",
            "|---|---|---|---|"
        ]
        for i in range(1, 41):
            table_lines.append(f"| prop{i} | string | 'default{i}' | Description for prop {i} |")

        (local_skill / "SKILL.md").write_text("\n".join(table_lines) + "\n", encoding="utf-8")

        res = self.run_cmd("inventory", "--root", ".")
        self.assertEqual(res.returncode, 0, res.stderr)

        ledger_text = (agents_dir / "legacy-parity.md").read_text(encoding="utf-8")
        self.assertIn("derivable-ui", ledger_text)
        self.assertIn("L001", ledger_text)

        res_route = self.run_cmd("apply", "--route", "L001", "--root", ".")
        self.assertEqual(res_route.returncode, 0, res_route.stderr)
        self.assertIn("Routed to blueprint contracts: 1", res_route.stdout)

        ui_bp = agents_dir / "blueprints" / "ui.md"
        self.assertTrue(ui_bp.is_file())
        ui_text = ui_bp.read_text(encoding="utf-8")

        self.assertIn("<!-- BEGIN CUSTOM: contracts -->", ui_text)
        self.assertIn("- source: legacy L001", ui_text)
        self.assertIn("| prop1 |", ui_text)
        self.assertIn("| prop40 |", ui_text)

    def test_evidence_anchor_creation_for_existing_path(self):
        """Routing creates evidence anchor when statement names an existing path."""
        agents_dir = self.root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        local_skill = agents_dir / "skills" / "local-components"
        local_skill.mkdir(parents=True, exist_ok=True)

        comp_file = self.root / "src" / "components" / "Modal.tsx"
        comp_file.parent.mkdir(parents=True, exist_ok=True)
        comp_file.write_text("export const Modal = () => null;\n", encoding="utf-8")

        skill_content = (
            "# UI Primitives\n\n"
            "- The component catalog provides `<Modal />` defined in src/components/Modal.tsx:10.\n"
        )
        (local_skill / "SKILL.md").write_text(skill_content, encoding="utf-8")

        res_inv = self.run_cmd("inventory", "--root", ".")
        self.assertEqual(res_inv.returncode, 0, res_inv.stderr)

        res_route = self.run_cmd("apply", "--route", "L001", "--root", ".")
        self.assertEqual(res_route.returncode, 0, res_route.stderr)

        ui_bp = agents_dir / "blueprints" / "ui.md"
        self.assertTrue(ui_bp.is_file())
        ui_text = ui_bp.read_text(encoding="utf-8")

        self.assertIn("Evidence: src/components/Modal.tsx:10", ui_text)

    def test_status_grouping_and_selective_exit(self):
        """Status groups by folder/class and exits 1 only for local rules/derivables or decisions."""
        agents_dir = self.root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        local_skill = agents_dir / "skills" / "my-skill"
        local_skill.mkdir(parents=True, exist_ok=True)
        (local_skill / "SKILL.md").write_text(
            "# Local Rules\n\n- Always use strict typing for API responses.\n",
            encoding="utf-8"
        )

        res_inv = self.run_cmd("inventory", "--root", ".")
        self.assertEqual(res_inv.returncode, 0, res_inv.stderr)

        # Status should exit 1 naming local rule-candidate
        res_stat = self.run_cmd("status", "--root", ".")
        self.assertEqual(res_stat.returncode, 1)
        self.assertIn("pending local rule-candidate", res_stat.stdout)
        self.assertIn(".agents/skills/my-skill", res_stat.stdout)

        # Accept the local rule into profile
        prof_file = agents_dir / "project-profile.yaml"
        prof_file.write_text("rules: []\n", encoding="utf-8")
        res_apply = self.run_cmd("apply", "--accept", "L001", "--root", ".")
        self.assertEqual(res_apply.returncode, 0, res_apply.stderr)

        # Now status should exit 0
        res_stat2 = self.run_cmd("status", "--root", ".")
        self.assertEqual(res_stat2.returncode, 0, res_stat2.stdout)

    def test_route_class_derivable_with_and_without_yes(self):
        """apply --route-class derivable requires --yes to proceed."""
        agents_dir = self.root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        local_skill = agents_dir / "skills" / "tokens-skill"
        local_skill.mkdir(parents=True, exist_ok=True)
        (local_skill / "SKILL.md").write_text(
            "# Design Tokens\n\n- Use token --color-brand-primary for headers.\n",
            encoding="utf-8"
        )

        res_inv = self.run_cmd("inventory", "--root", ".")
        self.assertEqual(res_inv.returncode, 0, res_inv.stderr)

        # Without --yes: prints list and does NOT route
        res_no_yes = self.run_cmd("apply", "--route-class", "derivable", "--root", ".")
        self.assertEqual(res_no_yes.returncode, 0, res_no_yes.stderr)
        self.assertIn("Pass --yes to route", res_no_yes.stdout)
        self.assertIn("[L001] (derivable-tokens -> tokens.md)", res_no_yes.stdout)

        # Check ledger still pending
        ledger_text = (agents_dir / "legacy-parity.md").read_text(encoding="utf-8")
        self.assertIn("| pending |", ledger_text)

        # With --yes: routes batch
        res_yes = self.run_cmd("apply", "--route-class", "derivable", "--yes", "--root", ".")
        self.assertEqual(res_yes.returncode, 0, res_yes.stderr)
        self.assertIn("Routed to blueprint contracts: 1", res_yes.stdout)

        tokens_bp = agents_dir / "blueprints" / "tokens.md"
        self.assertTrue(tokens_bp.is_file())
        tokens_text = tokens_bp.read_text(encoding="utf-8")
        self.assertIn("--color-brand-primary", tokens_text)

    def test_legacy_source_files_never_modified(self):
        """Legacy source files are never modified by any import or routing command."""
        agents_dir = self.root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        local_skill = agents_dir / "skills" / "untouchable-skill"
        local_skill.mkdir(parents=True, exist_ok=True)
        skill_file = local_skill / "SKILL.md"
        skill_file.write_text(
            "# Untouchable Skill\n\n"
            "- Always validate user input.\n"
            "- Design tokens: --color-accent-teal is primary.\n",
            encoding="utf-8"
        )
        orig_hash = sha256_file(skill_file)

        self.run_cmd("inventory", "--root", ".")
        self.assertEqual(sha256_file(skill_file), orig_hash)

        self.run_cmd("batch", "--area", "security", "--root", ".")
        self.assertEqual(sha256_file(skill_file), orig_hash)

        self.run_cmd("apply", "--route", "L002", "--root", ".")
        self.assertEqual(sha256_file(skill_file), orig_hash)

        self.run_cmd("apply", "--drop", "L001", "--reason", "Not needed", "--root", ".")
        self.assertEqual(sha256_file(skill_file), orig_hash)

    def test_windows_path_normalization(self):
        """Evidence anchors normalize Windows backslashes to forward slashes."""
        agents_dir = self.root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        local_skill = agents_dir / "skills" / "win-skill"
        local_skill.mkdir(parents=True, exist_ok=True)

        comp_file = self.root / "src" / "components" / "Widget.tsx"
        comp_file.parent.mkdir(parents=True, exist_ok=True)
        comp_file.write_text("export const Widget = () => null;\n", encoding="utf-8")

        # Statement referencing path with backslashes
        skill_content = (
            "# Windows Path Skill\n\n"
            "- Primitives table: `<Widget />` in src\\components\\Widget.tsx:5.\n"
        )
        (local_skill / "SKILL.md").write_text(skill_content, encoding="utf-8")

        self.run_cmd("inventory", "--root", ".")
        self.run_cmd("apply", "--route", "L001", "--root", ".")

        ui_bp = agents_dir / "blueprints" / "ui.md"
        self.assertTrue(ui_bp.is_file())
        ui_text = ui_bp.read_text(encoding="utf-8")
        self.assertIn("Evidence: src/components/Widget.tsx:5", ui_text)
        self.assertNotIn("Evidence: src\\", ui_text)


if __name__ == "__main__":
    unittest.main()
