#!/usr/bin/env python3
"""Validate .agents/project-profile.yaml.

Usage: python validate_profile.py --profile PATH [--root REPO_ROOT] [--strict]

Exit 0 when there are no errors. Exit 1 otherwise.
Unresolved "TODO" values are warnings. With --strict they are errors.
Needs PyYAML (pip install pyyaml).
"""
import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

AREAS = {"design", "tokens", "motion", "responsive", "structure", "naming", "data",
         "security", "verify", "git", "docs", "process"}
STAGES = {"audit", "plan", "build", "verify", "deploy", "commit", "docs", "report"}
REF_STAGES = {"audit", "build", "verify", "deploy", "report"}
REF_MODES = {"advisory", "gate"}
REF_ACTIVATIONS = {"pipeline-only", "native"}
REF_CATEGORIES = {"backend", "database", "security", "deploy", "hosting", "browser", "performance", "accessibility", "other"}
ENFORCED = {"manual", "test", "lint", "check"}
STATUS = {"declared", "installed", "rejected"}
PUSH = {"never", "ask", "allowed"}
MODES = {"existing", "new"}
RULE_KEYS = {"id", "area", "text", "enforced_by", "check"}
CHECK_TYPES = {"forbid", "require_file", "forbid_file", "root_only", "no_dual_homed_skills"}
CHECK_KEYS = {"type", "pattern", "include", "exclude", "path"}
NAMING_KEYS = {"item", "style", "example"}
LAYER_KEYS = {"path", "purpose"}
BP_KEYS = {"from", "layout"}
SCOPE_KEYS = {"name", "purpose", "paths"}


def stray(entry, allowed):
    return sorted(str(k) for k in entry if k not in allowed or entry[k] is None)


def get(d, path, default=None):
    cur = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def todos(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from todos(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from todos(v, f"{path}[{i}]")
    elif isinstance(node, str) and node.strip().upper().startswith("TODO"):
        yield path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--root", default=None)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()

    errors, warnings = [], []
    try:
        prof = yaml.safe_load(Path(a.profile).read_text())
    except Exception as e:
        sys.exit(f"ERROR: cannot read profile: {e}")
    if not isinstance(prof, dict):
        sys.exit("ERROR: profile must be a YAML mapping")

    if prof.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    for path in ("project.name", "project.summary", "stack.language", "stack.framework", "stack.package_manager"):
        if not get(prof, path):
            errors.append(f"{path} is required")
    if get(prof, "project.mode") not in MODES:
        errors.append("project.mode must be existing or new")

    cmds = get(prof, "commands", {}) or {}
    if not cmds.get("check") and not all(cmds.get(k) for k in ("lint", "test", "build")):
        errors.append("commands.check is required, or set lint, test and build")
    if "{path}" not in (cmds.get("test_single") or "{path}"):
        warnings.append("commands.test_single should contain {path}")

    layers = get(prof, "structure.layers", [])
    if not layers:
        errors.append("structure.layers needs at least 1 entry")
    for i, l in enumerate(layers or []):
        if not isinstance(l, dict) or not l.get("path") or not l.get("purpose"):
            errors.append(f"structure.layers[{i}] needs path and purpose")
        elif stray(l, LAYER_KEYS):
            errors.append(f"structure.layers[{i}] has unexpected keys {stray(l, LAYER_KEYS)}. Quote values that contain commas.")
    if get(prof, "structure.tests") not in ("colocated", "tests-dir"):
        errors.append("structure.tests must be colocated or tests-dir")

    for i, n in enumerate(prof.get("naming") or []):
        if not isinstance(n, dict) or not all(n.get(k) for k in ("item", "style", "example")):
            errors.append(f"naming[{i}] needs item, style and example")
        elif stray(n, NAMING_KEYS):
            errors.append(f"naming[{i}] has unexpected keys {stray(n, NAMING_KEYS)}. Quote values that contain commas.")

    if get(prof, "design.enabled") and not get(prof, "design.tokens_file"):
        errors.append("design.tokens_file is required when design.enabled is true")
    if get(prof, "responsive.enabled"):
        lo, hi = get(prof, "responsive.min_width", 0), get(prof, "responsive.max_width", 0)
        if not (isinstance(lo, int) and isinstance(hi, int) and 0 < lo < hi):
            errors.append("responsive.min_width must be less than responsive.max_width")

    for i, b in enumerate(get(prof, "responsive.breakpoints", []) or []):
        if not isinstance(b, dict) or not isinstance(b.get("from"), int) or not b.get("layout") or stray(b, BP_KEYS):
            errors.append(f"responsive.breakpoints[{i}] needs an integer from and a layout string. Quote values that contain commas.")

    if get(prof, "git.push") not in PUSH:
        errors.append("git.push must be never, ask or allowed")
    if not get(prof, "git.commit_format"):
        errors.append("git.commit_format is required")

    scopes = get(prof, "git.scopes")
    if scopes is not None:
        if not isinstance(scopes, list):
            errors.append("git.scopes must be a list")
        else:
            seen_scope_names = set()
            for idx, sc in enumerate(scopes):
                if isinstance(sc, str):
                    sname = sc
                    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", sname):
                        errors.append(f"git.scopes[{idx}] '{sname}' must be kebab-case")
                    if sname in seen_scope_names:
                        errors.append(f"duplicate scope name: {sname}")
                    seen_scope_names.add(sname)
                elif isinstance(sc, dict):
                    if stray(sc, SCOPE_KEYS):
                        errors.append(f"git.scopes[{idx}] has unexpected keys {stray(sc, SCOPE_KEYS)}")
                    sname = sc.get("name")
                    if sname is None or not isinstance(sname, str) or not sname.strip():
                        errors.append(f"git.scopes[{idx}].name must be a non-empty string")
                    else:
                        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", sname):
                            errors.append(f"git.scopes[{idx}].name '{sname}' must be kebab-case")
                        if sname in seen_scope_names:
                            errors.append(f"duplicate scope name: {sname}")
                        seen_scope_names.add(sname)

                    purpose = sc.get("purpose")
                    if purpose is not None:
                        if not isinstance(purpose, str):
                            errors.append(f"git.scopes[{idx}].purpose must be a string")
                        elif len(purpose) > 100:
                            errors.append(f"git.scopes[{idx}].purpose exceeds 100 characters ({len(purpose)} chars)")

                    paths = sc.get("paths")
                    if paths is not None:
                        if not isinstance(paths, list):
                            errors.append(f"git.scopes[{idx}].paths must be a list")
                        else:
                            for pidx, pat in enumerate(paths):
                                if not isinstance(pat, str) or not pat.strip():
                                    errors.append(f"git.scopes[{idx}].paths[{pidx}] must be a non-empty string")
                                elif pat.count("[") != pat.count("]") or "\x00" in pat:
                                    errors.append(f"git.scopes[{idx}].paths[{pidx}] '{pat}' is not a valid glob")
                else:
                    errors.append(f"git.scopes[{idx}] must be a string or a mapping")

    names = set()
    root_path = Path(a.root).resolve() if a.root else Path(".").resolve()
    ref_yaml = root_path / ".agents" / "references.yaml"

    if ref_yaml.is_file():
        try:
            rdata = yaml.safe_load(ref_yaml.read_text(encoding="utf-8")) or {}
        except Exception as e:
            errors.append(f"Invalid YAML in .agents/references.yaml: {e}")
            rdata = {}

        if not isinstance(rdata, dict):
            errors.append(".agents/references.yaml must be a mapping")
        else:
            if rdata.get("schema_version") != 1:
                errors.append(".agents/references.yaml schema_version must be 1")
            if not isinstance(rdata.get("vendor_in_git", False), bool):
                errors.append(".agents/references.yaml vendor_in_git must be a boolean")

            ref_entries = rdata.get("references")
            if not isinstance(ref_entries, list):
                errors.append(".agents/references.yaml 'references' must be a list")
            else:
                for idx, entry in enumerate(ref_entries):
                    if not isinstance(entry, dict):
                        errors.append(f"references[{idx}] must be a mapping")
                        continue
                    rname = entry.get("name")
                    if not rname or not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", str(rname)):
                        errors.append(f"references[{idx}].name '{rname}' must be kebab-case")
                    if rname in names:
                        errors.append(f"references[{idx}].name '{rname}' is a duplicate")
                    names.add(rname)

                    if entry.get("kind") != "skill":
                        errors.append(f"references[{idx}].kind must be 'skill'")
                    if entry.get("category") not in REF_CATEGORIES:
                        errors.append(f"references[{idx}].category must be one of {sorted(REF_CATEGORIES)}")
                    if entry.get("status") not in STATUS:
                        errors.append(f"references[{idx}].status must be one of {sorted(STATUS)}")
                    if entry.get("mode") not in REF_MODES:
                        errors.append(f"references[{idx}].mode must be one of {sorted(REF_MODES)}")
                    if entry.get("activation") not in REF_ACTIVATIONS:
                        errors.append(f"references[{idx}].activation must be one of {sorted(REF_ACTIVATIONS)}")

                    used = entry.get("used_by") or []
                    if not isinstance(used, list) or not used or (set(used) - REF_STAGES):
                        errors.append(f"references[{idx}].used_by must list stages from {sorted(REF_STAGES)}")

                    if entry.get("status") == "installed":
                        rpath = entry.get("path")
                        if not rpath:
                            errors.append(f"references[{idx}].path is required when installed")
                        else:
                            norm_path = Path(rpath).as_posix()
                            if not (norm_path.startswith(".agents/vendor/") or norm_path.startswith(".agents/skills/")):
                                errors.append(f"references[{idx}].path '{rpath}' must be inside .agents/vendor or .agents/skills")
                            elif a.root and not (root_path / rpath).exists():
                                errors.append(f"references[{idx}].path not found: {rpath}")
                        if not entry.get("pinned_commit") or entry.get("pinned_commit") == "unknown":
                            errors.append(f"references[{idx}].pinned_commit is required when installed")
                        if entry.get("approved") is not True:
                            errors.append(f"references[{idx}].approved must be true when installed")

    # Backwards compatibility: external_references in profile
    old_refs = prof.get("external_references")
    if old_refs is not None:
        warnings.append("`external_references` in project profile is deprecated. Use .agents/references.yaml instead.")
        if isinstance(old_refs, list):
            for i, r in enumerate(old_refs):
                if not isinstance(r, dict):
                    errors.append(f"external_references[{i}] must be a mapping")
                    continue
                name = r.get("name")
                if not name:
                    errors.append(f"external_references[{i}].name is required")
                names.add(name)
                repo = str(r.get("repo", ""))
                if not (repo.startswith("https://") or repo.startswith("git@")):
                    errors.append(f"external_references[{i}].repo must be an https or git URL")
                if r.get("status") not in STATUS:
                    errors.append(f"external_references[{i}].status must be one of {sorted(STATUS)}")
                bad = set(r.get("used_by") or []) - STAGES
                if bad or not r.get("used_by"):
                    errors.append(f"external_references[{i}].used_by must list stages from {sorted(STAGES)}")
                if r.get("status") == "installed":
                    if not r.get("path"):
                        errors.append(f"external_references[{i}].path is required when installed")
                    elif a.root and not (Path(a.root) / r["path"]).exists():
                        errors.append(f"external_references[{i}].path not found: {r['path']}")

    for cap, cfg in (prof.get("capabilities") or {}).items():
        if not isinstance(cfg, dict):
            errors.append(f"capabilities.{cap} must be a mapping")
            continue
        ref = cfg.get("reference")
        if ref and ref not in names:
            errors.append(f"capabilities.{cap}.reference '{ref}' is not in .agents/references.yaml")
        if cap == "deploy":
            if cfg.get("enabled") and not (cfg.get("command") or cmds.get("deploy")):
                errors.append("capabilities.deploy is enabled but has no command")
            if cfg.get("on_failure", "report") not in ("report", "self-heal"):
                errors.append("capabilities.deploy.on_failure must be report or self-heal")
            ma = cfg.get("max_attempts", 3)
            if not (isinstance(ma, int) and 1 <= ma <= 10):
                errors.append("capabilities.deploy.max_attempts must be an integer from 1 to 10")

    ids = set()
    for i, r in enumerate(prof.get("rules") or []):
        if not isinstance(r, dict):
            errors.append(f"rules[{i}] must be a mapping")
            continue
        rid = r.get("id")
        if not rid:
            errors.append(f"rules[{i}].id is required")
        elif rid in ids:
            errors.append(f"duplicate rule id: {rid}")
        ids.add(rid)
        if r.get("area") not in AREAS:
            errors.append(f"rules[{i}] ({rid}) area must be one of {sorted(AREAS)}")
        if not r.get("text"):
            errors.append(f"rules[{i}] ({rid}) text is required")
        if r.get("enforced_by", "manual") not in ENFORCED:
            errors.append(f"rules[{i}] ({rid}) enforced_by must be one of {sorted(ENFORCED)}")
        if stray(r, RULE_KEYS):
            errors.append(f"rules[{i}] ({rid}) has unexpected keys {stray(r, RULE_KEYS)}. Quote text that contains commas.")
        chk = r.get("check")
        if chk is not None:
            if isinstance(chk, str):
                if chk not in CHECK_TYPES:
                    errors.append(f"rules[{i}] ({rid}) check must be one of {sorted(CHECK_TYPES)}")
            elif not isinstance(chk, dict) or chk.get("type") not in CHECK_TYPES:
                errors.append(f"rules[{i}] ({rid}) check.type must be one of {sorted(CHECK_TYPES)}")
            else:
                bad_keys = sorted(set(chk) - CHECK_KEYS)
                if bad_keys:
                    errors.append(f"rules[{i}] ({rid}) check has unexpected keys {bad_keys}")
                t = chk["type"]
                if t == "forbid":
                    try:
                        re.compile(str(chk.get("pattern", "")))
                    except re.error as e:
                        errors.append(f"rules[{i}] ({rid}) check.pattern is not a valid regex: {e}")
                    if not chk.get("pattern"):
                        errors.append(f"rules[{i}] ({rid}) check.pattern is required for forbid")
                if t in ("forbid", "forbid_file") and not chk.get("include"):
                    errors.append(f"rules[{i}] ({rid}) check.include needs at least 1 glob")
                if t == "require_file" and not chk.get("path"):
                    errors.append(f"rules[{i}] ({rid}) check.path is required for require_file")
                if t == "root_only" and not get(prof, "structure.root_allowed"):
                    errors.append(f"rules[{i}] ({rid}) root_only needs structure.root_allowed")
            if r.get("enforced_by") != "test":
                warnings.append(f"rule {rid} has a check, so enforced_by should be test")
        if r.get("enforced_by") in ("test", "lint") and not get(prof, "design.enforced_by") and r.get("area") in ("design", "tokens"):
            warnings.append(f"rule {rid} claims {r['enforced_by']} enforcement but design.enforced_by is empty")

    for field in ("docs.skills_dir", "docs.agents_file", "docs.repo_map"):
        if not get(prof, field):
            errors.append(f"{field} is required")

    unresolved = list(todos(prof))
    for p in unresolved:
        (errors if a.strict else warnings).append(f"unresolved TODO at {p}")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s), {len(unresolved)} unresolved TODO(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
