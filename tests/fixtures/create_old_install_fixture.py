#!/usr/bin/env python3
"""Build an old install fixture from historical commit 5301f87 (or fallback builder).

The fixture simulates an existing Build Forge 0.1.0 install:
- 0.1.0 pipeline skills installed (lacks 0.2.0 core skill project-blueprints)
- .agents/build-forge.lock.json at version 0.1.0
- Edit to 1 pipeline skill (atomic-commits)
- Unstamped generated skill carrying old banner and hand-edited lines (build-ui)
- .agents/project-profile.yaml with schema_version 1 and deprecated external_references
- Vendor folder (.agents/vendor/old-vendor-skill) with reference entry
- Initialized clean git repository
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "old-install"
HISTORICAL_COMMIT = "5301f87"


def compute_sha256(path: Path) -> str:
    content = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def unpack_from_git_history(dest_skills_dir: Path) -> bool:
    """Try unpacking skills from git history commit 5301f87."""
    try:
        proc = subprocess.run(
            ["git", "archive", HISTORICAL_COMMIT, "skills/"],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout:
            return False

        tar_proc = subprocess.run(
            ["tar", "-x", "-C", str(dest_skills_dir.parent)],
            input=proc.stdout,
            capture_output=True,
            check=False,
        )
        return tar_proc.returncode == 0
    except Exception:
        return False


def build_fallback_skills(dest_skills_dir: Path) -> None:
    """Fallback: copy current skills excluding 0.2.0 additions (project-blueprints, extend-pipeline)."""
    repo_root = Path(__file__).resolve().parents[2]
    src_skills = repo_root / "skills"
    excluded = {"project-blueprints", "extend-pipeline"}

    dest_skills_dir.mkdir(parents=True, exist_ok=True)
    for entry in src_skills.iterdir():
        if entry.is_dir() and entry.name not in excluded:
            shutil.copytree(entry, dest_skills_dir / entry.name)


def generate_old_install_fixture(target_dir: Path = None, init_git: bool = False) -> Path:
    target = target_dir if target_dir is not None else FIXTURE_DIR
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    agents_dir = target / ".agents"
    target_skills_dir = agents_dir / "skills"
    agents_dir.mkdir(parents=True, exist_ok=True)

    # 1. Unpack 0.1.0 pipeline skills
    success = unpack_from_git_history(target_skills_dir)
    if not success or not target_skills_dir.exists():
        build_fallback_skills(target_skills_dir)

    # Ensure unwanted 0.2.0 core skills and optional module skill are omitted
    for unwanted in ("project-blueprints", "extend-pipeline", "targeted-module-testing"):
        unwanted_dir = target_skills_dir / unwanted
        if unwanted_dir.exists():
            shutil.rmtree(unwanted_dir)

    # Sanitize fixture URLs to only allowed hosts for dev.py fixture check
    for root_dir, _, files in os.walk(target_skills_dir):
        for f in files:
            full = Path(root_dir) / f
            try:
                txt = full.read_text(encoding="utf-8")
                sanitized = (
                    txt.replace("`https://`", "`https://example.com/`")
                    .replace("https://ne-mo-app.vercel.app", "https://example.com/nemo")
                    .replace("https://github.com", "https://example.com/repo")
                )
                if sanitized != txt:
                    full.write_text(sanitized, encoding="utf-8")
            except Exception:
                pass

    # 2. Compute 0.1.0 lock file before hand edits
    lock_manifest = {}
    for root_dir, _, files in os.walk(target_skills_dir):
        for f in files:
            full = Path(root_dir) / f
            rel = full.relative_to(agents_dir).as_posix()
            lock_manifest[rel] = compute_sha256(full)
    lock_manifest["_version"] = "0.1.0"

    lock_file = agents_dir / "build-forge.lock.json"
    lock_file.write_text(json.dumps(lock_manifest, indent=2) + "\n", encoding="utf-8")

    # 3. Edit 1 pipeline skill (atomic-commits)
    atomic_skill = target_skills_dir / "atomic-commits" / "SKILL.md"
    if atomic_skill.is_file():
        existing = atomic_skill.read_text(encoding="utf-8")
        edited = existing.rstrip() + "\n\n## Local Custom Rule\nAlways mention the ticket number in commit message.\n"
        atomic_skill.write_text(edited, encoding="utf-8")

    # 4. Create unstamped generated convention skill with old banner and hand edit (build-ui)
    build_ui_dir = target_skills_dir / "build-ui"
    build_ui_dir.mkdir(parents=True, exist_ok=True)
    build_ui_skill = build_ui_dir / "SKILL.md"
    build_ui_content = (
        "---\n"
        "name: build-ui\n"
        "description: UI conventions\n"
        "---\n"
        "<!-- Generated from .agents/project-profile.yaml by project-bootstrap. Edit the profile, then re-render. -->\n\n"
        "# How to build UI in test-app\n\n"
        "## Requirements\n"
        "1. Semantic HTML elements everywhere.\n\n"
        "## Custom team rule\n"
        "Never use div for button elements. Hand-edited line surviving upgrade.\n\n"
        "<!-- BEGIN CUSTOM: notes -->\n"
        "Local notes surviving upgrade.\n"
        "<!-- END CUSTOM: notes -->\n"
    )
    build_ui_skill.write_text(build_ui_content, encoding="utf-8")

    # 5. Profile with deprecated external_references and schema_version 1
    profile_path = agents_dir / "project-profile.yaml"
    profile_content = (
        "schema_version: 1\n\n"
        "project:\n"
        "  name: test-app\n"
        "  summary: Test application for safe update.\n"
        "  mode: existing\n\n"
        "stack:\n"
        "  language: typescript\n"
        "  framework: react\n"
        "  package_manager: npm\n\n"
        "design:\n"
        "  enabled: true\n"
        "  component_dirs:\n"
        "    - src/components\n"
        "  tokens_file: src/tokens.css\n\n"
        "external_references:\n"
        "  - name: old-vendor-skill\n"
        "    path: .agents/vendor/old-vendor-skill\n"
        "    purpose: Legacy vendor skill\n"
        "    status: active\n"
    )
    profile_path.write_text(profile_content, encoding="utf-8")

    # 6. Vendor folder with reference entry
    vendor_skill_dir = agents_dir / "vendor" / "old-vendor-skill"
    vendor_skill_dir.mkdir(parents=True, exist_ok=True)
    (vendor_skill_dir / "SKILL.md").write_text(
        "---\nname: old-vendor-skill\ndescription: Legacy vendor skill\n---\n# Old Vendor Skill\n",
        encoding="utf-8"
    )

    # 7. Minimal project files
    (target / "package.json").write_text(
        json.dumps({"name": "test-app", "version": "1.0.0"}, indent=2) + "\n",
        encoding="utf-8"
    )
    (target / "src" / "components").mkdir(parents=True, exist_ok=True)
    (target / "src" / "components" / "Button.tsx").write_text(
        "export const Button = () => <button>Click</button>;\n",
        encoding="utf-8"
    )
    (target / "src" / "tokens.css").write_text(
        ":root { --color-primary: #0000ff; }\n",
        encoding="utf-8"
    )
    (target / "INVENTED.md").write_text(
        "# Old Install Fixture\nSimulated Build Forge 0.1.0 install based on historical commit 5301f87.\n",
        encoding="utf-8"
    )

    # 8. Optional git repo
    if init_git:
        subprocess.run(["git", "init"], cwd=str(target), capture_output=True, check=False)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(target), capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(target), capture_output=True, check=False)
        subprocess.run(["git", "add", "."], cwd=str(target), capture_output=True, check=False)
        subprocess.run(["git", "commit", "-m", "Initial 0.1.0 state"], cwd=str(target), capture_output=True, check=False)

    return target


if __name__ == "__main__":
    out = generate_old_install_fixture()
    print(f"Old install fixture generated at {out}")
