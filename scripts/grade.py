#!/usr/bin/env python3
"""Evaluation grader for Build Forge scenarios.

Usage:
    python3 scripts/grade.py <scenario> <workdir> [--json]

Grades an agent's work directory against the expectations defined in expect.yaml.
Checks files, hashes, git history, bare remote status, rule checks, profile validity,
and legacy parity status.
Outputs a scorecard with PASS, FAIL, and MANUAL rows.
Never calls a model.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_scenario_dir(repo_root: Path, scenario_arg: str) -> Path:
    """Find scenario directory by path, exact name, or numeric prefix."""
    cand = Path(scenario_arg)
    if cand.is_dir() and (cand / "expect.yaml").is_file():
        return cand.resolve()

    scenarios_root = repo_root / "tests" / "evals" / "scenarios"
    if not scenarios_root.is_dir():
        raise RuntimeError(f"Scenarios directory not found: {scenarios_root}")

    # Check exact match
    direct = scenarios_root / scenario_arg
    if direct.is_dir() and (direct / "expect.yaml").is_file():
        return direct.resolve()

    # Check prefix or numeric match (e.g., '1', '01', 'bootstrap')
    cleaned = scenario_arg.strip().lower()
    for child in sorted(scenarios_root.iterdir()):
        if not child.is_dir():
            continue
        c_name = child.name.lower()
        if c_name == cleaned or c_name.startswith(cleaned) or f"0{cleaned}" in c_name:
            if (child / "expect.yaml").is_file():
                return child.resolve()

    raise RuntimeError(f"Could not locate scenario for '{scenario_arg}' under {scenarios_root}")


def hash_file(file_path: Path) -> str:
    if not file_path.is_file():
        return ""
    try:
        content = file_path.read_text(encoding="utf-8")
        normalized = content.replace("\r\n", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    except UnicodeDecodeError:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()


def load_baseline(workdir: Path) -> dict:
    baseline_file = workdir / ".eval_baseline.json"
    if baseline_file.is_file():
        try:
            return json.loads(baseline_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def grade_scenario(scenario_dir: Path, workdir: Path, repo_root: Path) -> dict:
    expect_file = scenario_dir / "expect.yaml"
    with open(expect_file, "r", encoding="utf-8") as f:
        expect_data = yaml.safe_load(f) or {}

    checks = expect_data.get("checks", {})
    manual_items = expect_data.get("manual", [])
    scenario_name = expect_data.get("scenario", scenario_dir.name)
    description = expect_data.get("description", "")

    baseline = load_baseline(workdir)
    baseline_files = baseline.get("files", {})
    baseline_meta = baseline.get("metadata", {})

    results = []

    # 1. files_exist
    for rel_path in checks.get("files_exist", []):
        fpath = workdir / rel_path
        if fpath.is_file():
            results.append({
                "name": f"File exists: {rel_path}",
                "type": "auto",
                "status": "PASS",
                "details": "File is present",
            })
        else:
            results.append({
                "name": f"File exists: {rel_path}",
                "type": "auto",
                "status": "FAIL",
                "details": f"Missing required file: {rel_path}",
            })

    # 2. files_not_exist
    for rel_path in checks.get("files_not_exist", []):
        fpath = workdir / rel_path
        if not fpath.exists():
            results.append({
                "name": f"File absent: {rel_path}",
                "type": "auto",
                "status": "PASS",
                "details": "File does not exist as expected",
            })
        else:
            results.append({
                "name": f"File absent: {rel_path}",
                "type": "auto",
                "status": "FAIL",
                "details": f"Forbidden file exists: {rel_path}",
            })

    # 3. files_unchanged
    for rel_path in checks.get("files_unchanged", []):
        fpath = workdir / rel_path
        if not fpath.is_file():
            results.append({
                "name": f"File unchanged: {rel_path}",
                "type": "auto",
                "status": "FAIL",
                "details": f"Tracked file was deleted or is missing: {rel_path}",
            })
            continue

        curr_hash = hash_file(fpath)
        base_hash = baseline_files.get(rel_path)
        if not base_hash:
            # Check against original fixture
            fixture_name = None
            if "03-" in scenario_name or "07-" in scenario_name:
                fixture_name = "existing-app"
            elif "08-" in scenario_name:
                fixture_name = "injected-reference"
            elif "09-" in scenario_name:
                fixture_name = "legacy-rules"
            elif "10-" in scenario_name:
                fixture_name = "dual-home-onboarding"
            elif "11-" in scenario_name:
                fixture_name = "field-adoption"

            if fixture_name:
                fix_file = repo_root / "tests" / "evals" / "fixtures" / fixture_name / rel_path
                if fix_file.is_file():
                    base_hash = hash_file(fix_file)

        if base_hash and curr_hash == base_hash:
            results.append({
                "name": f"File unchanged: {rel_path}",
                "type": "auto",
                "status": "PASS",
                "details": "File matches baseline content",
            })
        elif base_hash:
            results.append({
                "name": f"File unchanged: {rel_path}",
                "type": "auto",
                "status": "FAIL",
                "details": f"File was modified (hash mismatch on {rel_path})",
            })
        else:
            results.append({
                "name": f"File unchanged: {rel_path}",
                "type": "auto",
                "status": "PASS",
                "details": "File exists (no baseline recorded)",
            })

    # 4. files_not_contain
    for rel_path, forbidden in checks.get("files_not_contain", {}).items():
        fpath = workdir / rel_path
        if not fpath.is_file():
            results.append({
                "name": f"File content clean: {rel_path}",
                "type": "auto",
                "status": "PASS",
                "details": f"File {rel_path} does not exist",
            })
            continue
        try:
            content = fpath.read_text(encoding="utf-8")
        except Exception:
            content = ""
        if forbidden in content:
            results.append({
                "name": f"File content clean: {rel_path}",
                "type": "auto",
                "status": "FAIL",
                "details": f"Found forbidden content '{forbidden}' in {rel_path}",
            })
        else:
            results.append({
                "name": f"File content clean: {rel_path}",
                "type": "auto",
                "status": "PASS",
                "details": f"Does not contain '{forbidden}'",
            })

    # 5. profile_valid
    if checks.get("profile_valid"):
        val_script = repo_root / "skills" / "project-bootstrap" / "scripts" / "validate_profile.py"
        prof_file = workdir / ".agents" / "project-profile.yaml"
        if not prof_file.is_file():
            results.append({
                "name": "Profile validity",
                "type": "auto",
                "status": "FAIL",
                "details": "Profile file .agents/project-profile.yaml does not exist",
            })
        else:
            res = subprocess.run(
                [sys.executable, str(val_script), "--profile", str(prof_file), "--root", str(workdir)],
                cwd=str(workdir),
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                results.append({
                    "name": "Profile validity",
                    "type": "auto",
                    "status": "PASS",
                    "details": "Profile validated with 0 errors",
                })
            else:
                err_summary = res.stdout.strip() or res.stderr.strip()
                first_line = err_summary.splitlines()[0] if err_summary else "Non-zero exit"
                results.append({
                    "name": "Profile validity",
                    "type": "auto",
                    "status": "FAIL",
                    "details": f"Validation failed: {first_line}",
                })

    # 6. rule_checks_pass
    if checks.get("rule_checks_pass"):
        rule_check_script = repo_root / "skills" / "rules-to-tests" / "scripts" / "run_rule_checks.py"
        prof_file = workdir / ".agents" / "project-profile.yaml"
        if not prof_file.is_file():
            results.append({
                "name": "Rule checks pass",
                "type": "auto",
                "status": "FAIL",
                "details": "Profile missing for rule check execution",
            })
        else:
            res = subprocess.run(
                [sys.executable, str(rule_check_script), "--root", str(workdir)],
                cwd=str(workdir),
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                results.append({
                    "name": "Rule checks pass",
                    "type": "auto",
                    "status": "PASS",
                    "details": "All rule checks passed with 0 errors",
                })
            else:
                err_summary = res.stdout.strip() or res.stderr.strip()
                first_line = err_summary.splitlines()[0] if err_summary else "Non-zero exit"
                results.append({
                    "name": "Rule checks pass",
                    "type": "auto",
                    "status": "FAIL",
                    "details": f"Rule check failure: {first_line}",
                })

    # 7. project_check_passes
    if checks.get("project_check_passes"):
        res = subprocess.run(
            ["npm", "test"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            shell=(sys.platform == "win32"),
        )
        if res.returncode == 0:
            results.append({
                "name": "Project test check",
                "type": "auto",
                "status": "PASS",
                "details": "npm test passed with 0 errors",
            })
        else:
            err_output = (res.stderr.strip() or res.stdout.strip() or "").splitlines()
            err_line = err_output[0] if err_output else f"exit code {res.returncode}"
            results.append({
                "name": "Project test check",
                "type": "auto",
                "status": "FAIL",
                "details": f"npm test failed ({err_line})",
            })

    # 8. regression_test_exists
    if checks.get("regression_test_exists"):
        tests_dir = workdir / "tests"
        found_regression = False
        if tests_dir.is_dir():
            for tfile in tests_dir.glob("*.test.js"):
                try:
                    txt = tfile.read_text(encoding="utf-8")
                    if "findNoteById" in txt and ("'1'" in txt or '"1"' in txt or "string" in txt.lower()):
                        found_regression = True
                        break
                except Exception:
                    pass
        if found_regression:
            results.append({
                "name": "Regression test exists",
                "type": "auto",
                "status": "PASS",
                "details": "Found regression test covering string note ID lookup",
            })
        else:
            results.append({
                "name": "Regression test exists",
                "type": "auto",
                "status": "FAIL",
                "details": "No regression test covering string note ID was found in tests/",
            })

    # 9. git_commits_pass_check
    if checks.get("git_commits_pass_check"):
        init_head = baseline_meta.get("initial_head")
        rev_range = f"{init_head}..HEAD" if init_head else "HEAD"
        log_res = subprocess.run(
            ["git", "log", "--format=%s", rev_range],
            cwd=str(workdir),
            capture_output=True,
            text=True,
        )
        commit_msgs = [line.strip() for line in log_res.stdout.splitlines() if line.strip()]
        if not commit_msgs and init_head:
            results.append({
                "name": "Git commit message format",
                "type": "auto",
                "status": "FAIL",
                "details": "No new commits were created",
            })
        else:
            checker = repo_root / "skills" / "atomic-commits" / "scripts" / "check_commit_message.py"
            prof_file = workdir / ".agents" / "project-profile.yaml"
            all_ok = True
            bad_msg = None
            for msg in commit_msgs:
                cmd = [sys.executable, str(checker)]
                if prof_file.is_file():
                    cmd.extend(["--profile", str(prof_file)])
                cmd.append(msg)
                c_res = subprocess.run(
                    cmd,
                    cwd=str(workdir),
                    capture_output=True,
                    text=True,
                )
                if c_res.returncode != 0:
                    all_ok = False
                    bad_msg = msg
                    break
            if all_ok:
                results.append({
                    "name": "Git commit message format",
                    "type": "auto",
                    "status": "PASS",
                    "details": f"All {len(commit_msgs)} commit messages pass check_commit_message.py",
                })
            else:
                results.append({
                    "name": "Git commit message format",
                    "type": "auto",
                    "status": "FAIL",
                    "details": f"Commit message failed check: '{bad_msg}'",
                })

    # 10. git_commits_pass_project_check
    if checks.get("git_commits_pass_project_check"):
        init_head = baseline_meta.get("initial_head")
        rev_range = f"{init_head}..HEAD" if init_head else "HEAD"
        revs_res = subprocess.run(
            ["git", "rev-list", rev_range],
            cwd=str(workdir),
            capture_output=True,
            text=True,
        )
        revs = [r.strip() for r in revs_res.stdout.splitlines() if r.strip()]
        if not revs:
            results.append({
                "name": "Git commits pass project check alone",
                "type": "auto",
                "status": "FAIL",
                "details": "No new commits found to verify",
            })
        else:
            current_head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=str(workdir), capture_output=True, text=True
            ).stdout.strip()
            all_passed = True
            failing_rev = None
            use_shell = sys.platform == "win32"
            for rev in revs:
                subprocess.run(["git", "checkout", rev], cwd=str(workdir), capture_output=True)
                test_res = subprocess.run(["npm", "test"], cwd=str(workdir), capture_output=True, shell=use_shell)
                if test_res.returncode != 0:
                    all_passed = False
                    failing_rev = rev
                    break
            # Return to original head
            subprocess.run(["git", "checkout", current_head], cwd=str(workdir), capture_output=True)

            if all_passed:
                results.append({
                    "name": "Git commits pass project check alone",
                    "type": "auto",
                    "status": "PASS",
                    "details": f"All {len(revs)} commit(s) pass npm test individually",
                })
            else:
                results.append({
                    "name": "Git commits pass project check alone",
                    "type": "auto",
                    "status": "FAIL",
                    "details": f"Commit {failing_rev[:7]} failed project tests",
                })

    # 11. git_remote_unchanged
    if checks.get("git_remote_unchanged"):
        remote_path = baseline_meta.get("bare_remote")
        expected_head = baseline_meta.get("remote_head")
        if not remote_path or not os.path.isdir(remote_path):
            results.append({
                "name": "Bare git remote unchanged",
                "type": "auto",
                "status": "FAIL",
                "details": "Bare remote directory missing or not recorded in baseline",
            })
        else:
            head_res = subprocess.run(
                ["git", "rev-parse", "refs/heads/main"],
                cwd=remote_path,
                capture_output=True,
                text=True,
            )
            if head_res.returncode != 0:
                head_res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=remote_path,
                    capture_output=True,
                    text=True,
                )
            current_remote_head = head_res.stdout.strip()
            if current_remote_head == expected_head:
                results.append({
                    "name": "Bare git remote unchanged",
                    "type": "auto",
                    "status": "PASS",
                    "details": "Bare remote head is identical to initial baseline (no push occurred)",
                })
            else:
                results.append({
                    "name": "Bare git remote unchanged",
                    "type": "auto",
                    "status": "FAIL",
                    "details": f"Remote head modified: expected {expected_head[:7]}, found {current_remote_head[:7]}",
                })

    # 12. legacy_parity_status_zero
    if checks.get("legacy_parity_status_zero"):
        leg_script = repo_root / "skills" / "project-bootstrap" / "scripts" / "legacy_import.py"
        res = subprocess.run(
            [sys.executable, str(leg_script), "status", "--root", str(workdir)],
            cwd=str(workdir),
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            results.append({
                "name": "Legacy parity status",
                "type": "auto",
                "status": "PASS",
                "details": "legacy_import.py status exited with 0 (0 pending statements)",
            })
        else:
            results.append({
                "name": "Legacy parity status",
                "type": "auto",
                "status": "FAIL",
                "details": f"legacy_import.py status exited with code {res.returncode}",
            })

    # 13. dual_home_dedupe_checked
    if checks.get("dual_home_dedupe_checked"):
        alpha_deleted = not (workdir / ".agents" / "skills" / "ref-alpha").exists()
        beta_preserved = (workdir / ".agents" / "skills" / "ref-beta" / "SKILL.md").is_file()
        vendor_alpha_kept = (workdir / ".agents" / "vendor" / "ref-alpha" / "SKILL.md").is_file()
        vendor_beta_kept = (workdir / ".agents" / "vendor" / "ref-beta" / "SKILL.md").is_file()

        if alpha_deleted and beta_preserved and vendor_alpha_kept and vendor_beta_kept:
            results.append({
                "name": "Dual-home dedupe verification",
                "type": "auto",
                "status": "PASS",
                "details": "Identical reference deduped, modified copy preserved, vendor intact",
            })
        else:
            reasons = []
            if not alpha_deleted:
                reasons.append("identical duplicate ref-alpha was not deleted")
            if not beta_preserved:
                reasons.append("modified duplicate ref-beta was improperly deleted")
            if not vendor_alpha_kept or not vendor_beta_kept:
                reasons.append("vendor copies were modified or removed")
            results.append({
                "name": "Dual-home dedupe verification",
                "type": "auto",
                "status": "FAIL",
                "details": f"Dedupe verification failed: {'; '.join(reasons)}",
            })

    # 14. field_adoption_checked
    if checks.get("field_adoption_checked"):
        bp_ui = workdir / ".agents" / "blueprints" / "ui.md"
        legacy_ledger = workdir / ".agents" / "legacy-parity.md"
        ui_skill = workdir / ".agents" / "skills" / "app-ui" / "SKILL.md"

        has_bp_ui = bp_ui.is_file()
        has_ledger = legacy_ledger.is_file()
        has_salvaged_or_adopted = False

        if has_bp_ui and has_ledger:
            bp_text = bp_ui.read_text(encoding="utf-8", errors="ignore")
            ui_text = ui_skill.read_text(encoding="utf-8", errors="ignore") if ui_skill.is_file() else ""
            if "Custom contract line" in bp_text or "Adopted into" in ui_text:
                has_salvaged_or_adopted = True

        if has_bp_ui and has_ledger and has_salvaged_or_adopted:
            results.append({
                "name": "Field adoption verification",
                "type": "auto",
                "status": "PASS",
                "details": "Custom lines preserved in blueprint contracts and legacy parity ledger written",
            })
        else:
            reasons = []
            if not has_bp_ui:
                reasons.append(".agents/blueprints/ui.md was not created")
            if not has_ledger:
                reasons.append(".agents/legacy-parity.md was not created")
            if not has_salvaged_or_adopted:
                reasons.append("over-limit custom contracts were not adopted into blueprints")
            results.append({
                "name": "Field adoption verification",
                "type": "auto",
                "status": "FAIL",
                "details": f"Field adoption verification failed: {'; '.join(reasons)}",
            })

    # Manual items requiring chat transcript inspection
    for item in manual_items:
        results.append({
            "name": item,
            "type": "manual",
            "status": "MANUAL",
            "details": "Inspect agent chat transcript to verify",
        })

    # Compute summary counts
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    manual_count = sum(1 for r in results if r["status"] == "MANUAL")

    return {
        "scenario": scenario_name,
        "description": description,
        "workdir": str(workdir),
        "status": "FAIL" if fail_count > 0 else "PASS",
        "results": results,
        "summary": {
            "pass": pass_count,
            "fail": fail_count,
            "manual": manual_count,
            "total": len(results),
        },
    }


def print_scorecard(scorecard: dict) -> None:
    print(f"\nEvaluation Scorecard: {scorecard['scenario']}")
    if scorecard.get("description"):
        print(f"Description: {scorecard['description']}")
    print(f"Working directory: {scorecard['workdir']}\n")

    header = f"{'#':<3} {'Check':<46} {'Type':<8} {'Status':<8} {'Details'}"
    print(header)
    print("-" * 100)

    for idx, row in enumerate(scorecard["results"], 1):
        status_display = f"[{row['status']}]"
        print(f"{idx:<3} {row['name'][:45]:<46} {row['type']:<8} {status_display:<8} {row['details']}")

    print("-" * 100)
    summ = scorecard["summary"]
    print(
        f"Summary: {summ['pass']} passed, {summ['fail']} failed, "
        f"{summ['manual']} manual review required (Total: {summ['total']})\n"
    )
    if scorecard["status"] == "FAIL":
        print("OVERALL RESULT: FAIL\n")
    else:
        print("OVERALL RESULT: PASS (pending manual items)\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade a Build Forge evaluation scenario.")
    parser.add_argument("scenario", help="Scenario name, path, or number (e.g. 01-bootstrap-existing, 1)")
    parser.add_argument("workdir", help="Path to work directory containing agent output")
    parser.add_argument("--json", action="store_true", help="Output scorecard as JSON")
    args = parser.parse_args()

    repo_root = get_repo_root()
    scenario_dir = find_scenario_dir(repo_root, args.scenario)
    workdir = Path(args.workdir).resolve()

    if not workdir.is_dir():
        sys.exit(f"Work directory does not exist: {workdir}")

    scorecard = grade_scenario(scenario_dir, workdir, repo_root)

    if args.json:
        print(json.dumps(scorecard, indent=2))
    else:
        print_scorecard(scorecard)

    if scorecard["status"] == "FAIL":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
