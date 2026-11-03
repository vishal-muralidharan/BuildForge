#!/usr/bin/env python3
"""Parse feature-delivery stages and measure typical stage load costs.

For each stage in feature-delivery:
- Lists the skill files, references, and project context files read
- Totals the characters and estimated tokens (estimated tokens = characters / 4)
- Prints a structured load plan table
"""
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")


def estimate_tokens(chars: int) -> int:
    """Estimated tokens calculated as characters divided by 4 (approximate estimate)."""
    return round(chars / 4)


def get_file_stats(path: Path) -> dict:
    if not path.is_file():
        return {"path": path.as_posix(), "lines": 0, "chars": 0, "tokens": 0, "exists": False}
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = len(text.splitlines())
    chars = len(text)
    return {
        "path": path.as_posix(),
        "lines": lines,
        "chars": chars,
        "tokens": estimate_tokens(chars),
        "exists": True
    }


def parse_stages_and_gates(skill_md_path: Path) -> list:
    content = skill_md_path.read_text(encoding="utf-8", errors="ignore")
    stages = []

    # Parse Stages and gates markdown table
    in_table = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("| # | Stage | Skill to use |"):
            in_table = True
            continue
        if in_table:
            if re.match(r"^\|(\s*:?-+:?\s*\|)+$", stripped):
                continue
            if not stripped.startswith("|") or not stripped.endswith("|"):
                in_table = False
                continue
            parts = [p.strip() for p in stripped.split("|")[1:-1]]
            if len(parts) >= 4:
                stage_num = parts[0]
                stage_name = parts[1]
                skill_used = parts[2]
                gate_desc = parts[3]
                stages.append({
                    "stage": stage_num,
                    "name": stage_name,
                    "skill_used": skill_used,
                    "gate": gate_desc
                })
    return stages


def build_stage_load_plan(repo_root: Path) -> list:
    skills_dir = repo_root / "skills"
    fd_skill_path = skills_dir / "feature-delivery" / "SKILL.md"
    raw_stages = parse_stages_and_gates(fd_skill_path)

    # Typical profile size benchmark from example-nemo
    example_profile_path = skills_dir / "project-bootstrap" / "references" / "example-nemo.project-profile.yaml"
    profile_stats = get_file_stats(example_profile_path)
    # Typical CURRENT_GOAL.md benchmark (~35 lines, ~900 chars)
    goal_doc_chars = 900

    plan = []

    # Map each stage to the concrete files read during execution
    stage_file_map = {
        "0": {
            "desc": "Pre-flight: verify branch and working tree against profile policies",
            "files": [
                skills_dir / "feature-delivery" / "SKILL.md",
            ],
            "context_chars": profile_stats["chars"],
            "context_note": "project profile"
        },
        "1": {
            "desc": "Audit & Goal: repo discovery, diagnose cause, define goal invariants",
            "files": [
                skills_dir / "audit-and-planning" / "SKILL.md",
                skills_dir / "repo-search" / "SKILL.md",
            ],
            "context_chars": profile_stats["chars"],
            "context_note": "project profile"
        },
        "2": {
            "desc": "Plan: split feature into verified atomic steps with commit messages",
            "files": [
                skills_dir / "audit-and-planning" / "SKILL.md",
            ],
            "context_chars": 0,
            "context_note": "audit plan in memory"
        },
        "3": {
            "desc": "Build step: execute 1 functional step following area conventions",
            "files": [
                # Benchmark using convention skill size (~100 lines, ~3200 chars)
                skills_dir / "scaffold-app" / "SKILL.md",
            ],
            "context_chars": 0,
            "context_note": "area convention rules"
        },
        "3a": {
            "desc": "Verify step: run step checks and evaluate zero errors/warnings",
            "files": [
                skills_dir / "targeted-module-testing" / "SKILL.md",
            ],
            "context_chars": 0,
            "context_note": "test runner output"
        },
        "3b": {
            "desc": "Commit step: check conventional commit format and commit step",
            "files": [
                skills_dir / "atomic-commits" / "SKILL.md",
            ],
            "context_chars": 0,
            "context_note": "git commit message"
        },
        "4": {
            "desc": "Sync: detect drift and update profile, convention skills, and checks",
            "files": [
                skills_dir / "sync-skills-and-docs" / "SKILL.md",
                skills_dir / "rules-to-tests" / "SKILL.md",
            ],
            "context_chars": profile_stats["chars"],
            "context_note": "project profile"
        },
        "5": {
            "desc": "Full verify: execute complete check suite and rule verification",
            "files": [
                skills_dir / "targeted-module-testing" / "SKILL.md",
            ],
            "context_chars": 0,
            "context_note": "test suite results"
        },
        "5a": {
            "desc": "Goal loop gate: evaluate acceptance invariants in CURRENT_GOAL.md",
            "files": [
                skills_dir / "targeted-module-testing" / "SKILL.md",
            ],
            "context_chars": goal_doc_chars,
            "context_note": "CURRENT_GOAL.md"
        },
        "6": {
            "desc": "Deploy (optional): run deploy command and verify deployment URL",
            "files": [
                skills_dir / "targeted-module-testing" / "SKILL.md",
            ],
            "context_chars": 0,
            "context_note": "deployment verification"
        },
        "7": {
            "desc": "Report: compile post-build audit and final delivery report",
            "files": [
                skills_dir / "targeted-module-testing" / "SKILL.md",
            ],
            "context_chars": goal_doc_chars,
            "context_note": "final audit report"
        }
    }

    for s in raw_stages:
        s_num = s["stage"]
        cfg = stage_file_map.get(s_num, {
            "desc": s["name"],
            "files": [],
            "context_chars": 0,
            "context_note": ""
        })

        files_stats = [get_file_stats(f) for f in cfg["files"]]
        files_chars = sum(f["chars"] for f in files_stats)
        files_tokens = sum(f["tokens"] for f in files_stats)

        total_stage_chars = files_chars + cfg["context_chars"]
        total_stage_tokens = estimate_tokens(total_stage_chars)

        plan.append({
            "stage": s_num,
            "name": s["name"],
            "skill_used": s["skill_used"],
            "description": cfg["desc"],
            "files": [Path(f["path"]).name for f in files_stats],
            "files_chars": files_chars,
            "context_chars": cfg["context_chars"],
            "context_note": cfg["context_note"],
            "total_chars": total_stage_chars,
            "total_tokens": total_stage_tokens
        })

    # Also calculate specialized workflow load costs
    workflows = [
        {
            "name": "Bug fix workflow (`fix-bug.md`)",
            "files": [skills_dir / "feature-delivery" / "references" / "workflows" / "fix-bug.md"],
            "context_chars": profile_stats["chars"],
            "context_note": "project profile"
        },
        {
            "name": "Code review workflow (`review-changes.md`)",
            "files": [skills_dir / "feature-delivery" / "references" / "workflows" / "review-changes.md"],
            "context_chars": profile_stats["chars"],
            "context_note": "project profile"
        },
        {
            "name": "Release prep workflow (`release-prep.md`)",
            "files": [skills_dir / "feature-delivery" / "references" / "workflows" / "release-prep.md"],
            "context_chars": profile_stats["chars"],
            "context_note": "project profile"
        }
    ]

    wf_plan = []
    for wf in workflows:
        f_stats = [get_file_stats(f) for f in wf["files"]]
        f_chars = sum(f["chars"] for f in f_stats)
        t_chars = f_chars + wf["context_chars"]
        wf_plan.append({
            "name": wf["name"],
            "files": [Path(f["path"]).name for f in f_stats],
            "total_chars": t_chars,
            "total_tokens": estimate_tokens(t_chars)
        })

    return plan, wf_plan


def print_load_plan_report(plan: list, wf_plan: list):
    print("# Feature Delivery Stage Load Plan\n")
    print("> Note: Estimated tokens are calculated as characters divided by 4 (approximate estimate).\n")

    print("## 1. Pipeline Stages Load Cost (Standard 7-Stage Pipeline)\n")
    headers = [
        "Stage", "Stage Name", "Skill Used", "Files Read",
        "Skill Chars", "Context Chars", "Total Chars", "Est Tokens (chars / 4)"
    ]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")

    for p in plan:
        files_str = ", ".join(f"`{f}`" for f in p["files"]) if p["files"] else "none"
        ctx_str = f"{p['context_chars']} ({p['context_note']})" if p['context_chars'] else "0"
        row = [
            f"**{p['stage']}**",
            p["name"],
            f"`{p['skill_used']}`",
            files_str,
            str(p["files_chars"]),
            ctx_str,
            str(p["total_chars"]),
            f"**{p['total_tokens']}**"
        ]
        print("| " + " | ".join(row) + " |")

    max_stage = max(plan, key=lambda x: x["total_tokens"])
    avg_tokens = round(sum(p["total_tokens"] for p in plan) / len(plan))
    print(f"\n- Peak single stage load: **Stage {max_stage['stage']} ({max_stage['name']})** at {max_stage['total_tokens']} est. tokens ({max_stage['total_chars']} chars)")
    print(f"- Average load per stage: **{avg_tokens} est. tokens** ({avg_tokens * 4} chars)")

    print("\n## 2. Specialized Task Workflows Load Cost\n")
    wf_headers = ["Workflow", "Files Read", "Total Chars (inc. Profile)", "Est Tokens (chars / 4)"]
    print("| " + " | ".join(wf_headers) + " |")
    print("|" + "|".join("---" for _ in wf_headers) + "|")
    for wf in wf_plan:
        row = [
            wf["name"],
            ", ".join(f"`{f}`" for f in wf["files"]),
            str(wf["total_chars"]),
            f"**{wf['total_tokens']}**"
        ]
        print("| " + " | ".join(row) + " |")
    print()


def main():
    repo_root = Path(__file__).resolve().parent.parent
    plan, wf_plan = build_stage_load_plan(repo_root)
    print_load_plan_report(plan, wf_plan)


if __name__ == "__main__":
    main()
