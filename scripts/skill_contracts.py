#!/usr/bin/env python3
"""Enforce skill contracts across skills/ instructions, references, and scripts.

Checks:
1. Every file in skills/*/scripts (except tests and __pycache__) must be named in that skill's
   SKILL.md or references. Exceptions go in scripts/contracts-allow.txt with a reason.
2. Every path of the form .agents/skills/<skill>/scripts/<file> found in any SKILL.md or reference
   must exist in skills/.
3. For each referenced script that uses argparse, run it with --help and check that every
   subcommand named in the text exists.
4. REQUIRED_TEXT table:
   - atomic-commits: ".agents/skills/atomic-commits/scripts/suggest_scope.py", "--staged"
   - rules-to-tests: "no_dual_homed_skills"
   - project-bootstrap: "blueprint init", "legacy inventory"
   - sync-skills-and-docs: "drift", "check_sync.py"
   - feature-delivery: "stale"
"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REQUIRED_TEXT = {
    "atomic-commits": [
        ".agents/skills/atomic-commits/scripts/suggest_scope.py",
        "--staged",
    ],
    "rules-to-tests": [
        "no_dual_homed_skills",
    ],
    "project-bootstrap": [
        "blueprint init",
        "legacy inventory",
    ],
    "sync-skills-and-docs": [
        "drift",
        "check_sync.py",
    ],
    "feature-delivery": [
        "stale",
    ],
}


def load_allowlist(repo_root: Path) -> set:
    allow_path = repo_root / "scripts" / "contracts-allow.txt"
    allowed = set()
    if allow_path.is_file():
        for line in allow_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            entry = line.split(":", 1)[0].strip()
            allowed.add(entry.replace("\\", "/"))
    return allowed


def get_subcommands(script_path: Path) -> set:
    try:
        res = subprocess.run(
            [sys.executable, "-B", str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = res.stdout + "\n" + res.stderr
    except Exception:
        return set()

    subcmds = set()
    m = re.search(r"\{([a-zA-Z0-9_,-]+)\}", output)
    if m:
        for item in m.group(1).split(","):
            item = item.strip()
            if item:
                subcmds.add(item)
    return subcmds


def check_skill_contracts(repo_root: Path) -> list:
    errors = []
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return [f"Skills directory not found at {skills_dir}"]

    allowed_scripts = load_allowlist(repo_root)

    # 1. Every script in skills/*/scripts must be named in SKILL.md or references
    for script_file in sorted(skills_dir.glob("*/scripts/*")):
        if not script_file.is_file():
            continue
        rel_posix = script_file.relative_to(repo_root).as_posix()
        name = script_file.name
        if name.startswith(".") or "test" in name or "__pycache__" in rel_posix:
            continue
        if rel_posix in allowed_scripts:
            continue

        skill_dir = script_file.parent.parent
        skill_text = ""
        skill_md = skill_dir / "SKILL.md"
        if skill_md.is_file():
            skill_text += skill_md.read_text(encoding="utf-8", errors="ignore")
        for ref_md in (skill_dir / "references").rglob("*.md"):
            skill_text += ref_md.read_text(encoding="utf-8", errors="ignore")

        if name not in skill_text:
            errors.append(
                f"Script '{rel_posix}' is not mentioned in {skill_dir.name}/SKILL.md or references. "
                "Add to scripts/contracts-allow.txt if exempt."
            )

    # Collect all markdown files in skills/
    md_files = sorted(skills_dir.rglob("*.md"))

    # 2. Every path of the form .agents/skills/<skill>/scripts/<file> must exist in skills/
    script_ref_pat = re.compile(r"\.agents/skills/([a-z0-9-]+)/scripts/([a-zA-Z0-9_.-]+)")
    for mf in md_files:
        txt = mf.read_text(encoding="utf-8", errors="ignore")
        for m in script_ref_pat.finditer(txt):
            skill_name, script_name = m.group(1), m.group(2)
            target = skills_dir / skill_name / "scripts" / script_name
            if not target.is_file():
                errors.append(
                    f"{mf.relative_to(repo_root).as_posix()} references non-existent script: "
                    f".agents/skills/{skill_name}/scripts/{script_name}"
                )

    # 3. For each referenced script with subparsers, check that named subcommands exist
    subcmd_cache = {}
    invocation_pat = re.compile(
        r"(?:python3?|py(?: -3)?)\s+\.agents/skills/([a-z0-9-]+)/scripts/([a-zA-Z0-9_.-]+)(.*?)(?:\n|`|$)",
        re.MULTILINE,
    )
    for mf in md_files:
        txt = mf.read_text(encoding="utf-8", errors="ignore")
        for m in invocation_pat.finditer(txt):
            skill_name = m.group(1)
            script_name = m.group(2)
            args_str = m.group(3).strip()
            target_script = skills_dir / skill_name / "scripts" / script_name
            if not target_script.is_file():
                continue

            if target_script not in subcmd_cache:
                subcmd_cache[target_script] = get_subcommands(target_script)

            valid_subcmds = subcmd_cache[target_script]
            if not valid_subcmds:
                continue

            # Find the first positional token
            tokens = args_str.split()
            subcmd = None
            for tok in tokens:
                if tok.startswith("-") or tok.startswith("<") or tok.startswith('"') or tok.startswith("'"):
                    continue
                subcmd = tok
                break

            if subcmd and subcmd not in valid_subcmds:
                errors.append(
                    f"{mf.relative_to(repo_root).as_posix()}: Unknown subcommand '{subcmd}' for "
                    f"{skill_name}/scripts/{script_name}. Valid subcommands: {sorted(valid_subcmds)}"
                )

    # 4. REQUIRED_TEXT table check
    for skill_name, required_tokens in REQUIRED_TEXT.items():
        sdir = skills_dir / skill_name
        if not sdir.is_dir():
            errors.append(f"Required skill '{skill_name}' does not exist under skills/")
            continue

        skill_text = ""
        for mf in sorted(sdir.rglob("*.md")):
            skill_text += mf.read_text(encoding="utf-8", errors="ignore") + "\n"

        skill_text_lower = skill_text.lower()
        for token in required_tokens:
            if token.lower() not in skill_text_lower:
                errors.append(
                    f"Skill '{skill_name}' does not contain required text contract: '{token}'"
                )

    return errors


def main():
    repo_root = Path(__file__).resolve().parent.parent
    errors = check_skill_contracts(repo_root)
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        print(f"\n{len(errors)} skill contract violation(s) found.")
        sys.exit(1)
    else:
        print("OK: Skill contracts verified.")
        sys.exit(0)


if __name__ == "__main__":
    main()
