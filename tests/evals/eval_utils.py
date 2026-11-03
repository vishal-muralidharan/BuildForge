#!/usr/bin/env python3
"""Evaluation utilities for Build Forge scenario setup and grading."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def get_repo_root() -> Path:
    """Return the absolute path of the Build Forge repository root."""
    return Path(__file__).resolve().parent.parent.parent


def create_workdir(prefix: str = "bf-eval-", dest: str = None) -> Path:
    """Create or prepare a work directory."""
    if dest:
        dest_path = Path(dest).resolve()
        dest_path.mkdir(parents=True, exist_ok=True)
        return dest_path
    tmp = tempfile.mkdtemp(prefix=prefix)
    return Path(tmp).resolve()


def copy_fixture(fixture_name: str, dest_dir: Path) -> None:
    """Copy files from tests/evals/fixtures/<fixture_name> to dest_dir."""
    repo_root = get_repo_root()
    fixture_dir = repo_root / "tests" / "evals" / "fixtures" / fixture_name
    if not fixture_dir.is_dir():
        raise RuntimeError(f"Fixture directory not found: {fixture_dir}")

    for item in fixture_dir.iterdir():
        dest_item = dest_dir / item.name
        if item.is_dir():
            if dest_item.exists():
                shutil.rmtree(dest_item)
            shutil.copytree(item, dest_item)
        else:
            shutil.copy2(item, dest_item)


def hash_file(file_path: Path) -> str:
    """Compute sha256 hash of a file with normalized newlines."""
    if not file_path.is_file():
        return ""
    try:
        content = file_path.read_text(encoding="utf-8")
        normalized = content.replace("\r\n", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    except UnicodeDecodeError:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()


def init_git_repo(workdir: Path, bare_remote: bool = False) -> dict:
    """Initialize a git repository in workdir and optionally create a bare remote."""
    metadata = {}
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Build Forge Eval"
    env["GIT_AUTHOR_EMAIL"] = "eval@build-forge.local"
    env["GIT_COMMITTER_NAME"] = "Build Forge Eval"
    env["GIT_COMMITTER_EMAIL"] = "eval@build-forge.local"

    # Git init
    subprocess.run(["git", "init", "-b", "main"], cwd=str(workdir), env=env, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Build Forge Eval"], cwd=str(workdir), env=env, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "eval@build-forge.local"], cwd=str(workdir), env=env, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(workdir), env=env, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "chore: initial fixture commit"], cwd=str(workdir), env=env, check=True, capture_output=True)

    head_rev = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(workdir), env=env, capture_output=True, text=True, check=True
    ).stdout.strip()
    metadata["initial_head"] = head_rev

    if bare_remote:
        remote_dir = workdir.parent / f"{workdir.name}-remote.git"
        if remote_dir.exists():
            shutil.rmtree(remote_dir)
        subprocess.run(["git", "init", "--bare", str(remote_dir)], env=env, check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(remote_dir)], cwd=str(workdir), env=env, check=True, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=str(workdir), env=env, check=True, capture_output=True)
        metadata["bare_remote"] = str(remote_dir)
        metadata["remote_head"] = head_rev

    return metadata


def save_baseline(workdir: Path, tracked_files: list[str], extra_meta: dict = None) -> None:
    """Save baseline hashes of tracked files and metadata to .eval_baseline.json."""
    data = {
        "files": {},
        "metadata": extra_meta or {},
    }
    for rel_path in tracked_files:
        fpath = workdir / rel_path
        if fpath.is_file():
            data["files"][rel_path] = hash_file(fpath)
    baseline_file = workdir / ".eval_baseline.json"
    baseline_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
