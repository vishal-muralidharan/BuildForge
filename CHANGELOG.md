# Changelog

All notable changes to Build Forge will be documented in this file.

## [Unreleased]

### Added
- The `verify` command to inspect installed pipeline skill integrity.
- `.agents/build-forge.lock.json` lock file generated upon install.
- `integrity.json` checksum manifest for package verification.

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
