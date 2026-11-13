#!/usr/bin/env python3
"""Tests for the project-readme skill: readme_facts.py and check_readme.py."""
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
SKILL = REPO_ROOT / "skills" / "project-readme"
FACTS = SKILL / "scripts" / "readme_facts.py"
CHECK = SKILL / "scripts" / "check_readme.py"
sys.path.insert(0, str(SKILL / "scripts"))

import check_readme  # noqa: E402

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
MONEY = "\U0001F4B8"


def run(script, root, *args):
    return subprocess.run([sys.executable, "-B", str(script), "--root", str(root), *args],
                          capture_output=True, text=True, env=ENV)


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


GOOD_SHOWCASE = f"""# NeMo

Track your spending in seconds and see where your money goes.

![Home screen](docs/screenshot-home.png)

## Features

- {MONEY} **Track spending** with categories you control.

## Getting started

```bash
npm install
npm run dev
```

## Tech stack

| Part | Tool |
|---|---|
| Frontend | React |

## License

MIT. See [LICENSE](LICENSE).
"""

GOOD_META = """style: showcase
description: "Expense tracker that shows where your money goes."
homepage: "https://nemo.example.com"
topics: [react, vite, expense-tracker]
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="bf-readme-"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def facts(self):
        res = run(FACTS, self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)


class TestReadmeFacts(Base):
    def test_react_app_is_showcase(self):
        write(self.root, "package.json", json.dumps({"name": "nemo", "scripts": {"dev": "vite"},
                                                    "dependencies": {"react": "19"}, "devDependencies": {"vite": "6"}}))
        f = self.facts()
        self.assertEqual(f["suggested_style"], "showcase")
        self.assertIn("react", f["suggested_topics"])
        self.assertEqual(f["scripts"], {"dev": "vite"})

    def test_cli_is_technical(self):
        write(self.root, "package.json", json.dumps({"name": "tool", "bin": {"tool": "bin/tool.js"}}))
        self.assertEqual(self.facts()["suggested_style"], "technical")

    def test_fastapi_is_api(self):
        write(self.root, "backend/requirements.txt", "fastapi==0.110\nuvicorn\n")
        self.assertEqual(self.facts()["suggested_style"], "api")

    def test_static_site_is_minimal(self):
        write(self.root, "index.html", "<html></html>")
        self.assertEqual(self.facts()["suggested_style"], "minimal")

    def test_ignores_node_modules_and_agent_folders(self):
        write(self.root, "package.json", json.dumps({"name": "lib", "main": "index.js"}))
        write(self.root, "node_modules/x/package.json", json.dumps({"dependencies": {"react": "19"}}))
        write(self.root, ".agents/skills/scaffold-app/assets/screenshot.png", "x")
        f = self.facts()
        self.assertEqual(f["suggested_style"], "technical")
        self.assertEqual(f["screenshots"], [])

    def test_env_values_are_never_read(self):
        write(self.root, "package.json", json.dumps({"name": "app", "dependencies": {"react": "19"}}))
        write(self.root, ".env", "SECRET_VALUE=do-not-print-me\n")
        write(self.root, ".env.example", "PUBLIC_NAME=\n")
        res = run(FACTS, self.root)
        self.assertNotIn("do-not-print-me", res.stdout)
        self.assertNotIn("SECRET_VALUE", res.stdout)
        self.assertIn("PUBLIC_NAME", res.stdout)


class TestCheckReadme(Base):
    def make_good(self):
        write(self.root, "package.json", json.dumps({"name": "nemo", "scripts": {"dev": "vite", "build": "vite build"}}))
        write(self.root, "docs/screenshot-home.png", "x")
        write(self.root, "LICENSE", "MIT License\n")
        write(self.root, "README.md", GOOD_SHOWCASE)
        write(self.root, ".agents/repo-meta.yaml", GOOD_META)

    def test_good_readme_passes(self):
        self.make_good()
        res = run(CHECK, self.root)
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("0 error(s)", res.stdout)

    def test_missing_section_fails(self):
        self.make_good()
        write(self.root, "README.md", GOOD_SHOWCASE.replace("## Tech stack", "## Notes"))
        res = run(CHECK, self.root)
        self.assertEqual(res.returncode, 1)
        self.assertIn("tech stack", res.stdout)

    def test_unknown_script_fails(self):
        self.make_good()
        write(self.root, "README.md", GOOD_SHOWCASE.replace("npm run dev", "npm run serve"))
        res = run(CHECK, self.root)
        self.assertEqual(res.returncode, 1)
        self.assertIn("script 'serve'", res.stdout)

    def test_broken_image_fails(self):
        self.make_good()
        (self.root / "docs" / "screenshot-home.png").unlink()
        res = run(CHECK, self.root)
        self.assertEqual(res.returncode, 1)
        self.assertIn("docs/screenshot-home.png", res.stdout)

    def test_secret_fails_without_printing_it(self):
        self.make_good()
        fake = "AIza" + "B" * 35
        write(self.root, "README.md", GOOD_SHOWCASE + f"\nKey: {fake}\n")
        res = run(CHECK, self.root)
        self.assertEqual(res.returncode, 1)
        self.assertIn("Google API key", res.stdout)
        self.assertNotIn(fake, res.stdout)

    def test_placeholder_is_warning_then_error_with_strict(self):
        self.make_good()
        write(self.root, "README.md", GOOD_SHOWCASE + "\nTODO: add a demo link\n")
        self.assertEqual(run(CHECK, self.root).returncode, 0)
        self.assertEqual(run(CHECK, self.root, "--strict").returncode, 1)

    def test_technical_style_warns_on_emoji_headings(self):
        self.make_good()
        readme = "# Tool\n\nDoes a thing.\n\n## Install\n\nx\n\n## Usage\n\nx\n\n## Requirements\n\nx\n\n## " + MONEY + " License\n\nMIT\n"
        write(self.root, "README.md", readme)
        res = run(CHECK, self.root, "--style", "technical")
        self.assertIn("no emojis in headings", res.stdout)

    def test_meta_limits(self):
        self.make_good()
        long_desc = "x" * 351
        topics = ", ".join(f"t{i}" for i in range(21))
        write(self.root, ".agents/repo-meta.yaml",
              f'style: showcase\ndescription: "{long_desc}"\nhomepage: "http://insecure.example.com"\ntopics: [{topics}, Bad_Topic]\n')
        res = run(CHECK, self.root)
        self.assertEqual(res.returncode, 1)
        self.assertIn("the limit is 350", res.stdout)
        self.assertIn("the limit is 20", res.stdout)
        self.assertIn("https://", res.stdout)
        self.assertIn("Bad_Topic", res.stdout)

    def test_style_defaults_to_the_suggestion(self):
        write(self.root, "package.json", json.dumps({"name": "app", "dependencies": {"react": "19"}}))
        write(self.root, "README.md", "# App\n\nA small app.\n")
        res = run(CHECK, self.root)
        self.assertIn("Style: showcase", res.stdout)

    def test_print_gh(self):
        self.make_good()
        res = run(CHECK, self.root, "--print-gh")
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("gh repo edit --description", res.stdout)
        self.assertIn("--add-topic react,vite,expense-tracker", res.stdout)
        self.assertIn("--homepage https://nemo.example.com", res.stdout)


class TestTemplates(unittest.TestCase):
    def test_each_template_has_the_required_sections(self):
        for style in check_readme.STYLES:
            text = (SKILL / "assets" / "templates" / f"{style}.md").read_text(encoding="utf-8")
            with tempfile.TemporaryDirectory(prefix="bf-readme-tpl-") as tmp:
                Path(tmp, "README.md").write_text(text, encoding="utf-8")
                errors, _ = check_readme.check(Path(tmp), Path(tmp, "README.md"), style, {}, False)
                missing = [e for e in errors if e.startswith("missing section")]
                self.assertEqual(missing, [], f"{style}: {missing}")


if __name__ == "__main__":
    unittest.main()
