#!/usr/bin/env python3
"""Tests for bytecode cache filtering, .agents/.gitignore, doctor checks, update cleanup, and PYTHONDONTWRITEBYTECODE."""
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
CLI_PATH = REPO_ROOT / "bin" / "build-forge.js"


def find_cache_entries(root: Path) -> list:
    """Return relative POSIX paths of any __pycache__ dir, .pyc, .pyo, or .DS_Store under root."""
    hits = []
    if not root.exists():
        return hits
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        for d in dirnames:
            if d == "__pycache__":
                hits.append((dp / d).relative_to(root).as_posix() + "/")
        for f in filenames:
            if f.endswith(".pyc") or f.endswith(".pyo") or f == ".DS_Store":
                hits.append((dp / f).relative_to(root).as_posix())
    return sorted(hits)


def make_pkg_copy(dest: Path) -> Path:
    """Copy packaged CLI assets into dest for isolated mutation tests."""
    dest.mkdir(parents=True, exist_ok=True)
    for fname in ("package.json", "tiers.json", "integrity.json", "upgrade-notes.json"):
        src = REPO_ROOT / fname
        if src.is_file():
            shutil.copy2(src, dest / fname)
    for dname in ("bin", "skills"):
        shutil.copytree(
            REPO_ROOT / dname,
            dest / dname,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store"),
        )
    return dest


def init_git_repo(repo_dir: Path) -> None:
    """Initialize git repo with local identity."""
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True, capture_output=True)


class TestInstallerBytecode(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bf-test-inst-bc-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_package_copy_with_caches_install_copies_none_and_git_add_clean(self):
        """install from a package copy holding caches copies none, creates .agents/.gitignore, and git add -A stages no cache."""
        pkg = make_pkg_copy(self.tmp / "pkg")
        (pkg / "skills" / "project-bootstrap" / "scripts" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (pkg / "skills" / "project-bootstrap" / "scripts" / "__pycache__" / "x.cpython-314.pyc").write_bytes(b"pyc1")
        (pkg / "skills" / "atomic-commits" / "scripts" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (pkg / "skills" / "atomic-commits" / "scripts" / "__pycache__" / "y.pyc").write_bytes(b"pyc2")
        (pkg / "skills" / "atomic-commits" / "scripts" / "stray.pyc").write_bytes(b"pyc3")
        (pkg / "skills" / "atomic-commits" / "scripts" / "legacy.pyo").write_bytes(b"pyo1")
        (pkg / "skills" / "atomic-commits" / ".DS_Store").write_bytes(b"ds")
        (pkg / "skills" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (pkg / "skills" / "__pycache__" / "top.pyc").write_bytes(b"pyc4")

        proj = self.tmp / "proj"
        proj.mkdir()
        init_git_repo(proj)

        pkg_cli = pkg / "bin" / "build-forge.js"
        res = subprocess.run(["node", str(pkg_cli), "install"], cwd=str(proj), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"install failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("ignore added __pycache__/, *.pyc to .agents/.gitignore", res.stdout)

        # No cache files copied into .agents
        self.assertEqual(find_cache_entries(proj / ".agents"), [])

        # .agents/.gitignore created with exact patterns
        gi = proj / ".agents" / ".gitignore"
        self.assertTrue(gi.is_file())
        self.assertEqual(gi.read_text(encoding="utf-8"), "__pycache__/\n*.pyc\n")

        # Subsequent cache creation under .agents/ is ignored by git add -A
        runtime_cache = proj / ".agents" / "skills" / "project-bootstrap" / "scripts" / "__pycache__"
        runtime_cache.mkdir(parents=True, exist_ok=True)
        (runtime_cache / "runtime.cpython-314.pyc").write_bytes(b"runtime-pyc")
        (proj / ".agents" / "skills" / "atomic-commits" / "scripts" / "stray2.pyc").write_bytes(b"stray-pyc")

        subprocess.run(["git", "add", "-A"], cwd=str(proj), check=True, capture_output=True)
        st = subprocess.run(["git", "status", "--short"], cwd=str(proj), check=True, capture_output=True, text=True)
        cache_lines = [l for l in st.stdout.splitlines() if "__pycache__" in l or ".pyc" in l or ".pyo" in l]
        self.assertEqual(cache_lines, [], f"git add -A staged or showed caches:\n{st.stdout}")
        self.assertIn(".agents/.gitignore", st.stdout)

    def test_02_update_and_link_filter_caches_and_clean_untracked_only(self):
        """update skips package caches, removes untracked caches under replaced skills, keeps tracked ones; link fallback copies no caches."""
        pkg = make_pkg_copy(self.tmp / "pkg")
        (pkg / "skills" / "atomic-commits" / "scripts" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (pkg / "skills" / "atomic-commits" / "scripts" / "__pycache__" / "pkg_cache.pyc").write_bytes(b"pkg-pyc")
        (pkg / "skills" / "atomic-commits" / "scripts" / "pkg_stray.pyo").write_bytes(b"pkg-pyo")
        (pkg / "skills" / "atomic-commits" / ".DS_Store").write_bytes(b"pkg-ds")
        (pkg / "skills" / "project-bootstrap" / "scripts" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (pkg / "skills" / "project-bootstrap" / "scripts" / "__pycache__" / "boot.pyc").write_bytes(b"boot-pyc")

        pkg_cli = pkg / "bin" / "build-forge.js"
        proj = self.tmp / "proj_upd"
        proj.mkdir()
        init_git_repo(proj)

        res_inst = subprocess.run(["node", str(pkg_cli), "install"], cwd=str(proj), capture_output=True, text=True)
        self.assertEqual(res_inst.returncode, 0, res_inst.stderr)

        # Create and commit tracked_pyc using -f so git ls-files tracks it
        atomic_cache_dir = proj / ".agents" / "skills" / "atomic-commits" / "scripts" / "__pycache__"
        atomic_cache_dir.mkdir(parents=True, exist_ok=True)
        tracked_pyc = atomic_cache_dir / "tracked.pyc"
        tracked_pyc.write_bytes(b"tracked-pyc")

        subprocess.run(["git", "add", "."], cwd=str(proj), check=True, capture_output=True)
        subprocess.run(["git", "add", "-f", ".agents/skills/atomic-commits/scripts/__pycache__/tracked.pyc"], cwd=str(proj), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: initial"], cwd=str(proj), check=True, capture_output=True)

        # Now create truly untracked caches
        untracked_pyc = atomic_cache_dir / "untracked.pyc"
        untracked_pyc.write_bytes(b"untracked-pyc")
        untracked_pyo = proj / ".agents" / "skills" / "atomic-commits" / "scripts" / "untracked.pyo"
        untracked_pyo.write_bytes(b"untracked-pyo")

        # Separate skill where __pycache__ has ONLY untracked caches so directory is removed
        repo_cache_dir = proj / ".agents" / "skills" / "repo-search" / "__pycache__"
        repo_cache_dir.mkdir(parents=True, exist_ok=True)
        repo_untracked = repo_cache_dir / "repo.pyc"
        repo_untracked.write_bytes(b"repo-pyc")

        res_upd = subprocess.run(
            ["node", str(pkg_cli), "update", "--restore", "atomic-commits", "--restore", "repo-search"],
            cwd=str(proj),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_upd.returncode, 0, f"update failed:\n{res_upd.stdout}\n{res_upd.stderr}")

        # Tracked cache must survive
        self.assertTrue(tracked_pyc.is_file(), "update removed a tracked cache file")
        # Untracked caches and empty __pycache__ must be removed
        self.assertFalse(untracked_pyc.exists(), "update failed to remove untracked .pyc")
        self.assertFalse(untracked_pyo.exists(), "update failed to remove untracked .pyo")
        self.assertFalse(repo_untracked.exists(), "update failed to remove untracked repo.pyc")
        self.assertFalse(repo_cache_dir.exists(), "update failed to remove empty __pycache__ directory")
        # Caches inside pkg copy must NOT have been copied
        self.assertFalse((atomic_cache_dir / "pkg_cache.pyc").exists())
        self.assertFalse((proj / ".agents" / "skills" / "atomic-commits" / "scripts" / "pkg_stray.pyo").exists())
        self.assertFalse((proj / ".agents" / "skills" / "atomic-commits" / ".DS_Store").exists())

        # Verify symlink fallback copy in linkCommand skips caches even if caches exist in .agents/skills
        link_proj = self.tmp / "proj_link"
        link_proj.mkdir()
        r_li = subprocess.run(["node", str(pkg_cli), "install"], cwd=str(link_proj), capture_output=True, text=True)
        self.assertEqual(r_li.returncode, 0, r_li.stderr)
        # Put temporary caches in .agents/skills to test link copy filter
        tmp_cache = link_proj / ".agents" / "skills" / "atomic-commits" / "scripts" / "__pycache__"
        tmp_cache.mkdir(parents=True, exist_ok=True)
        (tmp_cache / "fallback.pyc").write_bytes(b"fb")
        (link_proj / ".agents" / "skills" / "atomic-commits" / "scripts" / "fb.pyo").write_bytes(b"fb-pyo")
        (link_proj / ".agents" / "skills" / "atomic-commits" / ".DS_Store").write_bytes(b"ds")

        # Force fallback copy in linkCommand (new .claude/skills) by throwing EPERM in fs.symlinkSync
        node_script = (
            "const fs = require('fs');"
            "const cli = require(process.argv[1]);"
            "fs.symlinkSync = () => { const e = new Error('EPERM mock'); e.code = 'EPERM'; throw e; };"
            "cli.linkCommand(process.cwd(), 'claude');"
        )
        r_link = subprocess.run(
            ["node", "-e", node_script, str(pkg_cli)],
            cwd=str(link_proj),
            capture_output=True,
            text=True,
        )
        self.assertEqual(r_link.returncode, 0, f"link fallback failed:\n{r_link.stdout}\n{r_link.stderr}")
        claude_skills = link_proj / ".claude" / "skills"
        self.assertTrue(claude_skills.is_dir())
        self.assertTrue((claude_skills / "atomic-commits" / "SKILL.md").is_file())
        self.assertEqual(find_cache_entries(claude_skills), [], "link fallback copied cache files")

        # Also test link fallback when .claude/skills already exists as a real folder
        shutil.rmtree(claude_skills)
        claude_skills.mkdir(parents=True)
        r_link2 = subprocess.run(
            ["node", "-e", node_script, str(pkg_cli)],
            cwd=str(link_proj),
            capture_output=True,
            text=True,
        )
        self.assertEqual(r_link2.returncode, 0, f"link fallback (existing dir) failed:\n{r_link2.stderr}")
        self.assertTrue((claude_skills / "atomic-commits" / "SKILL.md").is_file())
        self.assertEqual(find_cache_entries(claude_skills), [], "link per-skill fallback copied cache files")

        # Test update --adopt --restore all from package copy containing caches
        adopt_proj = self.tmp / "proj_adopt"
        adopt_proj.mkdir()
        init_git_repo(adopt_proj)
        subprocess.run(["node", str(pkg_cli), "install"], cwd=str(adopt_proj), check=True, capture_output=True)
        (adopt_proj / ".agents" / "build-forge.lock.json").unlink()
        (adopt_proj / ".agents" / ".gitignore").unlink()
        # Modify atomic-commits and add untracked cache
        atomic_md = adopt_proj / ".agents" / "skills" / "atomic-commits" / "SKILL.md"
        atomic_md.write_text(atomic_md.read_text(encoding="utf-8") + "\n# local edit\n", encoding="utf-8")
        a_cache = adopt_proj / ".agents" / "skills" / "atomic-commits" / "scripts" / "__pycache__"
        a_cache.mkdir(parents=True, exist_ok=True)
        (a_cache / "stale_adopt.pyc").write_bytes(b"adopt-pyc")
        r_adopt = subprocess.run(["node", str(pkg_cli), "update", "--adopt", "--restore", "all"], cwd=str(adopt_proj), capture_output=True, text=True)
        self.assertEqual(r_adopt.returncode, 0, f"update --adopt --restore all failed:\n{r_adopt.stdout}\n{r_adopt.stderr}")
        self.assertEqual(find_cache_entries(adopt_proj / ".agents"), [], "adopt copied or left cache files")
        self.assertTrue((adopt_proj / ".agents" / ".gitignore").is_file())

    def test_03_agents_gitignore_lifecycle_and_no_gitignore_flag(self):
        """install/update create .agents/.gitignore, preserve lines, stay idempotent, and skip with --no-gitignore."""
        # 1. install --no-gitignore skips creating .agents/.gitignore
        p_skip = self.tmp / "skip_gi"
        p_skip.mkdir()
        r_skip = subprocess.run(["node", str(CLI_PATH), "install", "--no-gitignore"], cwd=str(p_skip), capture_output=True, text=True)
        self.assertEqual(r_skip.returncode, 0, r_skip.stderr)
        self.assertFalse((p_skip / ".agents" / ".gitignore").exists(), "--no-gitignore created .agents/.gitignore")

        # update --no-gitignore also skips creating .agents/.gitignore
        r_upd_skip = subprocess.run(["node", str(CLI_PATH), "update", "--no-gitignore"], cwd=str(p_skip), capture_output=True, text=True)
        self.assertEqual(r_upd_skip.returncode, 0, r_upd_skip.stderr)
        self.assertFalse((p_skip / ".agents" / ".gitignore").exists(), "update --no-gitignore created .agents/.gitignore")

        # update without --no-gitignore creates .agents/.gitignore
        r_upd_create = subprocess.run(["node", str(CLI_PATH), "update"], cwd=str(p_skip), capture_output=True, text=True)
        self.assertEqual(r_upd_create.returncode, 0, r_upd_create.stderr)
        self.assertIn("ignore added __pycache__/, *.pyc to .agents/.gitignore", r_upd_create.stdout)
        self.assertEqual((p_skip / ".agents" / ".gitignore").read_text(encoding="utf-8"), "__pycache__/\n*.pyc\n")

        # 2. Existing custom lines and partial patterns preserve order
        p_pres = self.tmp / "preserve_gi"
        (p_pres / ".agents").mkdir(parents=True)
        gi_pres = p_pres / ".agents" / ".gitignore"
        gi_pres.write_text("# custom header\ncustom-dir/\n*.pyc", encoding="utf-8")

        r_pres = subprocess.run(["node", str(CLI_PATH), "install"], cwd=str(p_pres), capture_output=True, text=True)
        self.assertEqual(r_pres.returncode, 0, r_pres.stderr)
        self.assertIn("ignore added __pycache__/ to .agents/.gitignore", r_pres.stdout)
        self.assertNotIn("*.pyc to .agents/.gitignore", r_pres.stdout)
        self.assertEqual(
            gi_pres.read_text(encoding="utf-8"),
            "# custom header\ncustom-dir/\n*.pyc\n__pycache__/\n",
        )

        # 3. Idempotent on re-run
        r_idemp = subprocess.run(["node", str(CLI_PATH), "install"], cwd=str(p_pres), capture_output=True, text=True)
        self.assertEqual(r_idemp.returncode, 0, r_idemp.stderr)
        self.assertNotIn("ignore added", r_idemp.stdout)
        self.assertEqual(
            gi_pres.read_text(encoding="utf-8"),
            "# custom header\ncustom-dir/\n*.pyc\n__pycache__/\n",
        )

    def test_04_doctor_warns_tracked_bytecode_and_missing_ignore_returns_zero(self):
        """doctor emits WARN (exit 0) for tracked bytecode (max 10 listed) and missing .agents/.gitignore lines."""
        proj = self.tmp / "doc_proj"
        proj.mkdir()
        init_git_repo(proj)

        subprocess.run(["node", str(CLI_PATH), "install"], cwd=str(proj), check=True, capture_output=True)

        # Clean state: OK for both checks
        r_clean = subprocess.run(["node", str(CLI_PATH), "doctor", "--json"], cwd=str(proj), capture_output=True, text=True)
        self.assertEqual(r_clean.returncode, 0, r_clean.stdout)
        d_clean = json.loads(r_clean.stdout)
        c_bc = next(c for c in d_clean["checks"] if c["name"] == "Tracked python bytecode")
        c_gi = next(c for c in d_clean["checks"] if c["name"] == "Caches ignore")
        self.assertEqual(c_bc["status"], "OK")
        self.assertEqual(c_gi["status"], "OK")

        # Remove 1 line from .agents/.gitignore -> WARN
        gi = proj / ".agents" / ".gitignore"
        gi.write_text("__pycache__/\n", encoding="utf-8")
        r_gi_warn = subprocess.run(["node", str(CLI_PATH), "doctor", "--json"], cwd=str(proj), capture_output=True, text=True)
        self.assertEqual(r_gi_warn.returncode, 0)
        d_gi = json.loads(r_gi_warn.stdout)
        c_gi2 = next(c for c in d_gi["checks"] if c["name"] == "Caches ignore")
        self.assertEqual(c_gi2["status"], "WARN")
        self.assertIn("caches not ignored", c_gi2["message"])
        self.assertIn("run update", c_gi2["hint"])

        # Add 12 tracked bytecode files -> WARN listing up to 10 paths and returning exit 0
        cache_dir = proj / "extra" / "__pycache__"
        cache_dir.mkdir(parents=True, exist_ok=True)
        for idx in range(12):
            (cache_dir / f"mod_{idx:02d}.pyc").write_bytes(b"pyc")
        subprocess.run(["git", "add", "-f", "extra/__pycache__"], cwd=str(proj), check=True, capture_output=True)

        r_bc_warn = subprocess.run(["node", str(CLI_PATH), "doctor", "--json"], cwd=str(proj), capture_output=True, text=True)
        self.assertEqual(r_bc_warn.returncode, 0, f"doctor returned non-zero on WARN: {r_bc_warn.stdout}")
        d_bc = json.loads(r_bc_warn.stdout)
        c_bc2 = next(c for c in d_bc["checks"] if c["name"] == "Tracked python bytecode")
        self.assertEqual(c_bc2["status"], "WARN")
        self.assertIn("tracked python bytecode", c_bc2["message"])
        self.assertIn("(+2 more)", c_bc2["message"])
        self.assertIn("git rm --cached", c_bc2["hint"])
        # Up to 10 paths listed in hint
        hint_paths = [p for p in c_bc2["hint"].split() if p.startswith("extra/")]
        self.assertEqual(len(hint_paths), 10)
        self.assertNotIn("mod_10.pyc", c_bc2["message"])
        self.assertNotIn("mod_11.pyc", c_bc2["message"])

    def test_05_cli_python_subprocesses_set_pythondontwritebytecode(self):
        """CLI Python subprocesses in doctor and update set PYTHONDONTWRITEBYTECODE=1."""
        proj = self.tmp / "py_env_proj"
        proj.mkdir()
        subprocess.run(["node", str(CLI_PATH), "install"], cwd=str(proj), check=True, capture_output=True)
        (proj / ".agents" / "project-profile.yaml").write_text("schema_version: 2\n", encoding="utf-8")

        scripts_dir = proj / ".agents" / "skills" / "project-bootstrap" / "scripts"
        (scripts_dir / "env_probe_helper.py").write_text("VALUE = 42\n", encoding="utf-8")
        probe_body = (
            "import os, sys, pathlib\n"
            "import env_probe_helper\n"
            "p = pathlib.Path(os.getcwd()) / 'py_env_out.txt'\n"
            "p.write_text(os.environ.get('PYTHONDONTWRITEBYTECODE', 'MISSING'), encoding='utf-8')\n"
        )
        (scripts_dir / "validate_profile.py").write_text(probe_body, encoding="utf-8")
        (scripts_dir / "migrate_profile.py").write_text(
            "import os, pathlib, env_probe_helper\n"
            "pathlib.Path(os.getcwd(), 'py_upd_out.txt').write_text(os.environ.get('PYTHONDONTWRITEBYTECODE', 'MISSING'), encoding='utf-8')\n",
            encoding="utf-8",
        )

        # Strip PYTHONDONTWRITEBYTECODE from parent env so only CLI's injection can provide it
        clean_env = os.environ.copy()
        clean_env.pop("PYTHONDONTWRITEBYTECODE", None)

        r_doc = subprocess.run(["node", str(CLI_PATH), "doctor"], cwd=str(proj), capture_output=True, text=True, env=clean_env)
        self.assertTrue((proj / "py_env_out.txt").is_file(), f"doctor did not run validate_profile probe:\n{r_doc.stdout}\n{r_doc.stderr}")
        self.assertEqual((proj / "py_env_out.txt").read_text(encoding="utf-8"), "1")
        self.assertFalse((scripts_dir / "__pycache__").exists(), "Python subprocess created __pycache__ despite PYTHONDONTWRITEBYTECODE")

        r_upd = subprocess.run(["node", str(CLI_PATH), "update", "--keep-modified", "project-bootstrap"], cwd=str(proj), capture_output=True, text=True, env=clean_env)
        self.assertEqual(r_upd.returncode, 0, r_upd.stderr)
        self.assertTrue((proj / "py_upd_out.txt").is_file(), f"update did not run migrate_profile probe:\n{r_upd.stdout}\n{r_upd.stderr}")
        self.assertEqual((proj / "py_upd_out.txt").read_text(encoding="utf-8"), "1")
        self.assertFalse((scripts_dir / "__pycache__").exists(), "update Python subprocess created __pycache__")

    def test_06_verify_and_offline_verifier_ignore_caches_and_agents_gitignore(self):
        """verify, verify_integrity.py, and update --dry-run ignore caches and .agents/.gitignore."""
        proj = self.tmp / "verify_proj"
        proj.mkdir()
        init_git_repo(proj)

        r_inst = subprocess.run(["node", str(CLI_PATH), "install"], cwd=str(proj), capture_output=True, text=True)
        self.assertEqual(r_inst.returncode, 0, r_inst.stderr)

        # Create caches under .agents/skills/
        cdir = proj / ".agents" / "skills" / "project-bootstrap" / "scripts" / "__pycache__"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "render.cpython-314.pyc").write_bytes(b"pyc-bytes")
        (proj / ".agents" / "skills" / "atomic-commits" / "scripts" / "stray.pyc").write_bytes(b"stray")
        (proj / ".agents" / "skills" / "atomic-commits" / ".DS_Store").write_bytes(b"ds")

        # CLI verify must still exit 0
        r_ver = subprocess.run(["node", str(CLI_PATH), "verify"], cwd=str(proj), capture_output=True, text=True)
        self.assertEqual(r_ver.returncode, 0, f"verify failed with caches present:\n{r_ver.stdout}\n{r_ver.stderr}")

        # Offline verifier must still exit 0
        offline_script = proj / ".agents" / "skills" / "project-bootstrap" / "scripts" / "verify_integrity.py"
        r_off = subprocess.run(
            [sys.executable, "-B", str(offline_script), "--root", str(proj)],
            cwd=str(proj),
            capture_output=True,
            text=True,
        )
        self.assertEqual(r_off.returncode, 0, f"offline verify_integrity.py failed:\n{r_off.stdout}\n{r_off.stderr}")

        # update --dry-run reports nothing to do (ignores .agents/.gitignore and caches)
        r_dry = subprocess.run(["node", str(CLI_PATH), "update", "--dry-run"], cwd=str(proj), capture_output=True, text=True)
        self.assertEqual(r_dry.returncode, 0, f"update --dry-run failed:\n{r_dry.stdout}\n{r_dry.stderr}")
        self.assertIn("Nothing to do", r_dry.stdout)


if __name__ == "__main__":
    unittest.main()
