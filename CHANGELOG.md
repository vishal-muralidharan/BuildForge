# Changelog

All notable changes to Build Forge will be documented in this file.

## [Unreleased]

### Added
- `link` command in `bin/build-forge.js` to create relative symlinks or junctions for coding agents.
- `unlink` command in `bin/build-forge.js` to remove symlinks pointing to `.agents/skills`.
- `--agents <ids|auto|all>` CLI flag for `install`, `link`, and `unlink`.
- Automatic pointer file creation (`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.cursorrules`, `.windsurfrules`).
- [COMPATIBILITY.md](COMPATIBILITY.md) with agent compatibility matrix, test checklist, and known limits.

### Changed
- Conformed all 11 skills to Agent Skills specification frontmatter.
- Updated skill wording to vendor-neutral language.
- Replaced placeholder script paths with explicit project-relative paths.
- Standardized Python execution on `python3` across all skills.

## [0.1.0] - 2026-11-02

### Added
- Initial release of Build Forge (`@v1006/build-forge`).
- 11 core agent skills:
  - `product-spec`: Idea to spec, milestones, and non-goals.
  - `project-bootstrap`: Single source of truth profile and guidance generation.
  - `scaffold-app`: Green skeleton scaffolding for new apps.
  - `rules-to-tests`: Automated tests for project conventions.
  - `audit-and-planning`: Search, diagnose, and atomic plan.
  - `repo-search`: Read-only discovery and repo map refresh.
  - `atomic-commits`: Single-purpose commits with checked messages.
  - `feature-delivery`: 7-stage gated pipeline conductor.
  - `targeted-module-testing`: Verification, deploy loop, and post-build audit.
  - `sync-skills-and-docs`: Profile, skill, and doc drift detection.
  - `legal-and-settings-pages`: Settings, legal templates, consent, export, and deletion.
- CLI installer for `@v1006/build-forge`.
