#!/usr/bin/env python3
"""Negative and schema tests for validate_profile.py git.scopes."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
VAL_PY = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "validate_profile.py"

BASE_PROFILE = """schema_version: 1
project:
  name: demo
  summary: demo application
  mode: new
  platforms: [web]
stack:
  language: javascript
  framework: vanilla
  package_manager: npm
commands:
  check: npm test
structure:
  layers:
    - path: src
      purpose: src
  tests: tests-dir
docs:
  skills_dir: .agents/skills
  agents_file: AGENTS.md
  repo_map: .agents/repo-map.md
git:
  commit_format: '<type>: <subject>'
  push: never
"""


class TestValidateProfileScopes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bf-test-val-")
        self.profile = Path(self.tmp) / "profile.yaml"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_val(self, content: str):
        self.profile.write_text(content, encoding="utf-8")
        return subprocess.run([sys.executable, str(VAL_PY), "--profile", str(self.profile)], capture_output=True, text=True)

    def test_valid_mixed_scopes_pass(self):
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - simple-scope\n"
            "    - name: ui\n"
            "      purpose: UI components and styles\n"
            "      paths:\n"
            "        - src/ui/**\n"
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("0 error(s)", res.stdout)

    def test_negative_duplicate_names_fail(self):
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - ui\n"
            "    - name: ui\n"
            "      purpose: Duplicate ui scope\n"
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 1)
        self.assertIn("duplicate scope name: ui", res.stdout)

    def test_negative_long_purpose_fails(self):
        long_purpose = "A" * 105
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - name: ui\n"
            f"      purpose: {long_purpose}\n"
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 1)
        self.assertIn("exceeds 100 characters", res.stdout)

    def test_negative_bad_glob_fails(self):
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - name: ui\n"
            "      paths:\n"
            '        - "src/[invalid"\n'
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 1)
        self.assertIn("is not a valid glob", res.stdout)

    def test_negative_non_string_name_fails(self):
        content = BASE_PROFILE + (
            "  scopes:\n"
            "    - name: 12345\n"
        )
        res = self.run_val(content)
        self.assertEqual(res.returncode, 1)
        self.assertIn("git.scopes[0].name must be a non-empty string", res.stdout)


class TestProfileGlobsAndBootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bf-test-globs-")
        self.root = Path(self.tmp)
        self.profile = self.root / "profile.yaml"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unmatched_globs_warn_or_fail_strict(self):
        content = (
            "schema_version: 1\n"
            "project:\n"
            "  name: demo\n"
            "  summary: demo application\n"
            "  mode: new\n"
            "  platforms: [web]\n"
            "stack:\n"
            "  language: javascript\n"
            "  framework: vanilla\n"
            "  package_manager: npm\n"
            "commands:\n"
            "  check: npm test\n"
            "docs:\n"
            "  skills_dir: .agents/skills\n"
            "  agents_file: AGENTS.md\n"
            "  repo_map: .agents/repo-map.md\n"
            "design:\n"
            "  enabled: true\n"
            "  tokens_file: src/tokens.css\n"
            "  component_dirs: [src/components/ui]\n"
            "data:\n"
            "  schema_source: src/lib/storage/schema.sql\n"
            "structure:\n"
            "  layers:\n"
            "    - path: src/components/ui\n"
            "      purpose: UI layer\n"
            "  root_allowed: [package.json, src/]\n"
            "  tests: tests-dir\n"
            "git:\n"
            "  commit_format: '<type>: <subject>'\n"
            "  push: never\n"
            "  scopes:\n"
            "    - name: journal\n"
            "      purpose: Journaling\n"
            "      paths:\n"
            "        - src/components/journal/**\n"
        )
        self.profile.write_text(content, encoding="utf-8")

        # 1. Without --strict-paths: warns for each, exits 0
        cmd_warn = [sys.executable, "-B", str(VAL_PY), "--profile", str(self.profile), "--root", str(self.root)]
        res_warn = subprocess.run(cmd_warn, capture_output=True, text=True)
        self.assertEqual(res_warn.returncode, 0, res_warn.stdout + res_warn.stderr)
        self.assertIn("WARN  unmatched path in structure.layers", res_warn.stdout)
        self.assertIn("WARN  unmatched path in design.component_dirs", res_warn.stdout)
        self.assertIn("WARN  unmatched path in git.scopes[journal].paths", res_warn.stdout)
        self.assertIn("WARN  unmatched pattern in structure.root_allowed", res_warn.stdout)
        self.assertIn("WARN  unmatched path in data.schema_source", res_warn.stdout)
        self.assertIn("WARN  unmatched path in design.tokens_file", res_warn.stdout)

        # 2. With --strict-paths: fails with errors, exits 1
        cmd_err = [sys.executable, "-B", str(VAL_PY), "--profile", str(self.profile), "--root", str(self.root), "--strict-paths"]
        res_err = subprocess.run(cmd_err, capture_output=True, text=True)
        self.assertEqual(res_err.returncode, 1)
        self.assertIn("ERROR unmatched path in structure.layers", res_err.stdout)
        self.assertIn("ERROR unmatched path in design.component_dirs", res_err.stdout)
        self.assertIn("ERROR unmatched path in git.scopes[journal].paths", res_err.stdout)

    def test_bootstrap_generated_scopes_all_match(self):
        detect_script = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "detect_stack.py"
        (self.root / "package.json").write_text('{"name": "test-repo"}', encoding="utf-8")
        (self.root / "src" / "components" / "ui").mkdir(parents=True, exist_ok=True)
        (self.root / "src" / "components" / "ui" / "Button.jsx").write_text("export default function Button() {}", encoding="utf-8")
        (self.root / "src" / "lib" / "storage").mkdir(parents=True, exist_ok=True)
        (self.root / "src" / "lib" / "storage" / "db.js").write_text("export const db = {};", encoding="utf-8")

        res = subprocess.run([sys.executable, "-B", str(detect_script), str(self.root)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        facts = json.loads(res.stdout)
        self.assertIn("scope_candidates", facts)
        candidates = facts["scope_candidates"]
        self.assertTrue(len(candidates) >= 2)
        for sc in candidates:
            self.assertIn("paths", sc)
            for pat in sc["paths"]:
                norm = pat.replace("/**", "")
                self.assertTrue((self.root / norm).exists() and any((self.root / norm).rglob("*")))

    def test_scope_named_like_skill_works(self):
        check_sync_script = REPO_ROOT / "skills" / "sync-skills-and-docs" / "scripts" / "check_sync.py"
        (self.root / ".agents" / "skills" / "targeted-module-testing").mkdir(parents=True, exist_ok=True)
        (self.root / ".agents" / "skills" / "targeted-module-testing" / "SKILL.md").write_text("# Test", encoding="utf-8")
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "readme.txt").write_text("docs", encoding="utf-8")
        (self.root / "src").mkdir(parents=True, exist_ok=True)
        (self.root / "src" / "index.js").write_text("console.log(1)", encoding="utf-8")

        agents_md = """# App

## Areas
| Area | Skill |
| --- | --- |
| Testing | `targeted-module-testing` |

## Git
### Scope guide
| Scope | Purpose |
| --- | --- |
| `skills` | Skill updates |
| `docs` | Documentation updates |
"""
        (self.root / "AGENTS.md").write_text(agents_md, encoding="utf-8")

        content = (
            "schema_version: 1\n"
            "project:\n"
            "  name: demo\n"
            "  summary: demo application\n"
            "  mode: new\n"
            "  platforms: [web]\n"
            "stack:\n"
            "  language: javascript\n"
            "  framework: vanilla\n"
            "  package_manager: npm\n"
            "commands:\n"
            "  check: npm test\n"
            "structure:\n"
            "  layers:\n"
            "    - path: src\n"
            "      purpose: source\n"
            "  tests: tests-dir\n"
            "docs:\n"
            "  skills_dir: .agents/skills\n"
            "  agents_file: AGENTS.md\n"
            "  repo_map: .agents/repo-map.md\n"
            "git:\n"
            "  commit_format: '<type>: <subject>'\n"
            "  push: never\n"
            "  scopes:\n"
            "    - name: skills\n"
            "      purpose: Skill updates\n"
            "      paths:\n"
            "        - .agents/skills/**\n"
            "    - name: docs\n"
            "      purpose: Documentation updates\n"
            "      paths:\n"
            "        - docs/**\n"
        )
        self.profile.write_text(content, encoding="utf-8")

        # validate_profile with --strict-paths exits 0
        cmd_val = [sys.executable, "-B", str(VAL_PY), "--profile", str(self.profile), "--root", str(self.root), "--strict-paths"]
        res_val = subprocess.run(cmd_val, capture_output=True, text=True)
        self.assertEqual(res_val.returncode, 0, res_val.stdout + res_val.stderr)

        # check_sync exits 0
        cmd_sync = [sys.executable, "-B", str(check_sync_script), "--profile", str(self.profile), "--root", str(self.root)]
        res_sync = subprocess.run(cmd_sync, capture_output=True, text=True)
        self.assertEqual(res_sync.returncode, 0, res_sync.stdout + res_sync.stderr)
        self.assertNotIn("names 'skills'", res_sync.stdout)
        self.assertNotIn("names 'docs'", res_sync.stdout)

    def test_example_file_has_banner(self):
        example_f = REPO_ROOT / "skills" / "project-bootstrap" / "references" / "example-profile.yaml"
        old_nemo_f = REPO_ROOT / "skills" / "project-bootstrap" / "references" / "example-nemo.project-profile.yaml"
        self.assertTrue(example_f.is_file())
        self.assertFalse(old_nemo_f.exists())

        txt = example_f.read_text(encoding="utf-8")
        first_line = txt.splitlines()[0]
        self.assertEqual(first_line, "# EXAMPLE ONLY. Every value here is invented. Never copy values from this file into a real profile.")
        self.assertIn("Pocketlog", txt)

    def test_sentence_appears_in_bootstrap_skill_md(self):
        skill_md = REPO_ROOT / "skills" / "project-bootstrap" / "SKILL.md"
        txt = skill_md.read_text(encoding="utf-8")
        target_sentence = "Derive every value from detect_stack output and the real file tree. Do not copy values from references/example-*.yaml."
        self.assertIn(target_sentence, txt)


def run_all_validation_scope_tests():
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestValidateProfileScopes))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestProfileGlobsAndBootstrap))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_all_validation_scope_tests()

