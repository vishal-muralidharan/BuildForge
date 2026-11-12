#!/usr/bin/env python3
"""legacy_import.py must not read agent links to .agents/skills as user rules.

Also checks that the faster similarity test makes the same decisions as the exact one.
"""
import difflib
import re
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
sys.path.insert(0, str(REPO_ROOT / "skills" / "project-bootstrap" / "scripts"))

import legacy_import  # noqa: E402


def exact_decision(t1, t2, overlap_min, ratio_with_overlap, ratio_alone):
    s1 = legacy_import.normalize_text(t1)
    s2 = legacy_import.normalize_text(t2)
    if not s1 or not s2:
        return False
    a, b = set(s1.split()), set(s2.split())
    overlap = len(a & b) / max(1, len(a | b))
    ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
    return (overlap >= overlap_min and ratio >= ratio_with_overlap) or ratio >= ratio_alone


class TestLegacyImportLinks(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="bf-legacy-links-"))
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["node", str(CLI_PATH), "install"], cwd=self.root, capture_output=True, check=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def local_files(self):
        active, skipped, _, counts = legacy_import.find_and_classify_sources(self.root)
        locals_ = [f.relative_to(self.root).as_posix() for f, cls, _ in active if cls == "local"]
        return locals_, skipped, counts

    def test_symlinked_claude_skills_folder_is_skipped(self):
        claude = self.root / ".claude"
        claude.mkdir()
        try:
            os.symlink(os.path.join("..", ".agents", "skills"), claude / "skills", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available")
        locals_, skipped, counts = self.local_files()
        self.assertFalse([f for f in locals_ if f.startswith(".claude/")], locals_)
        self.assertEqual(counts["local"], 0)
        self.assertTrue(any(s["path"] == ".claude/skills" and s["class"] == "build-forge" for s in skipped))

    def test_copied_claude_skills_are_skipped(self):
        shutil.copytree(self.root / ".agents" / "skills", self.root / ".claude" / "skills")
        locals_, skipped, counts = self.local_files()
        self.assertFalse([f for f in locals_ if f.startswith(".claude/")], locals_)
        self.assertEqual(counts["local"], 0)
        self.assertTrue(any(s["path"] == ".claude/skills/atomic-commits" for s in skipped))

    def test_user_claude_skill_is_still_read(self):
        mine = self.root / ".claude" / "skills" / "my-rules"
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text("---\nname: my-rules\ndescription: house rules\n---\n\n- Always use the Button primitive for actions.\n")
        locals_, _, _ = self.local_files()
        self.assertIn(".claude/skills/my-rules/SKILL.md", locals_)

    def test_edited_copy_is_read_as_local(self):
        shutil.copytree(self.root / ".agents" / "skills" / "repo-search", self.root / ".claude" / "skills" / "repo-search")
        extra = self.root / ".claude" / "skills" / "repo-search" / "NOTES.md"
        extra.write_text("- Never search inside the vendor folder.\n")
        locals_, _, _ = self.local_files()
        self.assertIn(".claude/skills/repo-search/NOTES.md", locals_)


    def test_pointer_files_from_link_are_generated(self):
        subprocess.run(["node", str(CLI_PATH), "link", "--agents", "all"], cwd=self.root, capture_output=True, check=True)
        locals_, skipped, counts = self.local_files()
        self.assertEqual(locals_, [])
        self.assertEqual(counts["local"], 0)
        generated = {s["path"] for s in skipped if s["class"] == "generated"}
        self.assertIn("CLAUDE.md", generated)
        self.assertIn(".github/copilot-instructions.md", generated)

    def test_hand_written_claude_md_is_local(self):
        (self.root / "CLAUDE.md").write_text("- Always run npm test before a commit.\n")
        locals_, _, _ = self.local_files()
        self.assertIn("CLAUDE.md", locals_)


class TestSimilarityDecisions(unittest.TestCase):
    def test_fast_decision_matches_exact_decision(self):
        texts = []
        for md in sorted((REPO_ROOT / "skills").rglob("*.md"))[:40]:
            for line in md.read_text(encoding="utf-8").splitlines():
                line = re.sub(r"^[-*\\s]+", "", line).strip()
                if 20 <= len(line) <= 300:
                    texts.append(line)
        texts = texts[:220]
        texts += [t.replace("the", "a") for t in texts[:40]]
        thresholds = [(0.85, 0.85, 0.90), (0.50, 0.55, 0.72)]
        checked = 0
        for i in range(0, len(texts), 3):
            for j in range(i + 1, min(len(texts), i + 25)):
                for th in thresholds:
                    self.assertEqual(
                        legacy_import.is_similar(texts[i], texts[j], *th),
                        exact_decision(texts[i], texts[j], *th),
                        (texts[i], texts[j], th),
                    )
                    checked += 1
        self.assertGreater(checked, 1000)


if __name__ == "__main__":
    unittest.main()
