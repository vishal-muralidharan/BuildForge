# Changelog

All notable changes to Build Forge will be documented in this file.

## [Unreleased]

### Added
- Custom block support in `render.py` (`<!-- BEGIN CUSTOM: name -->` ... `<!-- END CUSTOM: name -->`) preserving handwritten notes byte for byte across updates.
- Stamping mechanism in `render.py` (`<!-- build-forge:generated v1 body=<sha256> -->`) tracking generated body hashes outside custom blocks.
- `--update` flag in `render.py` regenerating stamped files, restoring custom blocks, and refusing files with hand edits outside custom blocks with a unified diff.
- `--overwrite-unstamped` guard in `render.py` preventing `--force` from modifying unstamped files without explicit confirmation.
- Custom block orphan preservation writing displaced blocks to `.agents/custom-orphans.md`.
- Secret pattern and line limit scanning for custom blocks in `render.py`.
- Drift detection for unblocked edits, orphan blocks, and oversize blocks in `check_sync.py`.
- Guide section "Adding your own notes to generated skills" in `README.md`.
- Integration test suite in `tests/test_render_custom_blocks.py` integrated into `scripts/ci_check.py`.
- Agent evaluation harness under `tests/evals/` with 4 fixtures (`existing-app`, `empty-folder`, `legacy-rules`, `injected-reference`) and 9 evaluation scenarios.
- Evaluation grader CLI in `scripts/grade.py` scoring scenario outputs against `expect.yaml` without calling an LLM.
- Evaluation runbook and recording instructions in `tests/evals/README.md`.
- Grader integration test suite in `tests/test_eval_grader.py` verifying passing and failing states across all 9 scenarios, wired into `scripts/ci_check.py`.
- `doctor` command in `bin/build-forge.js` diagnosing Node.js, Python 3, PyYAML, git, lockfile integrity, profile validity, references, blueprints, links, AGENTS.md, and legacy parity.
- `outdated` command in `bin/build-forge.js` comparing installed lockfile version against latest release on npm.
- `update` command in `bin/build-forge.js` with pre-verification safety checks and profile migration planning.
- Profile migration framework in `skills/project-bootstrap/scripts/migrate_profile.py` supporting `plan` and `apply` across schema versions while preserving user rules and custom fields.
- Lifecycle integration test suite in `tests/test_lifecycle.py` integrated into `scripts/ci_check.py`.
- Lifecycle management guide in `README.md` and migration authoring guide in `MAINTAINING.md`.
- 3 task workflow references in `skills/feature-delivery/references/workflows/`: `fix-bug.md`, `review-changes.md`, and `release-prep.md`.
- Task router table in `skills/feature-delivery/SKILL.md` mapping request types to workflow references.
- Automated CI check verifying that task workflow references exist, are linked from `SKILL.md`, and contain all required sections.
- Legacy parity importer in `skills/project-bootstrap/scripts/legacy_import.py` with `inventory`, `batch`, `apply`, and `status` commands.
- Parity ledger at `.agents/legacy-parity.md` tracking statement coverage, class, and resolution status.
- Blueprint fact reconciliation for derivable tokens, data, layout, and UI statements in `legacy_import.py`.
- Integration test fixture in `tests/test_legacy_import.py` and wired into `scripts/ci_check.py`.
- `extend-pipeline` skill to manage third party references with security vetting and commit pinning.
- `skills/extend-pipeline/scripts/refs.py` CLI to fetch, vet, add, list, verify, update, remove, restore, and check due references.
- Security vetting specification in `skills/extend-pipeline/references/vetting.md` covering 9 risk categories.
- Dedicated `.agents/references.yaml` configuration file and `.agents/references.lock.json` hash manifest.
- Local git fixture test suite for the references system in `scripts/ci_check.py`.
- `link` command in `bin/build-forge.js` to create relative symlinks or junctions for coding agents.
- `unlink` command in `bin/build-forge.js` to remove symlinks pointing to `.agents/skills`.
- `--agents <ids|auto|all>` CLI flag for `install`, `link`, and `unlink`.
- Automatic pointer file creation (`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.cursorrules`, `.windsurfrules`).
- [COMPATIBILITY.md](COMPATIBILITY.md) with agent compatibility matrix, test checklist, and known limits.
- `ALLOWED_SKILLS` constant in `scripts/ci_check.py`; CI now fails if `skills/`, `integrity.json`, or the npm pack file list contains a folder not in the allowlist.
- `status` command in `bin/build-forge.js` reporting environment versions, project profile, installed skills, lockfile integrity, vendor references, and agent links.
- `diff` command in `bin/build-forge.js` comparing installed core skills in `.agents/skills` against bundled package skills.
- Goal-oriented verification loop in `feature-delivery` that iterates until measurable acceptance invariants in `.agents/work/CURRENT_GOAL.md` are proven true.
- Pre-flight branch gate (Stage 0) in `feature-delivery` preventing direct commits to `main` or `master`.
- Atomic rollback protocol in `feature-delivery` reverting changes cleanly after 2 consecutive verify failures.
- Goal acceptance verification in `targeted-module-testing` (Section 2b) and Post-Build Audit reporting.
- GitHub Actions workflow template in `skills/rules-to-tests/assets/rules-ci.yml` for automated rule check enforcement on PRs.
- `scripts/make_integrity.py` and `integrity.json` hash manifest recording SHA-256 hashes of all skills.
- Automatic `.gitignore` updating during `build-forge install` to ignore `.agents/work/` and `.agents/vendor/`.
- CI smoke test coverage for `status`, `diff`, and `.gitignore` auto-ignore in `scripts/ci_check.py`.
- `check_integrity_manifest` in `scripts/ci_check.py` verifying the skills tree against `integrity.json`.

### Changed
- Updated `sync-skills-and-docs` guidance and documentation to use `render.py --update` instead of `--force`.
- Expanded `feature-delivery` skill description to trigger on fix, review, and release requests.
- Updated `project-bootstrap` existing mode to inventory legacy agent files and require parity resolution before completing bootstrap.
- Scoped `computeSkillsManifest` in `bin/build-forge.js` to core package skills so project custom convention skills in `.agents/skills` are never locked or flagged during verification.
- Updated total pipeline skill count from 11 to 12.
- Integrated reference checks into `audit-and-planning`, `targeted-module-testing`, `feature-delivery`, `scaffold-app`, `legal-and-settings-pages`, and `sync-skills-and-docs`.
- Deprecated `external_references` field in `.agents/project-profile.yaml` in favor of `.agents/references.yaml`.
- Conformed all 12 skills to Agent Skills specification frontmatter.
- Updated skill wording to vendor-neutral language.
- Replaced placeholder script paths with explicit project-relative paths.
- Standardized Python execution on `python3` across all skills.

### Fixed
- Fixed cross-platform wildcard handling on Windows CI runners in `tests/evals/fixtures/existing-app/package.json` by replacing `"node --test tests/*.test.js"` with `"node --test"` to rely on Node's native recursive test discovery without depending on shell wildcard expansion.
- Resolved cross-platform CI failures on Windows by invoking `npm` with `shell=(sys.platform == "win32")` in `scripts/ci_check.py` and `scripts/grade.py`.
- Fixed bare git remote HEAD resolution on Linux and macOS CI runners in evaluation scenario 7 by explicitly initializing bare remotes with `-b main` and pointing symbolic-ref to `refs/heads/main`.
- Added repository `.gitignore` ignoring local agent skills (`.agents/`), caches, and build artifacts.
- Documented cross-platform CI failure causes and prevention rules in `MAINTAINING.md`.
- Removed third-party skill folders that were included in the package without authorisation.

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
