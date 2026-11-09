#!/usr/bin/env python3
"""Comprehensive test suite for safe update, upgrade actions, and render upgrade-unstamped.

Tests:
1. update --dry-run changes nothing
2. modified pipeline skill stops and lists it; --keep-modified works
3. core skills added, optional skills listed, add command works
4. vendor, references, profile untouched across updates
5. content differences detected under same version number
6. no lock stops, --adopt writes lock after resolving modified skills
7. render --upgrade-unstamped dry run and real:
   - property test: all old non-generated lines survive in salvaged block
   - custom block survives intact
   - idempotent: running twice changes nothing
   - dirty git tree is refused
   - unstamped file without old banner is skipped
8. upgrade-notes actions print and done flag persists in .agents/upgrade-state.json, doctor warns on pending
9. Windows cross-platform path safety: POSIX keys in lockfile
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "bin" / "build-forge.js"
RENDER_PATH = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "render.py"
FIXTURE_BUILDER = REPO_ROOT / "tests" / "fixtures" / "create_old_install_fixture.py"

sys.path.insert(0, str(REPO_ROOT / "tests" / "fixtures"))
from create_old_install_fixture import generate_old_install_fixture


def snapshot_dir(root: Path) -> dict:
    """Capture snapshot of all files and their contents."""
    snap = {}
    for r, _, files in os.walk(root):
        for f in files:
            p = Path(r) / f
            rel = p.relative_to(root).as_posix()
            try:
                snap[rel] = p.read_bytes()
            except Exception:
                pass
    return snap


def run_node(args: list, cwd: Path) -> subprocess.CompletedProcess:
    """Run build-forge CLI command with node."""
    cmd = ["node", str(CLI_PATH)] + args
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def run_py(args: list, cwd: Path) -> subprocess.CompletedProcess:
    """Run python script with -B (no bytecode)."""
    cmd = [sys.executable, "-B"] + args
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


class TestSafeUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bf_test_update_")
        self.project_dir = Path(self.tmp)
        generate_old_install_fixture(self.project_dir, init_git=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_update_dry_run_changes_nothing(self):
        """update --dry-run prints the plan and changes no files."""
        before = snapshot_dir(self.project_dir)

        res = run_node(["update", "--dry-run", "--keep-modified", "atomic-commits"], self.project_dir)
        self.assertEqual(res.returncode, 0, f"Expected 0, got {res.returncode}: {res.stderr}")
        self.assertIn("DRY RUN", res.stdout)
        self.assertIn("No files were changed", res.stdout)

        after = snapshot_dir(self.project_dir)
        self.assertEqual(before, after, "update --dry-run modified files on disk")

    def test_02_modified_pipeline_skill_stops_and_keep_modified_works(self):
        """update stops on modified pipeline skills; --keep-modified preserves edits and succeeds."""
        # 1. Update without --keep-modified must stop because atomic-commits was modified
        res = run_node(["update"], self.project_dir)
        self.assertNotEqual(res.returncode, 0, "update should have aborted on modified skill")
        combined = res.stdout + res.stderr
        self.assertIn("atomic-commits", combined)
        self.assertIn("local modifications", combined)

        # 2. Update with --keep-modified atomic-commits must succeed
        res2 = run_node(["update", "--keep-modified", "atomic-commits"], self.project_dir)
        self.assertEqual(res2.returncode, 0, f"update failed with --keep-modified: {res2.stderr}")

        # Verify hand edit survived
        atomic_file = self.project_dir / ".agents" / "skills" / "atomic-commits" / "SKILL.md"
        content = atomic_file.read_text(encoding="utf-8")
        self.assertIn("Always mention the ticket number in commit message.", content)

    def test_03_core_skills_added_optional_skills_listed_and_add_command(self):
        """update installs missing core skills and lists optional skills to add."""
        # Before update: project-blueprints does not exist
        bp_dir = self.project_dir / ".agents" / "skills" / "project-blueprints"
        self.assertFalse(bp_dir.exists())

        res = run_node(["update", "--keep-modified", "atomic-commits"], self.project_dir)
        self.assertEqual(res.returncode, 0)

        # After update: core skill project-blueprints is installed
        self.assertTrue((bp_dir / "SKILL.md").is_file())

        # Optional skills listed in output
        self.assertIn("Available optional skills:", res.stdout)
        self.assertIn("add targeted-module-testing", res.stdout)

        # Test add command
        res_add = run_node(["add", "targeted-module-testing"], self.project_dir)
        self.assertEqual(res_add.returncode, 0)
        tmt_file = self.project_dir / ".agents" / "skills" / "targeted-module-testing" / "SKILL.md"
        self.assertTrue(tmt_file.is_file())

        # Lockfile updated
        lock = json.loads((self.project_dir / ".agents" / "build-forge.lock.json").read_text(encoding="utf-8"))
        self.assertIn("skills/targeted-module-testing/SKILL.md", lock)

    def test_04_vendor_references_profile_untouched(self):
        """update never touches .agents/vendor, references, or project-profile.yaml."""
        vendor_file = self.project_dir / ".agents" / "vendor" / "old-vendor-skill" / "SKILL.md"
        profile_file = self.project_dir / ".agents" / "project-profile.yaml"

        vendor_before = vendor_file.read_text(encoding="utf-8")
        profile_before = profile_file.read_text(encoding="utf-8")

        res = run_node(["update", "--keep-modified", "atomic-commits"], self.project_dir)
        self.assertEqual(res.returncode, 0)

        self.assertEqual(vendor_file.read_text(encoding="utf-8"), vendor_before)
        self.assertEqual(profile_file.read_text(encoding="utf-8"), profile_before)

    def test_05_content_differences_detected_under_same_version(self):
        """update detects file content differences even if lockfile has matching version string."""
        lock_file = self.project_dir / ".agents" / "build-forge.lock.json"
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
        lock_data["_version"] = "0.2.0"
        lock_file.write_text(json.dumps(lock_data, indent=2) + "\n", encoding="utf-8")

        res = run_node(["update", "--dry-run", "--keep-modified", "atomic-commits"], self.project_dir)
        self.assertEqual(res.returncode, 0)
        # Missing core skill or differing skills should be detected
        self.assertIn("Would install missing core skill(s):", res.stdout)
        self.assertIn("project-blueprints", res.stdout)

    def test_06_no_lock_stops_and_adopt_writes_lock(self):
        """Missing lock file stops update; update --adopt resolves skills and writes lock."""
        lock_file = self.project_dir / ".agents" / "build-forge.lock.json"
        lock_file.unlink()

        # Plain update must fail without lock file
        res = run_node(["update"], self.project_dir)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("update --adopt", res.stderr)

        # --adopt without resolving modified skill stops
        res_adopt_fail = run_node(["update", "--adopt"], self.project_dir)
        self.assertNotEqual(res_adopt_fail.returncode, 0)
        self.assertIn("differ from the package", res_adopt_fail.stderr)

        # --adopt with --keep-modified atomic-commits and --restore all resolves and writes lock
        res_adopt_ok = run_node(["update", "--adopt", "--keep-modified", "atomic-commits", "--restore", "all"], self.project_dir)
        self.assertEqual(res_adopt_ok.returncode, 0, f"adopt failed: {res_adopt_ok.stderr}")
        self.assertTrue(lock_file.is_file())
        new_lock = json.loads(lock_file.read_text(encoding="utf-8"))
        self.assertIn("skills/atomic-commits/SKILL.md", new_lock)
        self.assertIn("skills/project-blueprints/SKILL.md", new_lock)

    def test_07_render_upgrade_unstamped_workflow(self):
        """render.py --upgrade-unstamped: property test for line survival, custom block survival, idempotency, dirty tree refusal, and non-banner skipping."""
        build_ui_path = self.project_dir / ".agents" / "skills" / "build-ui" / "SKILL.md"
        orig_content = build_ui_path.read_text(encoding="utf-8")

        # 1. Verify file starts unstamped with old banner
        self.assertIn("<!-- Generated from .agents/project-profile.yaml by project-bootstrap.", orig_content)
        self.assertNotIn("<!-- build-forge:generated v1 body=", orig_content)

        non_generated_line = "Never use div for button elements. Hand-edited line surviving upgrade."
        custom_block_line = "Local notes surviving upgrade."
        self.assertIn(non_generated_line, orig_content)
        self.assertIn(custom_block_line, orig_content)

        # 2. Dry run does not change file
        res_dry = run_py([
            str(RENDER_PATH),
            "--profile", ".agents/project-profile.yaml",
            "--root", ".",
            "--upgrade-unstamped",
            "--dry-run"
        ], self.project_dir)
        self.assertEqual(res_dry.returncode, 0, f"dry run failed: {res_dry.stderr}")
        self.assertEqual(build_ui_path.read_text(encoding="utf-8"), orig_content)

        # 3. Real upgrade
        res_real = run_py([
            str(RENDER_PATH),
            "--profile", ".agents/project-profile.yaml",
            "--root", ".",
            "--upgrade-unstamped"
        ], self.project_dir)
        self.assertEqual(res_real.returncode, 0, f"real upgrade failed: {res_real.stderr or res_real.stdout}")

        upgraded_content = build_ui_path.read_text(encoding="utf-8")

        # Property test: non-generated line survived in salvaged block
        self.assertIn(non_generated_line, upgraded_content, "Old non-generated line was lost during upgrade")
        self.assertIn("<!-- BEGIN CUSTOM: salvaged -->", upgraded_content)

        # Custom block survived intact
        self.assertIn(custom_block_line, upgraded_content, "Existing custom block was lost during upgrade")
        self.assertIn("<!-- BEGIN CUSTOM: notes -->", upgraded_content)

        # File is now stamped
        self.assertIn("<!-- build-forge:generated v1 body=", upgraded_content)

        # 4. Idempotency: running twice changes nothing
        res_idempotent = run_py([
            str(RENDER_PATH),
            "--profile", ".agents/project-profile.yaml",
            "--root", ".",
            "--upgrade-unstamped"
        ], self.project_dir)
        self.assertEqual(res_idempotent.returncode, 0)
        second_content = build_ui_path.read_text(encoding="utf-8")
        self.assertEqual(upgraded_content, second_content, "render --upgrade-unstamped is not idempotent")

        # 5. Dirty tree guard test
        # Initialize git repo and commit current state
        subprocess.run(["git", "init"], cwd=str(self.project_dir), capture_output=True, check=False)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(self.project_dir), capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(self.project_dir), capture_output=True, check=False)
        subprocess.run(["git", "add", "."], cwd=str(self.project_dir), capture_output=True, check=False)
        subprocess.run(["git", "commit", "-m", "clean"], cwd=str(self.project_dir), capture_output=True, check=False)

        # Make uncommitted edit to target file
        build_ui_path.write_text(second_content + "\n<!-- Uncommitted edit -->\n", encoding="utf-8")

        res_dirty = run_py([
            str(RENDER_PATH),
            "--profile", ".agents/project-profile.yaml",
            "--root", ".",
            "--upgrade-unstamped"
        ], self.project_dir)
        self.assertNotEqual(res_dirty.returncode, 0, "Dirty tree guard should have refused uncommitted changes")
        self.assertIn("uncommitted changes", res_dirty.stderr)

        # Passing --allow-dirty succeeds
        res_allow_dirty = run_py([
            str(RENDER_PATH),
            "--profile", ".agents/project-profile.yaml",
            "--root", ".",
            "--upgrade-unstamped",
            "--allow-dirty"
        ], self.project_dir)
        self.assertEqual(res_allow_dirty.returncode, 0, f"--allow-dirty failed: {res_allow_dirty.stderr}")

        # 6. Unstamped file without old banner is skipped
        no_banner_file = self.project_dir / ".agents" / "skills" / "maintain-design-system" / "SKILL.md"
        no_banner_file.parent.mkdir(parents=True, exist_ok=True)
        no_banner_file.write_text("# Handcrafted design skill\nNo generator banner here.\n", encoding="utf-8")

        res_skip = run_py([
            str(RENDER_PATH),
            "--profile", ".agents/project-profile.yaml",
            "--root", ".",
            "--upgrade-unstamped",
            "--allow-dirty"
        ], self.project_dir)
        self.assertEqual(res_skip.returncode, 0)
        self.assertIn("SKIPPED", res_skip.stdout)
        self.assertIn("maintain-design-system/SKILL.md", res_skip.stdout)

    def test_08_upgrade_notes_and_upgrade_done(self):
        """upgrade-notes actions print during update, doctor warns on pending, and upgrade done marks complete."""
        res_up = run_node(["update", "--keep-modified", "atomic-commits"], self.project_dir)
        self.assertEqual(res_up.returncode, 0)
        self.assertIn("Pending upgrade actions", res_up.stdout)
        self.assertIn("profile-migrate", res_up.stdout)

        # Doctor reports warnings on pending upgrade actions
        res_doc = run_node(["doctor"], self.project_dir)
        self.assertIn("[WARN] Upgrade actions:", res_doc.stdout)

        # Mark all actions as done
        for act in ("profile-migrate", "blueprints-init", "rule-packs", "migrate-external-refs", "upgrade-unstamped"):
            res_done = run_node(["upgrade", "done", act], self.project_dir)
            self.assertEqual(res_done.returncode, 0, f"upgrade done failed for {act}: {res_done.stderr}")

        # State file persists
        state_file = self.project_dir / ".agents" / "upgrade-state.json"
        self.assertTrue(state_file.is_file())
        state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertIn("profile-migrate", state.get("completed", []))

        # Doctor now reports OK
        res_doc2 = run_node(["doctor"], self.project_dir)
        self.assertIn("Upgrade actions: All upgrade actions completed", res_doc2.stdout)

    def test_09_windows_path_safety(self):
        """Lock file and manifest paths strictly use forward slashes."""
        res = run_node(["update", "--keep-modified", "atomic-commits"], self.project_dir)
        self.assertEqual(res.returncode, 0)

        lock_file = self.project_dir / ".agents" / "build-forge.lock.json"
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))

        for k in lock_data.keys():
            self.assertNotIn("\\", k, f"Backslash found in lockfile key: {k}")
            if not k.startswith("_") and k != "version":
                self.assertTrue(k.startswith("skills/"), f"Unexpected key format: {k}")


def main():
    unittest.main()


if __name__ == "__main__":
    main()
