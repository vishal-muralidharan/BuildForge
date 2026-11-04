"""UI component analyzer: components, props, variants, and state primitives."""
import re
from pathlib import Path
from .common import find_files, read_source_file

STATE_PRIMITIVES = {
    "Skeleton", "Spinner", "Loading", "Empty", "Error",
    "Toast", "Alert", "Modal", "Sheet"
}


def detect(root: Path, profile: dict) -> bool:
    """Return True if UI components exist in project."""
    files = find_files(root, {".tsx", ".jsx"}, max_files=5)
    return bool(files)


def extract(root: Path, profile: dict) -> dict:
    """Extract component catalog, state primitives, and select usages."""
    facts = []
    candidates = []
    sources = set()

    state_primitives_found = []
    select_count = 0
    components = []

    # Get component dirs from profile if available, else standard dirs
    comp_dirs = profile.get("design", {}).get("component_dirs", ["src/components", "components", "src/ui", "ui"])
    if isinstance(comp_dirs, str):
        comp_dirs = [comp_dirs]

    ui_files = find_files(root, {".tsx", ".jsx", ".vue", ".svelte"})
    for rel_path in ui_files:
        content = read_source_file(root, rel_path)
        if not content:
            continue
        lines = content.split("\n")
        has_ui = False

        # Check if in component dirs
        comp_dir_prefixes = []
        for d in comp_dirs:
            cleaned = d
            if cleaned.endswith("/*"):
                cleaned = cleaned[:-2]
            elif cleaned.endswith("/") or cleaned.endswith("*"):
                cleaned = cleaned[:-1]
            comp_dir_prefixes.append(cleaned)
        is_comp_dir = any(rel_path.startswith(pfx) for pfx in comp_dir_prefixes) or len(comp_dirs) == 0

        # Check native <select> usages
        for idx, line in enumerate(lines, start=1):
            if "<select" in line and "select" not in rel_path.lower():
                select_count += 1
                has_ui = True

            # Check role="alert"
            if 'role="alert"' in line or "role='alert'" in line:
                state_primitives_found.append({
                    "name": "role='alert'",
                    "evidence": f"{rel_path}:{idx}"
                })
                has_ui = True

        # Check for state primitives by component name
        base_name = Path(rel_path).stem
        for prim in STATE_PRIMITIVES:
            if prim.lower() in base_name.lower():
                state_primitives_found.append({
                    "name": prim,
                    "evidence": f"{rel_path}:1"
                })
                has_ui = True

        # Extract exported component info
        if is_comp_dir:
            for idx, line in enumerate(lines, start=1):
                # match: export function ComponentName or export const ComponentName
                comp_match = re.search(r"export\s+(?:default\s+)?(?:function|const)\s+([A-Z][A-Za-z0-9]+)", line)
                if comp_match:
                    cname = comp_match.group(1)
                    # Extract props hints
                    props_type = "unknown"
                    prop_match = re.search(rf"(?:interface|type)\s+({cname}Props|Props)\b", content)
                    if prop_match:
                        props_type = prop_match.group(1)

                    # Extract variant hints: variant = 'primary' | 'secondary'
                    variants = []
                    v_matches = re.findall(r"(?:variant|size|intent)\s*[:=]\s*['\"]([A-Za-z0-9_-]+)['\"]", content)
                    for vm in set(v_matches):
                        variants.append(vm)

                    comp_fact = {
                        "name": f"Component: {cname}",
                        "evidence": f"{rel_path}:{idx}",
                        "confidence": "high",
                        "props": props_type,
                        "variants": sorted(variants)[:6],
                        "details": [
                            f"File: {rel_path}",
                            f"Props Type: {props_type}",
                            f"Variants: {', '.join(sorted(variants)[:6]) or 'none'}"
                        ]
                    }
                    components.append(comp_fact)
                    facts.append(comp_fact)
                    has_ui = True

        if has_ui:
            sources.add(rel_path)

    # Sort deterministically
    components.sort(key=lambda x: (x["name"], x["evidence"]))
    state_primitives_found.sort(key=lambda x: (x["name"], x["evidence"]))

    if select_count > 0:
        candidates.append({
            "id": "ui-native-select",
            "area": "ui",
            "rule": "Avoid raw HTML <select>; use the design system Select primitive.",
            "evidence": f"Found {select_count} raw <select> usages across UI code."
        })

    return {
        "facts": sorted(facts, key=lambda x: (x["name"], x["evidence"])),
        "components": components,
        "state_primitives": state_primitives_found,
        "native_select_count": select_count,
        "candidates": candidates,
        "sources": sorted(sources),
        "unsupported": []
    }


def render(data: dict) -> str:
    """Render extracted UI components and state primitives to markdown format."""
    lines = ["# UI Component Blueprint\n"]
    lines.append("Extracted UI components, props contracts, variants, and state primitives.\n")

    lines.append("## Component catalog\n")
    if not data["components"]:
        lines.append("- No exported UI components detected in component directories.\n")
    else:
        for c in data["components"]:
            lines.append(f"- **{c['name']}**")
            lines.append(f"  - Evidence: `{c['evidence']}` (confidence: {c['confidence']})")
            lines.append(f"  - Props: `{c['props']}`")
            lines.append(f"  - Variants: {', '.join(f'`{v}`' for v in c['variants']) or 'none'}")

    lines.append("\n## State primitives and alerts\n")
    if not data["state_primitives"]:
        lines.append("- No specialized state primitives detected.\n")
    else:
        for sp in data["state_primitives"]:
            lines.append(f"- Primitive: `{sp['name']}` (`{sp['evidence']}`)")

    if data.get("native_select_count", 0) > 0:
        lines.append(f"\n- Native `<select>` usages: {data['native_select_count']} instances outside Select primitive.")

    return "\n".join(lines).strip() + "\n"
