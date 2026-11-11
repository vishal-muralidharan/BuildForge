---
name: review-directory-structure
description: Use this skill to place new files or move files in Build Forge. Describes each source layer and the root cleanliness rule.
---
<!-- build-forge:generated v1 body=12ab9cad3068730e4ba8bf2ffb2d4c56df49b6b091ba43e63711cd6e41c0212a -->

<!-- Generated from .agents/project-profile.yaml by project-bootstrap. Edit the profile, then re-render. -->

# Directory structure of Build Forge

| Path | Purpose |
|---|---|
| `bin` | The CLI |
| `skills` | The product, 1 folder per skill |
| `scripts` | Repo tools |
| `tests` | Fixtures and tests |
| `maintainers` | Playbooks and recipes |
| `.github` | CI and templates |
| `.agents` | Installed copies and project profile |

Tests: live in a tests folder.

## Root

Allowed in the repo root: `.agents`, `.claude`, `.editorconfig`, `.gitattributes`, `.github`, `.gitignore`, `.nvmrc`, `AGENTS.md`, `CHANGELOG.md`, `CLAUDE.md`, `COMPATIBILITY.md`, `CONTRIBUTING.md`, `GEMINI.md`, `LICENSE`, `MAINTAINING.md`, `README.md`, `SECURITY.md`, `UPGRADING.md`, `bin`, `integrity.json`, `maintainers`, `package.json`, `scripts`, `skills`, `tests`, `tiers.json`, `upgrade-notes.json`. Put nothing else there.

## Rules

- The repo root may only contain allowed files and directories. (enforced by test) `[repo-root-clean]`
- Only allowlisted root-level files and directories are allowed in the repository. (enforced by test) `[repo-allowlist]`
- The published package must not contain maintainers, scripts, tests, fixtures, or dotfiles. (enforced by test) `[repo-package-contents]`
- Python bytecode caches and pyc files must not exist in the repository. (enforced by test) `[repo-no-pyc]`

## Before you add a file

Search first with `repo-search`. Reuse or extend an existing file when it fits.
<!-- BEGIN CUSTOM: notes -->
<!-- END CUSTOM: notes -->
