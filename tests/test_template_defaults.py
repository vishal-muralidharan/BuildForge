#!/usr/bin/env python3
"""The profile template starts at the current schema and uses merge commits."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP = REPO_ROOT / "skills" / "project-bootstrap"
TEMPLATE = BOOTSTRAP / "assets" / "project-profile.template.yaml"


class TestTemplateDefaults(unittest.TestCase):
    def setUp(self):
        self.data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))

    def test_template_uses_latest_schema(self):
        sys.path.insert(0, str(BOOTSTRAP / "scripts"))
        import migrate_profile  # noqa: E402
        self.assertEqual(self.data["schema_version"], max(migrate_profile.SUPPORTED_SCHEMA_VERSIONS))
        self.assertEqual(self.data["blueprints"], {"enabled": True, "dir": ".agents/blueprints"})

    def test_template_merges_with_merge_commits(self):
        self.assertEqual(self.data["git"]["workflow"]["merge_method"], "merge")
        source = (REPO_ROOT / "skills" / "feature-delivery" / "scripts" / "branchflow.py").read_text(encoding="utf-8")
        self.assertIn('wf.get("merge_method", "merge")', source)

    def test_filled_template_validates_without_migration(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        filled = (text.replace('"TODO one sentence"', '"Demo app."')
                      .replace('package_manager: "TODO"', "package_manager: npm")
                      .replace('check: ""                 # ONE', 'check: "npm run check"   # ONE')
                      .replace('"TODO"', '"demo"'))
        with tempfile.TemporaryDirectory(prefix="bf-template-") as tmp:
            prof = Path(tmp) / "project-profile.yaml"
            prof.write_text(filled, encoding="utf-8")
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            res = subprocess.run([sys.executable, "-B", str(BOOTSTRAP / "scripts" / "validate_profile.py"), "--profile", str(prof)],
                                 capture_output=True, text=True, env=env)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            plan = subprocess.run([sys.executable, "-B", str(BOOTSTRAP / "scripts" / "migrate_profile.py"), "plan", "--profile", str(prof), "--root", tmp],
                                  capture_output=True, text=True, env=env)
            self.assertNotIn("schema_version 1 -> 2", plan.stdout)


if __name__ == "__main__":
    unittest.main()
