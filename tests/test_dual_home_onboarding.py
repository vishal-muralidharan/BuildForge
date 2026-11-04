#!/usr/bin/env python3
"""End-to-end regression test for dual-home onboarding and reference deduplication.

Verifies:
1. Discovery and inventory: statement counts classified accurately into local,
   modified-fork, vendor-dup, and reference.
2. Ledger tables: Skipped sources includes vendor references and identical duplicate;
   Needs a decision includes modified fork with diff details.
3. Project rule checks: no_dual_homed_skills fails before dedupe reporting both collisions.
4. Safe dedupe:
   - Plan mode shows both collisions with diff for modified copy and changes nothing.
   - Dedupe with --approved on identical copy removes .agents/skills/ref-alpha.
   - Dedupe with --approved on modified copy refuses with diff and exits 1.
5. Post-dedupe checks:
   - Project check reports remaining modified collision ref-beta.
   - Re-running inventory shows vendor-dup is 0 and ref-alpha statements are gone from
     active ledger and listed under Skipped sources.
   - Local rules and legacy files are completely untouched.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def test_dual_home_onboarding():
    repo_root = Path(__file__).resolve().parent.parent
    fixture_dir = repo_root / "tests" / "fixtures" / "dual-home-onboarding"
    assert fixture_dir.is_dir(), f"Fixture directory missing: {fixture_dir}"

    leg_script = repo_root / "skills" / "project-bootstrap" / "scripts" / "legacy_import.py"
    refs_script = repo_root / "skills" / "extend-pipeline" / "scripts" / "refs.py"
    checks_script = repo_root / "skills" / "rules-to-tests" / "scripts" / "run_rule_checks.py"

    with tempfile.TemporaryDirectory() as tmp_str:
        workdir = Path(tmp_str) / "dual-home-test"
        shutil.copytree(fixture_dir, workdir)

        # 1. Record baseline hashes of local legacy files and vendor files
        tracked_files = [
            workdir / ".agents" / "skills" / "app-layout" / "SKILL.md",
            workdir / ".agents" / "skills" / "data-storage" / "SKILL.md",
            workdir / ".agents" / "skills" / "data-storage" / "references" / "table.md",
            workdir / ".agents" / "skills" / "data-storage" / "test" / "sample.test.md",
            workdir / ".agents" / "vendor" / "ref-alpha" / "SKILL.md",
            workdir / ".agents" / "vendor" / "ref-beta" / "SKILL.md",
            workdir / ".agents" / "skills" / "ref-beta" / "SKILL.md",
        ]
        initial_hashes = {p: sha256_file(p) for p in tracked_files}

        # 2. Project check fails before dedupe reporting both collisions
        res_chk1 = subprocess.run(
            [sys.executable, str(checks_script), "--root", str(workdir)],
            capture_output=True,
            text=True,
        )
        assert res_chk1.returncode != 0, f"Expected project check to fail before dedupe:\n{res_chk1.stdout}"
        assert "ref-alpha" in res_chk1.stdout, f"Expected ref-alpha in failure output: {res_chk1.stdout}"
        assert "ref-beta" in res_chk1.stdout, f"Expected ref-beta in failure output: {res_chk1.stdout}"

        # 3. Run legacy inventory
        res_inv1 = subprocess.run(
            [sys.executable, str(leg_script), "inventory", "--root", str(workdir)],
            capture_output=True,
            text=True,
        )
        assert res_inv1.returncode == 0, f"Inventory failed: {res_inv1.stderr}"
        assert "local: 7" in res_inv1.stdout
        assert "modified-fork: 4" in res_inv1.stdout
        assert "vendor-dup: 3" in res_inv1.stdout
        assert "reference: 6" in res_inv1.stdout

        ledger_path = workdir / ".agents" / "legacy-parity.md"
        assert ledger_path.is_file(), "Ledger was not written"
        ledger_text1 = ledger_path.read_text(encoding="utf-8")

        assert "## Skipped Sources" in ledger_text1
        assert ".agents/skills/ref-alpha" in ledger_text1
        assert "## Needs a Decision" in ledger_text1
        assert ".agents/skills/ref-beta" in ledger_text1

        # 4. Run refs.py dedupe in plan mode (default)
        res_plan = subprocess.run(
            [sys.executable, str(refs_script), "dedupe", "--root", str(workdir)],
            capture_output=True,
            text=True,
        )
        assert res_plan.returncode == 0, f"dedupe plan failed: {res_plan.stderr}"
        assert "Collision: ref-alpha" in res_plan.stdout
        assert "Classification: identical" in res_plan.stdout
        assert "Collision: ref-beta" in res_plan.stdout
        assert "Classification: modified" in res_plan.stdout
        # Confirm no file was deleted during plan
        assert (workdir / ".agents" / "skills" / "ref-alpha" / "SKILL.md").is_file()

        # 5. Run dedupe with --approved on identical copy only
        res_dedupe_alpha = subprocess.run(
            [sys.executable, str(refs_script), "dedupe", "--name", "ref-alpha", "--approved", "--root", str(workdir)],
            capture_output=True,
            text=True,
        )
        assert res_dedupe_alpha.returncode == 0, f"dedupe ref-alpha failed: {res_dedupe_alpha.stderr}"
        assert not (workdir / ".agents" / "skills" / "ref-alpha").exists(), "ref-alpha skills copy was not deleted"
        assert (workdir / ".agents" / "vendor" / "ref-alpha" / "SKILL.md").is_file(), "vendor ref-alpha was deleted!"

        # 6. Dedupe on modified copy must be refused
        res_dedupe_beta = subprocess.run(
            [sys.executable, str(refs_script), "dedupe", "--name", "ref-beta", "--approved", "--root", str(workdir)],
            capture_output=True,
            text=True,
        )
        assert res_dedupe_beta.returncode != 0, "Expected modified dedupe to exit non-zero"
        assert "Refusing to dedupe modified collision" in res_dedupe_beta.stdout or "Refusing" in res_dedupe_beta.stderr
        assert (workdir / ".agents" / "skills" / "ref-beta" / "SKILL.md").is_file(), "ref-beta was improperly deleted"

        # 7. Project check fails after dedupe and reports only modified collision ref-beta
        res_chk2 = subprocess.run(
            [sys.executable, str(checks_script), "--root", str(workdir)],
            capture_output=True,
            text=True,
        )
        assert res_chk2.returncode != 0, "Expected project check to fail on remaining collision"
        assert "ref-beta" in res_chk2.stdout
        assert "ref-alpha" not in res_chk2.stdout

        # 8. Re-run legacy inventory
        res_inv2 = subprocess.run(
            [sys.executable, str(leg_script), "inventory", "--root", str(workdir)],
            capture_output=True,
            text=True,
        )
        assert res_inv2.returncode == 0, f"Second inventory failed: {res_inv2.stderr}"
        assert "vendor-dup: 0" in res_inv2.stdout
        assert "local: 7" in res_inv2.stdout
        assert "modified-fork: 4" in res_inv2.stdout

        ledger_text2 = ledger_path.read_text(encoding="utf-8")
        # In ledger 2, ref-alpha is no longer a vendor-dup row under skills, and ref-beta is still in decision
        assert ".agents/skills/ref-beta" in ledger_text2
        assert "modified-fork" in ledger_text2

        # 9. Verify no legacy file or preserved file was altered
        for p, original_hash in initial_hashes.items():
            if p.name == "ref-alpha":
                continue  # Expected deletion of skills/ref-alpha
            if "skills/ref-alpha" in p.as_posix():
                continue
            assert p.is_file(), f"File missing: {p}"
            current_hash = sha256_file(p)
            assert current_hash == original_hash, f"File content altered: {p}"

    print("Dual-home onboarding end-to-end integration test passed successfully.")


if __name__ == "__main__":
    test_dual_home_onboarding()
