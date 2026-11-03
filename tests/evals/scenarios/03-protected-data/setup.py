#!/usr/bin/env python3
"""Setup script for scenario 03-protected-data."""
import sys
from pathlib import Path

# Add tests/evals to sys.path
evals_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(evals_dir))

from eval_utils import copy_fixture, create_workdir, init_git_repo, save_baseline


def setup_scenario(dest: str = None) -> Path:
    workdir = create_workdir(prefix="bf-eval-03-", dest=dest)
    copy_fixture("existing-app", workdir)
    meta = init_git_repo(workdir)
    save_baseline(workdir, ["data/users.json"], meta)
    return workdir


if __name__ == "__main__":
    dest_arg = sys.argv[1] if len(sys.argv) > 1 else None
    workdir_path = setup_scenario(dest_arg)
    print(str(workdir_path))
