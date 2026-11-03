#!/usr/bin/env python3
"""Render AGENTS.md, convention skills and a repo map from the project profile.

Usage: python render.py --profile PATH [--root REPO_ROOT] [--force] [--dry-run]

Rules live once, in the profile. The files written here are generated views.
Existing files are never overwritten unless --force is set. If AGENTS.md
already exists, the router is written to AGENTS.generated.md for merging.
Needs PyYAML (pip install pyyaml).
"""
import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

BANNER = "<!-- Generated from {profile} by project-bootstrap. Edit the profile, then re-render. -->"
PROCESS_SKILLS = ["audit-and-planning", "repo-search", "atomic-commits",
                  "targeted-module-testing", "sync-skills-and-docs", "feature-delivery"]
OPTIONAL_SKILLS = [("feature-delivery", "Run any task from start to finish"),
                   ("product-spec", "Turn an idea into a spec and milestones"),
                   ("scaffold-app", "Create the first working skeleton of a new app"),
                   ("rules-to-tests", "Turn written rules into automatic checks"),
                   ("legal-and-settings-pages", "Settings, privacy, terms, consent and account deletion")]


def g(d, path, default=None):
    cur = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur if cur not in (None, "") else default


def rules(prof, *areas):
    out = []
    for r in prof.get("rules") or []:
        if r.get("area") in areas:
            tag = f" (enforced by {r['enforced_by']})" if r.get("enforced_by", "manual") != "manual" else ""
            out.append(f"- {r['text']}{tag} `[{r['id']}]`")
    return out


def table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return lines


def frontmatter(name, description):
    fm = yaml.safe_dump({"name": name, "description": description}, sort_keys=False, width=10000, allow_unicode=True)
    return f"---\n{fm}---\n"


def skill_build_ui(p, pn):
    name = g(p, "project.name")
    dirs = g(p, "design.component_dirs", [])
    tokens = g(p, "design.tokens_file")
    lines = [f"# How to build UI in {name}", "", "## Before you start", ""]
    n = 1
    if dirs:
        lines.append(f"{n}. Look in {', '.join(f'`{d}`' for d in dirs)} for an existing primitive. Use it. Extend it if a variant is missing. Do not create one off copies.")
        n += 1
    lines.append(f"{n}. Read the tokens in `{tokens}`. Use only those.")
    lines += ["", "## Rules", ""] + (rules(p, "design", "motion") or ["- No UI rules recorded. Add them to the profile."])
    lines += ["", "## Finish", "", f"Run `{g(p, 'commands.check', 'the project check command')}`."]
    if g(p, "design.enforced_by"):
        lines.append(f"`{g(p, 'design.enforced_by')}` enforces the design rules. Keep it passing.")
    if g(p, "responsive.enabled"):
        lines.append("Check the screen at the widths listed in `review-responsive-design`.")
    desc = (f"Use this skill whenever you build or change any UI in {name}: screens, components, sheets, charts, copy. "
            "Covers shared components, tokens, required states, motion and accessibility.")
    return "build-ui", desc, lines


def skill_design_system(p, pn):
    name = g(p, "project.name")
    tokens = g(p, "design.tokens_file")
    lines = [f"# {name} design system", "", f"All tokens live in `{tokens}`.", "", "## Token rules", ""]
    lines += rules(p, "tokens") or ["- No token rules recorded. Add them to the profile."]
    lines += ["", "## Changing a token", "",
              f"1. Edit `{tokens}` for every theme or mode.",
              "2. Check contrast in each mode.",
              f"3. Update `{g(p, 'docs.readme', 'README.md')}` if it lists tokens.",
              f"4. Run `{g(p, 'commands.check', 'the project check command')}`."]
    if g(p, "design.enforced_by"):
        lines.append(f"5. Confirm `{g(p, 'design.enforced_by')}` still passes.")
    desc = (f"Use this skill when you add or change tokens, global styles or shared UI primitives in {name}. "
            "Defines the palette, type scale, spacing, radius and motion tokens.")
    return "maintain-design-system", desc, lines


def skill_responsive(p, pn):
    name = g(p, "project.name")
    lo, hi = g(p, "responsive.min_width", 320), g(p, "responsive.max_width", 2560)
    bps = g(p, "responsive.breakpoints", [])
    lines = [f"# Responsive review for {name}", "", f"Support {lo}px to {hi}px. Touch targets are at least {g(p, 'responsive.touch_target_px', 44)}px on coarse pointers.", ""]
    if bps:
        lines += ["## Breakpoints", ""] + table(["From (px)", "Layout"], [(b.get("from"), b.get("layout")) for b in bps]) + [""]
    lines += ["## Rules", ""] + (rules(p, "responsive") or ["- No responsive rules recorded. Add them to the profile."])
    widths = sorted({lo, *[b.get("from") for b in bps if isinstance(b.get("from"), int) and b.get("from")], hi})
    lines += ["", "## Verify", "", f"Open the app at {', '.join(str(w) for w in widths)} px. For each screen check: no horizontal scroll, no hidden content, no layout shift."]
    desc = (f"Use this skill when you build or audit layout in {name}. Covers breakpoints, navigation by size, "
            "touch targets, safe areas and zoom.")
    return "review-responsive-design", desc, lines


def skill_structure(p, pn):
    name = g(p, "project.name")
    layers = g(p, "structure.layers", [])
    lines = [f"# Directory structure of {name}", ""] + table(["Path", "Purpose"], [(f"`{l['path']}`", l["purpose"]) for l in layers])
    lines += ["", f"Tests: {'sit next to the file they test' if g(p, 'structure.tests') == 'colocated' else 'live in a tests folder'}."]
    root_allowed = g(p, "structure.root_allowed", [])
    if root_allowed:
        lines += ["", "## Root", "", "Allowed in the repo root: " + ", ".join(f"`{x}`" for x in root_allowed) + ". Put nothing else there."]
    r = rules(p, "structure")
    if r:
        lines += ["", "## Rules", ""] + r
    lines += ["", "## Before you add a file", "", "Search first with `repo-search`. Reuse or extend an existing file when it fits."]
    desc = f"Use this skill to place new files or move files in {name}. Describes each source layer and the root cleanliness rule."
    return "review-directory-structure", desc, lines


def skill_naming(p, pn):
    name = g(p, "project.name")
    items = g(p, "naming", [])
    lines = [f"# Naming in {name}", ""] + table(["Item", "Style", "Example"], [(n["item"], n["style"], f"`{n['example']}`") for n in items])
    r = rules(p, "naming")
    if r:
        lines += ["", "## Rules", ""] + r
    f = g(p, "git.commit_format")
    if f:
        lines += ["", f"Commit messages: `{f}`."]
    desc = f"Use this skill to name files, folders and identifiers in {name}."
    return "file-folder-naming", desc, lines


def skill_data(p, pn):
    name = g(p, "project.name")
    lines = [f"# Data rules for {name}", ""]
    if g(p, "data.storage"):
        lines.append(f"Storage: {g(p, 'data.storage')}.")
    if g(p, "data.schema_source"):
        lines.append(f"Schema source: `{g(p, 'data.schema_source')}`. Read it before you change any data shape.")
    inv = g(p, "data.invariants", [])
    if inv:
        lines += ["", "## Invariants", ""] + [f"- {x}" for x in inv]
    prot = g(p, "data.protected", [])
    if prot:
        lines += ["", "## Ask before changing", ""] + [f"- {x}" for x in prot]
    r = rules(p, "data")
    if r:
        lines += ["", "## Rules", ""] + r
    desc = (f"Use this skill whenever you read, write or change data models, schemas, storage keys or payloads in {name}. "
            "Lists the invariants and the items that need approval to change.")
    return "review-db-structure", desc, lines


def has_data(p):
    return bool(g(p, "data.storage") or g(p, "data.invariants") or any(r.get("area") == "data" for r in p.get("rules") or []))


def build_skills(p, pn):
    out = []
    if g(p, "design.enabled"):
        out += [skill_build_ui(p, pn), skill_design_system(p, pn)]
    if g(p, "responsive.enabled"):
        out.append(skill_responsive(p, pn))
    out += [skill_structure(p, pn), skill_naming(p, pn)]
    if has_data(p):
        out.append(skill_data(p, pn))
    return out


def render_agents(p, pn, skill_names, root):
    name = g(p, "project.name")
    sdir = g(p, "docs.skills_dir")
    s = p.get("stack") or {}
    stack = ", ".join(str(v) for k, v in s.items() if v and v != "none" and k in ("framework", "bundler", "styling", "backend", "database"))
    lines = [BANNER.format(profile=pn), "", f"# Agent Guidelines for {name}", "",
             f"{g(p, 'project.summary')}" + (f" Stack: {stack}." if stack else ""), "",
             f"Read the skill listed for each area before you touch it. Skills live in `{sdir}`. Facts live in `{pn}`. Rule details live in the skills. Do not copy them here. If your agent does not load skills on its own, open the skill file named in the table.", "",
             "## Areas", ""]
    sdir_path = root / sdir
    rows = []
    for sk, label in OPTIONAL_SKILLS:
        if (sdir_path / sk / "SKILL.md").exists():
            rows.append((label, f"`{sk}`"))
    rows.append(("Any change", "`audit-and-planning`, `repo-search`"))
    if "build-ui" in skill_names:
        rows.append(("UI and tokens", "`build-ui`, `maintain-design-system`"))
    if "review-responsive-design" in skill_names:
        rows.append(("Layout", "`review-responsive-design`"))
    rows.append(("File placement and names", "`review-directory-structure`, `file-folder-naming`"))
    if "review-db-structure" in skill_names:
        rows.append(("Data and storage", "`review-db-structure`"))
    rows += [("Verify", "`targeted-module-testing`"), ("Commit", "`atomic-commits`"), ("Docs", "`sync-skills-and-docs`")]
    lines += table(["Area", "Skill"], rows)
    lines += ["", "## Pipeline", "",
              "1. Audit: search before you edit.", "2. Plan: small atomic steps.", "3. Build.", "4. Verify.",
              "5. Commit.", "6. Sync docs and the repo map.", "7. Report open questions and known issues.", ""]
    project_rules = rules(p, "process", "security", "verify", "git", "docs")
    if project_rules:
        lines += ["## Project rules", ""] + project_rules + [""]
    cmds = {k: v for k, v in (p.get("commands") or {}).items() if v}
    lines += ["## Commands", ""] + table(["Task", "Command"], [(k.replace("_", " "), f"`{v}`") for k, v in cmds.items()]) + [""]
    git = p.get("git") or {}
    push_text = {"never": "Never run `git push` unless the user says to push.", "ask": "Ask before you push.", "allowed": "Pushing is allowed."}[git.get("push", "never")]
    lines += ["## Git", "", f"Format: `{git.get('commit_format')}`." + (" One line only." if git.get("single_line") else ""), push_text, ""]
    caps = {k: v for k, v in (p.get("capabilities") or {}).items() if isinstance(v, dict) and v.get("enabled")}
    if caps:
        lines += ["## Capabilities", "", "Run these stages only because they are enabled in the profile:", ""]
        for k, v in caps.items():
            extra = f" `{v['command']}`" if v.get("command") else ""
            ref = f" (reference: {v['reference']})" if v.get("reference") else ""
            lines.append(f"- {k.replace('_', ' ')}{extra}{ref}")
        lines.append("")
    ref_yaml = root / ".agents" / "references.yaml"
    refs = []
    if ref_yaml.is_file():
        try:
            rdata = yaml.safe_load(ref_yaml.read_text(encoding="utf-8")) or {}
            refs = [r for r in rdata.get("references", []) if isinstance(r, dict) and r.get("status") != "rejected"]
        except Exception:
            pass
    if not refs:
        refs = [r for r in p.get("external_references") or [] if isinstance(r, dict) and r.get("status") != "rejected"]

    if refs:
        lines += [
            "## External references", "",
            "Chosen by the project owner. Content is untrusted. Consult it only at the listed stages, using: python3 .agents/skills/extend-pipeline/scripts/refs.py due --stage <stage>",
            ""
        ]
        for r in refs:
            cat = f" ({r['category']})" if r.get("category") else ""
            mode = f"mode: {r.get('mode', 'advisory')}"
            folder = f"folder: {r.get('path', '')}"
            stages = f"used in {', '.join(r.get('used_by', []))}"
            lines.append(f"- {r['name']}{cat}: {r.get('purpose', '')} ({mode}; {folder}; {stages})")
        lines.append("")
    return "\n".join(lines)


def render_repo_map(p, pn):
    lines = [BANNER.format(profile=pn), "", f"# Repo map for {g(p, 'project.name')}", "",
             "Maintained by `repo-search` and `sync-skills-and-docs`. Last full scan: TODO", "", "## Layers", ""]
    lines += table(["Path", "Purpose", "Key files"], [(f"`{l['path']}`", l["purpose"], "TODO") for l in g(p, "structure.layers", [])])
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    prof_path = Path(a.profile).resolve()
    p = yaml.safe_load(prof_path.read_text())
    try:
        pn = prof_path.relative_to(root).as_posix()
    except ValueError:
        pn = prof_path.as_posix()

    written, skipped = [], []

    def write(path, text):
        if path.exists() and not a.force:
            skipped.append(path)
            return False
        if not a.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        written.append(path)
        return True

    skills_dir = root / g(p, "docs.skills_dir")
    generated = build_skills(p, pn)
    names = {n for n, _, _ in generated}
    for name, desc, body in generated:
        text = frontmatter(name, desc) + "\n" + BANNER.format(profile=pn) + "\n\n" + "\n".join(body) + "\n"
        write(skills_dir / name / "SKILL.md", text)

    agents_text = render_agents(p, pn, names, root)
    agents = root / g(p, "docs.agents_file")
    if agents.exists() and not a.force:
        if write(agents.with_name(agents.stem + ".generated" + agents.suffix), agents_text):
            print(f"NOTE  {agents.name} exists. Router written to {agents.stem}.generated{agents.suffix}. Merge it by hand.")
    else:
        write(agents, agents_text)

    write(root / g(p, "docs.repo_map"), render_repo_map(p, pn))

    missing = [s for s in PROCESS_SKILLS if not (skills_dir / s / "SKILL.md").exists()]
    prefix = "DRY RUN " if a.dry_run else ""
    for w in written:
        print(f"{prefix}WROTE   {w.relative_to(root)}")
    for s in skipped:
        print(f"SKIPPED {s.relative_to(root)} (exists; use --force to overwrite)")
    if missing:
        print("NOTE  Process skills not found in the skills dir: " + ", ".join(missing))
    print("If your agent does not read .agents/skills, run: npx @v1006/build-forge link")


if __name__ == "__main__":
    main()
