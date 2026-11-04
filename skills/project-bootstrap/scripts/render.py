#!/usr/bin/env python3
"""Render AGENTS.md, convention skills and a repo map from the project profile.

Usage: python render.py --profile PATH [--root REPO_ROOT] [--update] [--force] [--overwrite-unstamped] [--dry-run]

Rules live once, in the profile. The files written here are generated views.
Existing files are never overwritten unless --update or --force is set.
Custom blocks (<!-- BEGIN CUSTOM: name --> ... <!-- END CUSTOM: name -->)
are preserved byte for byte across updates.
Needs PyYAML (pip install pyyaml).
"""
import argparse
import difflib
import hashlib
import re
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

CONVENTION_SKILLS = {
    "build-ui",
    "maintain-design-system",
    "review-responsive-design",
    "review-directory-structure",
    "file-folder-naming",
    "review-db-structure",
}

STAMP_RE = re.compile(r"^<!-- build-forge:generated v1 body=([0-9a-f]{64}) -->\n?", re.MULTILINE)
CUSTOM_BLOCK_RE = re.compile(
    r"<!-- BEGIN CUSTOM: ([a-z0-9-]{1,40}) -->\n?(.*?)<!-- END CUSTOM: \1 -->\n?",
    re.DOTALL
)
CUSTOM_NAME_RE = re.compile(r"^[a-z0-9-]{1,40}$")

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password|passwd)\b\s*[:=]\s*['\"]?([A-Za-z0-9+/=_-]{20,})['\"]?"),
]


def normalize_lf(text: str) -> str:
    """Normalize line endings to LF."""
    return text.replace("\r\n", "\n")


def strip_stamp(text: str) -> str:
    """Remove stamp line if present."""
    return STAMP_RE.sub("", text)


def strip_custom_blocks(text: str) -> str:
    """Remove all custom blocks."""
    return CUSTOM_BLOCK_RE.sub("", text)


def compute_body_hash(text: str) -> str:
    """Compute sha256 hash of body with custom blocks and stamp removed, LF normalized."""
    norm = normalize_lf(text)
    clean = strip_stamp(norm)
    clean = strip_custom_blocks(clean)
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def stamp_text(text: str, body_hash: str) -> str:
    """Add or replace the stamp line after frontmatter (or at file top)."""
    norm = normalize_lf(text)
    clean = strip_stamp(norm)
    stamp_line = f"<!-- build-forge:generated v1 body={body_hash} -->\n"
    fm_match = re.match(r"^(---\n.*?\n---\n)(.*)$", clean, re.DOTALL)
    if fm_match:
        return f"{fm_match.group(1)}{stamp_line}{fm_match.group(2)}"
    return f"{stamp_line}{clean}"


def extract_custom_blocks(text: str, source_label: str) -> dict:
    """Extract custom blocks from text. Return dict of {name: inner_content}."""
    norm = normalize_lf(text)

    open_matches = list(re.finditer(r"<!-- BEGIN CUSTOM: ([^\s>]+) -->", norm))
    close_matches = list(re.finditer(r"<!-- END CUSTOM: ([^\s>]+) -->", norm))

    open_names = [m.group(1) for m in open_matches]
    close_names = [m.group(1) for m in close_matches]

    for name in open_names:
        if not CUSTOM_NAME_RE.match(name):
            sys.exit(f"ERROR: Invalid custom block name '{name}' in {source_label}. Names must match [a-z0-9-]{{1,40}}.")

    seen = set()
    for name in open_names:
        if name in seen:
            sys.exit(f"ERROR: Duplicate custom block name '{name}' in {source_label}.")
        seen.add(name)

    if len(open_names) != len(close_names):
        sys.exit(f"ERROR: Mismatched custom block tags in {source_label} ({len(open_names)} BEGIN vs {len(close_names)} END).")

    blocks = {}
    for m in CUSTOM_BLOCK_RE.finditer(norm):
        name = m.group(1)
        inner = m.group(2)
        blocks[name] = inner

    if set(open_names) != set(blocks.keys()):
        sys.exit(f"ERROR: Malformed or unclosed custom block in {source_label}.")

    return blocks


AREA_MAP = {
    "build-ui": "ui",
    "maintain-design-system": "tokens",
    "review-db-structure": "data",
    "review-responsive-design": "layout",
}


def resolve_blueprint_area(source_label: str) -> str:
    """Resolve blueprint area from convention skill source label."""
    for skill_name, area in AREA_MAP.items():
        if skill_name in source_label:
            return area
    return "data"


def validate_custom_blocks(blocks: dict, source_label: str) -> list:
    """Validate block line counts and secret patterns. Return list of warning strings."""
    warnings = []
    total_lines = 0

    area = resolve_blueprint_area(source_label)

    for name, content in blocks.items():
        lines = content.splitlines()
        count = len(lines)
        total_lines += count

        for pat in SECRET_PATTERNS:
            if pat.search(content):
                sys.exit(
                    f"ERROR: Secret pattern detected in custom block '{name}' in {source_label}. "
                    "Remove secrets from custom blocks."
                )

        if count > 160:
            adopt_cmd = f"python3 .agents/skills/project-blueprints/scripts/blueprint.py adopt --from {source_label} --block {name} --area {area}"
            sys.exit(
                f"ERROR: Custom block '{name}' in {source_label} has {count} lines (> 160). "
                f"Facts belong in blueprints (.agents/blueprints/) or the profile (.agents/project-profile.yaml). "
                f"Adopt into blueprints: {adopt_cmd}"
            )
        elif count > 80:
            adopt_cmd = f"python3 .agents/skills/project-blueprints/scripts/blueprint.py adopt --from {source_label} --block {name} --area {area}"
            warnings.append(
                f"WARN  Custom block '{name}' in {source_label} has {count} lines (> 80). "
                f"Facts belong in blueprints (.agents/blueprints/) or the profile (.agents/project-profile.yaml). "
                f"Adopt into blueprints: {adopt_cmd}"
            )

    if total_lines > 600:
        sys.exit(
            f"ERROR: {source_label} has {total_lines} total custom lines (> 600). "
            "Facts belong in blueprints (.agents/blueprints/) or the profile (.agents/project-profile.yaml)."
        )
    elif total_lines > 300:
        warnings.append(
            f"WARN  {source_label} has {total_lines} total custom lines (> 300). "
            "Facts belong in blueprints (.agents/blueprints/) or the profile (.agents/project-profile.yaml)."
        )

    return warnings


def inject_custom_blocks(template_text: str, blocks: dict):
    """Inject preserved custom blocks into template_text. Return (merged_text, preserved_count, orphan_dict)."""
    norm = normalize_lf(template_text)
    orphan_blocks = {}
    preserved_count = 0

    for name, content in blocks.items():
        pattern = re.compile(rf"<!-- BEGIN CUSTOM: {re.escape(name)} -->\n?.*?<!-- END CUSTOM: {re.escape(name)} -->\n?", re.DOTALL)
        if pattern.search(norm):
            replacement = f"<!-- BEGIN CUSTOM: {name} -->\n{content}<!-- END CUSTOM: {name} -->\n"
            norm = pattern.sub(lambda _: replacement, norm, count=1)
            preserved_count += 1
        else:
            orphan_blocks[name] = content

    return norm, preserved_count, orphan_blocks


def append_orphans(orphans: list, root: Path) -> None:
    """Save orphan custom blocks to .agents/custom-orphans.md."""
    if not orphans:
        return
    orphans_file = root / ".agents" / "custom-orphans.md"
    orphans_file.parent.mkdir(parents=True, exist_ok=True)

    entries = []
    for rel_path, name, content in orphans:
        inner = content if (content.endswith("\n") or not content) else content + "\n"
        entry = (
            f"## {rel_path} (block: {name})\n\n"
            f"<!-- BEGIN CUSTOM: {name} -->\n"
            f"{inner}"
            f"<!-- END CUSTOM: {name} -->\n"
        )
        entries.append(entry)
        print(f"ORPHAN  Preserved custom block '{name}' from {rel_path} in .agents/custom-orphans.md")

    header = (
        "# Custom Block Orphans\n\n"
        "Preserved by render.py. Custom blocks whose file or block name no longer exists.\n\n"
    )
    if orphans_file.is_file():
        existing = orphans_file.read_text(encoding="utf-8")
        if not existing.startswith("# Custom Block Orphans"):
            existing = header + existing
        orphans_file.write_text(existing.rstrip() + "\n\n" + "\n".join(entries), encoding="utf-8")
    else:
        orphans_file.write_text(header + "\n".join(entries), encoding="utf-8")


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
    lines += ["", "## Blueprint", "",
              "Query codebase UI facts on demand:",
              "`python3 .agents/skills/project-blueprints/scripts/blueprint.py show --area ui --paths <files>`"]
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
    lines = [f"# {name} design system", "", f"All tokens live in `{tokens}`.", "",
             "## Blueprint", "",
             "Query codebase design tokens on demand:",
             "`python3 .agents/skills/project-blueprints/scripts/blueprint.py show --area tokens --paths <files>`", "",
             "## Token rules", ""]
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
    lines = [f"# Responsive review for {name}", "", f"Support {lo}px to {hi}px. Touch targets are at least {g(p, 'responsive.touch_target_px', 44)}px on coarse pointers.", "",
             "## Blueprint", "",
             "Query codebase layout and breakpoint facts on demand:",
             "`python3 .agents/skills/project-blueprints/scripts/blueprint.py show --area layout --paths <files>`", ""]
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
    lines = [f"# Data rules for {name}", "",
             "## Blueprint", "",
             "Query codebase data models and storage facts on demand:",
             "`python3 .agents/skills/project-blueprints/scripts/blueprint.py show --area data --paths <files>`", ""]
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
    scopes_list = git.get("scopes") or []
    if scopes_list:
        scope_rows = []
        for s in scopes_list:
            if isinstance(s, str):
                scope_rows.append((f"`{s}`", ""))
            elif isinstance(s, dict) and s.get("name"):
                scope_rows.append((f"`{s['name']}`", s.get("purpose", "")))
        if scope_rows:
            lines += ["### Scope guide", ""]
            lines += table(["Scope", "Purpose"], scope_rows[:25])
            if len(scope_rows) > 25:
                lines += ["", f"See the profile (`{pn}`) for the full list of {len(scope_rows)} scopes."]
            lines.append("")
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


def rel_posix(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--update", action="store_true", help="Regenerate stamped files while preserving custom blocks; refuse files with hand edits outside blocks")
    ap.add_argument("--force", action="store_true", help="Overwrite files outside custom blocks; keep blocks and report lost lines")
    ap.add_argument("--overwrite-unstamped", action="store_true", help="Allow --force to overwrite unstamped files")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    prof_path = Path(a.profile).resolve()
    if not prof_path.is_file():
        sys.exit(f"Profile not found: {prof_path}")
    p = yaml.safe_load(prof_path.read_text(encoding="utf-8")) or {}
    pn = rel_posix(prof_path, root)

    skills_dir = root / (g(p, "docs.skills_dir") or ".agents/skills")
    generated = build_skills(p, pn)
    names = {n for n, _, _ in generated}

    # Prepare targets: (dest_path, raw_template, kind)
    targets = []
    notes_block = "\n<!-- BEGIN CUSTOM: notes -->\n<!-- END CUSTOM: notes -->\n"

    for name, desc, body in generated:
        raw_body = frontmatter(name, desc) + "\n" + BANNER.format(profile=pn) + "\n\n" + "\n".join(body) + notes_block
        dest = skills_dir / name / "SKILL.md"
        targets.append((dest, raw_body, "skill"))

    agents_file = root / (g(p, "docs.agents_file") or "AGENTS.md")
    agents_raw = render_agents(p, pn, names, root) + notes_block
    targets.append((agents_file, agents_raw, "agents"))

    repo_map_path = g(p, "docs.repo_map")
    if repo_map_path:
        repo_map_dest = root / repo_map_path
        repo_map_raw = render_repo_map(p, pn) + notes_block
        targets.append((repo_map_dest, repo_map_raw, "repo_map"))

    active_dest_paths = {dest for dest, _, _ in targets}

    created = []
    updated = []
    refused = []
    skipped = []
    all_orphans = []
    all_warnings = []

    # Pre-flight check for --update: transactional validation
    if a.update and not a.force:
        refusal_diffs = {}
        for dest, raw_tmpl, kind in targets:
            if not dest.is_file():
                continue
            disk_text = normalize_lf(dest.read_text(encoding="utf-8"))
            m = STAMP_RE.search(disk_text)
            if not m:
                refused.append((dest, "unstamped file exists"))
                continue

            stamp_hash = m.group(1)
            disk_body_hash = compute_body_hash(disk_text)
            disk_blocks = extract_custom_blocks(disk_text, rel_posix(dest, root))
            warns = validate_custom_blocks(disk_blocks, rel_posix(dest, root))
            all_warnings.extend(warns)

            if disk_body_hash != stamp_hash:
                # Hand edits detected outside custom blocks
                # Compute unified diff
                merged_candidate, _, _ = inject_custom_blocks(raw_tmpl, disk_blocks)
                new_hash = compute_body_hash(raw_tmpl)
                candidate_stamped = stamp_text(merged_candidate, new_hash)

                diff_lines = list(difflib.unified_diff(
                    disk_text.splitlines(keepends=True),
                    candidate_stamped.splitlines(keepends=True),
                    fromfile=f"{rel_posix(dest, root)} (current)",
                    tofile=f"{rel_posix(dest, root)} (expected clean)",
                ))
                refusal_diffs[dest] = "".join(diff_lines)
                refused.append((dest, "hand edits outside custom blocks"))

        if refused:
            for w in all_warnings:
                print(w)
            for dest, diff in refusal_diffs.items():
                print(f"\nREFUSED {rel_posix(dest, root)} (hand edits outside custom blocks):\n")
                print(diff)
            print("\nRender summary:")
            print("  created:   none")
            print("  updated:   none")
            print("  refused:")
            for r, reason in refused:
                print(f"    - {rel_posix(r, root)} ({reason})")
            print("  skipped:   none")
            sys.exit(1)

    # Process all targets
    for dest, raw_tmpl, kind in targets:
        rel_label = rel_posix(dest, root)
        if not dest.is_file():
            # Fresh file
            body_hash = compute_body_hash(raw_tmpl)
            final_content = stamp_text(raw_tmpl, body_hash)
            if not a.dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(final_content, encoding="utf-8")
            created.append(dest)
            prefix = "DRY RUN " if a.dry_run else ""
            print(f"{prefix}WROTE   {rel_label}")
            continue

        # File exists
        disk_text = normalize_lf(dest.read_text(encoding="utf-8"))
        stamp_m = STAMP_RE.search(disk_text)

        if not stamp_m:
            # Unstamped file
            if a.force and a.overwrite_unstamped:
                body_hash = compute_body_hash(raw_tmpl)
                final_content = stamp_text(raw_tmpl, body_hash)
                if not a.dry_run:
                    dest.write_text(final_content, encoding="utf-8")
                updated.append((dest, 0))
                print(f"OVERWROTE {rel_label} (unstamped; forced with --overwrite-unstamped)")
            elif not a.force and not a.update and kind == "agents":
                gen_dest = dest.with_name(dest.stem + ".generated" + dest.suffix)
                body_hash = compute_body_hash(raw_tmpl)
                final_content = stamp_text(raw_tmpl, body_hash)
                if not a.dry_run:
                    gen_dest.write_text(final_content, encoding="utf-8")
                created.append(gen_dest)
                print(f"NOTE  {dest.name} exists. Router written to {gen_dest.name}. Merge it by hand.")
            else:
                skipped.append((dest, "unstamped file exists; use --force --overwrite-unstamped to overwrite"))
                print(f"SKIPPED {rel_label} (unstamped; use --force --overwrite-unstamped to overwrite)")
            continue

        # Stamped file
        stamp_hash = stamp_m.group(1)
        disk_body_hash = compute_body_hash(disk_text)
        disk_blocks = extract_custom_blocks(disk_text, rel_label)
        warns = validate_custom_blocks(disk_blocks, rel_label)
        all_warnings.extend(warns)
        has_hand_edits = (disk_body_hash != stamp_hash)

        if not a.update and not a.force:
            # Plain render.py: default behavior is skip existing files
            if kind == "agents":
                gen_dest = dest.with_name(dest.stem + ".generated" + dest.suffix)
                body_hash = compute_body_hash(raw_tmpl)
                final_content = stamp_text(raw_tmpl, body_hash)
                if not a.dry_run:
                    gen_dest.write_text(final_content, encoding="utf-8")
                created.append(gen_dest)
                print(f"NOTE  {dest.name} exists. Router written to {gen_dest.name}. Merge it by hand.")
            else:
                skipped.append((dest, "exists; use --update or --force"))
                print(f"SKIPPED {rel_label} (exists; use --update or --force to overwrite)")
            continue

        if a.force and has_hand_edits:
            # Overwrite outside custom blocks, keep blocks, report lost lines
            clean_disk = strip_custom_blocks(strip_stamp(disk_text))
            clean_tmpl = strip_custom_blocks(raw_tmpl)
            diff_lines = list(difflib.unified_diff(
                clean_disk.splitlines(keepends=True),
                clean_tmpl.splitlines(keepends=True),
                fromfile=f"{rel_label} (current disk)",
                tofile=f"{rel_label} (regenerated)",
            ))
            lost_lines = [l[1:].rstrip("\r\n") for l in diff_lines if l.startswith("-") and not l.startswith("---")]  # strip-chars-ok: strip trailing CR and LF
            if lost_lines:
                print(f"NOTE  Overwriting hand edits outside custom blocks in {rel_label}. Lost lines:")
                for lost in lost_lines:
                    print(f"  - {lost}")

        # Inject custom blocks and write updated stamped file
        merged, n_pres, orphans = inject_custom_blocks(raw_tmpl, disk_blocks)
        for oname, ocontent in orphans.items():
            all_orphans.append((rel_label, oname, ocontent))

        new_body_hash = compute_body_hash(raw_tmpl)
        final_content = stamp_text(merged, new_body_hash)
        if not a.dry_run:
            dest.write_text(final_content, encoding="utf-8")
        updated.append((dest, n_pres))
        prefix = "DRY RUN " if a.dry_run else ""
        print(f"{prefix}UPDATED {rel_label} (preserved {n_pres} block(s))")

    # Check for inactive convention skills that have custom blocks
    for skill_name in CONVENTION_SKILLS:
        skill_file = skills_dir / skill_name / "SKILL.md"
        if skill_file.is_file() and skill_file not in active_dest_paths:
            content = skill_file.read_text(encoding="utf-8")
            blocks = extract_custom_blocks(content, rel_posix(skill_file, root))
            for bname, bcontent in blocks.items():
                if bcontent.strip():
                    all_orphans.append((rel_posix(skill_file, root), bname, bcontent))

    if not a.dry_run:
        append_orphans(all_orphans, root)

    for w in all_warnings:
        print(w)

    missing = [s for s in PROCESS_SKILLS if not (skills_dir / s / "SKILL.md").exists()]
    if missing:
        print("NOTE  Process skills not found in the skills dir: " + ", ".join(missing))
    print("If your agent does not read .agents/skills, run: npx @v1006/build-forge link")

    print("\nRender summary:")
    if created:
        print("  created:")
        for c in created:
            print(f"    - {rel_posix(c, root)}")
    else:
        print("  created:   none")

    if updated:
        print("  updated:")
        for u, n_blk in updated:
            print(f"    - {rel_posix(u, root)} (preserved {n_blk} block(s))")
    else:
        print("  updated:   none")

    if refused:
        print("  refused:")
        for r, reason in refused:
            print(f"    - {rel_posix(r, root)} ({reason})")
    else:
        print("  refused:   none")

    if skipped:
        print("  skipped:")
        for s, reason in skipped:
            print(f"    - {rel_posix(s, root)} ({reason})")
    else:
        print("  skipped:   none")


if __name__ == "__main__":
    main()
