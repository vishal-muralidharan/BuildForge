#!/usr/bin/env python3
"""Comprehensive test suite for branchflow.py branch workflow tool."""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BRANCHFLOW_PY = REPO_ROOT / "skills" / "feature-delivery" / "scripts" / "branchflow.py"


def run_git(cmd, cwd):
    """Run git command in directory."""
    res = subprocess.run(["git"] + cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    return res


def run_bf(args, cwd):
    """Run branchflow.py in directory."""
    cmd = [sys.executable, "-B", str(BRANCHFLOW_PY)] + args
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    return res


class TestBranchflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bf-test-branchflow-")
        self.root = Path(self.tmp)

        # Initialize test repository
        run_git(["init", "-q", "-b", "main"], self.root)
        run_git(["config", "user.name", "Test User"], self.root)
        run_git(["config", "user.email", "test@example.com"], self.root)

        # Initial commit
        (self.root / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        run_git(["add", "README.md"], self.root)
        run_git(["commit", "-m", "chore: initial commit"], self.root)

        # Set up .agents profile
        (self.root / ".agents").mkdir(parents=True, exist_ok=True)
        prof_data = {
            "project": {"name": "test-repo"},
            "git": {
                "commit_format": "<type>(<scope>): <subject>",
                "types": ["feat", "fix", "chore", "docs", "test"],
                "workflow": {
                    "default_branch": "main",
                    "mode": "ask",
                    "branch_format": "<type>/<slug>",
                    "sync": "merge",
                    "merge_method": "squash",
                    "remote": "origin",
                    "cleanup": "ask",
                    "worktree": False,
                },
            },
        }
        import yaml
        (self.root / ".agents" / "project-profile.yaml").write_text(yaml.dump(prof_data), encoding="utf-8")
        run_git(["add", ".agents"], self.root)
        run_git(["commit", "-m", "chore: add profile"], self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_status_command(self):
        """status command reports branch, base, ahead/behind, dirty, remote, forge, and state."""
        res = run_bf(["status", "--json", "--root", str(self.root)], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(data["branch"], "main")
        self.assertEqual(data["base"], "main")
        self.assertFalse(data["dirty"])
        self.assertIsNone(data["state"])

    def test_02_start_happy_path_and_guard(self):
        """start creates branch, records state, and guard prevents committing on default branch."""
        # 1. Start task branch
        res = run_bf(["start", "--name", "add-keypad", "--type", "feat", "--root", str(self.root)], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Started task branch 'feat/add-keypad'", res.stdout)

        # Check current branch
        res_b = run_git(["branch", "--show-current"], self.root)
        self.assertEqual(res_b.stdout.strip(), "feat/add-keypad")

        # Check state file
        sfile = self.root / ".agents" / "work" / "branch-state.json"
        self.assertTrue(sfile.is_file())
        state = json.loads(sfile.read_text(encoding="utf-8"))
        self.assertEqual(state["task"], "add-keypad")
        self.assertEqual(state["branch"], "feat/add-keypad")
        self.assertEqual(state["base"], "main")
        self.assertEqual(state["status"], "started")
        self.assertIsNone(state["parent"])

        # Guard on task branch should pass
        res_g1 = run_bf(["guard", "--root", str(self.root)], self.root)
        self.assertEqual(res_g1.returncode, 0)

        # Switch to main; guard must now fail
        run_git(["checkout", "main"], self.root)
        res_g2 = run_bf(["guard", "--root", str(self.root)], self.root)
        self.assertNotEqual(res_g2.returncode, 0)
        self.assertIn("Cannot commit directly on default branch 'main'", res_g2.stderr)

    def test_03_start_refusals(self):
        """start refuses dirty tree, existing branch, and invalid slug."""
        # A. Dirty tree refusal
        (self.root / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
        res_dirty = run_bf(["start", "--name", "test-dirty", "--type", "feat", "--root", str(self.root)], self.root)
        self.assertNotEqual(res_dirty.returncode, 0)
        self.assertIn("Working tree has uncommitted changes", res_dirty.stderr)
        (self.root / "dirty.txt").unlink()

        # B. Bad slug refusal (>40 chars or uppercase)
        res_bad_slug = run_bf(["start", "--name", "ThisIsWayTooLongAndNotKebabCase12345678901234567890", "--type", "feat", "--root", str(self.root)], self.root)
        self.assertNotEqual(res_bad_slug.returncode, 0)
        self.assertIn("must be lowercase kebab-case and 40 characters or fewer", res_bad_slug.stderr)

        # C. Existing branch refusal
        run_git(["branch", "feat/existing"], self.root)
        res_exist = run_bf(["start", "--name", "existing", "--type", "feat", "--root", str(self.root)], self.root)
        self.assertNotEqual(res_exist.returncode, 0)
        self.assertIn("already exists locally", res_exist.stderr)

    def test_04_stacked_branches_depth_2_and_refusal_depth_3(self):
        """Stacked branches allow depth 2 and refuse depth 3."""
        # 1. Start parent task branch (depth 1)
        res1 = run_bf(["start", "--name", "parent-task", "--type", "feat", "--root", str(self.root)], self.root)
        self.assertEqual(res1.returncode, 0)

        # 2. Start child branch based on parent-task (depth 2)
        res2 = run_bf(["start", "--name", "child-task", "--type", "feat", "--base", "feat/parent-task", "--root", str(self.root)], self.root)
        self.assertEqual(res2.returncode, 0)
        state2 = json.loads((self.root / ".agents" / "work" / "branch-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state2["parent"], "feat/parent-task")

        # 3. Attempt grandchild branch based on child-task (depth 3) - MUST REFUSE
        res3 = run_bf(["start", "--name", "grandchild-task", "--type", "feat", "--base", "feat/child-task", "--root", str(self.root)], self.root)
        self.assertNotEqual(res3.returncode, 0)
        self.assertIn("Stacked branch depth limit exceeded", res3.stderr)

    def test_05_worktree_mode(self):
        """start --worktree creates separate worktree and records worktree_path."""
        res = run_bf(["start", "--name", "wt-feature", "--type", "feat", "--worktree", "--root", str(self.root)], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        state = json.loads((self.root / ".agents" / "work" / "branch-state.json").read_text(encoding="utf-8"))
        self.assertIsNotNone(state["worktree_path"])
        self.assertTrue(Path(state["worktree_path"]).is_dir())

    def test_06_handoff_and_choices(self):
        """handoff reports commits, files, try-it checklist, sets ready-for-test."""
        run_bf(["start", "--name", "handoff-test", "--type", "feat", "--root", str(self.root)], self.root)

        # Create a commit
        (self.root / "feature.py").write_text("# feature code\n", encoding="utf-8")
        run_git(["add", "feature.py"], self.root)
        run_git(["commit", "-m", "feat(handoff): implement feature"], self.root)

        res = run_bf(["handoff", "--json", "--root", str(self.root)], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(data["branch"], "feat/handoff-test")
        self.assertIn("feature.py", data["changed_files"])
        self.assertGreater(len(data["commits"]), 0)
        self.assertIn("approve", data["choices"])

        state = json.loads((self.root / ".agents" / "work" / "branch-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "ready-for-test")

    def test_06b_changes_requested_then_commit_then_approve(self):
        """User requests changes on handoff, another commit is added on the same branch, and then approved."""
        run_bf(["start", "--name", "iterate-test", "--type", "feat", "--root", str(self.root)], self.root)
        (self.root / "code.py").write_text("v1\n", encoding="utf-8")
        run_git(["add", "code.py"], self.root)
        run_git(["commit", "-m", "feat(iter): v1 implementation"], self.root)

        # 1. First handoff -> ready-for-test
        res1 = run_bf(["handoff", "--json", "--root", str(self.root)], self.root)
        self.assertEqual(res1.returncode, 0)
        state1 = json.loads((self.root / ".agents" / "work" / "branch-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state1["status"], "ready-for-test")

        # 2. User requests changes -> state becomes changes-requested
        state1["status"] = "changes-requested"
        (self.root / ".agents" / "work" / "branch-state.json").write_text(json.dumps(state1), encoding="utf-8")

        # 3. Implement requested change on same branch
        (self.root / "code.py").write_text("v2\n", encoding="utf-8")
        run_git(["add", "code.py"], self.root)
        run_git(["commit", "-m", "fix(iter): address user feedback"], self.root)

        # 4. Second handoff -> ready-for-test again with 2 commits
        res2 = run_bf(["handoff", "--json", "--root", str(self.root)], self.root)
        self.assertEqual(res2.returncode, 0)
        data2 = json.loads(res2.stdout)
        self.assertEqual(len(data2["commits"]), 2)

        # 5. User approves -> merge-local succeeds
        res_merge = run_bf(["merge-local", "--approved", "--phrase", "yes merge locally", "--root", str(self.root)], self.root)
        self.assertEqual(res_merge.returncode, 0)
        state_final = json.loads((self.root / ".agents" / "work" / "branch-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state_final["status"], "merged")

    def test_07_sync_conflict_stops_without_resolving(self):
        """sync on conflicting changes stops cleanly and leaves repository in conflict state."""
        run_bf(["start", "--name", "conflict-task", "--type", "feat", "--root", str(self.root)], self.root)
        (self.root / "shared.txt").write_text("branch line\n", encoding="utf-8")
        run_git(["add", "shared.txt"], self.root)
        run_git(["commit", "-m", "feat(task): branch edit"], self.root)

        # Make conflicting edit on main
        run_git(["checkout", "main"], self.root)
        (self.root / "shared.txt").write_text("main conflicting line\n", encoding="utf-8")
        run_git(["add", "shared.txt"], self.root)
        run_git(["commit", "-m", "chore: main edit"], self.root)

        # Switch back to task branch and sync
        run_git(["checkout", "feat/conflict-task"], self.root)
        res_sync = run_bf(["sync", "--root", str(self.root)], self.root)
        self.assertNotEqual(res_sync.returncode, 0)
        self.assertIn("Sync conflict", res_sync.stderr)

        # Check repository is in conflict state
        status_out = run_git(["status"], self.root).stdout
        self.assertIn("Unmerged paths", status_out)

    def test_08_merge_local_squash_and_sync_main(self):
        """merge-local squash requires phrase, creates clean commit, and sync-main verifies."""
        run_bf(["start", "--name", "local-squash", "--type", "feat", "--root", str(self.root)], self.root)
        (self.root / "item.txt").write_text("item content\n", encoding="utf-8")
        run_git(["add", "item.txt"], self.root)
        run_git(["commit", "-m", "feat(item): add item"], self.root)

        # 1. Refusal without exact phrase
        res_fail = run_bf(["merge-local", "--approved", "--phrase", "merge please", "--root", str(self.root)], self.root)
        self.assertNotEqual(res_fail.returncode, 0)
        self.assertIn("Confirmation required. Pass: --phrase \"yes merge locally\"", res_fail.stderr)

        # 2. Merge with exact phrase
        res_merge = run_bf(["merge-local", "--approved", "--phrase", "yes merge locally", "--root", str(self.root)], self.root)
        self.assertEqual(res_merge.returncode, 0, res_merge.stderr)
        self.assertIn("Successfully merged 'feat/local-squash' into 'main'", res_merge.stdout)

        state = json.loads((self.root / ".agents" / "work" / "branch-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "merged")
        self.assertIn("merge_sha", state)

        # 3. sync-main confirms merge presence
        res_sm = run_bf(["sync-main", "--root", str(self.root)], self.root)
        self.assertEqual(res_sm.returncode, 0, res_sm.stderr)
        self.assertIn("Confirmed merge commit", res_sm.stdout)

    def test_09_cleanup_requires_proof_and_phrase(self):
        """cleanup refuses without proof and without phrase, then deletes when proven."""
        run_bf(["start", "--name", "cleanup-test", "--type", "feat", "--root", str(self.root)], self.root)
        (self.root / "clean.txt").write_text("clean test\n", encoding="utf-8")
        run_git(["add", "clean.txt"], self.root)
        run_git(["commit", "-m", "feat(clean): clean commit"], self.root)

        # 1. Refuses without phrase
        res_fail_phrase = run_bf(["cleanup", "--approved", "--phrase", "delete please", "--root", str(self.root)], self.root)
        self.assertNotEqual(res_fail_phrase.returncode, 0)
        self.assertIn("Pass: --phrase \"yes delete branch cleanup-test\"", res_fail_phrase.stderr)

        # 2. Refuses without merge proof
        run_git(["checkout", "main"], self.root)
        res_fail_proof = run_bf(["cleanup", "--approved", "--phrase", "yes delete branch cleanup-test", "--root", str(self.root)], self.root)
        self.assertNotEqual(res_fail_proof.returncode, 0)
        self.assertIn("not proven merged", res_fail_proof.stderr)

        # 3. Merge locally first
        run_bf(["merge-local", "--approved", "--phrase", "yes merge locally", "--root", str(self.root)], self.root)

        # 4. Cleanup with proof succeeds
        res_clean = run_bf(["cleanup", "--approved", "--phrase", "yes delete branch cleanup-test", "--root", str(self.root)], self.root)
        self.assertEqual(res_clean.returncode, 0, res_clean.stderr)
        self.assertIn("Cleaned up task branch 'feat/cleanup-test' successfully", res_clean.stdout)

        # Branch should no longer exist locally
        res_chk = run_git(["rev-parse", "--verify", "refs/heads/feat/cleanup-test"], self.root)
        self.assertNotEqual(res_chk.returncode, 0)

    def test_10_park_and_resume(self):
        """park sets parked, resume reloads task branch."""
        run_bf(["start", "--name", "park-task", "--type", "feat", "--root", str(self.root)], self.root)

        # Park
        res_park = run_bf(["park", "--root", str(self.root)], self.root)
        self.assertEqual(res_park.returncode, 0)
        state_parked = json.loads((self.root / ".agents" / "work" / "branch-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state_parked["status"], "parked")

        # Resume
        res_resume = run_bf(["resume", "--task", "park-task", "--root", str(self.root)], self.root)
        self.assertEqual(res_resume.returncode, 0)
        self.assertEqual(run_git(["branch", "--show-current"], self.root).stdout.strip(), "feat/park-task")
        state_resumed = json.loads((self.root / ".agents" / "work" / "branch-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state_resumed["status"], "in-progress")

    def test_11_abandon_keeps_branch_and_tags(self):
        """abandon requires phrase, keeps branch, and creates local tag."""
        run_bf(["start", "--name", "abandon-task", "--type", "feat", "--root", str(self.root)], self.root)

        # Refusal without exact phrase
        res_fail = run_bf(["abandon", "--approved", "--phrase", "abandon it", "--root", str(self.root)], self.root)
        self.assertNotEqual(res_fail.returncode, 0)

        # Abandon with exact phrase
        res_ab = run_bf(["abandon", "--approved", "--phrase", "yes abandon abandon-task", "--root", str(self.root)], self.root)
        self.assertEqual(res_ab.returncode, 0)
        self.assertIn("abandoned (tagged locally as 'abandoned/abandon-task')", res_ab.stdout)

        # Branch still exists
        res_b = run_git(["rev-parse", "--verify", "refs/heads/feat/abandon-task"], self.root)
        self.assertEqual(res_b.returncode, 0)

        # Tag exists
        res_t = run_git(["rev-parse", "--verify", "refs/tags/abandoned/abandon-task"], self.root)
        self.assertEqual(res_t.returncode, 0)

    def test_12_corrupted_state_file_handled_gracefully(self):
        """Corrupted state file is handled gracefully without unhandled exception."""
        (self.root / ".agents" / "work").mkdir(parents=True, exist_ok=True)
        (self.root / ".agents" / "work" / "branch-state.json").write_text("{invalid json", encoding="utf-8")

        res = run_bf(["status", "--root", str(self.root)], self.root)
        self.assertEqual(res.returncode, 0)
        self.assertIn("no active task branch state", res.stdout)

    def test_14_merge_local_merge_commit_mode(self):
        """merge-local with merge_method 'merge' creates a true merge commit."""
        # Update profile to merge_method: merge
        import yaml
        prof_path = self.root / ".agents" / "project-profile.yaml"
        prof = yaml.safe_load(prof_path.read_text(encoding="utf-8"))
        prof["git"]["workflow"]["merge_method"] = "merge"
        prof_path.write_text(yaml.dump(prof), encoding="utf-8")
        run_git(["add", ".agents"], self.root)
        run_git(["commit", "-m", "chore: switch workflow merge_method to merge"], self.root)

        run_bf(["start", "--name", "merge-commit-task", "--type", "feat", "--root", str(self.root)], self.root)
        (self.root / "item2.txt").write_text("item2 content\n", encoding="utf-8")
        run_git(["add", "item2.txt"], self.root)
        run_git(["commit", "-m", "feat(item2): add item 2"], self.root)

        res = run_bf(["merge-local", "--approved", "--phrase", "yes merge locally", "--root", str(self.root)], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Successfully merged 'feat/merge-commit-task' into 'main'", res.stdout)

        # Verify last commit on main has 2 parents (a true merge commit)
        res_parents = run_git(["rev-list", "--parents", "-n", "1", "HEAD"], self.root)
        parents = res_parents.stdout.strip().split()
        self.assertGreaterEqual(len(parents), 3)  # [commit_sha, parent1, parent2]

    def test_15_sync_rebase_pushed_requires_phrase(self):
        """sync with rebase policy on a branch pushed to remote requires rewrite phrase."""
        import yaml
        # 1. Set up bare remote
        bare_dir = tempfile.mkdtemp(prefix="bf-test-bare-")
        try:
            run_git(["init", "--bare", "-q"], bare_dir)
            run_git(["remote", "add", "origin", bare_dir], self.root)

            # Update workflow to sync: rebase
            prof_path = self.root / ".agents" / "project-profile.yaml"
            prof = yaml.safe_load(prof_path.read_text(encoding="utf-8"))
            prof["git"]["workflow"]["sync"] = "rebase"
            prof_path.write_text(yaml.dump(prof), encoding="utf-8")
            run_git(["add", ".agents"], self.root)
            run_git(["commit", "-m", "chore: set sync rebase"], self.root)

            # Push main to origin
            run_git(["push", "-u", "origin", "main"], self.root)

            # Start branch
            run_bf(["start", "--name", "rebase-pushed", "--type", "feat", "--root", str(self.root)], self.root)
            (self.root / "feat_file.txt").write_text("hello\n", encoding="utf-8")
            run_git(["add", "feat_file.txt"], self.root)
            run_git(["commit", "-m", "feat(file): add feat file"], self.root)

            # Simulate push of task branch to remote
            run_git(["push", "-u", "origin", "feat/rebase-pushed"], self.root)

            # Add commit on main
            run_git(["checkout", "main"], self.root)
            (self.root / "main_file.txt").write_text("main update\n", encoding="utf-8")
            run_git(["add", "main_file.txt"], self.root)
            run_git(["commit", "-m", "chore: update main"], self.root)
            run_git(["push", "origin", "main"], self.root)

            run_git(["checkout", "feat/rebase-pushed"], self.root)

            # Rebase sync without phrase should refuse
            res_fail = run_bf(["sync", "--root", str(self.root)], self.root)
            self.assertNotEqual(res_fail.returncode, 0)
            self.assertIn("pass: --phrase \"yes rewrite branch feat/rebase-pushed\"", res_fail.stderr)

            # Rebase sync with phrase succeeds
            res_ok = run_bf(["sync", "--phrase", "yes rewrite branch feat/rebase-pushed", "--root", str(self.root)], self.root)
            self.assertEqual(res_ok.returncode, 0, res_ok.stderr)
            self.assertIn("Successfully rebased", res_ok.stdout)
        finally:
            shutil.rmtree(bare_dir, ignore_errors=True)

    def test_16_revert_plan(self):
        """revert-plan outputs structured json steps for non-destructive reverting."""
        res = run_bf(["revert-plan", "HEAD", "--json", "--root", str(self.root)], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(data["target"], "HEAD")
        self.assertGreater(len(data["steps"]), 0)

    def test_17_forbidden_git_commands_static_lint(self):
        """branchflow.py contains no reset --hard, clean, checkout -- ., or push (except none), with an empty allow list."""
        content = BRANCHFLOW_PY.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Allow list is required to exist and be strictly empty
        ALLOW_LIST = []
        self.assertEqual(len(ALLOW_LIST), 0, "Allow list must be strictly empty")

        forbidden_patterns = [
            (r"reset\s+--hard", "reset --hard is strictly forbidden"),
            (r"\bgit\s+clean\b", "git clean is strictly forbidden"),
            (r"checkout\s+--\s+\.", "checkout -- . is strictly forbidden"),
            (r"\bgit\s+push\b", "git push is strictly forbidden"),
        ]

        violations = []
        for line_no, line in enumerate(lines, start=1):
            if line_no in ALLOW_LIST:
                continue
            for pat, desc in forbidden_patterns:
                if re.search(pat, line):
                    violations.append(f"Line {line_no}: {desc} -> {line.strip()}")

        self.assertEqual(violations, [], f"Forbidden commands found in branchflow.py:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
