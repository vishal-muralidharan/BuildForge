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
ENFORCED = {"manual", "test", "lint"}
STATUS = {"declared", "installed", "rejected"}
PUSH = {"never", "ask", "allowed"}
MODES = {"existing", "new"}
RULE_KEYS = {"id", "area", "text", "enforced_by", "check"}
CHECK_TYPES = {"forbid", "require_file", "forbid_file", "root_only"}
CHECK_KEYS = {"type", "pattern", "include", "exclude", "path"}
NAMING_KEYS = {"item", "style", "example"}
LAYER_KEYS = {"path", "purpose"}
BP_KEYS = {"from", "layout"}


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

    refs = prof.get("external_references") or []
    names = set()
    for i, r in enumerate(refs):
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
            errors.append(f"capabilities.{cap}.reference '{ref}' is not in external_references")
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
            if not isinstance(chk, dict) or chk.get("type") not in CHECK_TYPES:
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
