#!/usr/bin/env python3
"""Tier classification tests.

The core tier must match the skills that the Build Forge repo dogfoods,
so that update installs them and remove protects them.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "bin" / "build-forge.js"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dogfood  # noqa: E402


def load_tiers() -> dict:
    return json.loads((REPO_ROOT / "tiers.json").read_text(encoding="utf-8"))


class TestTiers(unittest.TestCase):
    def test_core_matches_dogfood_set(self):
        self.assertEqual(sorted(load_tiers()["core"]), sorted(dogfood.DOGFOOD_SET))

    def test_every_skill_has_exactly_one_tier(self):
        tiers = load_tiers()
        seen = []
        for names in tiers.values():
            seen.extend(names)
        self.assertEqual(len(seen), len(set(seen)), "a skill is listed in 2 tiers")
        on_disk = sorted(p.name for p in (REPO_ROOT / "skills").iterdir() if p.is_dir() and not p.name.startswith((".", "__")))
        self.assertEqual(sorted(seen), on_disk)

    def test_skills_needed_by_update_are_core(self):
        core = set(load_tiers()["core"])
        for name in ("project-bootstrap", "rules-to-tests", "sync-skills-and-docs"):
            self.assertIn(name, core)

    def test_remove_refuses_core_skill_without_force(self):
        with tempfile.TemporaryDirectory(prefix="bf-tiers-") as tmp:
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp, check=True)
            subprocess.run(["node", str(CLI_PATH), "install"], cwd=tmp, capture_output=True, check=True)
            res = subprocess.run(["node", str(CLI_PATH), "remove", "project-bootstrap"], cwd=tmp, capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertTrue((Path(tmp) / ".agents" / "skills" / "project-bootstrap" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
