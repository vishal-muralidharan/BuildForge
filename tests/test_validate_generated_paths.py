#!/usr/bin/env python3
"""validate_profile.py accepts paths that Build Forge generates, and static sites."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "validate_profile.py"

PROFILE = """schema_version: 2
project:
  name: demo
  summary: Demo app.
  mode: existing
stack:
  language: {language}
  framework: {framework}
  package_manager: {package_manager}
commands:
{commands}
structure:
  layers:
    - path: src
      purpose: Source code
  root_allowed: [src/, AGENTS.md, CLAUDE.md, .agents/, {extra_root}]
  tests: colocated
naming:
  - {{item: Component, style: PascalCase, example: Button.jsx}}
git:
  commit_format: "<type>(<scope>): <subject>"
  push: never
  scopes:
    - {{name: ui, purpose: Source, paths: ["src/**"]}}
    - {{name: agents, purpose: Agent files, paths: [".agents/**", "AGENTS.md", ".agents/repo-map.md"]}}
docs:
  readme: README.md
  agents_file: AGENTS.md
  skills_dir: .agents/skills
  repo_map: .agents/repo-map.md
"""

JS_COMMANDS = "  check: npm run check"
NO_COMMANDS = "  check: \"\""


class TestValidateGeneratedPaths(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="bf-validate-gen-"))
        (self.root / "src").mkdir()
        (self.root / "src" / "index.js").write_text("export {}\n")
        (self.root / ".agents").mkdir()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_validate(self, **fields):
        values = {"language": "javascript", "framework": "React", "package_manager": "npm",
                  "commands": JS_COMMANDS, "extra_root": "package.json"}
        values.update(fields)
        prof = self.root / ".agents" / "project-profile.yaml"
        prof.write_text(PROFILE.format(**values))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        (self.root / "package.json").write_text("{}")
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "--profile", str(prof), "--root", str(self.root), "--strict-paths"],
                              capture_output=True, text=True, env=env)

    def test_generated_paths_pass_before_render(self):
        res = self.run_validate()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertNotIn("AGENTS.md", res.stdout)

    def test_real_missing_path_still_fails(self):
        res = self.run_validate(extra_root="docs/")
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("docs/", res.stdout)

    def test_static_site_without_commands_passes_with_warning(self):
        res = self.run_validate(language="html", framework="none", package_manager="none", commands=NO_COMMANDS)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("no check command", res.stdout)

    def test_missing_commands_fail_when_tooling_exists(self):
        res = self.run_validate(commands=NO_COMMANDS)
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("commands.check is required", res.stdout)


if __name__ == "__main__":
    unittest.main()
