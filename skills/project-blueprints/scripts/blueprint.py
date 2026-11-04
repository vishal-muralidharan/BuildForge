#!/usr/bin/env python3
"""Project blueprints extraction, verification, staleness checking, and querying tool."""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# Add script directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    import yaml
except ImportError:
    yaml = None

from analyzers import auth, common, config, data, layout, tokens, ui

GENERATOR_VERSION = "0.2.0"

AREAS = {
    "data": data,
    "tokens": tokens,
    "ui": ui,
    "layout": layout,
    "auth": auth,
    "config": config,
}

CUSTOM_BLOCK_RE = re.compile(
    r"(<!--\s*BEGIN CUSTOM:\s*([a-zA-Z0-9_-]+)\s*-->\n.*?\n<!--\s*END CUSTOM:\s*\2\s*-->)",
    re.DOTALL
)


def load_profile(root: Path) -> dict:
    """Load project profile if available."""
    p_file = root / ".agents" / "project-profile.yaml"
    if p_file.is_file() and yaml:
        try:
            return yaml.safe_load(p_file.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
    return {}


def extract_custom_blocks(text: str) -> dict:
    """Extract custom blocks from text keyed by block name."""
    blocks = {}
    for m in CUSTOM_BLOCK_RE.finditer(text):
        full_block = m.group(1)
        bname = m.group(2)
        blocks[bname] = full_block
    return blocks


def split_into_parts(lines: list, area: str, max_lines: int = 250) -> list:
    """Split generated content lines into parts of at most max_lines."""
    if len(lines) <= max_lines:
        return [(f"{area}.md", lines)]

    parts = []
    part_idx = 1
    for i in range(0, len(lines), max_lines):
        chunk = lines[i: i + max_lines]
        fname = f"{area}.md" if part_idx == 1 else f"{area}-part-{part_idx}.md"
        parts.append((fname, chunk))
        part_idx += 1
    return parts


def cmd_extract(root: Path, selected_areas: list = None) -> int:
    """Run analyzers and write blueprint files."""
    profile = load_profile(root)
    bp_dir = root / ".agents" / "blueprints"
    bp_dir.mkdir(parents=True, exist_ok=True)

    areas_to_run = selected_areas if selected_areas else list(AREAS.keys())

    manifest_sources = {}
    all_candidates = []
    generated_files = []
    unsupported_langs = set()

    for area_name in sorted(areas_to_run):
        if area_name not in AREAS:
            continue
        mod = AREAS[area_name]
        if not mod.detect(root, profile):
            continue

        result = mod.extract(root, profile)
        rendered_content = mod.render(result)

        # Check for secrets before saving
        secret_matches = common.scan_for_secrets(rendered_content)
        if secret_matches:
            print(f"Error: Secret pattern detected in generated {area_name} blueprint: {secret_matches[0]}", file=sys.stderr)
            return 1

        # Preserve existing custom blocks
        target_file = bp_dir / f"{area_name}.md"
        existing_blocks = {}
        if target_file.is_file():
            old_text = target_file.read_text(encoding="utf-8", errors="replace")
            existing_blocks = extract_custom_blocks(old_text)

        # Split generated content into parts if it exceeds budget
        gen_lines = rendered_content.strip().split("\n")
        parts = split_into_parts(gen_lines, area_name, max_lines=250)

        for p_idx, (fname, p_lines) in enumerate(parts):
            p_file = bp_dir / fname
            out_lines = list(p_lines)

            # Contracts custom block belongs on the primary area file
            if p_idx == 0:
                out_lines.append("")
                if "contracts" in existing_blocks:
                    out_lines.append(existing_blocks["contracts"])
                else:
                    out_lines.append("<!-- BEGIN CUSTOM: contracts -->")
                    out_lines.append("<!-- END CUSTOM: contracts -->")

                # Re-attach other existing custom blocks
                for bname, bcontent in existing_blocks.items():
                    if bname != "contracts":
                        out_lines.append("")
                        out_lines.append(bcontent)

            p_file.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
            generated_files.append(fname)

        # Collect source hashes for manifest
        src_hashes = {}
        for src in result.get("sources", []):
            if (root / src).is_file():
                src_hashes[src] = common.hash_file_lf(root, src)
        manifest_sources[area_name] = src_hashes

        # Collect candidates
        for c in result.get("candidates", []):
            all_candidates.append(c)

        for u in result.get("unsupported", []):
            unsupported_langs.add(u)

    # Write candidates.md
    c_file = bp_dir / "candidates.md"
    c_lines = ["# Blueprint Rule Candidates\n"]
    c_lines.append("Proposed candidates from codebase facts. User confirmation required before adding to profile.\n")
    if not all_candidates:
        c_lines.append("- No rule candidates identified.\n")
    else:
        for c in all_candidates:
            c_lines.append(f"- **{c['id']}** ({c['area']}): {c['rule']}")
            c_lines.append(f"  - Evidence: `{c['evidence']}`")
    c_file.write_text("\n".join(c_lines) + "\n", encoding="utf-8")

    # Write index.md (strictly budget <= 60 lines)
    idx_file = bp_dir / "index.md"
    idx_lines = [
        "# Project Blueprints Index\n",
        "Deterministic, verified facts extracted directly from codebase evidence.\n",
        "## Areas\n"
    ]
    for g in sorted(generated_files):
        idx_lines.append(f"- [{g}]({g})")

    idx_lines.append("\n## Generator\n")
    idx_lines.append(f"- Version: `{GENERATOR_VERSION}`")
    idx_lines.append(f"- Analyzers: {', '.join(sorted(areas_to_run))}")

    if unsupported_langs:
        idx_lines.append(f"- Unsupported languages: {', '.join(sorted(unsupported_langs))}")

    idx_file.write_text("\n".join(idx_lines[:58]) + "\n", encoding="utf-8")

    # Write manifest.json
    manifest_data = {
        "generator_version": GENERATOR_VERSION,
        "analyzers": sorted(areas_to_run),
        "areas": manifest_sources
    }
    m_file = bp_dir / "manifest.json"
    m_file.write_text(json.dumps(manifest_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Extracted blueprints to .agents/blueprints/ ({len(generated_files)} files).")
    return 0


def cmd_verify(root: Path) -> int:
    """Verify all evidence entries in generated blueprints match source files."""
    bp_dir = root / ".agents" / "blueprints"
    if not bp_dir.is_dir():
        print("Error: .agents/blueprints/ directory not found.", file=sys.stderr)
        return 1

    ev_pattern = re.compile(r"(?:evidence|Evidence):\s*`([^`:]+):(\d+)`")
    alt_pattern = re.compile(r"\(`([^`:]+):(\d+)`\)")

    failures = []
    checked = 0

    for fpath in sorted(bp_dir.glob("*.md")):
        if fpath.name in ("index.md", "candidates.md"):
            continue
        content = fpath.read_text(encoding="utf-8", errors="replace")
        matches = ev_pattern.findall(content) + alt_pattern.findall(content)

        for rel_src, line_str in matches:
            checked += 1
            src_file = root / rel_src
            if not src_file.is_file():
                failures.append(f"{fpath.name}: source file '{rel_src}' not found.")
                continue

            try:
                line_no = int(line_str)
                s_lines = src_file.read_text(encoding="utf-8", errors="replace").split("\n")
                if line_no < 1 or line_no > len(s_lines) + 5:
                    failures.append(f"{fpath.name}: line {line_no} out of bounds for '{rel_src}' ({len(s_lines)} lines).")
            except Exception as e:
                failures.append(f"{fpath.name}: error reading '{rel_src}': {e}")

    if failures:
        print(f"Blueprint verification failed ({len(failures)} errors):", file=sys.stderr)
        for err in failures[:10]:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"Verified {checked} evidence entries across blueprints. All passed.")
    return 0


def cmd_stale(root: Path, fail_on_stale: bool = False) -> int:
    """Check if any blueprint sources changed since extraction."""
    m_file = root / ".agents" / "blueprints" / "manifest.json"
    if not m_file.is_file():
        print("Blueprints not generated or manifest.json missing.")
        return 1 if fail_on_stale else 0

    try:
        manifest = json.loads(m_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading manifest: {e}", file=sys.stderr)
        return 1

    stale_areas = []
    areas_dict = manifest.get("areas", {})

    for area, src_hashes in sorted(areas_dict.items()):
        area_stale = False
        for src, old_hash in src_hashes.items():
            src_path = root / src
            if not src_path.is_file():
                area_stale = True
                break
            cur_hash = common.hash_file_lf(root, src)
            if cur_hash != old_hash:
                area_stale = True
                break
        if area_stale:
            stale_areas.append(area)

    if stale_areas:
        print(f"Stale blueprint areas: {', '.join(stale_areas)}")
        if fail_on_stale:
            return 1
    else:
        print("All blueprints are up to date.")

    return 0


def cmd_show(root: Path, area: str, paths: list = None, budget: int = 120) -> int:
    """Print blueprint facts relevant to given paths within line budget."""
    bp_file = root / ".agents" / "blueprints" / f"{area}.md"
    if not bp_file.is_file():
        print(f"Blueprint for area '{area}' not found at {bp_file}.")
        return 1

    content = bp_file.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")

    if not paths:
        # Show whole file within budget
        output_lines = lines[:budget]
        print("\n".join(output_lines))
        if len(lines) > budget:
            print(f"\n[Budget limit {budget} reached. Skipped {len(lines) - budget} lines.]")
        return 0

    # Filter lines relevant to paths
    filtered_lines = []
    path_keywords = set()
    for p in paths:
        path_keywords.add(Path(p).stem.lower())
        path_keywords.add(p.lower())

    for line in lines:
        if line.startswith("#"):
            filtered_lines.append(line)
        elif any(kw in line.lower() for kw in path_keywords):
            filtered_lines.append(line)

    if len(filtered_lines) <= 5:
        # Fall back to top budget lines if filtering was too aggressive
        filtered_lines = lines

    output_lines = filtered_lines[:budget]
    print("\n".join(output_lines))
    if len(filtered_lines) > budget:
        print(f"\n[Budget limit {budget} reached. Skipped {len(filtered_lines) - budget} lines.]")
    return 0


def cmd_candidates(root: Path) -> int:
    """Print rule candidates from candidates.md."""
    c_file = root / ".agents" / "blueprints" / "candidates.md"
    if not c_file.is_file():
        print("No candidates.md found. Run extract first.")
        return 1

    print(c_file.read_text(encoding="utf-8", errors="replace").strip())
    return 0


def main():
    parser = argparse.ArgumentParser(description="Build Forge codebase blueprints tool.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # extract
    p_extract = subparsers.add_parser("extract", help="Extract project facts into blueprints.")
    p_extract.add_argument("--areas", default="", help="Comma-separated areas to extract.")
    p_extract.add_argument("--root", default=".", help="Project root directory.")

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify evidence entries.")
    p_verify.add_argument("--root", default=".", help="Project root directory.")

    # stale
    p_stale = subparsers.add_parser("stale", help="Check for stale blueprints.")
    p_stale.add_argument("--fail", action="store_true", help="Exit 1 if any blueprint is stale.")
    p_stale.add_argument("--root", default=".", help="Project root directory.")

    # show
    p_show = subparsers.add_parser("show", help="Show blueprint section.")
    p_show.add_argument("--area", required=True, help="Blueprint area.")
    p_show.add_argument("--paths", default="", help="Comma-separated file paths to filter.")
    p_show.add_argument("--budget", type=int, default=120, help="Line limit budget.")
    p_show.add_argument("--root", default=".", help="Project root directory.")

    # candidates
    p_candidates = subparsers.add_parser("candidates", help="Print rule candidates.")
    p_candidates.add_argument("--root", default=".", help="Project root directory.")

    args = parser.parse_args()
    root = Path(args.root).resolve()

    if args.command == "extract":
        areas = [a.strip() for a in args.areas.split(",") if a.strip()] if args.areas else None
        sys.exit(cmd_extract(root, areas))
    elif args.command == "verify":
        sys.exit(cmd_verify(root))
    elif args.command == "stale":
        sys.exit(cmd_stale(root, args.fail))
    elif args.command == "show":
        paths = [p.strip() for p in args.paths.split(",") if p.strip()] if args.paths else None
        sys.exit(cmd_show(root, args.area, paths, args.budget))
    elif args.command == "candidates":
        sys.exit(cmd_candidates(root))


if __name__ == "__main__":
    main()
