#!/usr/bin/env python3
"""Detect drift between the project profile and the repo.

Usage: python check_sync.py --profile PATH [--root REPO_ROOT]

Checks:
  1. Layer paths and referenced files exist.
  2. Folders with files that no layer covers.
  3. Commands match the package.json scripts.
  4. Skills named in AGENTS.md exist in the skills folder.
  5. Recent commit scopes are listed in git.scopes.
  6. Installed external references exist on disk.
  7. Generated files have no edits outside custom blocks.
  8. Custom blocks do not exceed line limits.
  9. Orphan custom blocks in .agents/custom-orphans.md.

Exit 1 on errors. Warnings are advice. Needs PyYAML (pip install pyyaml).
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

IGNORE = {"node_modules", "dist", "build", ".git", ".next", ".nuxt", "coverage", ".venv",
          "venv", "__pycache__", ".turbo", ".vercel", ".netlify", "target", "out"}

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


def g(d, path, default=None):
    cur = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur if cur not in (None, "") else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    prof = yaml.safe_load(Path(a.profile).read_text()) or {}
    errors, warnings = [], []

    # 1. Paths exist
    layers = [l.get("path", "").rstrip("/") for l in g(prof, "structure.layers", []) or []]
    for p in layers:
        if p and not (root / p).exists():
            errors.append(f"layer path not found: {p}")
    for field in ("design.tokens_file", "design.enforced_by", "data.schema_source"):
        v = g(prof, field)
        if v and ("/" in v or "." in v) and not (root / v).exists():
            errors.append(f"{field} not found: {v}")
    for d in g(prof, "design.component_dirs", []) or []:
        if not (root / d).exists():
            errors.append(f"design.component_dirs not found: {d}")

    # 2. Uncovered folders
    roots = sorted({p.split("/")[0] for p in layers if p})
    for r in roots:
        base = root / r
        if not base.is_dir():
            continue
        for d in sorted(x for x in base.rglob("*") if x.is_dir()):
            rel = d.relative_to(root)
            if any(part in IGNORE for part in rel.parts) or len(rel.parts) > 4:
                continue
            if not any(f.is_file() for f in d.iterdir()):
                continue
            rp = rel.as_posix()
            covered = any(rp == l or rp.startswith(l + "/") or l.startswith(rp + "/") for l in layers)
            if not covered:
                warnings.append(f"folder has files but no layer in the profile: {rp}")

    # 3. Commands vs package.json
    pkg = root / "package.json"
    if pkg.exists():
        try:
            scripts = json.loads(pkg.read_text()).get("scripts", {})
        except Exception:
            scripts = {}
            warnings.append("package.json could not be parsed")
        for key, cmd in (prof.get("commands") or {}).items():
            if not cmd or key in ("install", "test_single"):
                continue
            m = re.match(r"^(?:npm|pnpm|yarn|bun)(?: run)? ([\w:-]+)", cmd)
            if m:
                name = m.group(1)
                if name in ("install", "ci", "add", "i"):
                    continue
                if name not in scripts:
                    errors.append(f"commands.{key} runs '{name}' but package.json has no such script")

    # 4. Skills named in AGENTS.md exist
    skills_dir = root / (g(prof, "docs.skills_dir") or ".agents/skills")
    for name in (g(prof, "docs.agents_file", "AGENTS.md"), "AGENTS.generated.md"):
        f = root / name
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            if line.startswith("|") and "`" in line:
                for token in re.findall(r"`([a-z0-9-]+)`", line):
                    if token in {"npm", "npx", "git"}:
                        continue
                    if (skills_dir / token).exists():
                        continue
                    if "skill" in line.lower() or token.count("-") >= 1:
                        if not (skills_dir / token / "SKILL.md").exists():
                            warnings.append(f"{name} names '{token}' but {skills_dir.relative_to(root)}/{token}/SKILL.md is missing")

    # 5. Commit scopes and paths validation
    raw_scopes = g(prof, "git.scopes", []) or []
    scope_names = set()
    for s in raw_scopes:
        if isinstance(s, str):
            scope_names.add(s)
        elif isinstance(s, dict) and s.get("name"):
            sname = str(s["name"])
            scope_names.add(sname)
            paths = s.get("paths") or []
            if paths:
                matched_any = False
                for pat in paths:
                    norm = str(pat).replace("\\", "/").strip().lstrip("./")
                    if (root / norm).exists():
                        matched_any = True
                        break
                    try:
                        if any(root.glob(norm)):
                            matched_any = True
                            break
                    except Exception:
                        pass
                if not matched_any:
                    warnings.append(f"scope '{sname}' has paths {paths} that match no files in the repository")

    if scope_names and (root / ".git").exists():
        try:
            subs = subprocess.run(["git", "-C", str(root), "log", "-n", "50", "--pretty=%s"],
                                  capture_output=True, text=True, timeout=20).stdout.splitlines()
            used = {m.group(1) for s in subs for m in [re.match(r"^\w+\(([^)]+)\)", s)] if m}
            for s in sorted(used - scope_names):
                warnings.append(f"recent commits use scope '{s}' which is not in git.scopes")
        except Exception:
            pass

    # 6. Installed references
    for r in prof.get("external_references") or []:
        if r.get("status") == "installed" and r.get("path") and not (root / r["path"]).exists():
            errors.append(f"installed reference '{r.get('name')}' not found at {r['path']}")

    # 7 & 8. Generated files: check body hashes and custom block limits
    gen_candidates = []
    agents_f = root / (g(prof, "docs.agents_file") or "AGENTS.md")
    if agents_f.is_file():
        gen_candidates.append(agents_f)
    repo_map_f = root / (g(prof, "docs.repo_map") or ".agents/repo-map.md")
    if repo_map_f.is_file():
        gen_candidates.append(repo_map_f)
    for cskill in CONVENTION_SKILLS:
        cf = skills_dir / cskill / "SKILL.md"
        if cf.is_file():
            gen_candidates.append(cf)

    for gf in gen_candidates:
        txt = gf.read_text(encoding="utf-8").replace("\r\n", "\n")
        sm = STAMP_RE.search(txt)
        rel_label = str(gf.relative_to(root))
        if sm:
            stamp_h = sm.group(1)
            clean = STAMP_RE.sub("", txt)
            clean = CUSTOM_BLOCK_RE.sub("", clean)
            body_h = hashlib.sha256(clean.encode("utf-8")).hexdigest()
            if body_h != stamp_h:
                errors.append(f"generated file '{rel_label}' has edits outside custom blocks (run render.py --update or --force)")

        # Check block limits
        total_custom = 0
        for m in CUSTOM_BLOCK_RE.finditer(txt):
            bname = m.group(1)
            bcontent = m.group(2)
            lines = len(bcontent.splitlines())
            total_custom += lines
            if lines > 160:
                errors.append(f"custom block '{bname}' in '{rel_label}' has {lines} lines (> 160; facts belong in blueprints or profile)")
            elif lines > 80:
                warnings.append(f"custom block '{bname}' in '{rel_label}' has {lines} lines (> 80; facts belong in blueprints or profile)")

        if total_custom > 600:
            errors.append(f"file '{rel_label}' has {total_custom} total custom lines (> 600; facts belong in blueprints or profile)")
        elif total_custom > 300:
            warnings.append(f"file '{rel_label}' has {total_custom} total custom lines (> 300; facts belong in blueprints or profile)")

    # 9. Orphan custom blocks
    orphans_f = root / ".agents" / "custom-orphans.md"
    if orphans_f.is_file():
        otxt = orphans_f.read_text(encoding="utf-8")
        if "<!-- BEGIN CUSTOM:" in otxt:
            warnings.append("orphan custom blocks exist in .agents/custom-orphans.md (review and merge or remove)")

    for w in sorted(set(warnings)):
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(set(warnings))} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
