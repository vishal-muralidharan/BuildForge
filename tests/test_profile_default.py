#!/usr/bin/env python3
"""Scripts that read the profile default to .agents/project-profile.yaml."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "bin" / "build-forge.js"

PROFILE = """schema_version: 2
project:
  name: demo
  summary: Demo app.
  mode: existing
stack:
  language: javascript
  framework: React
  package_manager: npm
commands:
  check: npm run check
structure:
  layers:
    - path: src
      purpose: Source code
  root_allowed: [src/, package.json, AGENTS.md, .agents/]
  tests: colocated
naming:
  - {item: Component, style: PascalCase, example: Button.jsx}
git:
  commit_format: "<type>(<scope>): <subject>"
  types: [feat, fix, chore]
  push: never
  scopes:
    - {name: ui, purpose: Source, paths: ["src/**"]}
docs:
  readme: README.md
  agents_file: AGENTS.md
  skills_dir: .agents/skills
  repo_map: .agents/repo-map.md
"""

SCRIPTS = {
    "validate": ["project-bootstrap/scripts/validate_profile.py"],
    "render": ["project-bootstrap/scripts/render.py"],
    "check_sync": ["sync-skills-and-docs/scripts/check_sync.py"],
    "suggest_scope": ["atomic-commits/scripts/suggest_scope.py", "--files", "src/index.js"],
    "commit_message": ["atomic-commits/scripts/check_commit_message.py", "feat(ui): add a button"],
}


class TestProfileDefault(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="bf-profile-default-"))
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["node", str(CLI_PATH), "install"], cwd=self.root, capture_output=True, check=True)
        (self.root / "src").mkdir()
        (self.root / "src" / "index.js").write_text("export {}\n")
        (self.root / "package.json").write_text("{}\n")
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_script(self, key, cwd, extra=None):
        rel, *args = SCRIPTS[key]
        script = self.root / ".agents" / "skills" / rel
        cmd = [sys.executable, "-B", str(script)] + list(args) + list(extra or [])
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=self.env)

    def test_scripts_run_without_profile_flag(self):
        (self.root / ".agents" / "project-profile.yaml").write_text(PROFILE)
        for key in ("validate", "render", "check_sync", "suggest_scope", "commit_message"):
            res = self.run_script(key, self.root)
            self.assertNotIn("arguments are required", res.stderr, key)
            self.assertIn(res.returncode, (0, 1), f"{key}: {res.stdout}{res.stderr}")
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertEqual(self.run_script("commit_message", self.root).returncode, 0)

    def test_root_flag_finds_profile_from_another_folder(self):
        (self.root / ".agents" / "project-profile.yaml").write_text(PROFILE)
        res = self.run_script("validate", REPO_ROOT, ["--root", str(self.root)])
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_missing_profile_gives_clear_error(self):
        res = self.run_script("validate", self.root)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Pass --profile", res.stderr)


if __name__ == "__main__":
    unittest.main()
