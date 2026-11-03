#!/usr/bin/env python3
"""CI verification checks for Build Forge.

Verifies:
1. Every folder in skills/ has a SKILL.md.
2. Frontmatter conformance for every skill (name matches folder, description present and <= 1024 chars,
   allowed fields only, compatibility <= 500 chars).
3. Tool-specific word denylist check in skills/.
4. No placeholder paths (<this-skill>, <project-bootstrap>) and no command uses 'python ' without the 3.
5. Every SKILL.md has <= 500 lines.
6. Every .py file compiles without syntax errors (using py_compile).
7. No __pycache__ directories or .pyc files exist in the repository tree.
8. No file under skills/ contains an em dash or en dash.
9. Smoke tests:
   - validate_profile.py exits 0 on example-nemo profile.
   - render.py exits 0 on example-nemo profile.
   - check_commit_message.py exits 0 on "feat(entry): add keypad" and exits 1 on "Added keypad".
   - bin/build-forge.js installs one skill per folder in skills/ in a temporary folder.
10. Multi-agent link and unlink tests in temporary folders.
11. Allowlist guard: skills/, integrity.json, and npm pack must not contain folders outside ALLOWED_SKILLS.
12. Integrity manifest: every file in skills/ must match its recorded hash in integrity.json.
"""
import os
import re
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

ALLOWED_SKILLS = {
    "atomic-commits",
    "audit-and-planning",
    "extend-pipeline",
    "feature-delivery",
    "legal-and-settings-pages",
    "product-spec",
    "project-bootstrap",
    "repo-search",
    "rules-to-tests",
    "scaffold-app",
    "sync-skills-and-docs",
    "targeted-module-testing",
}

TOOL_WORD_DENYLIST = [
    "str_replace",
    "ask_user_input",
    "view tool",
    "bash tool",
    "task tool",
    "CLAUDE.md"
]

ALLOWED_FRONTMATTER_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools"
}


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

        # Frontmatter conformance
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    fm = yaml.safe_load(parts[1]) or {}
                except Exception as e:
                    errors.append(f"Frontmatter parse error in '{skill_md}': {e}")
                    fm = {}

                # Check allowed fields
                extra_fields = set(fm.keys()) - ALLOWED_FRONTMATTER_FIELDS
                if extra_fields:
                    errors.append(f"Frontmatter failure: '{skill_md}' contains disallowed fields: {sorted(extra_fields)}.")

                name = fm.get("name")
                desc = fm.get("description")
                compat = fm.get("compatibility")

                if name != item:
                    errors.append(f"Frontmatter failure: '{skill_md}' name '{name}' does not match folder '{item}'.")
                if not name or not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", str(name)) or len(str(name)) > 64:
                    errors.append(f"Frontmatter failure: '{skill_md}' name '{name}' violates Agent Skills naming rules.")

                if not desc:
                    errors.append(f"Frontmatter failure: '{skill_md}' description is missing.")
                elif len(str(desc)) > 1024:
                    errors.append(f"Frontmatter failure: '{skill_md}' description length {len(str(desc))} > 1024.")

                if compat is not None and len(str(compat)) > 500:
                    errors.append(f"Frontmatter failure: '{skill_md}' compatibility length {len(str(compat))} > 500.")
            else:
                errors.append(f"Frontmatter failure: Malformed frontmatter in '{skill_md}'.")
        else:
            errors.append(f"Frontmatter failure: '{skill_md}' missing leading '---' frontmatter boundary.")

        # Denylist check for tool-specific words in SKILL.md
        for line_num, line in enumerate(lines, 1):
            for denylisted in TOOL_WORD_DENYLIST:
                if denylisted.lower() in line.lower():
                    errors.append(f"Denylist failure: '{skill_md}:{line_num}' contains denylisted term '{denylisted}'.")

            # Check for python without 3 in commands
            if re.search(r"`python\s+(?!3\b)", line) or re.search(r"^\s*python\s+(?!3\b)", line):
                errors.append(f"Command failure: '{skill_md}:{line_num}' uses 'python' without 3.")


def check_skill_placeholders(skills_dir, errors):
    for root, dirs, files in os.walk(skills_dir):
        for f in files:
            file_path = os.path.join(root, f)
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    for line_num, line in enumerate(fh, 1):
                        if "<this-skill>" in line:
                            errors.append(f"Placeholder failure: '{file_path}:{line_num}' contains '<this-skill>'.")
                        if "<project-bootstrap>" in line:
                            errors.append(f"Placeholder failure: '{file_path}:{line_num}' contains '<project-bootstrap>'.")
            except UnicodeDecodeError:
                pass


def check_python_files(repo_root, errors):
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
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d != ".git"]
        if "__pycache__" in dirs:
            errors.append(f"Rule 5 failure: Tree contains '__pycache__' directory at '{os.path.join(root, '__pycache__')}'.")
        for f in files:
            if f.endswith(".pyc"):
                errors.append(f"Rule 5 failure: Tree contains '.pyc' file at '{os.path.join(root, f)}'.")


def check_dashes(skills_dir, errors):
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


def check_feature_delivery_workflows(skills_dir, errors):
    """Verify that feature-delivery workflows exist, are linked from SKILL.md, and pass checks."""
    fd_dir = os.path.join(skills_dir, "feature-delivery")
    skill_md = os.path.join(fd_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        errors.append("feature-delivery/SKILL.md not found.")
        return

    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            skill_text = f.read()
    except Exception as e:
        errors.append(f"Failed to read feature-delivery/SKILL.md: {e}")
        return

    workflow_files = [
        "references/workflows/fix-bug.md",
        "references/workflows/review-changes.md",
        "references/workflows/release-prep.md"
    ]
    for rel_path in workflow_files:
        full_path = os.path.join(fd_dir, rel_path)
        if not os.path.isfile(full_path):
            errors.append(f"Workflow reference missing: '{full_path}' does not exist.")
            continue
        if rel_path not in skill_text:
            errors.append(f"Workflow reference not linked: '{rel_path}' is not linked in feature-delivery/SKILL.md.")

        try:
            with open(full_path, "r", encoding="utf-8") as wf:
                wf_text = wf.read()
            for section in ("When to use", "Stages with gates", "What to read", "What to produce", "Stop conditions"):
                if section not in wf_text:
                    errors.append(f"Workflow '{rel_path}' missing required section '{section}'.")
        except Exception as e:
            errors.append(f"Failed to read '{full_path}': {e}")


def check_integrity_manifest(repo_root, errors):
    """Verify that integrity.json exists and matches the skills directory exactly."""
    import json
    import hashlib
    integrity_path = os.path.join(repo_root, "integrity.json")
    if not os.path.isfile(integrity_path):
        errors.append("Integrity check failure: integrity.json not found. Run python3 scripts/make_integrity.py.")
        return

    try:
        with open(integrity_path, "r", encoding="utf-8") as f:
            integrity = json.load(f)
    except Exception as e:
        errors.append(f"Integrity check failure: could not parse integrity.json: {e}")
        return

    skills_dir = os.path.join(repo_root, "skills")
    actual = {}
    if os.path.isdir(skills_dir):
        for root, dirs, files in os.walk(skills_dir):
            dirs.sort()
            for file_name in sorted(files):
                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, repo_root).replace("\\", "/")
                try:
                    with open(full_path, "r", encoding="utf-8") as fh:
                        content = fh.read().replace("\r\n", "\n")
                    actual[rel_path] = hashlib.sha256(content.encode("utf-8")).hexdigest()
                except UnicodeDecodeError:
                    with open(full_path, "rb") as fh:
                        actual[rel_path] = hashlib.sha256(fh.read()).hexdigest()

    for path, expected_hash in integrity.items():
        if path not in actual:
            errors.append(f"Integrity check failure: '{path}' listed in integrity.json but missing on disk.")
        elif actual[path] != expected_hash:
            errors.append(f"Integrity check failure: '{path}' hash modified. Run python3 scripts/make_integrity.py.")

    for path in actual:
        if path not in integrity:
            errors.append(f"Integrity check failure: '{path}' exists on disk but missing from integrity.json.")


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

        # 5. node bin/build-forge.js install
        cli_js = os.path.join(repo_root, "bin/build-forge.js")
        with tempfile.TemporaryDirectory() as inst_tmpdir:
            # Create a mock .gitignore to verify auto-ignore behavior
            gi_path = os.path.join(inst_tmpdir, ".gitignore")
            with open(gi_path, "w", encoding="utf-8") as fh:
                fh.write("node_modules/\n")

            res_inst = subprocess.run(["node", cli_js, "install"], cwd=inst_tmpdir, capture_output=True, text=True)
            if res_inst.returncode != 0:
                errors.append(f"Smoke test failure: node bin/build-forge.js install failed with {res_inst.returncode}:\n{res_inst.stderr}")
            else:
                installed_dir = os.path.join(inst_tmpdir, ".agents", "skills")
                installed_skills = sorted(os.listdir(installed_dir)) if os.path.exists(installed_dir) else []
                skills_dir = os.path.join(repo_root, "skills")
                expected_skills = sorted([d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d))])
                if installed_skills != expected_skills:
                    errors.append(f"Smoke test failure: Installed skills {installed_skills} != expected {expected_skills}")

                # Verify .gitignore auto-appended
                with open(gi_path, "r", encoding="utf-8") as fh:
                    gi_content = fh.read()
                if ".agents/work/" not in gi_content or ".agents/vendor/" not in gi_content:
                    errors.append("Smoke test failure: install did not add .agents/work/ and .agents/vendor/ to .gitignore")

                # 6. Test status command (must exit 0)
                res_status = subprocess.run(["node", cli_js, "status"], cwd=inst_tmpdir, capture_output=True, text=True)
                if res_status.returncode != 0:
                    errors.append(f"Smoke test failure: status command failed with {res_status.returncode}:\n{res_status.stderr}")
                elif "Build Forge Status Report" not in res_status.stdout:
                    errors.append("Smoke test failure: status output missing header 'Build Forge Status Report'")

                # 7. Test diff command (must exit 0 on clean install)
                res_diff = subprocess.run(["node", cli_js, "diff"], cwd=inst_tmpdir, capture_output=True, text=True)
                if res_diff.returncode != 0:
                    errors.append(f"Smoke test failure: diff command failed with {res_diff.returncode}:\n{res_diff.stderr}")
                elif "Diff clean" not in res_diff.stdout:
                    errors.append("Smoke test failure: diff output missing 'Diff clean'")


def run_link_tests(repo_root, errors):
    cli = os.path.join(repo_root, "bin/build-forge.js")
    with tempfile.TemporaryDirectory() as tmp:
        # Install skills first
        res = subprocess.run(["node", cli, "install"], cwd=tmp, capture_output=True, text=True)
        if res.returncode != 0:
            errors.append(f"Link test failure: install failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
            return

        # 1. No agent folder: expect a whole folder symlink
        res = subprocess.run(["node", cli, "link", "--agents", "claude,gemini"], cwd=tmp, capture_output=True, text=True)
        if res.returncode != 0:
            errors.append(f"Link test failure: link --agents claude,gemini failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
            return

        claude_skills = os.path.join(tmp, ".claude", "skills")
        if not os.path.islink(claude_skills):
            errors.append("Link test failure: .claude/skills should be a symlink when no agent folder exists.")

        claude_ptr = os.path.join(tmp, "CLAUDE.md")
        if not os.path.isfile(claude_ptr):
            errors.append("Link test failure: Pointer file CLAUDE.md was not created.")

        # 2. verify exit 0 through the links
        res_v1 = subprocess.run(["node", cli, "verify"], cwd=tmp, capture_output=True, text=True)
        if res_v1.returncode != 0:
            errors.append(f"Link test failure: verify exit code was {res_v1.returncode} through links:\nSTDOUT:\n{res_v1.stdout}\nSTDERR:\n{res_v1.stderr}")

        # 3. Second link run: no change (idempotent)
        res_l2 = subprocess.run(["node", cli, "link", "--agents", "claude"], cwd=tmp, capture_output=True, text=True)
        if res_l2.returncode != 0:
            errors.append(f"Link test failure: Second link run failed:\nSTDOUT:\n{res_l2.stdout}\nSTDERR:\n{res_l2.stderr}")
        if not os.path.islink(claude_skills):
            errors.append("Link test failure: .claude/skills should remain a symlink after second link run.")

        # 4. Unlink: only links removed
        res_u1 = subprocess.run(["node", cli, "unlink", "--agents", "claude"], cwd=tmp, capture_output=True, text=True)
        if res_u1.returncode != 0:
            errors.append(f"Link test failure: unlink failed:\nSTDOUT:\n{res_u1.stdout}\nSTDERR:\n{res_u1.stderr}")
        if os.path.exists(claude_skills):
            errors.append("Link test failure: .claude/skills was not removed by unlink.")
        if not os.path.isfile(claude_ptr):
            errors.append("Link test failure: Pointer file CLAUDE.md should not be removed by unlink.")

        # 5. Existing folder holding user's own skill: expect per-skill links and user skill untouched
        os.makedirs(os.path.join(claude_skills, "user-skill"), exist_ok=True)
        user_skill_file = os.path.join(claude_skills, "user-skill", "SKILL.md")
        with open(user_skill_file, "w", encoding="utf-8") as f:
            f.write("user custom skill")

        res_l3 = subprocess.run(["node", cli, "link", "--agents", "claude"], cwd=tmp, capture_output=True, text=True)
        if res_l3.returncode != 0:
            errors.append(f"Link test failure: link on existing folder failed:\nSTDOUT:\n{res_l3.stdout}\nSTDERR:\n{res_l3.stderr}")
        if os.path.islink(claude_skills):
            errors.append("Link test failure: .claude/skills should not be a symlink when it was an existing folder.")
        if not os.path.isfile(user_skill_file):
            errors.append("Link test failure: User's custom skill was removed or overwritten.")
        pb_link = os.path.join(claude_skills, "project-bootstrap")
        if not os.path.islink(pb_link):
            errors.append("Link test failure: Expected per-skill symlink for project-bootstrap inside .claude/skills.")

        # 6. verify exit 0 through per-skill links
        res_v2 = subprocess.run(["node", cli, "verify"], cwd=tmp, capture_output=True, text=True)
        if res_v2.returncode != 0:
            errors.append(f"Link test failure: verify exit code was {res_v2.returncode} through per-skill links:\nSTDOUT:\n{res_v2.stdout}\nSTDERR:\n{res_v2.stderr}")

        # 7. Unlink on real folder: only links removed
        res_u2 = subprocess.run(["node", cli, "unlink", "--agents", "claude"], cwd=tmp, capture_output=True, text=True)
        if res_u2.returncode != 0:
            errors.append(f"Link test failure: unlink on real folder failed:\nSTDOUT:\n{res_u2.stdout}\nSTDERR:\n{res_u2.stderr}")
        if os.path.exists(pb_link):
            errors.append("Link test failure: Per-skill symlink was not removed by unlink.")
        if not os.path.isfile(user_skill_file):
            errors.append("Link test failure: User's custom skill should remain after unlink.")

        # 8. Pointer file creation must never overwrite an existing file
        with open(claude_ptr, "w", encoding="utf-8") as f:
            f.write("Custom instructions")
        res_l4 = subprocess.run(["node", cli, "link", "--agents", "claude"], cwd=tmp, capture_output=True, text=True)
        if res_l4.returncode != 0:
            errors.append(f"Link test failure: link run failed:\nSTDOUT:\n{res_l4.stdout}\nSTDERR:\n{res_l4.stderr}")
        with open(claude_ptr, "r", encoding="utf-8") as f:
            if f.read() != "Custom instructions":
                errors.append("Link test failure: Pointer file was overwritten by link command.")


def run_allowlist_fixture_tests(repo_root, errors):
    """Fixture tests: prove that each allowlist guard case fails as expected."""
    import json
    import shutil

    with tempfile.TemporaryDirectory() as tmp:
        fake_skills = os.path.join(tmp, "skills")
        os.makedirs(fake_skills)

        # Seed one allowed skill so integrity/pack checks have realistic context.
        allowed_skill = os.path.join(fake_skills, "atomic-commits")
        os.makedirs(allowed_skill)
        with open(os.path.join(allowed_skill, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: atomic-commits\ndescription: ok\n---\nContent.\n")

        # --- Fixture A: unlisted folder in skills/ ---
        unlisted_dir = os.path.join(fake_skills, "third-party-skill")
        os.makedirs(unlisted_dir)
        fixture_errors = []
        check_allowlist_skills(fake_skills, fixture_errors)
        if not any("third-party-skill" in e for e in fixture_errors):
            errors.append(
                "Allowlist fixture A failed: unlisted skills/ folder did not trigger an error."
            )
        shutil.rmtree(unlisted_dir)

        # --- Fixture B: integrity.json with unlisted skill path ---
        integrity_path = os.path.join(tmp, "integrity.json")
        with open(integrity_path, "w", encoding="utf-8") as f:
            json.dump({"skills/third-party-skill/SKILL.md": "abc123"}, f)
        fixture_errors = []
        check_allowlist_integrity(integrity_path, fixture_errors)
        if not any("third-party-skill" in e for e in fixture_errors):
            errors.append(
                "Allowlist fixture B failed: integrity.json with unlisted skill did not trigger an error."
            )
        os.remove(integrity_path)

        # --- Fixture C: npm pack file list with unlisted skill ---
        fake_pack_output = json.dumps([{"files": [
            {"path": "skills/atomic-commits/SKILL.md"},
            {"path": "skills/third-party-skill/SKILL.md"},
        ]}])
        fixture_errors = []
        check_allowlist_pack_output(fake_pack_output, fixture_errors)
        if not any("third-party-skill" in e for e in fixture_errors):
            errors.append(
                "Allowlist fixture C failed: npm pack output with unlisted skill did not trigger an error."
            )


def check_allowlist_skills(skills_dir, errors):
    """Sub-check: skills/ folders against ALLOWED_SKILLS."""
    if os.path.isdir(skills_dir):
        for item in sorted(os.listdir(skills_dir)):
            if os.path.isdir(os.path.join(skills_dir, item)) and item not in ALLOWED_SKILLS:
                errors.append(
                    f"Allowlist failure: skills/{item} is not in ALLOWED_SKILLS. "
                    "Remove it or add it to ALLOWED_SKILLS with maintainer approval."
                )


def check_allowlist_integrity(integrity_path, errors):
    """Sub-check: integrity.json paths against ALLOWED_SKILLS."""
    import json
    if os.path.isfile(integrity_path):
        try:
            with open(integrity_path, "r", encoding="utf-8") as f:
                integrity = json.load(f)
            for key in integrity:
                parts = key.replace("\\", "/").split("/")
                if len(parts) >= 2 and parts[0] == "skills":
                    skill_name = parts[1]
                    if skill_name and skill_name not in ALLOWED_SKILLS:
                        errors.append(
                            f"Allowlist failure: integrity.json lists path '{key}' "
                            f"whose skill folder '{skill_name}' is not in ALLOWED_SKILLS."
                        )
        except Exception as e:
            errors.append(f"Allowlist failure: could not parse integrity.json: {e}")


def check_allowlist_pack_output(pack_json_str, errors):
    """Sub-check: npm pack --json output against ALLOWED_SKILLS."""
    import json
    try:
        pack_data = json.loads(pack_json_str)
        files = pack_data[0].get("files", []) if pack_data else []
        for entry in files:
            path_str = entry.get("path", "").replace("\\", "/")
            parts = path_str.split("/")
            if len(parts) >= 2 and parts[0] == "skills":
                skill_name = parts[1]
                if skill_name and skill_name not in ALLOWED_SKILLS:
                    errors.append(
                        f"Allowlist failure: npm pack includes path '{path_str}' "
                        f"whose skill folder '{skill_name}' is not in ALLOWED_SKILLS."
                    )
    except Exception as e:
        errors.append(f"Allowlist failure: could not parse npm pack --json output: {e}")


def check_allowlist(repo_root, errors):
    """Guard: skills/, integrity.json, and npm pack must not contain folders outside ALLOWED_SKILLS."""
    skills_dir = os.path.join(repo_root, "skills")
    check_allowlist_skills(skills_dir, errors)

    integrity_path = os.path.join(repo_root, "integrity.json")
    check_allowlist_integrity(integrity_path, errors)

    res = subprocess.run(
        ["npm", "pack", "--dry-run", "--json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        check_allowlist_pack_output(res.stdout, errors)
    else:
        errors.append(f"Allowlist failure: npm pack --dry-run --json failed: {res.stderr.strip()}")


def run_references_tests(repo_root, errors):
    refs_py = os.path.join(repo_root, "skills", "extend-pipeline", "scripts", "refs.py")
    cli_js = os.path.join(repo_root, "bin", "build-forge.js")

    with tempfile.TemporaryDirectory() as tmp:
        # 1. Create local fixture git repository
        fixture_dir = os.path.join(tmp, "fixture-repo")
        os.makedirs(fixture_dir, exist_ok=True)
        res_init = subprocess.run(["git", "init"], cwd=fixture_dir, capture_output=True, text=True)
        if res_init.returncode != 0:
            errors.append(f"References test failure: git init failed:\n{res_init.stderr}")
            return
        subprocess.run(["git", "config", "user.email", "ci@example.com"], cwd=fixture_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "CI Tester"], cwd=fixture_dir, capture_output=True)

        skill_dir = os.path.join(fixture_dir, "fixture-skill")
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: fixture-skill\ndescription: A clean test skill.\ncompatibility: None.\n---\n# Test\nInstructions.\n")
        subprocess.run(["git", "add", "."], cwd=fixture_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=fixture_dir, capture_output=True)

        # 2. Test fetch
        out_inspect = os.path.join(tmp, "inspect")
        res_fetch = subprocess.run([sys.executable, refs_py, "fetch", fixture_dir, "--out", out_inspect], capture_output=True, text=True)
        if res_fetch.returncode != 0:
            errors.append(f"References test failure: fetch failed:\nSTDOUT:\n{res_fetch.stdout}\nSTDERR:\n{res_fetch.stderr}")
        elif "fixture-skill" not in res_fetch.stdout:
            errors.append("References test failure: fetch output missing 'fixture-skill'.")

        # 3. Test vet on clean fixture
        res_vet_clean = subprocess.run([sys.executable, refs_py, "vet", out_inspect], capture_output=True, text=True)
        if res_vet_clean.returncode != 0:
            errors.append(f"References test failure: vet clean failed:\nSTDOUT:\n{res_vet_clean.stdout}\nSTDERR:\n{res_vet_clean.stderr}")

        # 4. Test vet on bad fixture with high findings (scripts, curl, token, zero-width char, prompt override)
        bad_dir = os.path.join(tmp, "bad-dir")
        os.makedirs(bad_dir, exist_ok=True)
        with open(os.path.join(bad_dir, "script.py"), "w", encoding="utf-8") as f:
            f.write("import os\n# ignore previous instructions\napi_key = 'secret'\ncurl = 'curl'\nos.system('echo \u200b')\n")
        res_vet_bad = subprocess.run([sys.executable, refs_py, "vet", bad_dir], capture_output=True, text=True)
        if res_vet_bad.returncode != 1:
            errors.append(f"References test failure: vet bad directory expected exit code 1, got {res_vet_bad.returncode}")
        elif "HIGH" not in res_vet_bad.stdout:
            errors.append("References test failure: vet bad directory missing HIGH findings.")

        # 5. Test add without --approved fails
        proj_dir = os.path.join(tmp, "proj")
        os.makedirs(os.path.join(proj_dir, ".agents"), exist_ok=True)
        res_add_unapproved = subprocess.run(
            [sys.executable, refs_py, "add", "--name", "fixture-ref", "--source", fixture_dir, "--subpath", "fixture-skill",
             "--category", "security", "--purpose", "Audit tests", "--used-by", "audit,verify", "--root", proj_dir],
            capture_output=True, text=True
        )
        if res_add_unapproved.returncode == 0:
            errors.append("References test failure: add without --approved should fail.")

        # 6. Test add with --approved
        res_add = subprocess.run(
            [sys.executable, refs_py, "add", "--name", "fixture-ref", "--source", fixture_dir, "--subpath", "fixture-skill",
             "--category", "security", "--purpose", "Audit tests", "--used-by", "audit,verify",
             "--paths", "src/**", "--approved", "--root", proj_dir],
            capture_output=True, text=True
        )
        if res_add.returncode != 0:
            errors.append(f"References test failure: add failed:\nSTDOUT:\n{res_add.stdout}\nSTDERR:\n{res_add.stderr}")
        installed_skill_md = os.path.join(proj_dir, ".agents", "vendor", "fixture-ref", "SKILL.md")
        if not os.path.isfile(installed_skill_md):
            errors.append("References test failure: Installed skill file missing in .agents/vendor.")

        # 7. Test list
        res_list = subprocess.run([sys.executable, refs_py, "list", "--root", proj_dir], capture_output=True, text=True)
        if res_list.returncode != 0:
            errors.append(f"References test failure: list failed:\n{res_list.stderr}")
        elif "fixture-ref" not in res_list.stdout:
            errors.append("References test failure: list output missing 'fixture-ref'.")

        # 8. Test due
        res_due_match = subprocess.run(
            [sys.executable, refs_py, "due", "--stage", "audit", "--paths", "src/index.js", "--root", proj_dir],
            capture_output=True, text=True
        )
        if "fixture-ref/SKILL.md" not in res_due_match.stdout:
            errors.append("References test failure: due should return matching reference for path 'src/index.js'.")

        res_due_nomatch_path = subprocess.run(
            [sys.executable, refs_py, "due", "--stage", "audit", "--paths", "docs/spec.md", "--root", proj_dir],
            capture_output=True, text=True
        )
        if res_due_nomatch_path.stdout.strip() != "":
            errors.append("References test failure: due should return empty output for non-matching path.")

        res_due_nomatch_stage = subprocess.run(
            [sys.executable, refs_py, "due", "--stage", "deploy", "--paths", "src/index.js", "--root", proj_dir],
            capture_output=True, text=True
        )
        if res_due_nomatch_stage.stdout.strip() != "":
            errors.append("References test failure: due should return empty output for non-matching stage.")

        # 9. Test verify & restore
        res_ver_init = subprocess.run([sys.executable, refs_py, "verify", "--root", proj_dir], capture_output=True, text=True)
        if res_ver_init.returncode != 0:
            errors.append(f"References test failure: initial verify failed:\n{res_ver_init.stderr}")

        with open(installed_skill_md, "a", encoding="utf-8") as f:
            f.write("\ncorrupted content\n")
        res_ver_tamper = subprocess.run([sys.executable, refs_py, "verify", "--root", proj_dir], capture_output=True, text=True)
        if res_ver_tamper.returncode != 1:
            errors.append(f"References test failure: verify expected exit code 1 on modified file, got {res_ver_tamper.returncode}")

        res_restore = subprocess.run([sys.executable, refs_py, "restore", "--root", proj_dir], capture_output=True, text=True)
        if res_restore.returncode != 0:
            errors.append(f"References test failure: restore failed:\n{res_restore.stderr}")

        res_ver_clean2 = subprocess.run([sys.executable, refs_py, "verify", "--root", proj_dir], capture_output=True, text=True)
        if res_ver_clean2.returncode != 0:
            errors.append(f"References test failure: verify failed after restore:\n{res_ver_clean2.stderr}")

        # 10. Test update without --approved vs with --approved
        extra_file = os.path.join(skill_dir, "extra.md")
        with open(extra_file, "w", encoding="utf-8") as f:
            f.write("extra content\n")
        subprocess.run(["git", "add", "."], cwd=fixture_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add extra.md"], cwd=fixture_dir, capture_output=True)

        res_upd_dry = subprocess.run([sys.executable, refs_py, "update", "fixture-ref", "--root", proj_dir], capture_output=True, text=True)
        if "extra.md" not in res_upd_dry.stdout:
            errors.append("References test failure: update preview missing 'extra.md'.")
        installed_extra = os.path.join(proj_dir, ".agents", "vendor", "fixture-ref", "extra.md")
        if os.path.exists(installed_extra):
            errors.append("References test failure: update without --approved must not install files.")

        res_upd_appr = subprocess.run([sys.executable, refs_py, "update", "fixture-ref", "--approved", "--root", proj_dir], capture_output=True, text=True)
        if res_upd_appr.returncode != 0:
            errors.append(f"References test failure: update with --approved failed:\n{res_upd_appr.stderr}")
        if not os.path.exists(installed_extra):
            errors.append("References test failure: update with --approved should have installed 'extra.md'.")

        # 11. Pipeline-only reference is never linked into skills
        res_inst = subprocess.run(["node", cli_js, "install"], cwd=proj_dir, capture_output=True, text=True)
        if res_inst.returncode != 0:
            errors.append(f"References test failure: build-forge install failed:\n{res_inst.stderr}")
        res_link = subprocess.run(["node", cli_js, "link", "--agents", "claude"], cwd=proj_dir, capture_output=True, text=True)
        if res_link.returncode != 0:
            errors.append(f"References test failure: build-forge link failed:\n{res_link.stderr}")
        if os.path.exists(os.path.join(proj_dir, ".agents", "skills", "fixture-ref")):
            errors.append("References test failure: pipeline-only reference should not exist in .agents/skills.")
        if os.path.exists(os.path.join(proj_dir, ".claude", "skills", "fixture-ref")):
            errors.append("References test failure: pipeline-only reference should not be linked in .claude/skills.")

        # 12. Test remove
        res_rem = subprocess.run([sys.executable, refs_py, "remove", "fixture-ref", "--yes", "--root", proj_dir], capture_output=True, text=True)
        if res_rem.returncode != 0:
            errors.append(f"References test failure: remove failed:\n{res_rem.stderr}")
        if os.path.exists(os.path.join(proj_dir, ".agents", "vendor", "fixture-ref")):
            errors.append("References test failure: vendor directory still exists after remove.")


def run_legacy_parity_fixture_tests(repo_root, errors):
    test_script = os.path.join(repo_root, "tests", "test_legacy_import.py")
    if os.path.isfile(test_script):
        res = subprocess.run([sys.executable, test_script], capture_output=True, text=True)
        if res.returncode != 0:
            errors.append(f"Legacy parity importer tests failed:\n{res.stderr or res.stdout}")


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    skills_dir = os.path.join(repo_root, "skills")

    errors = []

    print("Running CI checks...")
    check_skills(skills_dir, errors)
    check_skill_placeholders(skills_dir, errors)
    check_python_files(repo_root, errors)
    check_no_cache_or_pyc(repo_root, errors)
    check_dashes(skills_dir, errors)
    check_feature_delivery_workflows(skills_dir, errors)

    print("Running smoke tests...")
    run_smoke_test(repo_root, errors)

    print("Running multi-agent link tests...")
    run_link_tests(repo_root, errors)

    print("Running references system tests...")
    run_references_tests(repo_root, errors)

    print("Running legacy parity importer fixture tests...")
    run_legacy_parity_fixture_tests(repo_root, errors)

    print("Running allowlist guard and fixture tests...")
    check_allowlist(repo_root, errors)
    run_allowlist_fixture_tests(repo_root, errors)

    print("Running integrity manifest checks...")
    check_integrity_manifest(repo_root, errors)

    if errors:
        print(f"\nCI checks failed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("\nAll CI checks, smoke tests, link tests, references tests, and allowlist tests passed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
