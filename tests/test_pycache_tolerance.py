#!/usr/bin/env python3
"""Tests for python bytecode cache tolerance in Build Forge."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPycacheTolerance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bf-test-pycache-"))
        self.repo_copy = self.temp_dir / "repo"

        subprocess.run(
            ["git", "clone", str(REPO_ROOT), str(self.repo_copy)],
            check=True,
            capture_output=True,
        )

        for item in ("package.json", ".gitignore", "integrity.json"):
            src = REPO_ROOT / item
            if src.is_file():
                shutil.copy(src, self.repo_copy / item)

        for folder in ("scripts", "maintainers", "skills"):
            src = REPO_ROOT / folder
            if src.is_dir():
                shutil.copytree(src, self.repo_copy / folder, dirs_exist_ok=True)

        fixtures_dir = REPO_ROOT / "tests" / "fixtures"
        if fixtures_dir.is_dir():
            shutil.copytree(fixtures_dir, self.repo_copy / "tests" / "fixtures", dirs_exist_ok=True)

        self.skill_cache = (
            self.repo_copy / "skills" / "project-bootstrap" / "scripts" / "__pycache__"
        )
        self.skill_cache.mkdir(parents=True, exist_ok=True)
        self.skill_pyc = self.skill_cache / "sample.cpython-314.pyc"
        self.skill_pyc.write_bytes(b"sample skill bytecode")

        self.scripts_cache = self.repo_copy / "scripts" / "__pycache__"
        self.scripts_cache.mkdir(parents=True, exist_ok=True)
        self.scripts_pyc = self.scripts_cache / "sample.cpython-314.pyc"
        self.scripts_pyc.write_bytes(b"sample script bytecode")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_untracked_caches_allowed_and_excluded_from_package(self):
        """Untracked caches pass checks and are excluded from the package tarball."""
        r_pkg = subprocess.run(
            [
                sys.executable,
                str(self.repo_copy / "scripts" / "check_package.py"),
                "--root",
                str(self.repo_copy),
            ],
            cwd=str(self.repo_copy),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            r_pkg.returncode,
            0,
            f"check_package failed with untracked caches:\n{r_pkg.stdout}\n{r_pkg.stderr}",
        )

        r_pack = subprocess.run(
            ["npm", "pack", "--dry-run", "--json"],
            cwd=str(self.repo_copy),
            capture_output=True,
            text=True,
            shell=(sys.platform == "win32"),
        )
        self.assertEqual(r_pack.returncode, 0, f"npm pack failed: {r_pack.stderr}")
        data = json.loads(r_pack.stdout)
        files = data[0].get("files", []) if data else []
        cache_paths = [
            f["path"]
            for f in files
            if "__pycache__" in f.get("path", "") or f.get("path", "").endswith(".pyc")
        ]
        self.assertEqual(
            cache_paths,
            [],
            f"npm pack tarball contains bytecode caches: {cache_paths}",
        )

        test_env = os.environ.copy()
        test_env["_BF_PYCACHE_TESTING"] = "1"

        r_ci = subprocess.run(
            [
                sys.executable,
                str(self.repo_copy / "scripts" / "ci_check.py"),
            ],
            cwd=str(self.repo_copy),
            capture_output=True,
            text=True,
            env=test_env,
        )
        self.assertEqual(
            r_ci.returncode,
            0,
            f"ci_check.py failed with untracked caches:\n{r_ci.stdout}\n{r_ci.stderr}",
        )

        r_dev = subprocess.run(
            [
                sys.executable,
                str(self.repo_copy / "scripts" / "dev.py"),
                "check",
            ],
            cwd=str(self.repo_copy),
            capture_output=True,
            text=True,
            env=test_env,
        )
        self.assertEqual(
            r_dev.returncode,
            0,
            f"dev.py check failed with untracked caches:\n{r_dev.stdout}\n{r_dev.stderr}",
        )

    def test_tracked_pyc_fails_check(self):
        """A tracked pyc file fails repo cache check."""
        rel_pyc = "skills/project-bootstrap/scripts/__pycache__/sample.cpython-314.pyc"
        subprocess.run(
            ["git", "add", "-f", rel_pyc],
            cwd=str(self.repo_copy),
            check=True,
            capture_output=True,
        )

        r_check = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; sys.path.insert(0, 'scripts'); "
                    "import ci_check; errors = []; "
                    "ci_check.check_no_cache_or_pyc('.', errors); "
                    "print(' '.join(errors)); "
                    "sys.exit(1 if errors else 0)"
                ),
            ],
            cwd=str(self.repo_copy),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(r_check.returncode, 0)
        output = r_check.stdout + r_check.stderr
        self.assertIn("Rule 5 failure", output)
        self.assertIn("sample.cpython-314.pyc", output)

    def test_package_json_without_patterns_fails_on_cache(self):
        """A package.json without negative cache patterns fails check_package on cache files."""
        pkg_json = self.repo_copy / "package.json"
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
        data["files"] = [
            f
            for f in data.get("files", [])
            if not f.startswith("!skills/")
        ]
        pkg_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        r_pkg = subprocess.run(
            [
                sys.executable,
                str(self.repo_copy / "scripts" / "check_package.py"),
                "--root",
                str(self.repo_copy),
            ],
            cwd=str(self.repo_copy),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(r_pkg.returncode, 0)
        output = r_pkg.stdout + r_pkg.stderr
        self.assertTrue(
            "sample.cpython-314.pyc" in output or "in tarball but not integrity" in output,
            f"Expected cache failure in check_package output:\n{output}",
        )

    def test_subprocess_env_sets_pythondontwritebytecode(self):
        """Subprocesses started by dev.py, ci_check.py and check_package.py set PYTHONDONTWRITEBYTECODE."""
        probe_code = (
            "import os, sys; print(os.environ.get('PYTHONDONTWRITEBYTECODE', ''))"
        )
        for mod_name in ("dev", "ci_check", "check_package"):
            cmd = [
                sys.executable,
                "-c",
                (
                    f"import sys; sys.path.insert(0, 'scripts'); "
                    f"import {mod_name}; "
                    f"res1 = {mod_name}.subprocess.run([sys.executable, '-c', \"{probe_code}\"], capture_output=True, text=True); "
                    f"res2 = {mod_name}.subprocess.run([sys.executable, '-c', \"{probe_code}\"], env={{'CUSTOM': '1'}}, capture_output=True, text=True); "
                    f"print(res1.stdout.strip(), res2.stdout.strip())"
                ),
            ]
            res = subprocess.run(
                cmd,
                cwd=str(self.repo_copy),
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                res.returncode,
                0,
                f"Probe for {mod_name} failed:\n{res.stdout}\n{res.stderr}",
            )
            val1, val2 = res.stdout.strip().split()
            self.assertEqual(
                val1,
                "1",
                f"{mod_name} subprocess did not set PYTHONDONTWRITEBYTECODE=1 (got '{val1}')",
            )
            self.assertEqual(
                val2,
                "1",
                f"{mod_name} subprocess with custom env did not set PYTHONDONTWRITEBYTECODE=1 (got '{val2}')",
            )


if __name__ == "__main__":
    unittest.main()
