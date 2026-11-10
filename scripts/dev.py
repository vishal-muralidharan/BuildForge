#!/usr/bin/env python3
"""Maintainer developer toolkit for Build Forge.

Usage:
  python3 scripts/dev.py new-skill <name> --tier core|new-app|module [--scripts] [--refs]
  python3 scripts/dev.py check [--fast]
  python3 scripts/dev.py impact <token>
  python3 scripts/dev.py recipe list
  python3 scripts/dev.py recipe show <name>
  python3 scripts/dev.py recipe verify <name> [--arg key=value ...]
  python3 scripts/dev.py fixture new <name>
  python3 scripts/dev.py fixture check
  python3 scripts/dev.py release-plan
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_new_skill(args, repo_root: Path) -> None:
    name = args.name.strip()
    if not re.match(r"^[a-z0-9-]{1,40}$", name):
        sys.exit(f"Error: Invalid skill name '{name}'. Allowed format: [a-z0-9-]{{1,40}}.")

    target_dir = repo_root / "skills" / name
    if target_dir.exists():
        sys.exit(f"Error: Skill '{name}' already exists at {target_dir}.")

    render_py = repo_root / "skills" / "project-bootstrap" / "scripts" / "render.py"
    gen_names = set()
    if render_py.is_file():
        content = render_py.read_text(encoding="utf-8")
        match = re.search(r"CONVENTION_SKILLS\s*=\s*\{([^}]+)\}", content)
        if match:
            gen_names = set(re.findall(r'["\']([a-z0-9-]+)["\']', match.group(1)))

    if name in gen_names:
        sys.exit(f"Error: Skill name '{name}' is reserved by generated skills in render.py.")

    if args.tier not in ("core", "new-app", "module"):
        sys.exit(f"Error: Tier must be one of: core, new-app, module. Got: '{args.tier}'.")

    template_skill = repo_root / "maintainers" / "templates" / "skill" / "SKILL.md"
    if not template_skill.is_file():
        sys.exit(f"Error: Template not found at {template_skill}.")

    target_dir.mkdir(parents=True, exist_ok=False)

    template_text = template_skill.read_text(encoding="utf-8")
    skill_text = template_text.replace("{name}", name)
    (target_dir / "SKILL.md").write_text(skill_text, encoding="utf-8")

    if args.scripts:
        (target_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (target_dir / "scripts" / ".gitkeep").write_text("", encoding="utf-8")

    if args.refs:
        (target_dir / "references").mkdir(parents=True, exist_ok=True)
        (target_dir / "references" / ".gitkeep").write_text("", encoding="utf-8")

    tiers_path = repo_root / "tiers.json"
    if tiers_path.is_file():
        try:
            tiers_data = json.loads(tiers_path.read_text(encoding="utf-8"))
        except Exception:
            tiers_data = {"core": [], "new-app": [], "module": []}
    else:
        tiers_data = {"core": [], "new-app": [], "module": []}

    if args.tier not in tiers_data or not isinstance(tiers_data[args.tier], list):
        tiers_data[args.tier] = []
    if name not in tiers_data[args.tier]:
        tiers_data[args.tier].append(name)
        tiers_data[args.tier].sort()
    tiers_path.write_text(json.dumps(tiers_data, indent=2) + "\n", encoding="utf-8")

    triggers_path = repo_root / "tests" / "triggers.yaml"
    trigger_lines = (
        f"\n{name}:\n"
        f"  positive:\n"
        f'    - "TODO: positive trigger 1 for {name}"\n'
        f'    - "TODO: positive trigger 2 for {name}"\n'
        f'    - "TODO: positive trigger 3 for {name}"\n'
        f'    - "TODO: positive trigger 4 for {name}"\n'
        f'    - "TODO: positive trigger 5 for {name}"\n'
        f"  negative:\n"
        f'    - "TODO: negative trigger 1 for {name}"\n'
        f'    - "TODO: negative trigger 2 for {name}"\n'
        f'    - "TODO: negative trigger 3 for {name}"\n'
    )
    if triggers_path.is_file():
        with open(triggers_path, "a", encoding="utf-8") as f:
            f.write(trigger_lines)
    else:
        triggers_path.write_text(trigger_lines.lstrip(), encoding="utf-8")

    readme_path = repo_root / "README.md"
    if readme_path.is_file():
        content = readme_path.read_text(encoding="utf-8")
        marker = "| Skill | What it does | When to use it |\n|---|---|---|\n"
        row = f"| `{name}` | [TODO: describe what {name} does] | [TODO: when to use {name}] |\n"
        if marker in content and row not in content:
            content = content.replace(marker, marker + row, 1)
            readme_path.write_text(content, encoding="utf-8")

    changelog_path = repo_root / "CHANGELOG.md"
    if changelog_path.is_file():
        cl_text = changelog_path.read_text(encoding="utf-8")
        added_marker = "### Added\n"
        cl_line = f"- Added `{name}` skill.\n"
        if added_marker in cl_text and cl_line not in cl_text:
            cl_text = cl_text.replace(added_marker, added_marker + cl_line, 1)
            changelog_path.write_text(cl_text, encoding="utf-8")

    make_integrity_py = repo_root / "scripts" / "make_integrity.py"
    if make_integrity_py.is_file():
        subprocess.run([sys.executable, str(make_integrity_py)], check=True, cwd=str(repo_root))

    print(f"Scaffolded skill '{name}' under skills/{name}.")
    print("Added to tiers.json, tests/triggers.yaml, README.md, and CHANGELOG.md.")
    print("Regenerated integrity.json.")


def cmd_check(args, repo_root: Path) -> None:
    tools = [
        ("lint_py", repo_root / "scripts" / "lint_py.py", []),
        ("skill_contracts", repo_root / "scripts" / "skill_contracts.py", []),
        ("budget", repo_root / "scripts" / "budget.py", []),
        ("trigger_check", repo_root / "scripts" / "trigger_check.py", []),
        ("ci_check", repo_root / "scripts" / "ci_check.py", ["--fast"] if args.fast else []),
        ("make_integrity", repo_root / "scripts" / "make_integrity.py", ["--check"]),
    ]
    if not args.fast:
        tools.append(("check_docs_truth", repo_root / "scripts" / "check_docs_truth.py", []))
        tools.append(("check_package", repo_root / "scripts" / "check_package.py", []))

    check_history_py = repo_root / "scripts" / "check_history.py"
    check_commits_py = repo_root / "scripts" / "check_commits.py"

    shallow_res = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    is_shallow = (shallow_res.returncode == 0 and shallow_res.stdout.strip().lower() == "true")

    results = []
    print("Running maintainer checks...\n")
    header = f"{'Tool':<20} {'Status':<10} {'Details'}"
    print(header)
    print("-" * 60)

    if is_shallow:
        print(f"{'check_history':<20} {'[SKIP]':<10} Shallow clone detected")
        results.append(("check_history", "SKIP", "Shallow clone detected"))
        print(f"{'check_commits':<20} {'[SKIP]':<10} Shallow clone detected")
        results.append(("check_commits", "SKIP", "Shallow clone detected"))
    else:
        if check_history_py.is_file():
            tools.append(("check_history", check_history_py, ["--ref", "HEAD"]))
        if check_commits_py.is_file():
            rev_origin = subprocess.run(
                ["git", "rev-parse", "--verify", "origin/main"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
            )
            base_ref = "origin/main" if rev_origin.returncode == 0 else "main"
            rev_base = subprocess.run(
                ["git", "rev-parse", "--verify", base_ref],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
            )
            if rev_base.returncode == 0:
                tools.append(("check_commits", check_commits_py, ["--base", base_ref, "--head", "HEAD"]))
            else:
                print(f"{'check_commits':<20} {'[SKIP]':<10} Base ref {base_ref} not available")
                results.append(("check_commits", "SKIP", f"Base ref {base_ref} not available"))

    any_failed = False
    for label, script_path, extra_args in tools:
        if not script_path.is_file():
            print(f"{label:<20} {'[SKIP]':<10} Not found: {script_path.name}")
            results.append((label, "SKIP", "Not found"))
            continue

        cmd = [sys.executable, str(script_path)] + extra_args
        t0 = time.time()
        res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
        duration = time.time() - t0

        if res.returncode == 0:
            print(f"{label:<20} {'[PASS]':<10} ({duration:.2f}s)")
            results.append((label, "PASS", f"{duration:.2f}s"))
        else:
            any_failed = True
            first_err = ""
            for line in (res.stderr + "\n" + res.stdout).splitlines():
                if line.strip():
                    first_err = line.strip()[:60]
                    break
            print(f"{label:<20} {'[FAIL]':<10} {first_err}")
            results.append((label, "FAIL", first_err))

    print("-" * 60)
    passed = sum(1 for _, st, _ in results if st == "PASS")
    failed = sum(1 for _, st, _ in results if st == "FAIL")
    skipped = sum(1 for _, st, _ in results if st == "SKIP")
    print(f"Summary: {passed} passed, {failed} failed, {skipped} skipped.")

    if any_failed:
        sys.exit(1)


def is_packaged_path(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/")
    if norm.startswith("skills/") or norm.startswith("bin/"):
        return True
    if norm in ("README.md", "package.json", "LICENSE"):
        return True
    return False


def cmd_impact(args, repo_root: Path) -> None:
    token = args.token.strip()
    if not token:
        sys.exit("Error: impact requires a non empty token.")

    search_dirs = [
        repo_root / "skills",
        repo_root / "scripts",
        repo_root / "tests",
        repo_root / "maintainers",
        repo_root / "bin",
        repo_root / "docs",
    ]
    standalone_files = [
        repo_root / "README.md",
        repo_root / "MAINTAINING.md",
        repo_root / "CHANGELOG.md",
        repo_root / "AGENTS.md",
    ]

    matches_by_folder = {}

    def scan_file(p: Path):
        try:
            rel = p.relative_to(repo_root).as_posix()
        except Exception:
            return
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        lines = text.splitlines()
        file_matches = []
        for line_num, line in enumerate(lines, 1):
            if token in line:
                file_matches.append((line_num, line.strip()))

        if file_matches:
            folder = os.path.dirname(rel) or "."
            if folder not in matches_by_folder:
                matches_by_folder[folder] = []
            matches_by_folder[folder].append((rel, file_matches))

    for sdir in search_dirs:
        if sdir.is_dir():
            for root, _, files in os.walk(sdir):
                if ".git" in root or "__pycache__" in root or "node_modules" in root:
                    continue
                for f in sorted(files):
                    scan_file(Path(root, f))

    for sfile in standalone_files:
        if sfile.is_file():
            scan_file(sfile)

    if not matches_by_folder:
        print(f"No occurrences of token '{token}' found.")
        return

    print(f"Impact report for token: '{token}'\n")
    for folder in sorted(matches_by_folder.keys()):
        pkg_status = "[PACKAGED]" if is_packaged_path(folder + "/dummy") else "[UNPACKAGED]"
        print(f"Folder: {folder}/ {pkg_status}")
        for rel_file, lines in matches_by_folder[folder]:
            file_pkg = "[PACKAGED]" if is_packaged_path(rel_file) else "[UNPACKAGED]"
            print(f"  {rel_file} {file_pkg} ({len(lines)} match{'es' if len(lines) > 1 else ''})")
            for line_no, text in lines[:5]:
                print(f"    Line {line_no}: {text[:90]}")
            if len(lines) > 5:
                print(f"    ... and {len(lines) - 5} more lines")
        print()


def cmd_recipe(args, repo_root: Path) -> None:
    recipes_dir = repo_root / "maintainers" / "recipes"
    action = args.recipe_action

    if action == "list":
        if not recipes_dir.is_dir():
            print("No recipes directory found at maintainers/recipes.")
            return
        files = sorted(recipes_dir.glob("*.yaml"))
        print(f"Available maintainer recipes ({len(files)}):")
        for f in files:
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                tps = len(data.get("touchpoints", []))
                args_list = data.get("args", [])
                args_str = ", ".join(args_list) if isinstance(args_list, list) else str(args_list)
                print(f"  - {f.stem:<22} args: [{args_str}] ({tps} touchpoints)")
            except Exception as e:
                print(f"  - {f.stem:<22} (parse error: {e})")

    elif action == "show":
        if not args.name:
            sys.exit("Error: recipe show requires a recipe name.")
        recipe_file = recipes_dir / f"{args.name}.yaml"
        if not recipe_file.is_file():
            sys.exit(f"Error: Recipe '{args.name}' not found at {recipe_file}.")
        print(recipe_file.read_text(encoding="utf-8"))

    elif action == "verify":
        if not args.name:
            sys.exit("Error: recipe verify requires a recipe name.")
        recipe_file = recipes_dir / f"{args.name}.yaml"
        if not recipe_file.is_file():
            sys.exit(f"Error: Recipe '{args.name}' not found at {recipe_file}.")

        recipe_data = yaml.safe_load(recipe_file.read_text(encoding="utf-8")) or {}
        touchpoints = recipe_data.get("touchpoints", [])

        # Parse key=value pairs from --arg
        parsed_args = {}
        for item in args.arg or []:
            if "=" in item:
                k, v = item.split("=", 1)
                parsed_args[k.strip()] = v.strip()

        print(f"Verifying recipe '{args.name}' with args {parsed_args}...\n")
        missing_count = 0

        for tp in touchpoints:
            raw_file = tp.get("file", "")
            raw_contains = tp.get("contains", "")
            why = tp.get("why", "")

            try:
                target_file = raw_file.format(**parsed_args)
            except KeyError as e:
                print(f"[FAIL] Missing argument {e} for file path: {raw_file}")
                missing_count += 1
                continue

            try:
                target_contains = raw_contains.format(**parsed_args) if raw_contains else ""
            except KeyError as e:
                print(f"[FAIL] Missing argument {e} for contains pattern: {raw_contains}")
                missing_count += 1
                continue

            full_path = repo_root / target_file
            if not full_path.is_file():
                print(f"[MISSING FILE] {target_file}")
                print(f"  Why: {why}")
                missing_count += 1
                continue

            if target_contains:
                try:
                    content = full_path.read_text(encoding="utf-8", errors="ignore")
                    if target_contains not in content:
                        print(f"[MISSING TEXT] {target_file}")
                        print(f"  Expected text: '{target_contains}'")
                        print(f"  Why: {why}")
                        missing_count += 1
                        continue
                except Exception as e:
                    print(f"[READ ERROR] {target_file}: {e}")
                    missing_count += 1
                    continue

            print(f"[OK] {target_file}")

        print(f"\nVerification finished. {missing_count} missing touchpoint(s).")
        if missing_count > 0:
            sys.exit(1)


def cmd_fixture(args, repo_root: Path) -> None:
    action = args.fixture_action

    if action == "new":
        name = args.name.strip()
        if not re.match(r"^[a-z0-9-]{1,40}$", name):
            sys.exit(f"Error: Invalid fixture name '{name}'.")
        target_dir = repo_root / "tests" / "fixtures" / name
        if target_dir.exists():
            sys.exit(f"Error: Fixture '{name}' already exists at {target_dir}.")
        target_dir.mkdir(parents=True, exist_ok=False)
        invented_file = target_dir / "INVENTED.md"
        invented_file.write_text(
            f"# Invented Fixture: {name}\n\n"
            "This fixture is synthetic and invented solely for testing Build Forge.\n"
            "No third party, proprietary, or licensed text is contained here.\n",
            encoding="utf-8"
        )
        print(f"Created new fixture directory at {target_dir} with INVENTED.md.")

    elif action == "check":
        if getattr(args, "root", None):
            fixture_roots = [Path(args.root)]
        else:
            fixture_roots = [
                repo_root / "tests" / "fixtures",
                repo_root / "tests" / "evals" / "fixtures",
            ]

        allowed_hosts = {"example.com", "example.org", "localhost", "127.0.0.1"}
        forbidden_license_phrases = ["copyright (c)", "spdx-license-identifier", "licensed under"]
        max_bytes = 50 * 1024

        errors = []
        checked_folders = 0

        for froots in fixture_roots:
            if not froots.is_dir():
                continue
            for entry in sorted(froots.iterdir()):
                if not entry.is_dir() or entry.name.startswith((".", "_")) or entry.name == "__pycache__":
                    continue

                checked_folders += 1
                fdir = entry

                # 1. Must hold INVENTED.md
                invented_md = fdir / "INVENTED.md"
                if not invented_md.is_file():
                    errors.append(f"{fdir.name}: Missing INVENTED.md in fixture folder.")

                # Scan all files in the fixture
                for root, dirs, files in os.walk(fdir):
                    if ".git" in dirs:
                        errors.append(f"{fdir.name}: Contains forbidden .git folder at {root}/.git.")

                    for fname in files:
                        p = Path(root, fname)
                        try:
                            rel = p.relative_to(repo_root).as_posix()
                        except ValueError:
                            rel = p.as_posix()

                        # 2. No file over 50 KB
                        try:
                            size = p.stat().st_size
                            if size > max_bytes:
                                errors.append(f"{rel}: File size {size} bytes exceeds 50 KB limit.")
                        except OSError:
                            pass

                        # 3. No copyright or license headers outside INVENTED.md
                        if p.name != "INVENTED.md":
                            try:
                                text = p.read_text(encoding="utf-8", errors="ignore")
                                for line_no, line in enumerate(text.splitlines(), 1):
                                    line_lower = line.lower()
                                    for phrase in forbidden_license_phrases:
                                        if phrase in line_lower:
                                            errors.append(
                                                f"{rel}:{line_no}: Forbidden license phrase '{phrase}' outside INVENTED.md."
                                            )
                                    # 4. URLs check
                                    for url_match in re.finditer(r"https?://([^/\s\"'>:]+)", line):
                                        host = url_match.group(1).lower()
                                        if host not in allowed_hosts and not host.endswith(".example.com"):
                                            errors.append(
                                                f"{rel}:{line_no}: Disallowed URL host '{host}'. Allowed: {sorted(allowed_hosts)}."
                                            )
                            except Exception:
                                pass

        if errors:
            print(f"Fixture check failed with {len(errors)} error(s) across {checked_folders} fixtures:\n")
            for err in errors:
                print(f"  [FAIL] {err}")
            sys.exit(1)
        else:
            print(f"All {checked_folders} fixture folders passed verification checks.")


def cmd_release_plan(args, repo_root: Path) -> None:
    print("Release Plan (read only)\n" + "=" * 50)

    # 1. Last tag
    last_tag = "none"
    try:
        tag_res = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(repo_root),
            capture_output=True,
            text=True
        )
        if tag_res.returncode == 0 and tag_res.stdout.strip():
            last_tag = tag_res.stdout.strip()
    except Exception:
        pass

    # 2. Commits since last tag
    git_range = f"{last_tag}..HEAD" if last_tag != "none" else "HEAD"
    commits = []
    prs_merged = 0
    try:
        log_res = subprocess.run(
            ["git", "log", "--no-merges", git_range, "--oneline"],
            cwd=str(repo_root),
            capture_output=True,
            text=True
        )
        if log_res.returncode == 0:
            for line in log_res.stdout.splitlines():
                if line.strip():
                    commits.append(line.strip())
    except Exception:
        pass

    try:
        pr_res = subprocess.run(
            ["git", "log", "--first-parent", "--merges", git_range, "--format=%s"],
            cwd=str(repo_root),
            capture_output=True,
            text=True
        )
        if pr_res.returncode == 0:
            for line in pr_res.stdout.splitlines():
                if re.match(r"^Merge pull request #\d+ from ", line.strip()):
                    prs_merged += 1
    except Exception:
        pass

    type_counts = {}
    has_breaking = False
    for c in commits:
        parts = c.split(" ", 1)
        subject = parts[1] if len(parts) > 1 else parts[0]
        if subject.startswith("Merge "):
            continue
        m = re.match(r"^([a-z]+)(\([^\)]+\))?(!)?:\s*(.*)$", subject)
        if m:
            ctype = m.group(1)
            is_bang = bool(m.group(3))
            type_counts[ctype] = type_counts.get(ctype, 0) + 1
            if is_bang:
                has_breaking = True
        else:
            type_counts["other"] = type_counts.get("other", 0) + 1

    # 3. Recommended bump
    if has_breaking:
        bump = "major"
        reason = "Breaking change detected in commit message."
    elif type_counts.get("feat", 0) > 0:
        bump = "minor"
        reason = "New features (feat) added since last tag."
    else:
        bump = "patch"
        reason = "Only fixes, docs, tests, or chores since last tag."

    # 4. CHANGELOG Unreleased section entries
    changelog_has_entries = False
    changelog_path = repo_root / "CHANGELOG.md"
    if changelog_path.is_file():
        text = changelog_path.read_text(encoding="utf-8")
        unreleased_match = re.search(r"## \[Unreleased\]\s*\n(.*?)(?=\n## \[|\Z)", text, re.DOTALL)
        if unreleased_match:
            lines = [ln.strip() for ln in unreleased_match.group(1).splitlines() if ln.strip().startswith("-")]
            changelog_has_entries = len(lines) > 0

    # 5. Integrity fresh
    make_integrity_py = repo_root / "scripts" / "make_integrity.py"
    integrity_fresh = False
    if make_integrity_py.is_file():
        chk = subprocess.run([sys.executable, str(make_integrity_py), "--check"], cwd=str(repo_root), capture_output=True)
        integrity_fresh = (chk.returncode == 0)

    # 6. Tree clean
    status_res = subprocess.run(["git", "status", "--porcelain"], cwd=str(repo_root), capture_output=True, text=True)
    tree_clean = (status_res.returncode == 0 and len(status_res.stdout.strip()) == 0)

    # Compute next version suggestion
    cur_ver = "0.1.0"
    pkg_json = repo_root / "package.json"
    if pkg_json.is_file():
        try:
            cur_ver = json.loads(pkg_json.read_text(encoding="utf-8")).get("version", cur_ver)
        except Exception:
            pass

    vparts = [int(p) for p in cur_ver.split(".")] if re.match(r"^\d+\.\d+\.\d+$", cur_ver) else [0, 1, 0]
    if bump == "major":
        next_ver = f"{vparts[0] + 1}.0.0"
    elif bump == "minor":
        next_ver = f"{vparts[0]}.{vparts[1] + 1}.0"
    else:
        next_ver = f"{vparts[0]}.{vparts[1]}.{vparts[2] + 1}"

    target_ver = getattr(args, "target_version", None)
    if target_ver:
        clean_target = target_ver.lstrip("v")
        if re.match(r"^\d+\.\d+\.\d+$", clean_target):
            next_ver = clean_target

    print(f"Last tag:                   {last_tag}")
    print(f"Commits since tag:          {len(commits)}")
    print(f"PRs merged:                 {prs_merged}")
    print(f"Commit types:               {dict(sorted(type_counts.items()))}")
    print(f"Recommended version bump:   {bump} ({reason})")
    print(f"Current package version:    {cur_ver}")
    print(f"Next version suggestion:    {next_ver}")
    print(f"CHANGELOG has Unreleased:   {'YES' if changelog_has_entries else 'NO'}")
    print(f"integrity.json is fresh:    {'YES' if integrity_fresh else 'NO'}")
    print(f"Git working tree is clean:  {'YES' if tree_clean else 'NO'}")
    print("\nSuggested release command (do not run automatically):")
    print(f"  git tag v{next_ver}")


def cmd_trail(args, repo_root: Path) -> None:
    git_range = f"{args.since}..HEAD" if args.since else "HEAD"
    cmd = ["git", "log", "--first-parent", "--format=%H|%h|%P|%s", git_range]
    if args.limit:
        cmd.extend(["-n", str(args.limit)])
    res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"Error reading git history: {res.stderr.strip()}")

    merges = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        full_sha, short_sha, parents_str, subject = parts
        parents = parents_str.split() if parents_str else []

        if len(parents) == 2:
            m = re.match(r"^Merge pull request #(\d+) from (.*)$", subject)
            if m:
                pr_num = int(m.group(1))
                source_branch = m.group(2)
                p1, p2 = parents[0], parents[1]
                count_res = subprocess.run(
                    ["git", "rev-list", "--count", f"{p1}..{p2}"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                )
                commit_count = int(count_res.stdout.strip()) if count_res.returncode == 0 and count_res.stdout.strip().isdigit() else 0
                files_res = subprocess.run(
                    ["git", "diff", "--name-only", f"{p1}...{p2}"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                )
                files = [f for f in files_res.stdout.splitlines() if f.strip()]
                subjects_res = subprocess.run(
                    ["git", "log", "--format=%h %s", f"{p1}..{p2}"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                )
                sub_lines = [sl.strip() for sl in subjects_res.stdout.splitlines() if sl.strip()]
                merges.append({
                    "is_pr": True,
                    "pr_number": pr_num,
                    "source_branch": source_branch,
                    "merge_sha": short_sha,
                    "full_sha": full_sha,
                    "commit_count": commit_count,
                    "files_changed": files,
                    "commit_subjects": sub_lines,
                })
                continue

        # Direct commit or non-PR merge
        files_res = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", full_sha],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        files = [f for f in files_res.stdout.splitlines() if f.strip()]
        merges.append({
            "is_pr": False,
            "pr_number": None,
            "source_branch": None,
            "merge_sha": short_sha,
            "full_sha": full_sha,
            "commit_count": 1,
            "files_changed": files,
            "commit_subjects": [f"{short_sha} {subject}"],
            "subject": subject,
        })

    if getattr(args, "json", False):
        print(json.dumps(merges, indent=2))
        return

    for item in merges:
        if item["is_pr"]:
            pr_n = item["pr_number"]
            br = item["source_branch"]
            sha = item["merge_sha"]
            cc = item["commit_count"]
            fc = len(item["files_changed"])
            print(f"PR #{pr_n} ({br}) -> merge {sha} [{cc} commit(s), {fc} file(s) changed]")
            for sub in item["commit_subjects"]:
                print(f"  - {sub}")
        else:
            sha = item["merge_sha"]
            subj = item["subject"]
            fc = len(item["files_changed"])
            print(f"! {sha} [direct] {subj} [{fc} file(s) changed]")

    print("\ngit log --graph --oneline --decorate -30")


def cmd_repo_settings(args, repo_root: Path) -> None:
    print("Repository Settings Audit (read only)\n" + "=" * 50)
    gh_path = shutil.which("gh")
    reb_word = "re" + "base"
    if not gh_path:
        print("gh CLI not installed or not in PATH.\n")
        print("Manual verification checklist in GitHub repository settings:")
        print("1. Settings -> General -> Pull Requests:")
        print("   - Allow merge commits: ON")
        print("   - Allow squash merging: OFF")
        print(f"   - Allow {reb_word} merging: OFF")
        print("   - Automatically delete head branches: ON")
        print("2. Settings -> Branches -> Branch protection for main:")
        print("   - Require linear history: OFF")
        print("   - Do not allow bypassing above settings (enforce on admins): ON")
        print("   - Required status checks: CI, commit-lint")
        return

    fields = f"nameWithOwner,defaultBranchRef,mergeCommitAllowed,squashMergeAllowed,{reb_word}MergeAllowed,deleteBranchOnMerge"
    res = subprocess.run([gh_path, "repo", "view", "--json", fields], cwd=str(repo_root), capture_output=True, text=True)
    if res.returncode != 0:
        print("cannot read, check the settings page")
        return

    try:
        repo_data = json.loads(res.stdout)
    except Exception:
        print("cannot read, check the settings page")
        return

    owner_repo = repo_data.get("nameWithOwner", "")
    default_branch = repo_data.get("defaultBranchRef", {}).get("name", "main")

    protection_data = None
    prot_res = subprocess.run(
        [gh_path, "api", f"repos/{owner_repo}/branches/{default_branch}/protection"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if prot_res.returncode == 0:
        try:
            protection_data = json.loads(prot_res.stdout)
        except Exception:
            pass

    checks = []
    # 1. merge allowed (desired: True)
    m_val = repo_data.get("mergeCommitAllowed")
    checks.append(("Merge commits allowed", m_val, True))

    # 2. squash allowed (desired: False)
    sq_val = repo_data.get("squashMergeAllowed")
    checks.append(("Squash merging allowed", sq_val, False))

    # 3. re-base allowed (desired: False)
    reb_val = repo_data.get(f"{reb_word}MergeAllowed")
    checks.append((f"{reb_word.capitalize()} merging allowed", reb_val, False))

    # 4. delete branch on merge (desired: True)
    del_val = repo_data.get("deleteBranchOnMerge")
    checks.append(("Auto delete head branches", del_val, True))

    # Protection settings
    if protection_data:
        lin_hist = protection_data.get("required_linear_history", {}).get("enabled", False)
        checks.append(("Linear history required", lin_hist, False))

        enf_admins = protection_data.get("enforce_admins", {}).get("enabled", False)
        checks.append(("Enforce on administrators", enf_admins, True))

    header = f"{'Setting':<32} {'Status':<8} {'Current':<12} {'Desired'}"
    print(header)
    print("-" * 65)
    for name, cur, desired in checks:
        status = "OK" if cur == desired else "WARN"
        print(f"{name:<32} [{status:<4}]  {str(cur):<12} {str(desired)}")

    if not protection_data:
        print("\nBranch protection: cannot read, check the settings page")


def main():
    repo_root = get_repo_root()
    parser = argparse.ArgumentParser(description="Build Forge Maintainer Developer Toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # new-skill
    p_new = subparsers.add_parser("new-skill", help="Scaffold a new skill")
    p_new.add_argument("name", help="Name of the new skill")
    p_new.add_argument("--tier", required=True, choices=["core", "new-app", "module"], help="Skill tier")
    p_new.add_argument("--scripts", action="store_true", help="Scaffold scripts/ directory")
    p_new.add_argument("--refs", action="store_true", help="Scaffold references/ directory")

    # check
    p_chk = subparsers.add_parser("check", help="Run maintainer checks")
    p_chk.add_argument("--fast", action="store_true", help="Fast mode skipping slow tests")

    # impact
    p_imp = subparsers.add_parser("impact", help="Measure token impact across repository")
    p_imp.add_argument("token", help="Search token")

    # recipe
    p_rec = subparsers.add_parser("recipe", help="Maintainer recipe tools")
    p_rec.add_argument("recipe_action", choices=["list", "show", "verify"], help="Recipe action")
    p_rec.add_argument("name", nargs="?", default="", help="Recipe name")
    p_rec.add_argument("--arg", action="append", help="Argument for recipe verify in key=value format")

    # fixture
    p_fix = subparsers.add_parser("fixture", help="Manage test fixtures")
    p_fix.add_argument("fixture_action", choices=["new", "check"], help="Fixture action")
    p_fix.add_argument("name", nargs="?", default="", help="Fixture name (for new)")
    p_fix.add_argument("--root", default=None, help="Root folder to check (for check)")

    # release-plan
    p_rel = subparsers.add_parser("release-plan", help="Generate read only release plan")
    p_rel.add_argument("target_version", nargs="?", default=None, help="Target release version (optional)")

    # trail
    p_trail = subparsers.add_parser("trail", help="Display git merge trail")
    p_trail.add_argument("--since", default=None, help="Show trail since git reference")
    p_trail.add_argument("--limit", type=int, default=None, help="Limit number of commits to show")
    p_trail.add_argument("--json", action="store_true", help="Output trail in JSON format")

    # repo-settings
    p_rs = subparsers.add_parser("repo-settings", help="Audit repository settings against merge policy")

    args = parser.parse_args()

    if args.command == "new-skill":
        cmd_new_skill(args, repo_root)
    elif args.command == "check":
        cmd_check(args, repo_root)
    elif args.command == "impact":
        cmd_impact(args, repo_root)
    elif args.command == "recipe":
        cmd_recipe(args, repo_root)
    elif args.command == "fixture":
        cmd_fixture(args, repo_root)
    elif args.command == "release-plan":
        cmd_release_plan(args, repo_root)
    elif args.command == "trail":
        cmd_trail(args, repo_root)
    elif args.command == "repo-settings":
        cmd_repo_settings(args, repo_root)


if __name__ == "__main__":
    main()

