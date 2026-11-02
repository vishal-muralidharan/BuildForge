#!/usr/bin/env python3
"""CI verification checks for Build Forge.

Verifies:
1. Every folder in skills/ has a SKILL.md.
2. Frontmatter 'name' matches the folder name, and 'description' is present and <= 1024 chars.
3. Every SKILL.md has <= 500 lines.
4. Every .py file compiles without syntax errors (using py_compile).
5. No __pycache__ directories or .pyc files exist in the repository tree.
6. No file under skills/ contains an em dash or en dash.
7. Smoke tests:
   - validate_profile.py exits 0 on example-nemo profile.
   - render.py exits 0 on example-nemo profile.
   - check_commit_message.py exits 0 on "feat(entry): add keypad" and exits 1 on "Added keypad".
   - bin/install.js installs one skill per folder in skills/ in a temporary folder.
"""
import os
import sys
import shutil
import tempfile
import py_compile
import subprocess
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")


def check_skills(skills_dir, errors):
    if not os.path.isdir(skills_dir):
        errors.append(f"Skills directory '{skills_dir}' not found.")
        return

    for item in sorted(os.listdir(skills_dir)):
        skill_dir = os.path.join(skills_dir, item)
        if not os.path.isdir(skill_dir):
            continue

        skill_md = os.path.join(skill_dir, "SKILL.md")
        # Rule 1: A folder in skills/ has no SKILL.md
        if not os.path.isfile(skill_md):
            errors.append(f"Rule 1 failure: Skill folder '{item}' has no SKILL.md.")
            continue

        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            errors.append(f"Error reading {skill_md}: {e}")
            continue

        lines = content.splitlines()
        # Rule 3: A SKILL.md has more than 500 lines
        if len(lines) > 500:
            errors.append(f"Rule 3 failure: '{skill_md}' has {len(lines)} lines (maximum allowed is 500).")

        # Rule 2: A SKILL.md frontmatter name differs from folder, or description missing or > 1024 chars
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    fm = yaml.safe_load(parts[1]) or {}
                except Exception as e:
                    errors.append(f"Rule 2 failure: Invalid YAML frontmatter in '{skill_md}': {e}")
                    fm = {}

                name = fm.get("name")
                desc = fm.get("description")

                if name != item:
                    errors.append(f"Rule 2 failure: '{skill_md}' frontmatter name '{name}' does not match folder name '{item}'.")
                if not desc:
                    errors.append(f"Rule 2 failure: '{skill_md}' description is missing.")
                elif len(str(desc)) > 1024:
                    errors.append(f"Rule 2 failure: '{skill_md}' description is {len(str(desc))} characters (maximum allowed is 1024).")
            else:
                errors.append(f"Rule 2 failure: Malformed frontmatter in '{skill_md}'.")
        else:
            errors.append(f"Rule 2 failure: '{skill_md}' missing leading '---' frontmatter boundary.")


def check_python_files(repo_root, errors):
    # Rule 4: A .py file does not compile (use py_compile)
    with tempfile.TemporaryDirectory() as tmp:
        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules"}]
            for f in files:
                if f.endswith(".py"):
                    file_path = os.path.join(root, f)
                    cfile = os.path.join(tmp, f"{hash(file_path)}.pyc")
                    try:
                        py_compile.compile(file_path, cfile=cfile, doraise=True)
                    except py_compile.PyCompileError as e:
                        errors.append(f"Rule 4 failure: '{file_path}' does not compile: {e}")


def check_no_cache_or_pyc(repo_root, errors):
    # Rule 5: The tree holds __pycache__ or .pyc files
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d != ".git"]
        if "__pycache__" in dirs:
            errors.append(f"Rule 5 failure: Tree contains '__pycache__' directory at '{os.path.join(root, '__pycache__')}'.")
        for f in files:
            if f.endswith(".pyc"):
                errors.append(f"Rule 5 failure: Tree contains '.pyc' file at '{os.path.join(root, f)}'.")


def check_dashes(skills_dir, errors):
    # Rule 6: A file under skills/ contains an em dash or an en dash
    dashes = {"\u2014": "em dash (\u2014)", "\u2013": "en dash (\u2013)"}
    for root, dirs, files in os.walk(skills_dir):
        for f in files:
            file_path = os.path.join(root, f)
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    for line_num, line in enumerate(fh, 1):
                        for char, name in dashes.items():
                            if char in line:
                                errors.append(f"Rule 6 failure: '{file_path}:{line_num}' contains {name}.")
            except UnicodeDecodeError:
                pass


def run_smoke_test(repo_root, errors):
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        profile_src = os.path.join(repo_root, "skills/project-bootstrap/references/example-nemo.project-profile.yaml")
        profile_dst = os.path.join(agents_dir, "project-profile.yaml")

        if not os.path.isfile(profile_src):
            errors.append(f"Smoke test failure: Example profile not found at '{profile_src}'.")
            return

        shutil.copyfile(profile_src, profile_dst)

        # 1. validate_profile.py (must exit 0)
        val_py = os.path.join(repo_root, "skills/project-bootstrap/scripts/validate_profile.py")
        res_val = subprocess.run([sys.executable, val_py, "--profile", profile_dst, "--root", tmpdir], capture_output=True, text=True)
        if res_val.returncode != 0:
            errors.append(f"Smoke test failure: validate_profile.py exited with {res_val.returncode}:\n{res_val.stdout}\n{res_val.stderr}")

        # 2. render.py (must exit 0)
        ren_py = os.path.join(repo_root, "skills/project-bootstrap/scripts/render.py")
        res_ren = subprocess.run([sys.executable, ren_py, "--profile", profile_dst, "--root", tmpdir], capture_output=True, text=True)
        if res_ren.returncode != 0:
            errors.append(f"Smoke test failure: render.py exited with {res_ren.returncode}:\n{res_ren.stdout}\n{res_ren.stderr}")

        # 3. check_commit_message.py "feat(entry): add keypad" (must exit 0)
        chk_py = os.path.join(repo_root, "skills/atomic-commits/scripts/check_commit_message.py")
        res_chk_valid = subprocess.run([sys.executable, chk_py, "--profile", profile_dst, "feat(entry): add keypad"], capture_output=True, text=True)
        if res_chk_valid.returncode != 0:
            errors.append(f"Smoke test failure: check_commit_message.py exited with {res_chk_valid.returncode} for valid message:\n{res_chk_valid.stdout}\n{res_chk_valid.stderr}")

        # 4. check_commit_message.py "Added keypad" (must exit 1)
        res_chk_invalid = subprocess.run([sys.executable, chk_py, "--profile", profile_dst, "Added keypad"], capture_output=True, text=True)
        if res_chk_invalid.returncode != 1:
            errors.append(f"Smoke test failure: check_commit_message.py expected exit code 1 for invalid message, got {res_chk_invalid.returncode}:\n{res_chk_invalid.stdout}")

        # 5. node bin/install.js installs one skill per folder in skills/
        inst_js = os.path.join(repo_root, "bin/install.js")
        with tempfile.TemporaryDirectory() as inst_tmpdir:
            res_inst = subprocess.run(["node", inst_js], cwd=inst_tmpdir, capture_output=True, text=True)
            if res_inst.returncode != 0:
                errors.append(f"Smoke test failure: node bin/install.js failed with {res_inst.returncode}:\n{res_inst.stderr}")
            else:
                installed_dir = os.path.join(inst_tmpdir, ".agents", "skills")
                installed_skills = sorted(os.listdir(installed_dir)) if os.path.exists(installed_dir) else []
                skills_dir = os.path.join(repo_root, "skills")
                expected_skills = sorted([d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d))])
                if installed_skills != expected_skills:
                    errors.append(f"Smoke test failure: Installed skills {installed_skills} != expected {expected_skills}")


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    skills_dir = os.path.join(repo_root, "skills")

    errors = []

    print("Running CI checks...")
    check_skills(skills_dir, errors)
    check_python_files(repo_root, errors)
    check_no_cache_or_pyc(repo_root, errors)
    check_dashes(skills_dir, errors)

    print("Running smoke tests...")
    run_smoke_test(repo_root, errors)

    if errors:
        print(f"\nCI checks failed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("\nAll CI checks and smoke tests passed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
