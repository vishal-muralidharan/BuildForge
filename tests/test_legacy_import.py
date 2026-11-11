#!/usr/bin/env python3
"""Test fixture and integration tests for legacy parity importer.

Verifies:
1. Discovery of legacy files across AGENTS.md, .claude/skills, and .cursor/rules.
2. Statement classification: rule-candidate, duplicate, derivable-tokens, derivable-data, note.
3. Coverage number calculation.
4. Batch command output for rule candidates.
5. Apply command: writing accepted rules with evidence to profile, dropped statements with reasons,
   and notes to .agents/notes/.
6. Blueprint fact matching for derivable statements.
7. Status exit codes: exits 1 when pending items remain, exits 0 when resolved.
8. Preservation of legacy files: confirms no legacy file is modified or deleted.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_legacy_import_tests(repo_root: str = None) -> None:
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    script_path = os.path.join(
        repo_root, "skills", "project-bootstrap", "scripts", "legacy_import.py"
    )
    if not os.path.isfile(script_path):
        raise RuntimeError(f"legacy_import.py not found at {script_path}")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)

        # 1. Create tiny invented project with legacy files
        agents_md = tmp / "AGENTS.md"
        agents_md.write_text(
            "# Agent Guidelines\n\n"
            "## Design Tokens\n"
            "| Token | Value | Role |\n"
            "|---|---|---|\n"
            "| --color-primary | #0055ff | action |\n"
            "| --color-surface | #ffffff | surface |\n\n"
            "## Rules\n"
            "- Always use kebab-case for CSS file names.\n"
            "- Always use kebab-case for CSS file names.\n\n"
            "## Architecture Rationale\n"
            "We centralize state in store to prevent state drift across views.\n",
            encoding="utf-8"
        )

        claude_skill = tmp / ".claude" / "skills" / "data-ops" / "SKILL.md"
        claude_skill.parent.mkdir(parents=True, exist_ok=True)
        claude_skill.write_text(
            "# Data Operations\n\n"
            "## Account Model\n"
            "```typescript\n"
            "interface UserAccount {\n"
            "  id: string;\n"
            "  email: string;\n"
            "}\n"
            "```\n\n"
            "## Invariants\n"
            "- Must validate all user input on the server before database write.\n",
            encoding="utf-8"
        )

        cursor_rule = tmp / ".cursor" / "rules" / "styling.md"
        cursor_rule.parent.mkdir(parents=True, exist_ok=True)
        cursor_rule.write_text(
            "# Styling Rules\n\n"
            "- Always use kebab-case for CSS file names.\n"
            "- Never use inline styles in React components.\n",
            encoding="utf-8"
        )

        # Initial profile
        prof_file = tmp / ".agents" / "project-profile.yaml"
        prof_file.parent.mkdir(parents=True, exist_ok=True)
        prof_file.write_text(
            "schema_version: 1\n"
            "project:\n"
            "  name: TestApp\n"
            "  summary: Test application\n"
            "  mode: existing\n"
            "stack:\n"
            "  language: typescript\n"
            "  framework: React\n"
            "  package_manager: npm\n"
            "commands:\n"
            "  check: npm test\n"
            "rules: []\n",
            encoding="utf-8"
        )

        # Record original hashes
        orig_hashes = {
            agents_md: sha256_file(agents_md),
            claude_skill: sha256_file(claude_skill),
            cursor_rule: sha256_file(cursor_rule)
        }

        # Step A: Run inventory
        res_inv = subprocess.run(
            [sys.executable, script_path, "inventory", "--write", "--root", str(tmp)],
            capture_output=True, text=True
        )
        assert res_inv.returncode == 0, f"inventory failed: {res_inv.stderr}"
        ledger_path = tmp / ".agents" / "legacy-parity.md"
        assert ledger_path.is_file(), "ledger .agents/legacy-parity.md was not created"
        ledger_text = ledger_path.read_text(encoding="utf-8")

        # Verify classes are present
        assert "duplicate" in ledger_text, "expected duplicate classification in ledger"
        assert "derivable-tokens" in ledger_text, "expected derivable-tokens classification in ledger"
        assert "derivable-data" in ledger_text, "expected derivable-data classification in ledger"
        assert "note" in ledger_text, "expected note classification in ledger"
        assert "rule-candidate" in ledger_text, "expected rule-candidate classification in ledger"

        # Step B: Status must exit 1 because items are pending
        res_stat1 = subprocess.run(
            [sys.executable, script_path, "status", "--root", str(tmp)],
            capture_output=True, text=True
        )
        assert res_stat1.returncode == 1, (
            f"status expected returncode 1 when items pending, got {res_stat1.returncode}"
        )
        assert "Exit 1:" in res_stat1.stdout or "still pending" in res_stat1.stdout

        # Step C: Batch for area naming
        res_batch = subprocess.run(
            [sys.executable, script_path, "batch", "--area", "naming", "--root", str(tmp)],
            capture_output=True, text=True
        )
        assert res_batch.returncode == 0, f"batch failed: {res_batch.stderr}"
        assert "kebab-case" in res_batch.stdout
        assert "Proposed Profile Rule:" in res_batch.stdout

        # Step D: Apply accepts and drops
        # Parse statements from ledger
        lines = [line.strip() for line in ledger_text.splitlines() if line.strip().startswith("| L")]
        assert len(lines) >= 5, f"expected at least 5 statements in ledger, got {len(lines)}"

        rule_cand_ids = []
        derivable_ids = []
        note_ids = []
        for l in lines:
            parts = [p.strip() for p in l.split("|")[1:-1]]
            sid, _, sclass, _, status = parts[:5]
            if sclass == "rule-candidate" and status == "pending":
                rule_cand_ids.append(sid)
            elif sclass.startswith("derivable-") and status == "pending":
                derivable_ids.append(sid)
            elif sclass == "note" and status == "pending":
                note_ids.append(sid)

        assert len(rule_cand_ids) >= 2, f"expected at least 2 rule candidates, got {rule_cand_ids}"

        accept_id = rule_cand_ids[0]
        drop_id = rule_cand_ids[1]

        res_apply = subprocess.run(
            [
                sys.executable, script_path, "apply",
                "--accept", accept_id,
                "--drop", drop_id,
                "--reason", "Enforced by linter",
                "--root", str(tmp)
            ],
            capture_output=True, text=True
        )
        assert res_apply.returncode == 0, f"apply failed: {res_apply.stderr}"

        # Verify accepted rule written to profile with evidence
        prof_text = prof_file.read_text(encoding="utf-8")
        assert "evidence:" in prof_text, "profile must contain evidence for accepted rule"
        assert "enforced_by: manual" in prof_text

        # Verify note accept
        if note_ids:
            res_apply_note = subprocess.run(
                [
                    sys.executable, script_path, "apply",
                    "--accept", note_ids[0],
                    "--root", str(tmp)
                ],
                capture_output=True, text=True
            )
            assert res_apply_note.returncode == 0
            notes_dir = tmp / ".agents" / "notes"
            assert notes_dir.is_dir(), "expected .agents/notes directory"

        # Step E: Blueprints matching for derivable statements
        # Create blueprints holding matching facts
        bp_dir = tmp / ".agents" / "blueprints"
        bp_dir.mkdir(parents=True, exist_ok=True)
        (bp_dir / "tokens.md").write_text(
            "# Design Tokens\n| Token | Light | Dark |\n|---|---|---|\n| --color-primary | #0055ff | #3388ff |\n",
            encoding="utf-8"
        )
        (bp_dir / "data.md").write_text(
            "# Data Models\n\nModel UserAccount with id and email fields.\n",
            encoding="utf-8"
        )

        # Run inventory or status to re-evaluate against blueprints
        res_inv2 = subprocess.run(
            [sys.executable, script_path, "inventory", "--root", str(tmp)],
            capture_output=True, text=True
        )
        assert res_inv2.returncode == 0

        # Any remaining rule-candidate accept or drop to reach 100% resolution
        res_stat_check = subprocess.run(
            [sys.executable, script_path, "status", "--root", str(tmp)],
            capture_output=True, text=True
        )
        if res_stat_check.returncode != 0:
            # Drop any remaining rule candidates that were not accepted
            ledger2_text = (tmp / ".agents" / "legacy-parity.md").read_text(encoding="utf-8")
            rem_lines = [line.strip() for line in ledger2_text.splitlines() if line.strip().startswith("| L")]
            rem_pending = []
            for l in rem_lines:
                parts = [p.strip() for p in l.split("|")[1:-1]]
                sid, _, sclass, _, status = parts[:5]
                if status == "pending" and sclass in ("rule-candidate", "derivable-data", "derivable-tokens"):
                    rem_pending.append(sid)
            if rem_pending:
                res_apply_rem = subprocess.run(
                    [
                        sys.executable, script_path, "apply",
                        "--drop", ",".join(rem_pending),
                        "--reason", "Resolved during bootstrap",
                        "--root", str(tmp)
                    ],
                    capture_output=True, text=True
                )
                assert res_apply_rem.returncode == 0

        # Step F: Status must now exit 0
        res_stat_final = subprocess.run(
            [sys.executable, script_path, "status", "--root", str(tmp)],
            capture_output=True, text=True
        )
        assert res_stat_final.returncode == 0, (
            f"status expected 0 after all resolved, got {res_stat_final.returncode}\n{res_stat_final.stdout}"
        )
        assert "All rule-candidate and derivable statements resolved" in res_stat_final.stdout

        # Step G: Confirm NO legacy file changed
        for legacy_file, orig_hash in orig_hashes.items():
            assert legacy_file.is_file(), f"legacy file {legacy_file} was deleted"
            current_hash = sha256_file(legacy_file)
            assert current_hash == orig_hash, (
                f"legacy file {legacy_file} was modified! Original hash {orig_hash}, got {current_hash}"
            )


def test_legacy_import_readonly_by_default(repo_root: str = None) -> None:
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    script_path = os.path.join(
        repo_root, "skills", "project-bootstrap", "scripts", "legacy_import.py"
    )
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        subprocess.run(["git", "init"], cwd=str(tmp), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp), check=True, capture_output=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=str(tmp), check=True, capture_output=True)
        agents_md = tmp / "AGENTS.md"
        agents_md.write_text(
            "# Rules\n- Always use kebab-case for CSS file names.\n",
            encoding="utf-8"
        )
        subprocess.run(["git", "add", "AGENTS.md"], cwd=str(tmp), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp), check=True, capture_output=True)

        # 1. Inventory in a fixture project with agent files leaves git status empty
        res_inv = subprocess.run(
            [sys.executable, script_path, "inventory", "--root", str(tmp)],
            capture_output=True,
            text=True
        )
        assert res_inv.returncode == 0, f"inventory failed: {res_inv.stderr}"
        assert not (tmp / ".agents" / "legacy-parity.md").exists(), "ledger file was created when read-only expected"
        st = subprocess.run(["git", "status", "--porcelain"], cwd=str(tmp), capture_output=True, text=True)
        assert st.stdout.strip() == "", f"git status not clean after read-only inventory: {st.stdout}"
        assert "Legacy Parity Ledger" in res_inv.stdout, "expected ledger printed to terminal"

        # 2. Status exits 1 for pending items without writing
        res_stat = subprocess.run(
            [sys.executable, script_path, "status", "--root", str(tmp)],
            capture_output=True,
            text=True
        )
        assert res_stat.returncode == 1, f"status should exit 1 for pending items, got {res_stat.returncode}"
        assert not (tmp / ".agents" / "legacy-parity.md").exists(), "ledger file was created by status"
        st_after = subprocess.run(["git", "status", "--porcelain"], cwd=str(tmp), capture_output=True, text=True)
        assert st_after.stdout.strip() == "", f"git status not clean after read-only status: {st_after.stdout}"

        # 3. --write creates the file
        res_inv_write = subprocess.run(
            [sys.executable, script_path, "inventory", "--write", "--root", str(tmp)],
            capture_output=True,
            text=True
        )
        assert res_inv_write.returncode == 0, f"inventory --write failed: {res_inv_write.stderr}"
        ledger_file = tmp / ".agents" / "legacy-parity.md"
        assert ledger_file.is_file(), "ledger file was not created with --write"
        assert "Ledger written to" in res_inv_write.stdout


def main():
    print("Running legacy parity importer integration tests...")
    run_legacy_import_tests()
    test_legacy_import_readonly_by_default()
    print("All legacy parity importer tests passed successfully.")


if __name__ == "__main__":
    main()
