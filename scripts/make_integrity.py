#!/usr/bin/env python3
"""Generate integrity.json hash manifest for skills in Build Forge."""
import os
import sys
import json
import hashlib


def hash_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        normalized = content.replace("\r\n", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    except UnicodeDecodeError:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()


def compute_manifest(repo_root):
    skills_dir = os.path.join(repo_root, "skills")
    manifest = {}
    if not os.path.isdir(skills_dir):
        return manifest

    for root, dirs, files in os.walk(skills_dir):
        dirs.sort()
        for f in sorted(files):
            file_path = os.path.join(root, f)
            rel_path = os.path.relpath(file_path, repo_root).replace("\\", "/")
            manifest[rel_path] = hash_file(file_path)
    return manifest


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    manifest = compute_manifest(repo_root)
    out_path = os.path.join(repo_root, "integrity.json")

    if "--check" in sys.argv:
        if not os.path.isfile(out_path):
            print("ERROR: integrity.json does not exist.")
            sys.exit(1)
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception as e:
            print(f"ERROR reading integrity.json: {e}")
            sys.exit(1)

        if existing == manifest:
            print(f"PASS: integrity.json is up to date ({len(manifest)} files).")
            sys.exit(0)
        else:
            print("FAIL: integrity.json differs from current skills/ directory.")
            sys.exit(1)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Generated integrity.json with {len(manifest)} files.")


if __name__ == "__main__":
    main()
