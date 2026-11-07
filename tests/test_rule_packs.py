#!/usr/bin/env python3
"""Comprehensive test suite for Build Forge rule packs and packs.py CLI."""
import copy
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKS_PY = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "packs.py"
RUNNER_PY = REPO_ROOT / "skills" / "rules-to-tests" / "scripts" / "run_rule_checks.py"
DEV_PY = REPO_ROOT / "scripts" / "dev.py"
PACKS_DIR = REPO_ROOT / "skills" / "project-bootstrap" / "references" / "rule-packs"

sys.path.insert(0, str(REPO_ROOT / "skills" / "project-bootstrap" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "rules-to-tests" / "scripts"))

import packs
import run_rule_checks


BASE_PROFILE = {
    "schema_version": 1,
    "project": {
        "name": "fixture-app",
        "summary": "Fixture application for testing rule packs",
        "mode": "existing",
        "platforms": ["web"]
    },
    "stack": {
        "language": "typescript",
        "framework": "react",
        "package_manager": "npm"
    },
    "commands": {
        "check": "npm test"
    },
    "design": {
        "component_dirs": ["src/components/ui"]
    },
    "structure": {
        "layers": [
            {"path": "src", "purpose": "Application source"}
        ],
        "tests": "tests"
    },
    "docs": {
        "skills_dir": ".agents/skills",
        "agents_file": "AGENTS.md",
        "repo_map": ".agents/repo-map.md"
    },
    "git": {
        "commit_format": "<type>: <subject>",
        "push": "never"
    },
    "rules": [],
    "rule_packs": []
}


class TestRulePacks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bf-test-packs-")
        self.tmp_path = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_fixture_profile(self, data, root: Path = None):
        target_root = root or self.tmp_path
        prof_dir = target_root / ".agents"
        prof_dir.mkdir(parents=True, exist_ok=True)
        prof_file = prof_dir / "project-profile.yaml"
        prof_file.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
        return prof_file

    def test_lint_passes_for_all_nine_packs(self):
        """packs.py lint passes for all 9 curated rule packs with 0 errors."""
        self.assertTrue(PACKS_DIR.is_dir(), f"Rule packs directory missing: {PACKS_DIR}")
        pack_files = sorted(PACKS_DIR.glob("*.yaml"))
        self.assertEqual(len(pack_files), 9, f"Expected exactly 9 packs, found {len(pack_files)}")

        errors = packs.lint_packs(PACKS_DIR)
        self.assertEqual(len(errors), 0, f"packs.py lint failed with errors: {errors}")

        # Also test via subprocess CLI
        cmd = [sys.executable, "-B", str(PACKS_PY), "lint"]
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"packs.py lint CLI failed:\n{res.stderr or res.stdout}")
        self.assertIn("All 9 rule packs passed lint checks with 0 errors", res.stdout)

    def test_lint_fails_on_broken_packs(self):
        """packs.py lint catches schema violations on broken fixture packs."""
        broken_dir = self.tmp_path / "broken-packs"
        broken_dir.mkdir()

        # Fixture 1: Pack with > 12 rules
        p1 = {
            "id": "too-many-rules",
            "version": 1,
            "title": "Too Many Rules",
            "summary": "Summary line 1\nSummary line 2",
            "rules": [
                {
                    "id": f"rule-{i}",
                    "area": "design",
                    "text": f"Rule number {i} text.",
                    "enforced_by": "manual"
                }
                for i in range(13)
            ]
        }
        (broken_dir / "too-many-rules.yaml").write_text(yaml.dump(p1), encoding="utf-8")

        # Fixture 2: Rule text > 160 characters
        p2 = {
            "id": "long-text",
            "version": 1,
            "title": "Long Text",
            "summary": "Summary 1\nSummary 2",
            "rules": [
                {
                    "id": "rule-long",
                    "area": "verify",
                    "text": "This is an excessively long rule sentence designed to violate the strict 160 character maximum rule text length enforced by Build Forge rule packs linting check.",
                    "enforced_by": "manual"
                }
            ]
        }
        (broken_dir / "long-text.yaml").write_text(yaml.dump(p2), encoding="utf-8")

        # Fixture 3: Duplicate rule id across packs
        p3 = {
            "id": "dup-id",
            "version": 1,
            "title": "Dup ID",
            "summary": "Summary 1\nSummary 2",
            "rules": [
                {
                    "id": "rule-long",  # Same id as in long-text.yaml
                    "area": "verify",
                    "text": "Duplicate rule id from long-text.",
                    "enforced_by": "manual"
                }
            ]
        }
        (broken_dir / "dup-id.yaml").write_text(yaml.dump(p3), encoding="utf-8")

        # Fixture 4: Invalid area
        p4 = {
            "id": "bad-area",
            "version": 1,
            "title": "Bad Area",
            "summary": "Summary 1\nSummary 2",
            "rules": [
                {
                    "id": "rule-bad-area",
                    "area": "invalid_area_value",
                    "text": "Valid sentence text here.",
                    "enforced_by": "manual"
                }
            ]
        }
        (broken_dir / "bad-area.yaml").write_text(yaml.dump(p4), encoding="utf-8")

        # Fixture 5: Em dash or en dash in text
        p5 = {
            "id": "has-em-dash",
            "version": 1,
            "title": "Has Dash",
            "summary": "Summary 1\nSummary 2",
            "rules": [
                {
                    "id": "rule-em-dash",
                    "area": "design",
                    "text": "Never use native controls \u2014 always use primitives.",
                    "enforced_by": "manual"
                }
            ]
        }
        (broken_dir / "has-em-dash.yaml").write_text(yaml.dump(p5), encoding="utf-8")

        # Fixture 6: Check missing hint or examples
        p6 = {
            "id": "missing-hint",
            "version": 1,
            "title": "Missing Hint",
            "summary": "Summary 1\nSummary 2",
            "rules": [
                {
                    "id": "rule-no-hint",
                    "area": "design",
                    "text": "Never use select elements.",
                    "enforced_by": "test",
                    "check": {
                        "type": "forbid",
                        "pattern": "<select\\b"
                    }
                }
            ]
        }
        (broken_dir / "missing-hint.yaml").write_text(yaml.dump(p6), encoding="utf-8")

        errors = packs.lint_packs(broken_dir)
        self.assertGreaterEqual(len(errors), 6)

        err_text = "\n".join(errors)
        self.assertIn("exceeds limit of 12", err_text)
        self.assertIn("exceeds limit of 160 characters", err_text)
        self.assertIn("duplicate rule id", err_text)
        self.assertIn("not a valid area", err_text)
        self.assertIn("contains em or en dashes", err_text)
        self.assertIn("must include a non-empty hint", err_text)
        self.assertIn("must include examples", err_text)

    def test_pack_rules_selftest_passes(self):
        """Every rule with a check passes selftest across all 9 packs."""
        pack_files = sorted(PACKS_DIR.glob("*.yaml"))
        total_checks_tested = 0

        for pf in pack_files:
            data = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
            for r in data.get("rules", []):
                chk = r.get("check")
                if not chk:
                    continue
                total_checks_tested += 1
                rid = r["id"]
                ctype = chk["type"]
                exs = chk.get("examples", {})
                bad_list = exs.get("bad", [])
                good_list = exs.get("good", [])

                self.assertGreater(len(bad_list), 0, f"{pf.name} rule {rid} has no bad examples")
                self.assertGreater(len(good_list), 0, f"{pf.name} rule {rid} has no good examples")
                self.assertTrue(chk.get("hint"), f"{pf.name} rule {rid} missing hint")

                if ctype == "forbid":
                    pat = chk["pattern"]
                    rx = re.compile(pat)
                    for bad in bad_list:
                        self.assertIsNotNone(
                            rx.search(bad),
                            f"{pf.name} rule {rid}: bad example failed to match pattern '{pat}': {bad}"
                        )
                    for good in good_list:
                        self.assertIsNone(
                            rx.search(good),
                            f"{pf.name} rule {rid}: good example unexpectedly matched pattern '{pat}': {good}"
                        )
                elif ctype == "forbid_file":
                    from run_rule_checks import matching
                    inc = chk["include"]
                    exc = chk.get("exclude", [])
                    for bad in bad_list:
                        matched = matching([bad], inc, exc)
                        self.assertIn(bad, matched, f"{pf.name} rule {rid}: bad file was not flagged: {bad}")
                    for good in good_list:
                        matched = matching([good], inc, exc)
                        self.assertNotIn(good, matched, f"{pf.name} rule {rid}: good file was flagged: {good}")

        self.assertGreaterEqual(total_checks_tested, 10, "Expected at least 10 rule checks across packs")

    def test_every_check_proven_both_sides_on_fixtures(self):
        """Every rule check is verified against violating and clean fixture files."""
        # 1. Native controls check
        native_pack = packs.load_pack("native-controls", PACKS_DIR)
        select_rule = next(r for r in native_pack["rules"] if r["id"] == "ui-no-native-selects")

        # Violating fixture
        violating_dir = self.tmp_path / "violating-app"
        violating_dir.mkdir()
        (violating_dir / "src").mkdir()
        (violating_dir / "src" / "page.tsx").write_text("<select name='country'></select>", encoding="utf-8")
        prof_violating = copy.deepcopy(BASE_PROFILE)
        prof_violating["rules"] = [copy.deepcopy(select_rule)]
        prof_violating["rules"][0]["check"]["exclude"] = ["src/components/ui/**"]
        self.write_fixture_profile(prof_violating, violating_dir)

        runner_cmd = [sys.executable, "-B", str(RUNNER_PY), "--profile", ".agents/project-profile.yaml", "--root", str(violating_dir)]
        res_fail = subprocess.run(runner_cmd, capture_output=True, text=True)
        self.assertEqual(res_fail.returncode, 1, "Expected run_rule_checks to fail on violating fixture")
        self.assertIn("ui-no-native-selects", res_fail.stdout)
        self.assertIn("Hint: Use the themed Select primitive", res_fail.stdout)

        # Clean fixture
        clean_dir = self.tmp_path / "clean-app"
        clean_dir.mkdir()
        (clean_dir / "src").mkdir()
        (clean_dir / "src" / "page.tsx").write_text("<Select name='country'></Select>", encoding="utf-8")
        (clean_dir / "src" / "components" / "ui").mkdir(parents=True)
        (clean_dir / "src" / "components" / "ui" / "PrimitiveSelect.tsx").write_text("<select></select>", encoding="utf-8")
        prof_clean = copy.deepcopy(BASE_PROFILE)
        prof_clean["rules"] = [copy.deepcopy(select_rule)]
        prof_clean["rules"][0]["check"]["exclude"] = ["src/components/ui/**"]
        self.write_fixture_profile(prof_clean, clean_dir)

        runner_cmd_clean = [sys.executable, "-B", str(RUNNER_PY), "--profile", ".agents/project-profile.yaml", "--root", str(clean_dir)]
        res_pass = subprocess.run(runner_cmd_clean, capture_output=True, text=True)
        self.assertEqual(res_pass.returncode, 0, f"Expected run_rule_checks to pass on clean fixture:\n{res_pass.stdout}")

    def test_packs_apply_works_on_fixture_repo(self):
        """packs.py apply adds rules with pack tag, updates rule_packs, and routes verify_checks."""
        app_dir = self.tmp_path / "apply-app"
        app_dir.mkdir()
        (app_dir / "src" / "components" / "ui").mkdir(parents=True)
        self.write_fixture_profile(copy.deepcopy(BASE_PROFILE), app_dir)

        cmd = [sys.executable, "-B", str(PACKS_PY), "apply", "native-controls", "--root", str(app_dir), "--yes"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"packs.py apply failed:\n{res.stderr or res.stdout}")

        # Verify profile content
        prof = yaml.safe_load((app_dir / ".agents" / "project-profile.yaml").read_text(encoding="utf-8"))
        rule_ids = [r["id"] for r in prof.get("rules", [])]
        self.assertIn("ui-no-native-pickers", rule_ids)
        self.assertIn("ui-no-native-selects", rule_ids)
        self.assertIn("ui-no-browser-dialogs", rule_ids)

        # Check pack attribution
        for r in prof.get("rules", []):
            self.assertEqual(r.get("pack"), "native-controls@1")

        # Check rule_packs list updated
        self.assertEqual(prof.get("rule_packs"), [{"id": "native-controls", "version": 1}])

        # Check verify checks routed
        qg = prof.get("quality_gates", [])
        self.assertTrue(any("visual design tokens" in q for q in qg))

    def test_user_edited_rule_text_preserves_conflict(self):
        """If a user edits a pack rule's text, packs.py apply preserves the user text and flags conflict."""
        app_dir = self.tmp_path / "edit-app"
        app_dir.mkdir()
        (app_dir / "src" / "components" / "ui").mkdir(parents=True)
        self.write_fixture_profile(copy.deepcopy(BASE_PROFILE), app_dir)

        # First apply
        subprocess.run([sys.executable, "-B", str(PACKS_PY), "apply", "native-controls", "--root", str(app_dir), "--yes"], check=True)

        # User edits rule text
        prof_file = app_dir / ".agents" / "project-profile.yaml"
        prof = yaml.safe_load(prof_file.read_text(encoding="utf-8"))
        for r in prof["rules"]:
            if r["id"] == "ui-no-native-selects":
                r["text"] = "Custom user rule for select elements."
        prof_file.write_text(yaml.dump(prof, sort_keys=False), encoding="utf-8")

        # Re-apply
        cmd = [sys.executable, "-B", str(PACKS_PY), "apply", "native-controls", "--root", str(app_dir), "--yes"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("conflict", res.stdout.lower())

        # Assert user text was not overwritten
        prof_after = yaml.safe_load(prof_file.read_text(encoding="utf-8"))
        rule_select = next(r for r in prof_after["rules"] if r["id"] == "ui-no-native-selects")
        self.assertEqual(rule_select["text"], "Custom user rule for select elements.")

    def test_dropped_pack_rules_persistence(self):
        """If a rule is in dropped_pack_rules, packs.py apply never re-adds it."""
        app_dir = self.tmp_path / "dropped-app"
        app_dir.mkdir()
        (app_dir / "src" / "components" / "ui").mkdir(parents=True)
        prof_data = copy.deepcopy(BASE_PROFILE)
        prof_data["dropped_pack_rules"] = ["ui-no-browser-dialogs"]
        self.write_fixture_profile(prof_data, app_dir)

        cmd = [sys.executable, "-B", str(PACKS_PY), "apply", "native-controls", "--root", str(app_dir), "--yes"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("ui-no-browser-dialogs", res.stdout)
        self.assertIn("dropped", res.stdout.lower())

        prof_after = yaml.safe_load((app_dir / ".agents" / "project-profile.yaml").read_text(encoding="utf-8"))
        rule_ids = [r["id"] for r in prof_after.get("rules", [])]
        self.assertNotIn("ui-no-browser-dialogs", rule_ids)
        self.assertIn("ui-no-native-selects", rule_ids)

    def test_packs_diff_shows_version_bump(self):
        """packs.py diff reports added, removed, or changed rules across pack versions."""
        app_dir = self.tmp_path / "diff-app"
        app_dir.mkdir()
        (app_dir / "src" / "components" / "ui").mkdir(parents=True)
        self.write_fixture_profile(copy.deepcopy(BASE_PROFILE), app_dir)

        # Apply native-controls v1
        subprocess.run([sys.executable, "-B", str(PACKS_PY), "apply", "native-controls", "--root", str(app_dir), "--yes"], check=True)

        # Simulate custom pack dir with v2 having an added rule
        custom_packs_dir = self.tmp_path / "custom-packs"
        custom_packs_dir.mkdir()
        v2_data = packs.load_pack("native-controls", PACKS_DIR)
        v2_data["version"] = 2
        v2_data["rules"].append({
            "id": "ui-no-native-file-inputs",
            "area": "design",
            "text": "Never use native browser file inputs without the custom file upload primitive.",
            "enforced_by": "manual"
        })
        (custom_packs_dir / "native-controls.yaml").write_text(yaml.dump(v2_data), encoding="utf-8")

        # Test diff with custom pack dir
        cmd = [
            sys.executable, "-B", str(PACKS_PY), "diff", "native-controls",
            "--root", str(app_dir), "--packs-dir", str(custom_packs_dir)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("v1", res.stdout)
        self.assertIn("v2", res.stdout)
        self.assertIn("ui-no-native-file-inputs", res.stdout)

    def test_violation_probe_without_write(self):
        """packs.py plan probes repository code and does not modify project-profile.yaml."""
        app_dir = self.tmp_path / "probe-app"
        app_dir.mkdir()
        (app_dir / "src").mkdir()
        (app_dir / "src" / "form.tsx").write_text("<select name='country'></select>", encoding="utf-8")
        prof_file = self.write_fixture_profile(copy.deepcopy(BASE_PROFILE), app_dir)
        original_content = prof_file.read_text(encoding="utf-8")

        # Run plan (probe)
        cmd = [sys.executable, "-B", str(PACKS_PY), "plan", "native-controls", "--root", str(app_dir)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("src/form.tsx", res.stdout)
        self.assertIn("ui-no-native-selects", res.stdout)

        # Confirm profile was not modified
        self.assertEqual(prof_file.read_text(encoding="utf-8"), original_content)

    def test_component_dirs_variable_expansion_and_skip(self):
        """{{component_dirs}} expands dynamically from design.component_dirs or skips if empty."""
        # Case A: Expansion
        app_dir_a = self.tmp_path / "expand-app"
        app_dir_a.mkdir()
        (app_dir_a / "src" / "primitives").mkdir(parents=True)
        prof_a = copy.deepcopy(BASE_PROFILE)
        prof_a["design"]["component_dirs"] = ["src/primitives"]
        self.write_fixture_profile(prof_a, app_dir_a)

        subprocess.run([sys.executable, "-B", str(PACKS_PY), "apply", "native-controls", "--root", str(app_dir_a), "--yes"], check=True)
        prof_after_a = yaml.safe_load((app_dir_a / ".agents" / "project-profile.yaml").read_text(encoding="utf-8"))
        select_rule = next(r for r in prof_after_a["rules"] if r["id"] == "ui-no-native-selects")
        self.assertIn("src/primitives/**", select_rule["check"]["exclude"])

        # Case B: Skip when empty
        app_dir_b = self.tmp_path / "skip-app"
        app_dir_b.mkdir()
        prof_b = copy.deepcopy(BASE_PROFILE)
        prof_b["design"]["component_dirs"] = []
        self.write_fixture_profile(prof_b, app_dir_b)

        cmd = [sys.executable, "-B", str(PACKS_PY), "apply", "native-controls", "--root", str(app_dir_b), "--yes"]
        res_b = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res_b.returncode, 0)
        self.assertIn("skipped", res_b.stdout.lower())

        prof_after_b = yaml.safe_load((app_dir_b / ".agents" / "project-profile.yaml").read_text(encoding="utf-8"))
        rule_ids_b = [r["id"] for r in prof_after_b.get("rules", [])]
        self.assertNotIn("ui-no-native-selects", rule_ids_b)
        self.assertNotIn("ui-no-native-pickers", rule_ids_b)
        # ui-no-browser-dialogs does not use component_dirs so it should be added
        self.assertIn("ui-no-browser-dialogs", rule_ids_b)

    def test_dev_recipe_verify_add_rule_pack(self):
        """scripts/dev.py recipe verify add-rule-pack passes for packaged rule packs."""
        cmd = [
            sys.executable, "-B", str(DEV_PY), "recipe", "verify", "add-rule-pack",
            "--arg", "pack_name=native-controls"
        ]
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Recipe verify failed:\n{res.stderr or res.stdout}")
        self.assertIn("0 missing touchpoint(s)", res.stdout)


if __name__ == "__main__":
    unittest.main()
