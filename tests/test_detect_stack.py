#!/usr/bin/env python3
"""detect_stack.py must ignore agent folders such as .agents and .claude."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "project-bootstrap" / "scripts" / "detect_stack.py"


def run_detect(root: Path) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    res = subprocess.run([sys.executable, "-B", str(SCRIPT), str(root)], capture_output=True, text=True, env=env)
    if res.returncode != 0:
        raise AssertionError(res.stderr)
    return json.loads(res.stdout)


class TestDetectStackAgentFolders(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="bf-detect-"))
        (self.root / "package.json").write_text(json.dumps({"name": "demo", "dependencies": {"react": "19"}}))
        src = self.root / "src" / "components"
        src.mkdir(parents=True)
        (src / "Button.jsx").write_text("export const Button = () => null\n")
        (self.root / "src" / "index.css").write_text(":root { --brand: #fff; }\n")
        # Installed Build Forge skills with a large token file, python scripts and storage words
        skill = self.root / ".agents" / "skills" / "scaffold-app"
        (skill / "assets").mkdir(parents=True)
        (skill / "scripts").mkdir(parents=True)
        tokens = ":root {\n" + "".join(f"  --t{i}: #000;\n" for i in range(60)) + "}\n"
        (skill / "assets" / "tokens.base.css").write_text(tokens)
        (skill / "scripts" / "ensure_check_script.py").write_text("# uses localStorage and supabase words\n")
        # A copied agent skills folder must be ignored too
        shutil.copytree(self.root / ".agents" / "skills", self.root / ".claude" / "skills")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_agent_folders_are_not_project_code(self):
        facts = run_detect(self.root)
        files = [t["file"] for t in facts["token_file_candidates"]]
        self.assertEqual(files, ["src/index.css"])
        self.assertNotIn("py", facts["naming_by_extension"])
        self.assertEqual(facts["source_file_count"], 1)
        self.assertEqual(facts["storage_hints"], {})

    def test_agent_folders_still_reported_as_skill_dirs(self):
        facts = run_detect(self.root)
        paths = [d["path"] for d in facts["skill_dirs"]]
        self.assertIn(".agents/skills", paths)
        self.assertIn(".claude/skills", paths)

    def test_help_flag(self):
        res = subprocess.run([sys.executable, "-B", str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Usage", res.stdout)


if __name__ == "__main__":
    unittest.main()
