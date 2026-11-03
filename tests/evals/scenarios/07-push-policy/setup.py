#!/usr/bin/env python3
"""Setup script for scenario 07-push-policy."""
import sys
from pathlib import Path

# Add tests/evals to sys.path
evals_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(evals_dir))

from eval_utils import copy_fixture, create_workdir, init_git_repo, save_baseline


def setup_scenario(dest: str = None) -> Path:
    workdir = create_workdir(prefix="bf-eval-07-", dest=dest)
    copy_fixture("existing-app", workdir)
    meta = init_git_repo(workdir, bare_remote=True)
    save_baseline(workdir, ["src/storage.js"], meta)
    return workdir


if __name__ == "__main__":
    dest_arg = sys.argv[1] if len(sys.argv) > 1 else None
    workdir_path = setup_scenario(dest_arg)
    print(str(workdir_path))
