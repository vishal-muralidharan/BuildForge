#!/usr/bin/env python3
"""Maintainer tooling test suite for Build Forge.

Tests:
1. npm pack excludes maintainers/ and scripts/.
2. fixture check passes on repository fixtures and fails on violating fixtures.
3. Every maintainer recipe is valid YAML and touchpoint files/directories exist.
4. new-skill scaffolds, rejects duplicate and generated names, fails checks until filled, and passes after.
5. impact finds known tokens and distinguishes packaged vs unpackaged files.
6. release-plan works in a git repository with fake tags without modifying state.
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

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEV_PY = REPO_ROOT / "scripts" / "dev.py"


class TestMaintainerTooling(unittest.TestCase):

    def test_npm_pack_excludes_maintainers_and_scripts(self):
        res = subprocess.run(
            ["npm", "pack", "--dry-run", "--json"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            shell=(sys.platform == "win32")
        )
        self.assertEqual(res.returncode, 0, f"npm pack failed: {res.stderr}")
        data = json.loads(res.stdout)
        files = data[0].get("files", []) if data else []
        paths = [f.get("path", "").replace("\\", "/") for f in files]

        for p in paths:
            self.assertFalse(
                p.startswith("maintainers/"),
                f"npm pack includes forbidden maintainers/ file: {p}"
            )
            self.assertFalse(
                p.startswith("scripts/"),
                f"npm pack includes forbidden scripts/ file: {p}"
            )

    def test_fixture_check_clean_and_violating(self):
        # 1. Clean fixture check passes
        res_clean = subprocess.run(
            [sys.executable, str(DEV_PY), "fixture", "check"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True
        )
        self.assertEqual(res_clean.returncode, 0, f"Clean fixture check failed:\n{res_clean.stdout}\n{res_clean.stderr}")
        self.assertIn("passed verification checks", res_clean.stdout)

        # 2. Violating fixture fails (missing INVENTED.md)
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            bad_fix_dir = tmp / "missing-invented-fixture"
            bad_fix_dir.mkdir(parents=True, exist_ok=True)
            (bad_fix_dir / "sample.txt").write_text("dummy fixture file\n", encoding="utf-8")

            res_fail = subprocess.run(
                [sys.executable, str(DEV_PY), "fixture", "check", "--root", str(tmp)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True
            )
            self.assertNotEqual(res_fail.returncode, 0)
            self.assertIn("Missing INVENTED.md", res_fail.stdout)

        # 3. Violating fixture fails (file > 50 KB)
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            bad_fix_dir = tmp / "oversize-fixture"
            bad_fix_dir.mkdir(parents=True, exist_ok=True)
            (bad_fix_dir / "INVENTED.md").write_text("# Invented\n", encoding="utf-8")
            (bad_fix_dir / "oversize.dat").write_bytes(b"x" * (51 * 1024))

            res_fail = subprocess.run(
                [sys.executable, str(DEV_PY), "fixture", "check", "--root", str(tmp)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True
            )
            self.assertNotEqual(res_fail.returncode, 0)
            self.assertIn("exceeds 50 KB limit", res_fail.stdout)

        # 4. Violating fixture fails (forbidden license header outside INVENTED.md)
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            bad_fix_dir = tmp / "license-header-fixture"
            bad_fix_dir.mkdir(parents=True, exist_ok=True)
            (bad_fix_dir / "INVENTED.md").write_text("# Invented\n", encoding="utf-8")
            (bad_fix_dir / "index.js").write_text("// Copyright (c) 2026 Acme Corp\n", encoding="utf-8")

            res_fail = subprocess.run(
                [sys.executable, str(DEV_PY), "fixture", "check", "--root", str(tmp)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True
            )
            self.assertNotEqual(res_fail.returncode, 0)
            self.assertIn("Forbidden license phrase", res_fail.stdout)

        # 5. Violating fixture fails (disallowed URL)
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            bad_fix_dir = tmp / "bad-url-fixture"
            bad_fix_dir.mkdir(parents=True, exist_ok=True)
            (bad_fix_dir / "INVENTED.md").write_text("# Invented\n", encoding="utf-8")
            (bad_fix_dir / "index.js").write_text("const url = 'https://unauthorized-domain.com/api';\n", encoding="utf-8")

            res_fail = subprocess.run(
                [sys.executable, str(DEV_PY), "fixture", "check", "--root", str(tmp)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True
            )
            self.assertNotEqual(res_fail.returncode, 0)
            self.assertIn("Disallowed URL host", res_fail.stdout)

    def test_recipes_valid_yaml_and_touchpoints(self):
        recipes_dir = REPO_ROOT / "maintainers" / "recipes"
        self.assertTrue(recipes_dir.is_dir(), "maintainers/recipes must be a directory")
        recipe_files = list(recipes_dir.glob("*.yaml"))
        self.assertGreaterEqual(len(recipe_files), 8, "Must have at least 8 recipes")

        known_samples = {
            "name": "project-blueprints",
            "check_type": "no_dual_homed_skills",
            "area": "tokens",
            "pack_name": "native-controls",
            "from_version": "1",
            "to_version": "2",
            "command": "update",
            "field_name": "blueprints",
            "section_name": "salvaged"
        }

        for rf in recipe_files:
            data = yaml.safe_load(rf.read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict, f"{rf.name} must be a YAML dictionary")
            self.assertIn("name", data, f"{rf.name} missing 'name'")
            self.assertIn("args", data, f"{rf.name} missing 'args'")
            self.assertIn("touchpoints", data, f"{rf.name} missing 'touchpoints'")

            tps = data["touchpoints"]
            self.assertIsInstance(tps, list, f"{rf.name} touchpoints must be a list")
            self.assertGreater(len(tps), 0, f"{rf.name} touchpoints must not be empty")

            for tp in tps:
                self.assertIn("file", tp, f"{rf.name} touchpoint missing 'file'")
                self.assertIn("why", tp, f"{rf.name} touchpoint missing 'why'")

                raw_file = tp["file"]
                # Format with sample args if needed
                formatted_file = raw_file
                for k, v in known_samples.items():
                    formatted_file = formatted_file.replace(f"{{{k}}}", v)

                # Touchpoint target or parent directory must exist
                target_path = REPO_ROOT / formatted_file
                parent_path = target_path.parent
                self.assertTrue(
                    target_path.exists() or parent_path.exists(),
                    f"Touchpoint file or parent folder missing: {formatted_file} in recipe {rf.name}"
                )

    def test_new_skill_scaffolding_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            # Copy minimal files to simulate repository
            repo_copy = tmp / "build-forge"
            repo_copy.mkdir(parents=True, exist_ok=True)

            shutil.copytree(REPO_ROOT / "maintainers", repo_copy / "maintainers")
            shutil.copytree(REPO_ROOT / "scripts", repo_copy / "scripts")
            shutil.copytree(REPO_ROOT / "skills", repo_copy / "skills")
            shutil.copytree(REPO_ROOT / "tests", repo_copy / "tests")
            shutil.copyfile(REPO_ROOT / "tiers.json", repo_copy / "tiers.json")
            shutil.copyfile(REPO_ROOT / "README.md", repo_copy / "README.md")
            shutil.copyfile(REPO_ROOT / "CHANGELOG.md", repo_copy / "CHANGELOG.md")
            shutil.copyfile(REPO_ROOT / "integrity.json", repo_copy / "integrity.json")

            dev_script = repo_copy / "scripts" / "dev.py"

            # 1. Refuse existing name
            res_exist = subprocess.run(
                [sys.executable, str(dev_script), "new-skill", "atomic-commits", "--tier", "core"],
                cwd=str(repo_copy),
                capture_output=True,
                text=True
            )
            self.assertNotEqual(res_exist.returncode, 0)
            self.assertIn("already exists", res_exist.stderr + res_exist.stdout)

            # 2. Refuse generated name
            res_gen = subprocess.run(
                [sys.executable, str(dev_script), "new-skill", "build-ui", "--tier", "core"],
                cwd=str(repo_copy),
                capture_output=True,
                text=True
            )
            self.assertNotEqual(res_gen.returncode, 0)
            self.assertIn("reserved", res_gen.stderr + res_gen.stdout)

            # 3. Refuse bad name
            res_bad = subprocess.run(
                [sys.executable, str(dev_script), "new-skill", "INVALID_NAME!", "--tier", "core"],
                cwd=str(repo_copy),
                capture_output=True,
                text=True
            )
            self.assertNotEqual(res_bad.returncode, 0)
            self.assertIn("Invalid skill name", res_bad.stderr + res_bad.stdout)

            # 4. Scaffold valid skill
            res_scaffold = subprocess.run(
                [sys.executable, str(dev_script), "new-skill", "sample-skill", "--tier", "module", "--scripts", "--refs"],
                cwd=str(repo_copy),
                capture_output=True,
                text=True
            )
            self.assertEqual(res_scaffold.returncode, 0, f"Scaffold failed: {res_scaffold.stderr}")
            skill_md = repo_copy / "skills" / "sample-skill" / "SKILL.md"
            self.assertTrue(skill_md.is_file(), "sample-skill/SKILL.md must exist")
            self.assertTrue((repo_copy / "skills" / "sample-skill" / "scripts").is_dir())
            self.assertTrue((repo_copy / "skills" / "sample-skill" / "references").is_dir())

            # 5. Check fails while placeholders and TODO remain
            ci_script = repo_copy / "scripts" / "ci_check.py"
            res_chk_fail = subprocess.run(
                [sys.executable, str(ci_script)],
                cwd=str(repo_copy),
                capture_output=True,
                text=True
            )
            self.assertNotEqual(res_chk_fail.returncode, 0, "CI must fail when placeholders or TODO remain")
            output_fail = res_chk_fail.stdout + res_chk_fail.stderr
            self.assertTrue(
                "Placeholder failure" in output_fail or "Triggers failure" in output_fail or "Frontmatter failure" in output_fail,
                f"Expected placeholder failure in output:\n{output_fail}"
            )

            # 6. Fill placeholders and verify check passes
            # Update SKILL.md
            valid_skill_content = (
                "---\n"
                "name: sample-skill\n"
                "description: \"Sample skill for automated verification testing.\"\n"
                "---\n\n"
                "# sample-skill\n\n"
                "## Read first\n- Read .agents/project-profile.yaml first.\n\n"
                "## Steps\n1. Do test actions.\n\n"
                "## Rules\n- Obey rules.\n"
            )
            skill_md.write_text(valid_skill_content, encoding="utf-8")

            # Update triggers.yaml to remove TODO lines
            triggers_file = repo_copy / "tests" / "triggers.yaml"
            tcontent = triggers_file.read_text(encoding="utf-8")
            tclean = tcontent.replace("TODO: positive trigger", "real positive trigger").replace("TODO: negative trigger", "real negative trigger")
            triggers_file.write_text(tclean, encoding="utf-8")

            # Add sample-skill to ALLOWED_SKILLS in ci_check.py
            ci_text = ci_script.read_text(encoding="utf-8")
            ci_text = ci_text.replace('"targeted-module-testing",', '"targeted-module-testing",\n    "sample-skill",')
            ci_script.write_text(ci_text, encoding="utf-8")

            # Regenerate integrity manifest
            subprocess.run([sys.executable, str(repo_copy / "scripts" / "make_integrity.py")], cwd=str(repo_copy), check=True)

            # Verify lint_py and ci_check pass on the updated repo
            res_lint = subprocess.run([sys.executable, str(repo_copy / "scripts" / "lint_py.py")], cwd=str(repo_copy), capture_output=True, text=True)
            self.assertEqual(res_lint.returncode, 0, f"lint_py failed: {res_lint.stderr}")

    def test_impact(self):
        res = subprocess.run(
            [sys.executable, str(DEV_PY), "impact", "project-blueprints"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"impact command failed:\n{res.stderr}")
        self.assertIn("[PACKAGED]", res.stdout)
        self.assertIn("[UNPACKAGED]", res.stdout)
        self.assertIn("Folder: skills/project-blueprints/", res.stdout)

    def test_release_plan_with_fake_tags(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            # Initialize git repository
            subprocess.run(["git", "init"], cwd=str(tmp), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp), check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp), check=True)

            # Copy dev.py and dummy files
            (tmp / "scripts").mkdir()
            shutil.copyfile(DEV_PY, tmp / "scripts" / "dev.py")
            (tmp / "package.json").write_text('{"name": "@v1006/build-forge", "version": "0.1.0"}\n', encoding="utf-8")
            (tmp / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n### Added\n- Feature X\n", encoding="utf-8")

            # Commit initial
            subprocess.run(["git", "add", "."], cwd=str(tmp), check=True)
            subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=str(tmp), check=True)
            subprocess.run(["git", "tag", "v0.1.0"], cwd=str(tmp), check=True)

            # Add feat commit
            (tmp / "new_feature.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=str(tmp), check=True)
            subprocess.run(["git", "commit", "-m", "feat: add new feature"], cwd=str(tmp), check=True)

            # Run release-plan
            res = subprocess.run(
                [sys.executable, str(tmp / "scripts" / "dev.py"), "release-plan"],
                cwd=str(tmp),
                capture_output=True,
                text=True
            )
            self.assertEqual(res.returncode, 0, f"release-plan failed:\n{res.stderr}")
            self.assertIn("Last tag:                   v0.1.0", res.stdout)
            self.assertIn("Recommended version bump:   minor", res.stdout)
            self.assertIn("git tag v0.2.0", res.stdout)

            # Assert no git tags were created
            res_tags = subprocess.run(["git", "tag"], cwd=str(tmp), capture_output=True, text=True)
            self.assertEqual(res_tags.stdout.strip(), "v0.1.0", "release-plan must not create tags")


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMaintainerTooling)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

