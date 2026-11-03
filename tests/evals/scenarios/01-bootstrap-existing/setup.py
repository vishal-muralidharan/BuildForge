#!/usr/bin/env python3
"""Setup script for scenario 01-bootstrap-existing."""
import os
import shutil
import sys
from pathlib import Path

# Add tests/evals to sys.path
evals_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(evals_dir))

from eval_utils import copy_fixture, create_workdir, init_git_repo, save_baseline


def setup_scenario(dest: str = None) -> Path:
    workdir = create_workdir(prefix="bf-eval-01-", dest=dest)
    copy_fixture("existing-app", workdir)

    # Remove existing Build Forge files so app is unbootstrapped
    agents_dir = workdir / ".agents"
    if agents_dir.exists():
        shutil.rmtree(agents_dir)
    agents_md = workdir / "AGENTS.md"
    if agents_md.exists():
        agents_md.unlink()
    repo_map = workdir / "docs" / "repo-map.md"
    if repo_map.exists():
        repo_map.unlink()

    meta = init_git_repo(workdir)
    save_baseline(workdir, ["package.json", "src/storage.js", "src/tokens.css"], meta)
    return workdir


if __name__ == "__main__":
    dest_arg = sys.argv[1] if len(sys.argv) > 1 else None
    workdir_path = setup_scenario(dest_arg)
    print(str(workdir_path))
