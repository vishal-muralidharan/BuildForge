#!/usr/bin/env python3
"""Tests for check_sync.py path normalization, mdscan markdown parsing, and lint_py AST linting.

Covers:
a) The pattern '.agents/**' with existing .agents directory gives no missing directory warning.
   Same for '.agents/legacy-parity.md', '.agents/skills/**', '.github/**', './src/**', and '..\\.agents\\**'.
b) AGENTS.md whose Scope guide table has rows named skills, docs, and ui gives no missing skill warning.
c) A skill missing from the Areas table still warns.
d) Headings and table rows inside fenced code blocks (``` and ~~~) are ignored.
e) A second table inside Areas with other columns is ignored.
f) CRLF line endings and trailing spaces are handled cleanly.
g) lint_py.py fails on the original bug line and passes on the fix.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK_SYNC_PY = REPO_ROOT / "skills" / "sync-skills-and-docs" / "scripts" / "check_sync.py"
LINT_PY = REPO_ROOT / "scripts" / "lint_py.py"

sys.path.insert(0, str(REPO_ROOT / "skills" / "sync-skills-and-docs" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mdscan import sections, table_rows, tables  # noqa: E402
from check_sync import strip_dot_slash  # noqa: E402
from lint_py import check_source  # noqa: E402


class TestCheckSync(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp_dir.name)
        # Create a repo folder inside tmp_dir so parent has .agents for '..\\.agents\\**' test
        (self.base / ".agents").mkdir(parents=True, exist_ok=True)
        (self.base / ".agents" / "parent-marker.txt").write_text("ok", encoding="utf-8")

        self.root = self.base / "repo"
        self.root.mkdir(parents=True, exist_ok=True)

        # Scaffolding inside repo
        (self.root / ".agents" / "skills" / "targeted-module-testing").mkdir(parents=True, exist_ok=True)
        (self.root / ".agents" / "skills" / "targeted-module-testing" / "SKILL.md").write_text(
            "---\nname: targeted-module-testing\ndescription: test skill\n---\n# Targeted Module Testing\n",
            encoding="utf-8"
        )
        (self.root / ".agents" / "legacy-parity.md").write_text("# Legacy Parity\n", encoding="utf-8")
        (self.root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        (self.root / ".github" / "workflows" / "ci.yml").write_text("name: CI\n", encoding="utf-8")
        (self.root / "src").mkdir(parents=True, exist_ok=True)
        (self.root / "src" / "index.js").write_text("console.log('hello');\n", encoding="utf-8")

        self.profile_path = self.root / ".agents" / "project-profile.yaml"
        self.base_profile = {
            "schema_version": 1,
            "project": {"name": "test-app", "summary": "Test App", "mode": "existing"},
            "docs": {"agents_file": "AGENTS.md", "skills_dir": ".agents/skills"},
        }

    def tearDown(self):
        self.tmp_dir.cleanup()

    def run_check_sync(self, profile_file=None):
        prof = profile_file or self.profile_path
        cmd = [sys.executable, "-B", str(CHECK_SYNC_PY), "--profile", str(prof), "--root", str(self.root)]
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return res

    def test_01_glob_normalization(self):
        """Test a: .agents/**, .agents/legacy-parity.md, .agents/skills/**, .github/**, ./src/**, ..\\.agents\\**."""
        # Unit test strip_dot_slash
        self.assertEqual(strip_dot_slash(".agents/**"), ".agents/**")
        self.assertEqual(strip_dot_slash(".agents/legacy-parity.md"), ".agents/legacy-parity.md")
        self.assertEqual(strip_dot_slash(".agents/skills/**"), ".agents/skills/**")
        self.assertEqual(strip_dot_slash(".github/**"), ".github/**")
        self.assertEqual(strip_dot_slash("./src/**"), "src/**")
        self.assertEqual(strip_dot_slash("..\\.agents\\**"), "../.agents/**")
        self.assertEqual(strip_dot_slash(".\\.agents\\**"), ".agents/**")
        self.assertEqual(strip_dot_slash("././src/**"), "src/**")

        # Full check_sync run with these exact patterns in git.scopes
        profile_content = """schema_version: 1
project:
  name: test-app
  summary: Test app
  mode: existing
git:
  scopes:
    - name: agents-all
      paths:
        - ".agents/**"
    - name: legacy
      paths:
        - ".agents/legacy-parity.md"
    - name: skills
      paths:
        - ".agents/skills/**"
    - name: github
      paths:
        - ".github/**"
    - name: src-dot-slash
      paths:
        - "./src/**"
    - name: parent-windows-slashes
      paths:
        - "..\\\\.agents\\\\**"
"""
        self.profile_path.write_text(profile_content, encoding="utf-8")
        res = self.run_check_sync()
        self.assertNotIn("match no files in the repository", res.stdout)
        self.assertNotIn("match no files in the repository", res.stderr)

    def test_02_scope_guide_not_read_as_skills(self):
        """Test b: AGENTS.md Scope guide table with rows named skills, docs and ui gives no warning."""
        profile_content = """schema_version: 1
project:
  name: test-app
  summary: Test app
  mode: existing
docs:
  agents_file: AGENTS.md
  skills_dir: .agents/skills
"""
        self.profile_path.write_text(profile_content, encoding="utf-8")

        agents_md = """# Project AGENTS

## Areas
| Area | Skill | Description |
| --- | --- | --- |
| Testing | `targeted-module-testing` | Test runner |

## Git
### Scope guide
| Scope | Purpose |
| --- | --- |
| `skills` | Skill definitions |
| `docs` | Documentation changes |
| `ui` | UI changes |
"""
        (self.root / "AGENTS.md").write_text(agents_md, encoding="utf-8")

        res = self.run_check_sync()
        self.assertEqual(res.returncode, 0)
        self.assertNotIn("names 'skills'", res.stdout)
        self.assertNotIn("names 'docs'", res.stdout)
        self.assertNotIn("names 'ui'", res.stdout)

    def test_03_missing_skill_in_areas_table_warns(self):
        """Test c: A skill missing from the Areas table still warns."""
        profile_content = """schema_version: 1
project:
  name: test-app
  summary: Test app
  mode: existing
"""
        self.profile_path.write_text(profile_content, encoding="utf-8")

        agents_md = """# Project AGENTS

## Areas
| Area | Skill | Description |
| --- | --- | --- |
| Testing | `targeted-module-testing` | Test runner |
| UI | `nonexistent-ui-skill` | Missing skill |
"""
        (self.root / "AGENTS.md").write_text(agents_md, encoding="utf-8")

        res = self.run_check_sync()
        self.assertIn("AGENTS.md names 'nonexistent-ui-skill' but .agents/skills/nonexistent-ui-skill/SKILL.md is missing", res.stdout)

    def test_04_fenced_code_blocks_ignored(self):
        """Test d: Headings and rows inside a fenced code block are ignored."""
        profile_content = """schema_version: 1
project:
  name: test-app
  summary: Test app
  mode: existing
"""
        self.profile_path.write_text(profile_content, encoding="utf-8")

        agents_md = """# Project AGENTS

## Areas
| Area | Skill | Description |
| --- | --- | --- |
| Testing | `targeted-module-testing` | Test runner |

```markdown
# Areas
| Area | Skill |
| --- | --- |
| Fake | `fake-skill-in-backticks` |
```

~~~markdown
## Areas
| Area | Skill |
| --- | --- |
| Fake2 | `fake-skill-in-tildes` |
~~~
"""
        (self.root / "AGENTS.md").write_text(agents_md, encoding="utf-8")

        res = self.run_check_sync()
        self.assertNotIn("fake-skill-in-backticks", res.stdout)
        self.assertNotIn("fake-skill-in-tildes", res.stdout)

        # Directly verify mdscan functions
        secs = sections(agents_md)
        heading_names = [s["heading"] for s in secs]
        self.assertEqual(heading_names.count("Areas"), 1)
        self.assertNotIn("Fake", str(heading_names))

        rows = table_rows(secs.get("Areas"))
        for row in rows:
            self.assertNotIn("`fake-skill-in-backticks`", row)
            self.assertNotIn("`fake-skill-in-tildes`", row)

    def test_05_second_table_in_areas_ignored(self):
        """Test e: A second table inside Areas with other columns is ignored."""
        profile_content = """schema_version: 1
project:
  name: test-app
  summary: Test app
  mode: existing
"""
        self.profile_path.write_text(profile_content, encoding="utf-8")

        agents_md = """# Project AGENTS

## Areas
| Area | Skill | Description |
| --- | --- | --- |
| Testing | `targeted-module-testing` | Test runner |

Here is an architectural metrics table:

| Metric | Target | Notes |
| --- | --- | --- |
| Coverage | `test-coverage-threshold` | 80 percent |
| Bundle | `maximum-bundle-size` | 500kb |
"""
        (self.root / "AGENTS.md").write_text(agents_md, encoding="utf-8")

        res = self.run_check_sync()
        self.assertNotIn("test-coverage-threshold", res.stdout)
        self.assertNotIn("maximum-bundle-size", res.stdout)
        self.assertEqual(res.returncode, 0)

    def test_06_crlf_and_trailing_spaces(self):
        """Test f: CRLF and trailing spaces are handled cleanly."""
        profile_content = "schema_version: 1\r\nproject:\r\n  name: test-app\r\n  summary: Test app\r\n  mode: existing\r\n"
        self.profile_path.write_bytes(profile_content.encode("utf-8"))

        agents_md = (
            "## Areas   \r\n"
            "| Area | Skill | Description |   \r\n"
            "| --- | --- | --- |   \r\n"
            "| Testing | `targeted-module-testing` | Test runner |   \r\n\r\n"
            "### Scope guide   \r\n"
            "| Scope | Purpose |   \r\n"
            "| `skills` | Skill definitions |   \r\n"
        )
        (self.root / "AGENTS.md").write_bytes(agents_md.encode("utf-8"))

        res = self.run_check_sync()
        self.assertEqual(res.returncode, 0)
        self.assertNotIn("names 'skills'", res.stdout)

    def test_07_lint_py_checks(self):
        """Test g: lint_py.py fails on original bug lines and passes on the fixes."""
        bad_lstrip = 'norm = str(pat).replace("\\\\", "/").strip().lstrip("./")'
        errs_lstrip = check_source(bad_lstrip)
        self.assertTrue(len(errs_lstrip) >= 1)
        self.assertIn("uses multi-character strip", errs_lstrip[0])

        bad_glob = 'paths = list(root.glob("./src/**"))'
        errs_glob = check_source(bad_glob)
        self.assertTrue(len(errs_glob) >= 1)
        self.assertIn("pattern starts with './'", errs_glob[0])

        good_strip_dot_slash = 'norm = strip_dot_slash(pat)'
        errs_good = check_source(good_strip_dot_slash)
        self.assertEqual(len(errs_good), 0)

        good_whitespace_strip = 'lost_lines = [l[1:].rstrip("\\r\\n") for l in diff_lines]'
        errs_ws = check_source(good_whitespace_strip)
        self.assertEqual(len(errs_ws), 0)

        good_with_comment = 'p = pat.lstrip("./")  # strip-chars-ok: custom prefix strip'
        errs_comment = check_source(good_with_comment)
        self.assertEqual(len(errs_comment), 0)


if __name__ == "__main__":
    unittest.main()
