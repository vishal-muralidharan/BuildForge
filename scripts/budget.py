#!/usr/bin/env python3
"""Measure pipeline load costs and token estimates across all skills.

Calculates:
- Description characters and estimated tokens (startup cost loaded by agents)
- SKILL.md lines, characters, and estimated tokens
- Reference files count, characters, and estimated tokens
- Total estimated tokens (estimated tokens = characters / 4)
"""
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")


def estimate_tokens(chars: int) -> int:
    """Estimated tokens calculated as characters divided by 4 (approximate estimate)."""
    return round(chars / 4)


def parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}


def analyze_skills(skills_dir: Path) -> dict:
    skills_data = []
    ref_details = []

    for item in sorted(skills_dir.iterdir()):
        if not item.is_dir():
            continue
        skill_name = item.name
        skill_md_path = item / "SKILL.md"
        if not skill_md_path.is_file():
            continue

        skill_text = skill_md_path.read_text(encoding="utf-8", errors="ignore")
        skill_lines = len(skill_text.splitlines())
        skill_chars = len(skill_text)
        skill_tokens = estimate_tokens(skill_chars)

        fm = parse_frontmatter(skill_text)
        desc = fm.get("description", "")
        desc_chars = len(desc)
        desc_tokens = estimate_tokens(desc_chars)

        ref_dir = item / "references"
        ref_files = []
        ref_chars_total = 0
        if ref_dir.is_dir():
            for p in sorted(ref_dir.rglob("*")):
                if p.is_file():
                    rel_p = p.relative_to(ref_dir).as_posix()
                    txt = p.read_text(encoding="utf-8", errors="ignore")
                    r_lines = len(txt.splitlines())
                    r_chars = len(txt)
                    r_tokens = estimate_tokens(r_chars)
                    ref_files.append({
                        "file": rel_p,
                        "lines": r_lines,
                        "chars": r_chars,
                        "tokens": r_tokens
                    })
                    ref_details.append({
                        "skill": skill_name,
                        "file": rel_p,
                        "lines": r_lines,
                        "chars": r_chars,
                        "tokens": r_tokens
                    })
                    ref_chars_total += r_chars

        ref_tokens_total = estimate_tokens(ref_chars_total)
        total_skill_tokens = skill_tokens + ref_tokens_total

        skills_data.append({
            "name": skill_name,
            "desc": desc,
            "desc_chars": desc_chars,
            "desc_tokens": desc_tokens,
            "lines": skill_lines,
            "chars": skill_chars,
            "tokens": skill_tokens,
            "ref_count": len(ref_files),
            "ref_chars": ref_chars_total,
            "ref_tokens": ref_tokens_total,
            "total_tokens": total_skill_tokens
        })

    return {
        "skills": skills_data,
        "ref_details": ref_details
    }


def print_report(data: dict):
    skills = data["skills"]
    ref_details = data["ref_details"]

    print("# Build Forge Pipeline Load Budget Report\n")
    print("> Note: Estimated tokens are calculated as characters divided by 4 (approximate estimate).\n")

    # Table 1: Skill summary
    print("## 1. Skill Size and Load Cost Summary\n")
    headers = [
        "Skill", "Desc Chars", "Desc Est Tok", "SKILL Lines",
        "SKILL Chars", "SKILL Est Tok", "Refs", "Ref Chars",
        "Ref Est Tok", "Total Est Tok"
    ]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")

    tot_desc_chars = 0
    tot_desc_tokens = 0
    tot_skill_lines = 0
    tot_skill_chars = 0
    tot_skill_tokens = 0
    tot_refs_count = 0
    tot_refs_chars = 0
    tot_refs_tokens = 0
    tot_tokens_all = 0

    for s in skills:
        tot_desc_chars += s["desc_chars"]
        tot_desc_tokens += s["desc_tokens"]
        tot_skill_lines += s["lines"]
        tot_skill_chars += s["chars"]
        tot_skill_tokens += s["tokens"]
        tot_refs_count += s["ref_count"]
        tot_refs_chars += s["ref_chars"]
        tot_refs_tokens += s["ref_tokens"]
        tot_tokens_all += s["total_tokens"]

        row = [
            f"`{s['name']}`",
            str(s["desc_chars"]),
            str(s["desc_tokens"]),
            str(s["lines"]),
            str(s["chars"]),
            str(s["tokens"]),
            str(s["ref_count"]),
            str(s["ref_chars"]),
            str(s["ref_tokens"]),
            str(s["total_tokens"])
        ]
        print("| " + " | ".join(row) + " |")

    totals_row = [
        "**TOTAL**",
        f"**{tot_desc_chars}**",
        f"**{tot_desc_tokens}**",
        f"**{tot_skill_lines}**",
        f"**{tot_skill_chars}**",
        f"**{tot_skill_tokens}**",
        f"**{tot_refs_count}**",
        f"**{tot_refs_chars}**",
        f"**{tot_refs_tokens}**",
        f"**{tot_tokens_all}**"
    ]
    print("| " + " | ".join(totals_row) + " |\n")

    # Table 2: Startup cost summary
    print("## 2. Startup Description Budget (Loaded by Agent at Session Start)\n")
    print(f"- Total skills: {len(skills)}")
    print(f"- Total description characters: {tot_desc_chars}")
    print(f"- Total description estimated tokens: {tot_desc_tokens} est. tokens")
    avg_chars = round(tot_desc_chars / len(skills)) if skills else 0
    print(f"- Average description characters: {avg_chars} chars ({estimate_tokens(avg_chars)} est. tokens)")
    max_desc_skill = max(skills, key=lambda s: s["desc_chars"]) if skills else None
    if max_desc_skill:
        print(f"- Largest description: `{max_desc_skill['name']}` ({max_desc_skill['desc_chars']} chars, {max_desc_skill['desc_tokens']} est. tokens)\n")

    # Table 3: Reference files detail
    print("## 3. Reference Files Detail\n")
    if not ref_details:
        print("No reference files found.")
    else:
        ref_headers = ["Skill", "Reference File", "Lines", "Characters", "Est. Tokens (chars / 4)"]
        print("| " + " | ".join(ref_headers) + " |")
        print("|" + "|".join("---" for _ in ref_headers) + "|")
        for r in ref_details:
            r_row = [
                f"`{r['skill']}`",
                f"`{r['file']}`",
                str(r["lines"]),
                str(r["chars"]),
                str(r["tokens"])
            ]
            print("| " + " | ".join(r_row) + " |")
    print()


def main():
    repo_root = Path(__file__).resolve().parent.parent
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        sys.exit(f"Error: {skills_dir} is not a directory.")

    data = analyze_skills(skills_dir)
    print_report(data)


if __name__ == "__main__":
    main()
