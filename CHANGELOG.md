# Changelog

All notable changes to Build Forge will be documented in this file.

## [Unreleased]

### Added
- Skill contracts verification script `scripts/skill_contracts.py` and allowlist `scripts/contracts-allow.txt` enforcing script mentions, path existence, subcommand validity, and required text contracts.
- Skill contracts test suite `tests/test_skill_contracts.py` integrated into `scripts/ci_check.py`.
- Fictional reference profile `example-profile.yaml` for invented app `Pocketlog` with explicit warning banner.
- Scope candidate generation in `detect_stack.py` with validation that each candidate path matches existing files.
- Path and glob coverage validation in `validate_profile.py --root R` and strict failure mode with `--strict-paths`.
- Grouped glob and path validation in `check_sync.py`.
- Integration and unit tests in `tests/test_validate_profile.py` for glob mismatch warnings and strict validation.
- Markdown scanner `skills/sync-skills-and-docs/scripts/mdscan.py` for section and table extraction that ignores fenced code blocks.
- Python AST linter `scripts/lint_py.py` that fails on multi-character strip operations without `# strip-chars-ok:` comments and `./` prefixes in glob patterns.
- Integration test suite `tests/test_check_sync.py` verifying glob normalization, code block isolation, and AST linting rules.

### Fixed
- Fixed `check_sync.py` stripping leading dots from paths like `.agents/**` by introducing `strip_dot_slash`.
- Restricted skill discovery in `check_sync.py` to the Areas table's Skill column, preventing false warnings from the Scope guide table.
- Restricted scope discovery in `check_sync.py` to the Scope guide table.
- Fixed prefix stripping in `legacy_import.py` for references starting with `.`.
- Added troubleshooting row to `README.md` for false warnings from `check_sync`.
- Reference collision detection and deduplication tool `refs.py dedupe` in `skills/extend-pipeline/scripts/refs.py` resolving dual-homed references between `.agents/vendor` and `.agents/skills`.
- Machine check `no_dual_homed_skills` in `run_rule_checks.py` with `RUNNER_VERSION = 1` and validation schema support.
- Dual-home, orphan vendor folder, and rule runner version diagnostic checks in `bin/build-forge.js doctor`.
- Third-party skill awareness and classification in `skills/project-bootstrap/scripts/legacy_import.py` classifying sources into `build-forge`, `generated`, `reference`, `vendor-dup`, `modified-fork`, `likely-third-party`, and `local`.
- Ledger additions in `.agents/legacy-parity.md` including Skipped Sources and Needs a Decision tables, `--include-skipped` audit flag, and statement counts by source class.
- Evaluation Scenario 10 (`10-dual-home-onboarding`) in `tests/evals` and end-to-end regression test suite in `tests/test_dual_home_onboarding.py`.
- Suggest scope script in `skills/atomic-commits/scripts/suggest_scope.py` ranking commit scopes by file path globs.
- Scope guide table rendering in `AGENTS.md` Git section from `git.scopes`.
- Scope object support in project profile schema permitting `{name, purpose, paths}` mappings.
- Schema validation and negative tests for commit scope objects in `validate_profile.py` and `tests/test_validate_profile.py`.
- Suggest scope CI test suite in `tests/test_suggest_scope.py` wired into `scripts/ci_check.py`.
- Section "Self-explaining commit scopes" in `README.md`.
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
- Fixed root `.gitignore` pattern anchoring (`/.agents/`, `/.claude/`, `/.gemini/`) so that test fixtures containing nested `.agents/` folders remain tracked in Git and present in clean CI checkouts.
- Fixed relative path formatting in `render.py`, `check_sync.py`, and `refs.py` to output POSIX slashes (`Path.as_posix()`) across Linux, macOS, and Windows, avoiding path separator mismatches in terminal summaries and test assertions.
- Added cross-platform testing guidelines and path normalization conventions into native skills (`targeted-module-testing`, `project-bootstrap`, `rules-to-tests`, `feature-delivery`).
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
