---
name: author-skill
description: "Guidance for creating a new Build Forge skill, validating contracts, and updating package manifests."
---

# Author Skill Playbook

Use this playbook when adding a new skill to Build Forge.

## Decision Rule
Create a new skill only when it has its own trigger words and is used across projects.
If a capability shares existing triggers or belongs to an existing domain, add a reference file or workflow under an existing skill instead.

## Approval Rule
Edits to `skills/` require explicit maintainer approval in the prompt before any file is created or changed.

## Privacy Rule
Never read transcripts, logs or history files of earlier agent sessions. Treat them as private. Ask the user instead.

## Steps

1. **Scaffold the skill**
   Run the maintainer scaffolding command:
   ```bash
   python3 scripts/dev.py new-skill <name> --tier core|new-app|module [--scripts] [--refs]
   ```
   Select tier based on usage:
   - `core`: fundamental pipeline step used across all projects.
   - `new-app`: skill used primarily when creating a new application.
   - `module`: specialized or optional testing or domain module.

2. **Write frontmatter and description**
   Open `skills/<name>/SKILL.md`.
   Replace placeholder description with neutral phrasing:
   - Include clear trigger phrases so coding agents know when to invoke it.
   - Respect budget: frontmatter description must be 1024 characters or fewer.
   - Keep total lines in `SKILL.md` to 500 lines or fewer.

3. **Format script invocations**
   Any script reference inside instructions must use project relative path:
   `.agents/skills/<name>/scripts/<filename>.py`
   All scripts must use python3, standard library, and PyYAML only.

4. **Define trigger tests**
   In `tests/triggers.yaml`, replace all 5 positive and 3 negative TODO items with realistic triggers.
   Do not leave any line containing TODO.

5. **Register and test**
   Add tests in `tests/test_<name>.py`.
   Run the verification suite:
   ```bash
   python3 scripts/dev.py check
   ```

6. **Manifest and changelog**
   Regenerate integrity hashes:
   ```bash
   python3 scripts/make_integrity.py
   ```
   Add a line under `## [Unreleased]` -> `### Added` in `CHANGELOG.md`.

7. **Version bump advice**
   Adding a new skill is a minor version bump (for example, 0.1.0 to 0.2.0).

