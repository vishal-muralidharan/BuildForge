#!/usr/bin/env python3
"""Tests for the merge trail policy tools and scripts."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list, cwd: Path, env: dict = None) -> subprocess.CompletedProcess:
    base_env = os.environ.copy()
    base_env["GIT_AUTHOR_NAME"] = "Test Author"
    base_env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    base_env["GIT_COMMITTER_NAME"] = "Test Committer"
    base_env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    base_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        base_env.update(env)
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=base_env)


class TestMergeTrailPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="bf_test_policy_")
        self.root = Path(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _init_git_repo(self) -> Path:
        run_cmd(["git", "init", "-b", "main"], self.root)
        run_cmd(["git", "config", "user.name", "Test Author"], self.root)
        run_cmd(["git", "config", "user.email", "test@example.com"], self.root)
        run_cmd(["git", "config", "commit.gpgsign", "false"], self.root)
        (self.root / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        run_cmd(["git", "add", "README.md"], self.root)
        run_cmd(["git", "commit", "-m", "chore: initial commit"], self.root)
        return self.root

    def test_01_history_check(self):
        """history check passes with only PR merges; fails on direct commit; passes when in baseline."""
        self._init_git_repo()
        check_history_py = REPO_ROOT / "scripts" / "check_history.py"

        # 1. Direct commit without baseline should fail
        (self.root / "file1.txt").write_text("1", encoding="utf-8")
        run_cmd(["git", "add", "file1.txt"], self.root)
        run_cmd(["git", "commit", "-m", "feat: direct commit on main"], self.root)

        res_fail = run_cmd([sys.executable, str(check_history_py), "--ref", "main"], self.root)
        self.assertEqual(res_fail.returncode, 1)
        self.assertIn("FAIL", res_fail.stdout)

        # 2. Baseline initialization records the direct commits
        baseline_file = self.root / "maintainers" / "history-baseline.txt"
        res_init = run_cmd(
            [sys.executable, str(check_history_py), "--ref", "main", "--baseline", str(baseline_file), "--init-baseline"],
            self.root
        )
        self.assertEqual(res_init.returncode, 0)
        self.assertTrue(baseline_file.is_file())
        self.assertIn("before merge policy", baseline_file.read_text(encoding="utf-8"))

        # Now check with baseline passes
        res_pass = run_cmd(
            [sys.executable, str(check_history_py), "--ref", "main", "--baseline", str(baseline_file)],
            self.root
        )
        self.assertEqual(res_pass.returncode, 0)
        self.assertIn("PASS", res_pass.stdout)

        # 3. Create a branch and a valid PR merge commit
        run_cmd(["git", "switch", "-c", "feat/sample-task"], self.root)
        (self.root / "feature.txt").write_text("feature", encoding="utf-8")
        run_cmd(["git", "add", "feature.txt"], self.root)
        run_cmd(["git", "commit", "-m", "feat(sample): implement feature"], self.root)
        run_cmd(["git", "switch", "main"], self.root)

        # Merge with 2 parents and standard PR merge subject
        res_merge = run_cmd(
            ["git", "merge", "--no-ff", "-m", "Merge pull request #101 from user/feat/sample-task", "feat/sample-task"],
            self.root
        )
        self.assertEqual(res_merge.returncode, 0)

        # Check passes with new PR merge without needing baseline update
        res_after_merge = run_cmd(
            [sys.executable, str(check_history_py), "--ref", "main", "--baseline", str(baseline_file)],
            self.root
        )
        self.assertEqual(res_after_merge.returncode, 0)
        self.assertIn("PASS", res_after_merge.stdout)

    def test_02_commit_lint(self):
        """commit lint accepts conventional subjects, rejects WIP, fixup!, empty subject, and 101 char subject, and skips merge commits."""
        self._init_git_repo()
        check_commits_py = REPO_ROOT / "scripts" / "check_commits.py"

        # Valid commit passes
        (self.root / "fileA.txt").write_text("A", encoding="utf-8")
        run_cmd(["git", "add", "fileA.txt"], self.root)
        run_cmd(["git", "commit", "-m", "feat(core): add feature A"], self.root)
        res_ok = run_cmd([sys.executable, str(check_commits_py), "--base", "HEAD~1", "--head", "HEAD"], self.root)
        self.assertEqual(res_ok.returncode, 0)
        self.assertIn("PASS", res_ok.stdout)

        # Merge commit skipped
        run_cmd(["git", "switch", "-c", "feat/dummy"], self.root)
        (self.root / "fileB.txt").write_text("B", encoding="utf-8")
        run_cmd(["git", "add", "fileB.txt"], self.root)
        run_cmd(["git", "commit", "-m", "fix(bug): fix issue B"], self.root)
        run_cmd(["git", "switch", "main"], self.root)
        run_cmd(["git", "merge", "--no-ff", "-m", "Merge pull request #2 from feat/dummy", "feat/dummy"], self.root)

        # Check including the merge commit passes
        res_merge = run_cmd([sys.executable, str(check_commits_py), "--base", "HEAD~2", "--head", "HEAD"], self.root)
        self.assertEqual(res_merge.returncode, 0)

        # Reject WIP
        (self.root / "wip.txt").write_text("W", encoding="utf-8")
        run_cmd(["git", "add", "wip.txt"], self.root)
        run_cmd(["git", "commit", "-m", "WIP: work in progress"], self.root)
        res_wip = run_cmd([sys.executable, str(check_commits_py), "--base", "HEAD~1", "--head", "HEAD"], self.root)
        self.assertEqual(res_wip.returncode, 1)
        self.assertIn("forbidden prefix 'wip'", res_wip.stdout)

        # Reject fixup!
        (self.root / "fixup.txt").write_text("F", encoding="utf-8")
        run_cmd(["git", "add", "fixup.txt"], self.root)
        run_cmd(["git", "commit", "-m", "fixup! fix(bug): fix issue"], self.root)
        res_fixup = run_cmd([sys.executable, str(check_commits_py), "--base", "HEAD~1", "--head", "HEAD"], self.root)
        self.assertEqual(res_fixup.returncode, 1)
        self.assertIn("forbidden prefix 'fixup!'", res_fixup.stdout)

        # Reject empty subject
        (self.root / "empty.txt").write_text("E", encoding="utf-8")
        run_cmd(["git", "add", "empty.txt"], self.root)
        run_cmd(["git", "commit", "-m", "feat:   "], self.root)
        res_empty = run_cmd([sys.executable, str(check_commits_py), "--base", "HEAD~1", "--head", "HEAD"], self.root)
        self.assertEqual(res_empty.returncode, 1)

        # Reject 101 character subject
        long_subject = "feat(core): " + "x" * (101 - len("feat(core): "))
        self.assertEqual(len(long_subject), 101)
        (self.root / "long.txt").write_text("L", encoding="utf-8")
        run_cmd(["git", "add", "long.txt"], self.root)
        run_cmd(["git", "commit", "-m", long_subject], self.root)
        res_long = run_cmd([sys.executable, str(check_commits_py), "--base", "HEAD~1", "--head", "HEAD"], self.root)
        self.assertEqual(res_long.returncode, 1)
        self.assertIn("exceeds 100 characters", res_long.stdout)

    def test_03_trail_output(self):
        """trail output shows PR number, branch and commit count and flags a direct commit."""
        self._init_git_repo()
        dev_py = REPO_ROOT / "scripts" / "dev.py"

        # Direct commit
        (self.root / "d1.txt").write_text("d1", encoding="utf-8")
        run_cmd(["git", "add", "d1.txt"], self.root)
        run_cmd(["git", "commit", "-m", "chore: direct commit"], self.root)

        # PR merge with 2 commits on branch
        run_cmd(["git", "switch", "-c", "feat/my-feature"], self.root)
        (self.root / "p1.txt").write_text("p1", encoding="utf-8")
        run_cmd(["git", "add", "p1.txt"], self.root)
        run_cmd(["git", "commit", "-m", "feat: step one"], self.root)
        (self.root / "p2.txt").write_text("p2", encoding="utf-8")
        run_cmd(["git", "add", "p2.txt"], self.root)
        run_cmd(["git", "commit", "-m", "feat: step two"], self.root)
        run_cmd(["git", "switch", "main"], self.root)

        run_cmd(["git", "merge", "--no-ff", "-m", "Merge pull request #55 from user/feat/my-feature", "feat/my-feature"], self.root)

        res = run_cmd([sys.executable, str(dev_py), "trail", "--limit", "10"], self.root)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PR #55 (user/feat/my-feature) -> merge", res.stdout)
        self.assertIn("2 commit(s)", res.stdout)
        self.assertIn("! ", res.stdout)
        self.assertIn("chore: direct commit", res.stdout)
        self.assertIn("git log --graph --oneline --decorate -30", res.stdout)

    def test_04_release_plan(self):
        """release-plan ignores merge commits in type counts and shows PRs merged."""
        self._init_git_repo()
        dev_py = REPO_ROOT / "scripts" / "dev.py"

        run_cmd(["git", "tag", "v0.1.0"], self.root)

        # Add 1 feat commit on branch and merge as PR
        run_cmd(["git", "switch", "-c", "feat/add-foo"], self.root)
        (self.root / "foo.txt").write_text("foo", encoding="utf-8")
        run_cmd(["git", "add", "foo.txt"], self.root)
        run_cmd(["git", "commit", "-m", "feat: add foo capability"], self.root)
        run_cmd(["git", "switch", "main"], self.root)
        run_cmd(["git", "merge", "--no-ff", "-m", "Merge pull request #77 from feat/add-foo", "feat/add-foo"], self.root)

        res = run_cmd([sys.executable, str(dev_py), "release-plan"], self.root)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PRs merged:                 1", res.stdout)
        self.assertIn("'feat': 1", res.stdout)
        self.assertNotIn("'merge'", res.stdout.lower())

    def test_05_repo_settings(self):
        """repo-settings with a stub gh first in PATH prints OK/WARN, handles 403 and missing gh."""
        self._init_git_repo()
        dev_py = REPO_ROOT / "scripts" / "dev.py"

        stub_dir = Path(tempfile.mkdtemp(prefix="stub_gh_"))
        try:
            gh_stub = stub_dir / ("gh.cmd" if sys.platform == "win32" else "gh")
            # The stub will be called by dev.py. It must fail if called with POST/PATCH/PUT/DELETE or pr merge.
            stub_script = f"""#!{sys.executable}
import sys, json

args = sys.argv[1:]

for bad in ["-X", "POST", "PATCH", "PUT", "DELETE"]:
    if bad in args:
        sys.exit(f"Stub Error: forbidden write method in args: {{args}}")

if "pr" in args and "merge" in args:
    sys.exit("Stub Error: forbidden 'pr merge' called!")

mode = sys.argv[0] + "_mode.txt"
with open("{stub_dir.as_posix()}/mode.txt", "r") as f:
    mode = f.read().strip()

if mode == "compliant":
    if "repo" in args and "view" in args:
        print(json.dumps({{
            "nameWithOwner": "owner/repo",
            "defaultBranchRef": {{"name": "main"}},
            "mergeCommitAllowed": True,
            "squashMergeAllowed": False,
            "rebaseMergeAllowed": False,
            "deleteBranchOnMerge": True
        }}))
        sys.exit(0)
    elif "api" in args:
        print(json.dumps({{
            "required_linear_history": {{"enabled": False}},
            "enforce_admins": {{"enabled": True}}
        }}))
        sys.exit(0)

elif mode == "non_compliant":
    if "repo" in args and "view" in args:
        print(json.dumps({{
            "nameWithOwner": "owner/repo",
            "defaultBranchRef": {{"name": "main"}},
            "mergeCommitAllowed": True,
            "squashMergeAllowed": True,
            "rebaseMergeAllowed": True,
            "deleteBranchOnMerge": False
        }}))
        sys.exit(0)
    elif "api" in args:
        print(json.dumps({{
            "required_linear_history": {{"enabled": True}},
            "enforce_admins": {{"enabled": False}}
        }}))
        sys.exit(0)

elif mode == "forbidden_post":
    # Used to verify the stub enforces the test requirement
    pass

elif mode == "403_error":
    if "repo" in args and "view" in args:
        print(json.dumps({{
            "nameWithOwner": "owner/repo",
            "defaultBranchRef": {{"name": "main"}},
            "mergeCommitAllowed": True,
            "squashMergeAllowed": False,
            "rebaseMergeAllowed": False,
            "deleteBranchOnMerge": True
        }}))
        sys.exit(0)
    elif "api" in args:
        sys.stderr.write("HTTP 403 Forbidden\\n")
        sys.exit(1)

sys.exit(0)
"""
            gh_stub.write_text(stub_script, encoding="utf-8")
            gh_stub.chmod(gh_stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            env = {"PATH": f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

            # 1. Compliant mode -> All OK
            (stub_dir / "mode.txt").write_text("compliant", encoding="utf-8")
            res_comp = run_cmd([sys.executable, str(dev_py), "repo-settings"], self.root, env=env)
            self.assertEqual(res_comp.returncode, 0)
            self.assertIn("Merge commits allowed            [OK  ]", res_comp.stdout)
            self.assertIn("Squash merging allowed           [OK  ]", res_comp.stdout)
            self.assertIn("Auto delete head branches        [OK  ]", res_comp.stdout)
            self.assertIn("Linear history required          [OK  ]", res_comp.stdout)
            self.assertIn("Enforce on administrators        [OK  ]", res_comp.stdout)
            self.assertNotIn("WARN", res_comp.stdout)

            # 2. Non-compliant mode -> WARN
            (stub_dir / "mode.txt").write_text("non_compliant", encoding="utf-8")
            res_non = run_cmd([sys.executable, str(dev_py), "repo-settings"], self.root, env=env)
            self.assertEqual(res_non.returncode, 0)
            self.assertIn("Squash merging allowed           [WARN]", res_non.stdout)
            self.assertIn("Linear history required          [WARN]", res_non.stdout)

            # 3. 403 error mode
            (stub_dir / "mode.txt").write_text("403_error", encoding="utf-8")
            res_403 = run_cmd([sys.executable, str(dev_py), "repo-settings"], self.root, env=env)
            self.assertEqual(res_403.returncode, 0)
            self.assertIn("cannot read, check the settings page", res_403.stdout)

            # 4. Missing gh mode
            res_no_gh = run_cmd([sys.executable, str(dev_py), "repo-settings"], self.root, env={"PATH": ""})
            self.assertEqual(res_no_gh.returncode, 0)
            self.assertIn("gh CLI not installed or not in PATH", res_no_gh.stdout)
            self.assertIn("Manual verification checklist", res_no_gh.stdout)

            # 5. Verify stub fails if called with forbidden method
            bad_res = run_cmd([sys.executable, str(gh_stub), "api", "-X", "POST", "something"], self.root)
            self.assertNotEqual(bad_res.returncode, 0)
            self.assertIn("Stub Error", bad_res.stderr)
        finally:
            shutil.rmtree(stub_dir, ignore_errors=True)

    def test_06_static_forbidden_strings(self):
        """None of the new scripts contains --squash, --rebase, 'pr merge', ' push', 'reset --hard', 'filter-branch', '--admin' or 'rebase'."""
        target_scripts = [
            REPO_ROOT / "scripts" / "check_history.py",
            REPO_ROOT / "scripts" / "check_commits.py",
            REPO_ROOT / "scripts" / "dev.py",
        ]
        forbidden_tokens = [
            "--squash",
            "--rebase",
            "pr merge",
            " push",
            "reset --hard",
            "filter-branch",
            "--admin",
            "rebase",
        ]
        violations = []
        for s in target_scripts:
            self.assertTrue(s.is_file(), f"Target script {s} must exist.")
            content = s.read_text(encoding="utf-8")
            for tok in forbidden_tokens:
                if tok in content:
                    violations.append((s.name, tok))

        self.assertEqual(
            violations,
            [],
            f"Found forbidden tokens in scripts: {violations}"
        )


if __name__ == "__main__":
    unittest.main()
