#!/usr/bin/env python3
"""Manage third party references and external skills for Build Forge.

Dependency-free standard library script with PyYAML.
Subcommands:
  fetch       Fetch repository or directory for inspection
  vet         Security scan on a skill directory
  add         Install and pin an approved reference
  list        List configured references
  verify      Verify installed reference files against lock file
  update      Preview or apply updates for an installed reference
  remove      Delete an installed reference and its configuration
  restore     Restore vendor files at pinned commits from lock
  due         List references due for a specific pipeline stage
  migrate     Migrate external_references from project profile
"""
import os
import re
import sys
import shutil
import tempfile
import argparse
import json
import hashlib
import fnmatch
import subprocess
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

VALID_CATEGORIES = {
    "backend",
    "database",
    "security",
    "deploy",
    "hosting",
    "browser",
    "performance",
    "accessibility",
    "other"
}

VALID_STAGES = {"audit", "build", "verify", "deploy", "report"}
VALID_MODES = {"advisory", "gate"}
VALID_ACTIVATIONS = {"pipeline-only", "native"}
VALID_STATUSES = {"declared", "installed", "rejected"}

VET_SCRIPT_EXTENSIONS = {".sh", ".bash", ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".php", ".bin", ".exe"}
VET_NETWORK_PATTERNS = re.compile(r"\b(curl|wget|fetch|axios|urllib|requests|http\.client|socket|aiohttp)\b", re.IGNORECASE)
VET_EXEC_PATTERNS = re.compile(r"\b(subprocess|os\.system|exec|spawn|eval|popen|child_process)\b", re.IGNORECASE)
VET_CREDENTIAL_PATTERNS = re.compile(r"\b(api_key|token|secret|password|private_key|auth_token|bearer|npm_token|github_token)\b", re.IGNORECASE)
VET_PATH_ESCAPE_PATTERNS = re.compile(r"(/etc/|/usr/|/tmp/|~/\.ssh|~/\.bashrc|\.\./\.\.)")
VET_PUBLISH_PATTERNS = re.compile(r"\b(git\s+push|npm\s+publish|twine\s+upload|docker\s+push)\b", re.IGNORECASE)
VET_ZERO_WIDTH_CHARS = re.compile(r"[\u200b\u200c\u200d\ufeff\u202a-\u202e]")
VET_HTML_COMMENTS = re.compile(r"<!--[\s\S]*?-->")
VET_INJECTION_PHRASES = [
    "ignore previous instructions",
    "disregard all previous instructions",
    "disregard",
    "do not tell the user",
    "system prompt",
    "override instructions",
    "bypass security",
    "hidden instruction"
]


def hash_file(file_path):
    with open(file_path, "rb") as f:
        content = f.read().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def compute_dir_hashes(dir_path):
    hashes = {}
    for root, _, files in os.walk(dir_path):
        for f in sorted(files):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, dir_path).replace("\\", "/")
            hashes[rel] = hash_file(full)
    return hashes


def get_paths(root=None):
    root_path = Path(root or ".").resolve()
    agents_dir = root_path / ".agents"
    yaml_path = agents_dir / "references.yaml"
    lock_path = agents_dir / "references.lock.json"
    return root_path, yaml_path, lock_path


def load_references(yaml_path):
    if not yaml_path.is_file():
        return {"schema_version": 1, "vendor_in_git": False, "references": []}
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("schema_version", 1)
    data.setdefault("vendor_in_git", False)
    data.setdefault("references", [])
    return data


def save_references(yaml_path, data):
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)


def load_lock(lock_path):
    if not lock_path.is_file():
        return {}
    with open(lock_path, "r", encoding="utf-8") as f:
        return json.load(f) or {}


def save_lock(lock_path, lock_data):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(lock_data, f, indent=2, sort_keys=True)
        f.write("\n")


# -------------------------------------------------------------------------
# Subcommand: fetch
# -------------------------------------------------------------------------
def git_clone_or_fetch(url, ref, target_dir):
    """Clone or fetch a repository at a given ref (branch, tag, or commit SHA)."""
    os.makedirs(target_dir, exist_ok=True)
    clone_cmd = ["git", "clone", "--depth", "1"]
    if ref and ref != "HEAD":
        clone_cmd += ["--branch", ref]
    clone_cmd += [url, str(target_dir)]
    res = subprocess.run(clone_cmd, capture_output=True, text=True)
    if res.returncode == 0:
        return res
    # If clone failed (e.g. ref is a commit SHA), use git init + fetch + checkout
    shutil.rmtree(target_dir, ignore_errors=True)
    os.makedirs(target_dir, exist_ok=True)
    subprocess.run(["git", "init"], cwd=target_dir, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", url], cwd=target_dir, capture_output=True)
    fetch_target = ref if (ref and ref != "HEAD") else "HEAD"
    res_fetch = subprocess.run(["git", "fetch", "--depth", "1", "origin", fetch_target], cwd=target_dir, capture_output=True, text=True)
    if res_fetch.returncode == 0:
        res_co = subprocess.run(["git", "checkout", "FETCH_HEAD"], cwd=target_dir, capture_output=True, text=True)
        if res_co.returncode == 0:
            return subprocess.CompletedProcess(args=clone_cmd, returncode=0, stdout=res_fetch.stdout, stderr="")
    return res


def cmd_fetch(args):
    url = args.url
    subpath = args.subpath or ""
    ref = args.ref or "HEAD"
    out_dir = args.out

    temp_created = False
    if not out_dir:
        target_dir = tempfile.mkdtemp(prefix="bf-fetch-")
        temp_created = True
    else:
        target_dir = os.path.abspath(out_dir)
        os.makedirs(target_dir, exist_ok=True)

    try:
        # Check if local directory or git url
        is_local = os.path.isdir(url)
        commit_sha = "local"
        if is_local:
            src = os.path.abspath(url)
            for item in os.listdir(src):
                s_item = os.path.join(src, item)
                d_item = os.path.join(target_dir, item)
                if os.path.isdir(s_item):
                    shutil.copytree(s_item, d_item, dirs_exist_ok=True)
                else:
                    shutil.copy2(s_item, d_item)
            try:
                res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True)
                if res.returncode == 0:
                    commit_sha = res.stdout.strip()
            except Exception:
                pass
        else:
            # Git clone
            res = git_clone_or_fetch(url, ref, target_dir)
            if res.returncode != 0:
                sys.exit(f"Fetch failed: git clone error:\n{res.stderr}")
            res_rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=target_dir, capture_output=True, text=True)
            if res_rev.returncode == 0:
                commit_sha = res_rev.stdout.strip()

        # Locate inspect target
        inspect_root = os.path.join(target_dir, subpath) if subpath else target_dir
        if not os.path.exists(inspect_root):
            sys.exit(f"Subpath '{subpath}' does not exist in the fetched repository.")

        # Find license
        license_info = "Not found"
        for name in ["LICENSE", "LICENSE.md", "LICENSE.txt"]:
            lpath = os.path.join(inspect_root, name)
            if os.path.isfile(lpath):
                with open(lpath, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                license_info = f"{name} ({first_line[:60]})"
                break

        # Find skills
        skills_found = []
        for root, dirs, files in os.walk(inspect_root):
            if "SKILL.md" in files:
                skill_dir = root
                skill_md_path = os.path.join(skill_dir, "SKILL.md")
                name = os.path.basename(skill_dir)
                desc = "No description"
                try:
                    with open(skill_md_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            fm = yaml.safe_load(parts[1]) or {}
                            name = fm.get("name", name)
                            desc = fm.get("description", desc)
                except Exception:
                    pass

                skill_files = []
                for sroot, _, sfiles in os.walk(skill_dir):
                    for sf in sfiles:
                        skill_files.append(os.path.relpath(os.path.join(sroot, sf), skill_dir).replace("\\", "/"))
                skills_found.append({
                    "name": name,
                    "description": desc,
                    "path": os.path.relpath(skill_dir, inspect_root).replace("\\", "/"),
                    "files": sorted(skill_files)
                })

        print(f"Fetched repository: {url}")
        print(f"Commit SHA: {commit_sha}")
        print(f"License: {license_info}")
        print(f"Skills discovered: {len(skills_found)}")
        for s in skills_found:
            print(f"\n  Skill: {s['name']}")
            print(f"  Description: {s['description']}")
            print(f"  Path in repo: {s['path']}")
            print(f"  Files ({len(s['files'])}): {', '.join(s['files'][:10])}" + ("..." if len(s['files']) > 10 else ""))

    finally:
        if temp_created and not out_dir:
            shutil.rmtree(target_dir, ignore_errors=True)


# -------------------------------------------------------------------------
# Subcommand: vet
# -------------------------------------------------------------------------
def cmd_vet(args):
    scan_dir = os.path.abspath(args.dir)
    if not os.path.isdir(scan_dir):
        sys.exit(f"Vetting directory '{scan_dir}' not found.")

    findings = []

    for root, dirs, files in os.walk(scan_dir):
        # Ignore .git
        if ".git" in dirs:
            dirs.remove(".git")

        for f in files:
            file_path = os.path.join(root, f)
            rel_path = os.path.relpath(file_path, scan_dir).replace("\\", "/")
            _, ext = os.path.splitext(f)

            # 1. Scripts present
            if ext in VET_SCRIPT_EXTENSIONS or "scripts" in Path(rel_path).parts:
                findings.append(("HIGH", rel_path, None, f"Executable script file present: {rel_path}"))

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
            except Exception as e:
                findings.append(("MEDIUM", rel_path, None, f"Could not read file: {e}"))
                continue

            for line_idx, line in enumerate(lines, 1):
                # 2. Network calls
                net_match = VET_NETWORK_PATTERNS.search(line)
                if net_match:
                    findings.append(("HIGH", rel_path, line_idx, f"Network call pattern detected: '{net_match.group(0)}'"))

                # 3. Shell execution
                exec_match = VET_EXEC_PATTERNS.search(line)
                if exec_match:
                    findings.append(("HIGH", rel_path, line_idx, f"Shell/code execution pattern detected: '{exec_match.group(0)}'"))

                # 4. Credential or token identifiers
                cred_match = VET_CREDENTIAL_PATTERNS.search(line)
                if cred_match:
                    findings.append(("HIGH", rel_path, line_idx, f"Credential/token keyword detected: '{cred_match.group(0)}'"))

                # 5. Writes outside project boundary
                path_match = VET_PATH_ESCAPE_PATTERNS.search(line)
                if path_match:
                    findings.append(("HIGH", rel_path, line_idx, f"Path referencing outside project boundary: '{path_match.group(0)}'"))

                # 6. Remote publishing commands
                pub_match = VET_PUBLISH_PATTERNS.search(line)
                if pub_match:
                    findings.append(("HIGH", rel_path, line_idx, f"Publishing/pushing command detected: '{pub_match.group(0)}'"))

                # 7. Invisible / bidirectional unicode
                if VET_ZERO_WIDTH_CHARS.search(line):
                    findings.append(("HIGH", rel_path, line_idx, "Zero-width or bidirectional Unicode character discovered."))

                # 8. HTML comments
                if VET_HTML_COMMENTS.search(line):
                    findings.append(("MEDIUM", rel_path, line_idx, "HTML comment present in text."))

                # 9. Instruction override / prompt injection phrases
                l_lower = line.lower()
                for phrase in VET_INJECTION_PHRASES:
                    if phrase in l_lower:
                        findings.append(("HIGH", rel_path, line_idx, f"Suspicious instruction override phrase detected: '{phrase}'"))

    print(f"=== VETTING REPORT FOR {scan_dir} ===")
    high_findings = [f for f in findings if f[0] == "HIGH"]
    med_findings = [f for f in findings if f[0] == "MEDIUM"]

    if not findings:
        print("✓ No security findings detected.")
        print("\nNote: A clean scan is not proof of safety. Verify all third party text by hand.")
        sys.exit(0)

    for severity, file_p, line_n, msg in findings:
        loc = f"{file_p}:{line_n}" if line_n else file_p
        print(f"[{severity}] {loc} - {msg}")

    print(f"\nSummary: {len(high_findings)} HIGH, {len(med_findings)} MEDIUM finding(s).")
    print("Note: A clean scan is not proof of safety. Never execute unverified code.")

    if high_findings:
        sys.exit(1)
    sys.exit(0)


# -------------------------------------------------------------------------
# Subcommand: add
# -------------------------------------------------------------------------
def cmd_add(args):
    if not args.approved:
        sys.exit("Error: Adding a reference requires explicit user approval flag --approved.")

    name = args.name
    if not name or not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        sys.exit(f"Error: Reference name '{name}' must be kebab-case (lowercase letters, numbers, hyphens).")

    root_path, yaml_path, lock_path = get_paths(args.root)
    ref_data = load_references(yaml_path)

    for r in ref_data.get("references", []):
        if r.get("name") == name:
            sys.exit(f"Error: Reference with name '{name}' already exists.")

    category = args.category
    if category not in VALID_CATEGORIES:
        sys.exit(f"Error: Category '{category}' must be one of: {sorted(VALID_CATEGORIES)}")

    used_by = [s.strip() for s in (args.used_by or "").split(",") if s.strip()]
    invalid_stages = set(used_by) - VALID_STAGES
    if invalid_stages or not used_by:
        sys.exit(f"Error: --used-by must contain valid stages: {sorted(VALID_STAGES)}")

    mode = args.mode or "advisory"
    if mode not in VALID_MODES:
        sys.exit(f"Error: Mode '{mode}' must be 'advisory' or 'gate'.")

    activation = args.activation or "pipeline-only"
    if activation not in VALID_ACTIVATIONS:
        sys.exit(f"Error: Activation '{activation}' must be 'pipeline-only' or 'native'.")

    source_input = args.source
    source_type = args.source_type or ("local" if os.path.exists(source_input) else "git")
    subpath = args.subpath or ""
    ref = args.ref or "HEAD"

    # Resolve target directory
    if activation == "native":
        target_dir = root_path / ".agents" / "skills" / name
    else:
        target_dir = root_path / ".agents" / "vendor" / name

    if target_dir.exists():
        sys.exit(f"Error: Target installation folder '{target_dir}' already exists.")

    pinned_commit = "unknown"
    license_text = "Unknown"

    with tempfile.TemporaryDirectory() as tmp_clone:
        if source_type == "local" or os.path.isdir(source_input):
            src_path = Path(source_input).resolve()
            pinned_commit = "local"
            try:
                res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src_path, capture_output=True, text=True)
                if res.returncode == 0:
                    pinned_commit = res.stdout.strip()
            except Exception:
                pass
            skill_source = src_path / subpath if subpath else src_path
        else:
            res = git_clone_or_fetch(source_input, ref, tmp_clone)
            if res.returncode != 0:
                sys.exit(f"Clone failed during add: {res.stderr}")
            res_rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_clone, capture_output=True, text=True)
            if res_rev.returncode == 0:
                pinned_commit = res_rev.stdout.strip()
            skill_source = Path(tmp_clone) / subpath if subpath else Path(tmp_clone)

        if not skill_source.is_dir():
            sys.exit(f"Skill source path '{skill_source}' does not exist or is not a directory.")

        # Copy into destination
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_source, target_dir)

    # Compute hashes and write to lock file
    rel_path_from_root = target_dir.relative_to(root_path).as_posix()
    dir_hashes = compute_dir_hashes(target_dir)

    lock_data = load_lock(lock_path)
    lock_data[name] = {
        "commit": pinned_commit,
        "path": rel_path_from_root,
        "files": dir_hashes
    }
    save_lock(lock_path, lock_data)

    triggers = {
        "paths": [p.strip() for p in (args.paths or "").split(",") if p.strip()],
        "keywords": [k.strip() for k in (args.keywords or "").split(",") if k.strip()]
    }

    new_entry = {
        "name": name,
        "kind": "skill",
        "category": category,
        "purpose": args.purpose or "",
        "source": {
            "type": source_type,
            "url": source_input,
            "subpath": subpath,
            "ref": ref
        },
        "pinned_commit": pinned_commit,
        "license": license_text,
        "activation": activation,
        "allow_scripts": bool(args.allow_scripts),
        "used_by": used_by,
        "triggers": triggers,
        "mode": mode,
        "status": "installed",
        "path": rel_path_from_root,
        "approved": True
    }

    ref_data["references"].append(new_entry)
    save_references(yaml_path, ref_data)

    print(f"Successfully added reference '{name}':")
    print(f"  Target path: {rel_path_from_root}")
    print(f"  Pinned commit: {pinned_commit}")
    print(f"  Mode: {mode}")
    print(f"  Stages: {', '.join(used_by)}")
    print(f"  Allow scripts: {bool(args.allow_scripts)}")


# -------------------------------------------------------------------------
# Subcommand: list
# -------------------------------------------------------------------------
def cmd_list(args):
    root_path, yaml_path, _ = get_paths(args.root)
    ref_data = load_references(yaml_path)
    refs = ref_data.get("references", [])

    if not refs:
        print("No references configured in .agents/references.yaml.")
        return

    print(f"{'NAME':<20} {'CATEGORY':<14} {'STATUS':<10} {'MODE':<10} {'SCRIPTS':<8} {'STAGES':<20} {'PATH'}")
    print("-" * 100)
    for r in refs:
        name = r.get("name", "")
        cat = r.get("category", "")
        status = r.get("status", "")
        mode = r.get("mode", "advisory")
        scripts = "yes" if r.get("allow_scripts") else "no"
        stages = ", ".join(r.get("used_by", []))
        path_str = r.get("path", "")
        print(f"{name:<20} {cat:<14} {status:<10} {mode:<10} {scripts:<8} {stages:<20} {path_str}")


# -------------------------------------------------------------------------
# Subcommand: verify
# -------------------------------------------------------------------------
def cmd_verify(args):
    root_path, yaml_path, lock_path = get_paths(args.root)
    ref_data = load_references(yaml_path)
    refs = [r for r in ref_data.get("references", []) if r.get("status") == "installed"]

    if not refs:
        print("No installed references found. Skipping reference verification.")
        sys.exit(0)

    if not lock_path.is_file():
        sys.exit("Error: .agents/references.lock.json not found for installed references.")

    lock_data = load_lock(lock_path)
    failed = False

    for r in refs:
        name = r.get("name")
        ref_lock = lock_data.get(name)
        if not ref_lock:
            print(f"ERROR: Lock entry missing for reference '{name}'.")
            failed = True
            continue

        target_dir = root_path / r.get("path", "")
        if not target_dir.is_dir():
            print(f"ERROR: Installed directory not found for '{name}': {target_dir}")
            failed = True
            continue

        expected_files = ref_lock.get("files", {})
        current_hashes = compute_dir_hashes(target_dir)

        # Check missing or modified
        for rel_f, expected_hash in expected_files.items():
            if rel_f not in current_hashes:
                print(f"ERROR: [{name}] missing file: {rel_f}")
                failed = True
            elif current_hashes[rel_f] != expected_hash:
                print(f"ERROR: [{name}] modified file: {rel_f}")
                failed = True

        # Check extra files
        for rel_f in current_hashes:
            if rel_f not in expected_files:
                print(f"ERROR: [{name}] extra file: {rel_f}")
                failed = True

    if failed:
        sys.exit(1)

    print("Verify ok: All installed third party references match the lock file.")
    sys.exit(0)


# -------------------------------------------------------------------------
# Subcommand: update
# -------------------------------------------------------------------------
def cmd_update(args):
    name = args.name
    root_path, yaml_path, lock_path = get_paths(args.root)
    ref_data = load_references(yaml_path)

    entry = next((r for r in ref_data.get("references", []) if r.get("name") == name), None)
    if not entry:
        sys.exit(f"Error: Reference '{name}' not found in .agents/references.yaml.")

    source_info = entry.get("source", {})
    url = source_info.get("url")
    subpath = source_info.get("subpath", "")
    ref = source_info.get("ref", "HEAD")

    target_dir = root_path / entry.get("path", "")
    if not target_dir.is_dir():
        sys.exit(f"Error: Target path '{target_dir}' does not exist.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        res = git_clone_or_fetch(url, ref, tmp_dir)
        if res.returncode != 0:
            sys.exit(f"Error fetching update: {res.stderr}")

        res_rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_dir, capture_output=True, text=True)
        new_commit = res_rev.stdout.strip() if res_rev.returncode == 0 else "unknown"

        fetched_skill_dir = Path(tmp_dir) / subpath if subpath else Path(tmp_dir)
        old_hashes = compute_dir_hashes(target_dir)
        new_hashes = compute_dir_hashes(fetched_skill_dir)

        added = sorted(set(new_hashes.keys()) - set(old_hashes.keys()))
        removed = sorted(set(old_hashes.keys()) - set(new_hashes.keys()))
        changed = sorted(k for k in set(old_hashes.keys()) & set(new_hashes.keys()) if old_hashes[k] != new_hashes[k])

        print(f"=== UPDATE PREVIEW FOR '{name}' ===")
        print(f"Current commit: {entry.get('pinned_commit')}")
        print(f"Upstream commit: {new_commit}")
        print(f"Changes: {len(added)} added, {len(removed)} removed, {len(changed)} changed.")
        for f in added:
            print(f"  + {f}")
        for f in removed:
            print(f"  - {f}")
        for f in changed:
            print(f"  * {f}")

        # Run vetting on new version
        print("\nRunning vetting scan on updated source...")
        vet_cmd = [sys.executable, __file__, "vet", str(fetched_skill_dir)]
        vet_res = subprocess.run(vet_cmd, capture_output=True, text=True)
        print(vet_res.stdout)

        if not args.approved:
            print("To install this update, re-run with: python3 ... refs.py update <name> --approved")
            return

        # Install update
        shutil.rmtree(target_dir)
        shutil.copytree(fetched_skill_dir, target_dir)

        entry["pinned_commit"] = new_commit
        save_references(yaml_path, ref_data)

        lock_data = load_lock(lock_path)
        lock_data[name] = {
            "commit": new_commit,
            "path": entry.get("path"),
            "files": compute_dir_hashes(target_dir)
        }
        save_lock(lock_path, lock_data)
        print(f"Successfully updated '{name}' to commit {new_commit}.")


# -------------------------------------------------------------------------
# Subcommand: remove
# -------------------------------------------------------------------------
def cmd_remove(args):
    name = args.name
    root_path, yaml_path, lock_path = get_paths(args.root)
    ref_data = load_references(yaml_path)

    entry = next((r for r in ref_data.get("references", []) if r.get("name") == name), None)
    if not entry:
        sys.exit(f"Error: Reference '{name}' not found.")

    if not args.yes:
        confirm = input(f"Are you sure you want to remove reference '{name}'? Type 'yes' to confirm: ")
        if confirm.strip() != "yes":
            print("Removal cancelled.")
            return

    target_dir = root_path / entry.get("path", "")
    if target_dir.exists():
        shutil.rmtree(target_dir)

    ref_data["references"] = [r for r in ref_data["references"] if r.get("name") != name]
    save_references(yaml_path, ref_data)

    lock_data = load_lock(lock_path)
    if name in lock_data:
        del lock_data[name]
        save_lock(lock_path, lock_data)

    print(f"Reference '{name}' and its files have been removed.")


# -------------------------------------------------------------------------
# Subcommand: restore
# -------------------------------------------------------------------------
def cmd_restore(args):
    root_path, yaml_path, lock_path = get_paths(args.root)
    ref_data = load_references(yaml_path)
    lock_data = load_lock(lock_path)

    for entry in ref_data.get("references", []):
        if entry.get("status") != "installed":
            continue

        name = entry.get("name")
        target_dir = root_path / entry.get("path", "")
        pinned_commit = entry.get("pinned_commit")
        source = entry.get("source", {})
        url = source.get("url")
        subpath = source.get("subpath", "")

        print(f"Restoring '{name}' from {url} at commit {pinned_commit}...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            if os.path.isdir(url):
                skill_source = Path(url) / subpath if subpath else Path(url)
            else:
                clone_cmd = ["git", "clone", url, tmp_dir]
                res = subprocess.run(clone_cmd, capture_output=True, text=True)
                if res.returncode != 0:
                    sys.exit(f"Restore failed cloning {url}: {res.stderr}")
                if pinned_commit and pinned_commit != "unknown":
                    subprocess.run(["git", "checkout", pinned_commit], cwd=tmp_dir, capture_output=True, text=True)
                skill_source = Path(tmp_dir) / subpath if subpath else Path(tmp_dir)

            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skill_source, target_dir)

    # Verify after restore
    res_v = subprocess.run([sys.executable, __file__, "verify", "--root", str(root_path)], capture_output=True, text=True)
    if res_v.returncode != 0:
        sys.exit(f"Verification failed after restore:\n{res_v.stderr}")
    print("All references restored and verified successfully.")


# -------------------------------------------------------------------------
# Subcommand: due
# -------------------------------------------------------------------------
def cmd_due(args):
    stage = args.stage
    root_path, yaml_path, _ = get_paths(args.root)
    ref_data = load_references(yaml_path)

    input_paths = [p.replace("\\", "/") for p in (args.paths or [])]
    input_keywords = set(k.lower() for k in (args.keywords or []))

    due_references = []

    for r in ref_data.get("references", []):
        if r.get("status") != "installed" or not r.get("approved"):
            continue

        used_by = r.get("used_by", [])
        if stage not in used_by:
            continue

        triggers = r.get("triggers") or {}
        trig_paths = triggers.get("paths") or []
        trig_keywords = [k.lower() for k in (triggers.get("keywords") or [])]

        # Empty triggers match always
        matched = False
        if not trig_paths and not trig_keywords:
            matched = True
        else:
            # Check path triggers
            if trig_paths and input_paths:
                for inp in input_paths:
                    for pat in trig_paths:
                        if fnmatch.fnmatch(inp, pat):
                            matched = True
                            break
                    if matched:
                        break

            # Check keyword triggers
            if not matched and trig_keywords and input_keywords:
                if any(kw in input_keywords for kw in trig_keywords):
                    matched = True

        if matched:
            rel_path = r.get("path", "")
            skill_md = os.path.join(rel_path, "SKILL.md").replace("\\", "/")
            due_references.append({
                "name": r.get("name"),
                "skill_md": skill_md,
                "mode": r.get("mode", "advisory"),
                "allow_scripts": r.get("allow_scripts", False)
            })

    for d in due_references:
        scripts_info = "true" if d["allow_scripts"] else "false"
        print(f"{d['skill_md']} (mode: {d['mode']}, allow_scripts: {scripts_info})")


# -------------------------------------------------------------------------
# Subcommand: migrate
# -------------------------------------------------------------------------
def cmd_migrate(args):
    root_path, yaml_path, _ = get_paths(args.root)
    profile_path = root_path / ".agents" / "project-profile.yaml"
    if not profile_path.is_file():
        sys.exit(f"Project profile not found at '{profile_path}'.")

    with open(profile_path, "r", encoding="utf-8") as f:
        prof = yaml.safe_load(f) or {}

    old_refs = prof.get("external_references") or []
    if not old_refs:
        print("No external_references in project profile to migrate.")
        return

    ref_data = load_references(yaml_path)
    existing_names = {r.get("name") for r in ref_data.get("references", [])}
    count = 0

    for old in old_refs:
        name = old.get("name")
        if not name or name in existing_names:
            continue
        new_entry = {
            "name": name,
            "kind": "skill",
            "category": "other",
            "purpose": old.get("purpose", ""),
            "source": {
                "type": "git",
                "url": old.get("repo", ""),
                "subpath": "",
                "ref": "HEAD"
            },
            "pinned_commit": "unknown",
            "license": "Unknown",
            "activation": "pipeline-only",
            "allow_scripts": False,
            "used_by": old.get("used_by", ["audit"]),
            "triggers": {"paths": [], "keywords": []},
            "mode": "advisory",
            "status": "declared",
            "path": old.get("path", ""),
            "approved": False
        }
        ref_data["references"].append(new_entry)
        count += 1

    save_references(yaml_path, ref_data)
    print(f"Migrated {count} reference(s) from project profile to .agents/references.yaml.")


# -------------------------------------------------------------------------
# Main CLI dispatcher
# -------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Build Forge references manager")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # fetch
    p_fetch = subparsers.add_parser("fetch")
    p_fetch.add_argument("url")
    p_fetch.add_argument("--subpath", default="")
    p_fetch.add_argument("--ref", default="HEAD")
    p_fetch.add_argument("--out", default=None)

    # vet
    p_vet = subparsers.add_parser("vet")
    p_vet.add_argument("dir")

    # add
    p_add = subparsers.add_parser("add")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--source", required=True)
    p_add.add_argument("--source-type", default="git")
    p_add.add_argument("--subpath", default="")
    p_add.add_argument("--ref", default="HEAD")
    p_add.add_argument("--category", required=True)
    p_add.add_argument("--purpose", required=True)
    p_add.add_argument("--used-by", required=True)
    p_add.add_argument("--paths", default="")
    p_add.add_argument("--keywords", default="")
    p_add.add_argument("--mode", default="advisory")
    p_add.add_argument("--activation", default="pipeline-only")
    p_add.add_argument("--allow-scripts", action="store_true")
    p_add.add_argument("--approved", action="store_true")
    p_add.add_argument("--root", default=".")

    # list
    p_list = subparsers.add_parser("list")
    p_list.add_argument("--root", default=".")

    # verify
    p_ver = subparsers.add_parser("verify")
    p_ver.add_argument("--root", default=".")

    # update
    p_upd = subparsers.add_parser("update")
    p_upd.add_argument("name")
    p_upd.add_argument("--approved", action="store_true")
    p_upd.add_argument("--root", default=".")

    # remove
    p_rem = subparsers.add_parser("remove")
    p_rem.add_argument("name")
    p_rem.add_argument("--yes", action="store_true")
    p_rem.add_argument("--root", default=".")

    # restore
    p_res = subparsers.add_parser("restore")
    p_res.add_argument("--root", default=".")

    # due
    p_due = subparsers.add_parser("due")
    p_due.add_argument("--stage", required=True)
    p_due.add_argument("--paths", nargs="*", default=[])
    p_due.add_argument("--keywords", nargs="*", default=[])
    p_due.add_argument("--root", default=".")

    # migrate
    p_mig = subparsers.add_parser("migrate")
    p_mig.add_argument("--root", default=".")

    args = parser.parse_args()

    handlers = {
        "fetch": cmd_fetch,
        "vet": cmd_vet,
        "add": cmd_add,
        "list": cmd_list,
        "verify": cmd_verify,
        "update": cmd_update,
        "remove": cmd_remove,
        "restore": cmd_restore,
        "due": cmd_due,
        "migrate": cmd_migrate
    }

    handlers[args.subcommand](args)


if __name__ == "__main__":
    main()

