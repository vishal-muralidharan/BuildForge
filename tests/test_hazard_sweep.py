#!/usr/bin/env python3
"""Tests for web-hazards pack, hazard sweep, exceptions, and incident-to-rule workflow."""
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
sys.path.insert(0, str(REPO_ROOT / "skills" / "rules-to-tests" / "scripts"))
VAL_PY = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "validate_profile.py"
RUNNER_PY = REPO_ROOT / "skills" / "rules-to-tests" / "scripts" / "run_rule_checks.py"
SWEEP_PY = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "hazard_sweep.py"
PACK_BOOTSTRAP = REPO_ROOT / "skills" / "project-bootstrap" / "assets" / "packs" / "web-hazards.yaml"
PACK_RULES = REPO_ROOT / "skills" / "rules-to-tests" / "assets" / "packs" / "web-hazards.yaml"


class TestHazardSweep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_web_hazards_pack_rules_match_bad_and_reject_good(self):
        """Each new rule matches every bad example and rejects every good example."""
        for pack_path in (PACK_BOOTSTRAP, PACK_RULES):
            self.assertTrue(pack_path.is_file(), f"Pack file not found: {pack_path}")
            data = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
            rules = data.get("rules", [])
            self.assertGreaterEqual(len(rules), 4)
            self.assertLessEqual(len(rules), 6)

            for r in rules:
                rid = r["id"]
                chk = r["check"]
                t = chk["type"]
                exs = chk.get("examples", {})
                bad_list = exs.get("bad", [])
                good_list = exs.get("good", [])
                self.assertGreater(len(bad_list), 0, f"Rule {rid} has no bad examples")
                self.assertGreater(len(good_list), 0, f"Rule {rid} has no good examples")
                self.assertIn("hint", chk, f"Rule {rid} missing hint")

                if t == "forbid":
                    rx = re.compile(chk["pattern"])
                    for b in bad_list:
                        self.assertIsNotNone(
                            rx.search(b),
                            f"Rule {rid}: bad example did not match pattern '{chk['pattern']}': {b}"
                        )
                    for g in good_list:
                        self.assertIsNone(
                            rx.search(g),
                            f"Rule {rid}: good example unexpectedly matched pattern: {g}"
                        )
                elif t == "forbid_file":
                    from run_rule_checks import matching
                    inc = chk["include"]
                    exc = chk.get("exclude", [])
                    for b in bad_list:
                        matched = matching([b], inc, exc)
                        self.assertIn(b, matched, f"Rule {rid}: bad file example was not flagged: {b}")
                    for g in good_list:
                        matched = matching([g], inc, exc)
                        self.assertNotIn(g, matched, f"Rule {rid}: good file example was flagged: {g}")

    def test_run_rule_checks_selftest(self):
        """run_rule_checks.py --selftest passes on the web-hazards pack."""
        data = yaml.safe_load(PACK_BOOTSTRAP.read_text(encoding="utf-8"))
        prof_data = {
            "schema_version": 1,
            "rules": data["rules"]
        }
        prof_file = self.tmp_path / "project-profile.yaml"
        prof_file.write_text(yaml.dump(prof_data), encoding="utf-8")

        res = subprocess.run(
            [sys.executable, "-B", str(RUNNER_PY), "--profile", str(prof_file), "--selftest"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Selftest failed: {res.stderr}\n{res.stdout}")
        self.assertIn("Selftest passed", res.stdout)

    def test_run_rule_checks_explain(self):
        """run_rule_checks.py --explain <id> prints rule metadata, pattern, and examples."""
        data = yaml.safe_load(PACK_BOOTSTRAP.read_text(encoding="utf-8"))
        prof_data = {
            "schema_version": 1,
            "rules": data["rules"]
        }
        prof_file = self.tmp_path / "project-profile.yaml"
        prof_file.write_text(yaml.dump(prof_data), encoding="utf-8")

        res = subprocess.run(
            [sys.executable, "-B", str(RUNNER_PY), "--profile", str(prof_file), "--explain", "web-no-console"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Rule: web-no-console", res.stdout)
        self.assertIn("Hint: Remove console.log", res.stdout)
        self.assertIn("Check type: forbid", res.stdout)

    def test_run_rule_checks_exceptions_and_list(self):
        """Exceptions are excluded from checks and reported in --list."""
        src_dir = self.tmp_path / "src"
        src_dir.mkdir(parents=True)
        bad_file = src_dir / "legacy.js"
        bad_file.write_text('console.log("legacy logging");\n', encoding="utf-8")

        prof_without_exc = {
            "schema_version": 1,
            "rules": [
                {
                    "id": "web-no-console",
                    "area": "verify",
                    "text": "No console logging.",
                    "enforced_by": "test",
                    "check": {
                        "type": "forbid",
                        "pattern": r"(?<![\w.$])console\.(?:log|debug)\s*\(",
                        "include": ["src/**/*.js"]
                    }
                }
            ]
        }
        prof_file = self.tmp_path / "project-profile.yaml"
        prof_file.write_text(yaml.dump(prof_without_exc), encoding="utf-8")

        # Without exception: fails
        res_fail = subprocess.run(
            [sys.executable, "-B", str(RUNNER_PY), "--profile", str(prof_file), "--root", str(self.tmp_path)],
            capture_output=True,
            text=True
        )
        self.assertNotEqual(res_fail.returncode, 0)
        self.assertIn("FAIL web-no-console", res_fail.stdout)

        # With exception: passes
        prof_with_exc = {
            "schema_version": 1,
            "rules": [
                {
                    "id": "web-no-console",
                    "area": "verify",
                    "text": "No console logging.",
                    "enforced_by": "test",
                    "exceptions": [
                        {
                            "path": "src/legacy.js",
                            "reason": "Legacy code pending logger migration"
                        }
                    ],
                    "check": {
                        "type": "forbid",
                        "pattern": r"(?<![\w.$])console\.(?:log|debug)\s*\(",
                        "include": ["src/**/*.js"]
                    }
                }
            ]
        }
        prof_file.write_text(yaml.dump(prof_with_exc), encoding="utf-8")

        res_pass = subprocess.run(
            [sys.executable, "-B", str(RUNNER_PY), "--profile", str(prof_file), "--root", str(self.tmp_path)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_pass.returncode, 0)
        self.assertIn("PASS web-no-console", res_pass.stdout)

        # Check --list reports exception count
        res_list = subprocess.run(
            [sys.executable, "-B", str(RUNNER_PY), "--profile", str(prof_file), "--list"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_list.returncode, 0)
        self.assertIn("web-no-console: forbid (1 exception)", res_list.stdout)

    def test_validate_profile_exceptions_schema(self):
        """validate_profile.py enforces exceptions schema and reasons."""
        base_prof = {
            "schema_version": 1,
            "project": {"name": "test", "summary": "test app", "mode": "new", "platforms": ["web"]},
            "stack": {"language": "js", "framework": "none", "package_manager": "npm"},
            "commands": {"check": "echo ok"},
            "structure": {"layers": [{"path": "src", "purpose": "source"}], "tests": "colocated"},
            "naming": [{"item": "file", "style": "kebab-case", "example": "foo"}],
            "git": {"push": "never", "commit_format": "<type>: <subject>"},
            "docs": {"skills_dir": ".agents/skills", "agents_file": "AGENTS.md", "repo_map": ".agents/repo-map.md"},
            "rules": [
                {
                    "id": "web-no-raw-eval",
                    "area": "security",
                    "text": "No eval.",
                    "enforced_by": "test",
                    "exceptions": [
                        {"path": "src/bad.js", "reason": ""}
                    ],
                    "check": {
                        "type": "forbid",
                        "pattern": r"eval\(",
                        "include": ["src/**/*.js"]
                    }
                }
            ]
        }
        prof_file = self.tmp_path / "project-profile.yaml"
        prof_file.write_text(yaml.dump(base_prof), encoding="utf-8")

        # Empty reason -> error
        res = subprocess.run(
            [sys.executable, "-B", str(VAL_PY), "--profile", str(prof_file)],
            capture_output=True,
            text=True
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("reason is required and non-empty", res.stdout)

        # Valid reason but non-existent file with --root -> warning
        base_prof["rules"][0]["exceptions"][0]["reason"] = "Valid migration reason"
        prof_file.write_text(yaml.dump(base_prof), encoding="utf-8")

        res_warn = subprocess.run(
            [sys.executable, "-B", str(VAL_PY), "--profile", str(prof_file), "--root", str(self.tmp_path)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_warn.returncode, 0)
        self.assertIn("exception path matches no file", res_warn.stdout)

    def test_hazard_sweep_clean_repo(self):
        """hazard_sweep.py accepts a clean repository with 0 violations."""
        src = self.tmp_path / "src"
        src.mkdir(parents=True)
        (src / "app.js").write_text('console.error("ok error");\n', encoding="utf-8")
        (self.tmp_path / "package.json").write_text('{"name": "clean-app"}\n', encoding="utf-8")

        res = subprocess.run(
            [sys.executable, "-B", str(SWEEP_PY), str(self.tmp_path), "--json"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        checklist = data["checklist"]
        for item in checklist:
            self.assertEqual(item["violations_count"], 0, f"Expected clean sweep for {item['id']}")

    def test_hazard_sweep_flagged_violations(self):
        """hazard_sweep.py flags violations in non-compliant code."""
        src = self.tmp_path / "src"
        src.mkdir(parents=True)
        (self.tmp_path / "package.json").write_text('{"name": "dirty-app"}\n', encoding="utf-8")

        # Violations:
        (src / "logger.js").write_text('console.log("debug data");\n', encoding="utf-8")
        (src / "link.html").write_text('<a href="https://example.com" target="_blank">External</a>\n', encoding="utf-8")
        (src / "calc.js").write_text('eval("2+2");\n', encoding="utf-8")
        (src / "dom.js").write_text('container.innerHTML = "<b>raw</b>";\n', encoding="utf-8")
        (self.tmp_path / ".env").write_text("SECRET=123\n", encoding="utf-8")

        res = subprocess.run(
            [sys.executable, "-B", str(SWEEP_PY), str(self.tmp_path), "--json"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        by_id = {item["id"]: item for item in data["checklist"]}

        web_hazards = by_id.get("web-hazards")
        self.assertIsNotNone(web_hazards)
        self.assertGreaterEqual(web_hazards["violations_count"], 4)
        v_rules = {v["rule_id"] for v in web_hazards["violations"]}
        self.assertIn("web-no-console", v_rules)
        self.assertIn("web-target-blank-rel", v_rules)
        self.assertIn("web-no-raw-eval", v_rules)
        self.assertIn("web-no-inner-html", v_rules)
        self.assertIn("web-no-committed-env", v_rules)

    def test_skill_contracts_pass(self):
        """skill_contracts.py passes with incident-to-rule and hazard_sweep additions."""
        contracts_py = REPO_ROOT / "scripts" / "skill_contracts.py"
        res = subprocess.run(
            [sys.executable, "-B", str(contracts_py)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"skill_contracts failed: {res.stdout}\n{res.stderr}")


if __name__ == "__main__":
    unittest.main()
