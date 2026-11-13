#!/usr/bin/env python3
"""A new skill must not leave a registry out of date.

Registries: DOGFOOD_SET or DOGFOOD_EXCLUDED in scripts/dogfood.py, ALLOWED_SKILLS in
scripts/ci_check.py, tiers.json. The dogfood list check must also work without an
installed .agents folder, as in CI.
"""
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

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
SKIP = shutil.ignore_patterns(".git", "node_modules", "__pycache__", "*.pyc", ".DS_Store", ".agents", ".claude",
                              ".cursor", ".windsurf", ".gemini", "*.tgz")


def py(repo: Path, *args):
    return subprocess.run([sys.executable, "-B", *args], cwd=str(repo), capture_output=True, text=True, env=ENV)


def collection(path: Path, var: str) -> list:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^" + re.escape(var) + r"\s*=\s*[\[{]\n((?:[ \t]+\"[^\"\n]+\",\n)*)^[\]}]", text, re.M)
    assert m, f"{var} not found in {path}"
    return re.findall(r'"([^"\n]+)"', m.group(1))


class TestSkillRegistry(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="bf-registry-"))
        shutil.rmtree(self.repo)
        shutil.copytree(REPO_ROOT, self.repo, ignore=SKIP)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_module_skill_is_registered_everywhere(self):
        res = py(self.repo, "scripts/dev.py", "new-skill", "demo-module", "--tier", "module")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("demo-module", collection(self.repo / "scripts" / "dogfood.py", "DOGFOOD_EXCLUDED"))
        self.assertNotIn("demo-module", collection(self.repo / "scripts" / "dogfood.py", "DOGFOOD_SET"))
        self.assertIn("demo-module", collection(self.repo / "scripts" / "ci_check.py", "ALLOWED_SKILLS"))
        self.assertIn("demo-module", json.loads((self.repo / "tiers.json").read_text(encoding="utf-8"))["module"])
        for script in (("scripts/dogfood.py", "check"), ("scripts/make_integrity.py", "--check"),
                       ("scripts/skill_contracts.py",), ("scripts/lint_py.py",)):
            out = py(self.repo, *script)
            self.assertEqual(out.returncode, 0, f"{script}: {out.stdout}{out.stderr}")

    def test_core_skill_is_dogfooded_and_matches_tiers(self):
        res = py(self.repo, "scripts/dev.py", "new-skill", "demo-core", "--tier", "core")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("dogfood sync", res.stdout)
        dogfood_set = collection(self.repo / "scripts" / "dogfood.py", "DOGFOOD_SET")
        self.assertIn("demo-core", dogfood_set)
        tiers = json.loads((self.repo / "tiers.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(tiers["core"]), sorted(dogfood_set))
        self.assertEqual(py(self.repo, "scripts/dogfood.py", "check").returncode, 0)

    def test_registration_is_idempotent_and_keeps_order(self):
        py(self.repo, "scripts/dev.py", "new-skill", "demo-a", "--tier", "module")
        before = collection(self.repo / "scripts" / "ci_check.py", "ALLOWED_SKILLS")
        self.assertEqual(before, sorted(before))
        self.assertEqual(before.count("demo-a"), 1)

    def test_unregistered_skill_fails_even_without_agents_folder(self):
        rogue = self.repo / "skills" / "rogue-skill"
        rogue.mkdir()
        (rogue / "SKILL.md").write_text("---\nname: rogue-skill\ndescription: x\n---\n", encoding="utf-8")
        self.assertFalse((self.repo / ".agents").exists())
        res = py(self.repo, "scripts/dogfood.py", "check")
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("new skill rogue-skill", res.stdout)

    def test_missing_registry_literal_is_an_error_not_a_skip(self):
        ci = self.repo / "scripts" / "ci_check.py"
        ci.write_text(ci.read_text(encoding="utf-8").replace("ALLOWED_SKILLS = {", "OTHER_NAME = {"), encoding="utf-8")
        res = py(self.repo, "scripts/dev.py", "new-skill", "demo-b", "--tier", "module")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("ALLOWED_SKILLS", res.stdout + res.stderr)

    def test_docs_truth_flags_a_stale_skill_count(self):
        readme = self.repo / "README.md"
        text = readme.read_text(encoding="utf-8")
        self.assertEqual(py(self.repo, "scripts/check_docs_truth.py").returncode, 0)
        readme.write_text(text.replace("pipeline skills", "pipeline skills", 1) + "\nThe 3 pipeline skills are old.\n", encoding="utf-8")
        res = py(self.repo, "scripts/check_docs_truth.py")
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("SKILL COUNT", res.stdout)

    def test_new_skill_updates_the_documented_count(self):
        before = (self.repo / "README.md").read_text(encoding="utf-8")
        res = py(self.repo, "scripts/dev.py", "new-skill", "demo-c", "--tier", "module")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        after = (self.repo / "README.md").read_text(encoding="utf-8")
        self.assertNotEqual(before, after)
        self.assertEqual(py(self.repo, "scripts/check_docs_truth.py").returncode, 0)

    def test_repo_lists_match_skills_folder(self):
        res = py(REPO_ROOT, "scripts/dogfood.py", "check")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
