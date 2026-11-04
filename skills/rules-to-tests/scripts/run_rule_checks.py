#!/usr/bin/env python3
"""Run the machine checks attached to rules in the project profile.

Usage: python run_rule_checks.py [--profile .agents/project-profile.yaml] [--root .] [--only RULE_ID] [--list]

Copy this file into the project (for example .agents/checks/run_rule_checks.py)
so the project's check command does not depend on any installed skill.
Exit 1 when any check fails. Needs PyYAML (pip install pyyaml).

Check types (see the profile schema):
  forbid        a regex must not appear in the included files
  require_file  a file must exist
  forbid_file   no file may match the included globs
  root_only     the repo root may hold only structure.root_allowed entries
"""
import argparse
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

IGNORE_DIRS = {"node_modules", "dist", "build", ".git", ".next", ".nuxt", "coverage", ".venv",
               "venv", "__pycache__", ".turbo", ".vercel", ".netlify", "target", "out"}
ROOT_IGNORE = {".git", "node_modules", "dist", "build", ".DS_Store", "coverage"}
MAX_BYTES = 1_000_000
RUNNER_VERSION = 1


def expand_braces(pattern):
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    out = []
    for option in m.group(1).split(","):
        out += expand_braces(pattern[:m.start()] + option + pattern[m.end():])
    return out


def glob_to_regex(glob):
    i, out = 0, ""
    while i < len(glob):
        c = glob[i]
        if glob.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile("^" + out + "$")


def compile_globs(globs):
    regexes = []
    for g in globs or []:
        for expanded in expand_braces(g):
            regexes.append(glob_to_regex(expanded))
    return regexes


def list_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for name in filenames:
            files.append(Path(dirpath, name).relative_to(root).as_posix())
    return files


def matching(files, include, exclude):
    inc, exc = compile_globs(include), compile_globs(exclude)
    return [f for f in files if any(r.match(f) for r in inc) and not any(r.match(f) for r in exc)]


def gitignored_names(root):
    """Plain names listed in the root .gitignore (no wildcards or sub paths)."""
    names = set()
    gi = root / ".gitignore"
    if gi.exists():
        for line in gi.read_text(errors="ignore").splitlines():
            line = line.strip().lstrip("/").rstrip("/")
            if line and not line.startswith(("#", "!")) and not any(c in line for c in "*?[/"):
                names.add(line)
    return names


def run_check(rule, prof, root, files):
    chk = rule["check"]
    t = chk.get("type") if isinstance(chk, dict) else chk
    problems = []
    if t == "forbid":
        rx = re.compile(chk["pattern"])
        for rel in matching(files, chk.get("include"), chk.get("exclude")):
            p = root / rel
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                m = rx.search(line)
                if m:
                    problems.append(f"{rel}:{n}: {m.group(0)[:40]}")
    elif t == "require_file":
        if not (root / chk["path"]).exists():
            problems.append(f"missing file: {chk['path']}")
    elif t == "forbid_file":
        for rel in matching(files, chk.get("include"), chk.get("exclude")):
            problems.append(f"forbidden file: {rel}")
    elif t == "root_only":
        allowed = {a.rstrip("/") for a in (prof.get("structure") or {}).get("root_allowed", [])}
        ignored = gitignored_names(root)
        for entry in sorted(os.listdir(root)):
            if entry in ROOT_IGNORE or entry in allowed or entry in ignored:
                continue
            problems.append(f"not allowed in the repo root: {entry}")
    elif t == "no_dual_homed_skills":
        vendor_dir = root / ".agents" / "vendor"
        skills_dir = root / ".agents" / "skills"
        if vendor_dir.is_dir() and skills_dir.is_dir():
            vendor_folders = {d.name for d in vendor_dir.iterdir() if d.is_dir() and not d.name.startswith(".")}
            skills_folders = {d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")}
            overlap = vendor_folders & skills_folders
            for o in sorted(overlap):
                problems.append(f"dual-homed skill collision: '{o}' exists in both .agents/vendor and .agents/skills")
            for sname in sorted(skills_folders - overlap):
                sm = skills_dir / sname / "SKILL.md"
                if sm.is_file():
                    try:
                        content = sm.read_text(encoding="utf-8", errors="ignore")
                        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                        if match:
                            y = yaml.safe_load(match.group(1)) or {}
                            fn_name = str(y.get("name", "")).strip() if isinstance(y, dict) else ""
                            if fn_name and fn_name in vendor_folders:
                                problems.append(f"dual-homed skill collision: skill '{sname}' frontmatter name '{fn_name}' matches .agents/vendor/{fn_name}")
                    except Exception:
                        pass
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=".agents/project-profile.yaml")
    ap.add_argument("--root", default=".")
    ap.add_argument("--only", default=None)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    prof_path = Path(a.profile)
    if not prof_path.is_absolute() and not prof_path.is_file() and (root / a.profile).is_file():
        prof_path = root / a.profile
    prof = yaml.safe_load(prof_path.read_text()) or {}
    rules = prof.get("rules") or []
    checked = [r for r in rules if isinstance(r.get("check"), (dict, str))]
    unchecked = [r for r in rules if not isinstance(r.get("check"), (dict, str))]

    if a.list:
        for r in checked:
            chk = r["check"]
            ctype = chk.get("type") if isinstance(chk, dict) else chk
            print(f"{r['id']}: {ctype}")
        print(f"\n{len(checked)} checked, {len(unchecked)} without a check")
        return
    if a.only:
        checked = [r for r in checked if r["id"] == a.only]
        if not checked:
            sys.exit(f"No rule with a check and id '{a.only}'")

    files = list_files(root)
    failed = 0
    for r in checked:
        problems = run_check(r, prof, root, files)
        if problems:
            failed += 1
            print(f"FAIL {r['id']}: {r['text']}")
            for line in problems[:5]:
                print(f"     {line}")
            if len(problems) > 5:
                print(f"     ... and {len(problems) - 5} more")
        else:
            print(f"PASS {r['id']}")
    print(f"\n{len(checked) - failed} passed, {failed} failed, {len(unchecked)} rules have no automatic check")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
