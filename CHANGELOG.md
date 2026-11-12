# Changelog

All notable changes to Build Forge will be documented in this file.

## [Unreleased]

### Added
- Merge trail policy and maintainer playbook `maintainers/skills/merge-trail/SKILL.md` enforcing merge commits on `main`.
- First-parent git history checker `scripts/check_history.py` and baseline file `maintainers/history-baseline.txt`.
- Conventional commit message validator `scripts/check_commits.py`.
- Git merge trail viewer `scripts/dev.py trail` and repository settings auditor `scripts/dev.py repo-settings`.
- GitHub Actions CI workflow jobs `commit-lint` and `history` enforcing commit messages on pull requests and merge trail on `main`.

### Fixed
- B1: Legacy import inventory and status are read-only by default and write .agents/legacy-parity.md only when --write is passed.
- B2: Render scope guide outputs profile path and skips empty scope rows, formatting overflow as N more scopes: see <profile>.
- B3: Added check_preservation.py to verify non-generated lines across migration, rollout, or update.
- B4: Added rule forbidding agents from reading transcripts, logs, or history files of earlier sessions to guidelines and playbooks.
- B5: Added published root check to doctor to warn when repo root containing agent files may be published.
- Core tier in `tiers.json` lists the 10 dogfooded pipeline skills again (`project-bootstrap`, `rules-to-tests` and `targeted-module-testing` had been moved out of core), so `update` installs them and `remove` refuses them without `--force`. New test `tests/test_tiers.py` keeps the core tier equal to the dogfood set.
- `detect_stack.py` skips agent folders (`.agents`, `.claude`, `.cursor` and similar) when it counts source files, naming, token files and storage hints. Before, it proposed the installed `scaffold-app` token template as the project token file and reported false storage hints. It also answers `--help`. New test `tests/test_detect_stack.py`.
- `legacy_import.py` skips `.claude/skills` when it is a link or a copy made by `build-forge link`, and treats pointer files written by `link` as generated. Before, the linked Build Forge skills were read as user rules (1,153 statements and 278 false rule candidates on a 4 file app). Similarity checks use cached normalization and cheap upper bounds, so inventory on that app dropped from over 100 seconds to under 1 second with the same decisions. New test `tests/test_legacy_import_links.py`.

## [0.2.0] - 2026-11-09

### Security
- Updated third party skill vetting tool `refs.py vet` in `skills/extend-pipeline`:
  - New three-tier severity model: HIGH (exit code 1) for script extensions, shebang lines, executable permissions, zero-width and bidirectional unicode characters, instruction override phrases, and HTML comments containing instruction-like words or imperative verbs; MEDIUM for in-code install and download commands (`npx`, `npm install`, `pip install`, `curl | sh`), credential commands, outside path escapes, and network calls; LOW for informational prose keywords (`fetch`, `requests`, `token`, `socket`, `secret`, `password`) and placeholder comments (`<!-- e.g. ... -->`).
  - Output formatting prints summary counts per file, every HIGH and MEDIUM finding in full, and LOW findings collapsed into 1 count per file by default, with `--all` to expand and `--json` for machine-readable output.
  - Exact 1-based line numbers matching file lines.
  - Markdown-aware scanner distinguishing frontmatter, fenced code blocks, inline code, and prose.
  - Vetting summary printed at approval time during `refs.py add`, emphasizing review of HIGH and MEDIUM findings.

### Upgrading
- Safe, integrity-verified update workflow via `build-forge update`: hash verification against packaged `integrity.json`, pre-update modification guard with `--keep-modified` and `--restore`, core tier skill installation (`project-blueprints`), `--adopt` for adoption without lock files, and upgrade action reporting.
- Package integrity lock verification: locks are always generated from packaged `integrity.json` rather than disk files, ensuring kept or tampered skills are accurately reported as modified during verification.
- Offline integrity script `skills/project-bootstrap/scripts/verify_integrity.py` for headless verification against `build-forge.lock.json`.
- Per-file `render --update` execution exiting with code 3 when unstamped files are skipped, and recommending `--upgrade-unstamped` for old generator banner files.
- Safe overwrite protections requiring `--discard-edits` and `--yes-discard` together before overwriting unstamped content, with discarded line counts and dirty tree safety.
- Pre-overwrite patch archival saving unified diffs to `.agents/work/overwritten-<skill>.patch` on `update --restore`, and patch export via `build-forge diff --patch`.
- Consistent `SUPPORTED_SCHEMA_VERSIONS` constant across profile validation, migrations, doctor checks, and schema documentation.
- Non-destructive `.gitignore` configuration supporting `--no-gitignore`.
- Upgrade guide `UPGRADING.md` documenting step by step upgrade workflows across versions, and machine-readable actions in `upgrade-notes.json`.
- CLI command `upgrade done <action-id>` for recording completed upgrade actions in `.agents/upgrade-state.json`, `add <skill>` for installing optional skills, and `list` for browsing skills by tier.
- Unstamped convention skill upgrade in `render.py --upgrade-unstamped` upgrading 0.1.0 unstamped files carrying old generator banners to stamped templates while preserving custom blocks and salvaging non-generated lines into `salvaged` blocks.
- Doctor check reporting pending upgrade actions as warnings.

### Added
- Permanent clean-room packaging check `scripts/check_package.py` and test suite `tests/test_check_package.py` verifying npm pack tarball extraction, bin targets, forbidden files exclusion, tiers and integrity alignment, and multi-project CLI clean-room installation.
- Documentation truth check `scripts/check_docs_truth.py` verifying all documented CLI commands and Python scripts exist across documentation.
- Opt-in branch workflow configuration under `git.workflow` in project profile (`default_branch`, `mode`, `branch_format`, `sync`, `merge_method`, `remote`, `cleanup`, `worktree`).
- Task branch workflow tool `skills/feature-delivery/scripts/branchflow.py` supporting `status`, `start`, `guard`, `handoff`, `sync`, `merge-local`, `sync-main`, `park`, `resume`, `abandon`, `cleanup`, and `revert-plan`.
- Branch workflow reference guide `skills/feature-delivery/references/workflows/branch-mode.md` with state machine documentation and typed confirmation phrases.
- Branch workflow hooks in `feature-delivery` (Stage 0 branch prompt, Stage 8 handoff), `atomic-commits` (pre-commit guard check), and `targeted-module-testing` (manual Try it checklist).
- Branch workflow diagnostics in `build-forge doctor` (stale state files, merged uncleaned local branches, missing default branch) and `check_sync.py` (state files referencing missing git branches).
- Unit and integration test suite `tests/test_branchflow.py` covering all 17 lifecycle scenarios, stacked branches, worktrees, rebase phrase checks, and forbidden command static lints.
- Rule pack system in `skills/project-bootstrap/scripts/packs.py` supporting `list`, `show`, `plan`, `apply`, `diff`, and `lint` commands.
- 9 curated, opt-in rule packs in `skills/project-bootstrap/references/rule-packs/`: `native-controls`, `web-hazards`, `ui-states`, `mobile-web`, `shortcuts`, `a11y-basics`, `motion-basics`, `testing-practices`, and `browser-checks`.
- Rule pack schema validation in `validate_profile.py` supporting `rule_packs` (`[{id, version}]`), `rule.pack` (`<id>@<version>`), `dropped_pack_rules`, `enforced_by_ref: {file, contains}`, and `claim-unverified` warnings with `--strict-claims`.
- Dynamic variable expansion for `{{component_dirs}}` in rule checks with graceful skip when `design.component_dirs` is not configured.
- Comprehensive test suite `tests/test_rule_packs.py` covering lint, broken packs rejection, selftest, fixture probes, apply, conflict preservation on user edits, dropped rules persistence, diff after version bumps, and recipe verification.
- Rule pack `web-hazards` with checks, hints, and examples covering console logging, target=_blank rel attributes, raw eval, innerHTML/dangerouslySetInnerHTML, and committed .env files.
- Rule schema enhancements in `validate_profile.py` supporting `exceptions: [{path, reason}]`, check `hint`, and check `examples`.
- Check runner enhancements in `run_rule_checks.py` (version 2) supporting `--selftest`, `--explain <id>`, exception merging into excludes, and hint reporting on check failure.
- Hazard sweep scanner `skills/project-bootstrap/scripts/hazard_sweep.py` and bootstrap checklist integration for common stack hazards.
- Incident to rule workflow `skills/feature-delivery/references/workflows/incident-to-rule.md`, task router entry, final message rule gaps line, and Post-Build Audit rule gap question in `targeted-module-testing`.
- Test suite `tests/test_hazard_sweep.py` covering rule pattern matching, runner selftest and explain, exceptions, validate_profile enforcement, clean and flagged sweep scans, and skill contracts.
- Form controls analysis in UI blueprint analyzer `skills/project-blueprints/scripts/analyzers/ui.py` detecting native controls, low-level widgets, themed primitives, gap/violation status, and candidate proposals.
- Form controls guidance section in generated `build-ui` skill, `audit-and-planning` Phase 2 form control checklist, and `scaffold-app` component creation rule.
- Maintainer developer toolkit `scripts/dev.py` supporting `new-skill`, `check`, `impact`, `recipe`, `fixture`, and `release-plan`.
- Maintainer documentation and 4 playbooks under `maintainers/skills/`: `author-skill`, `author-extension`, `triage-field-report`, and `cut-release`.
- 8 maintainer change recipes in `maintainers/recipes/*.yaml` for repeatable touchpoint management.
- Test suite `tests/test_maintainer_tooling.py` verifying package exclusions, fixture validation, recipe integrity, and release planning.
- Trigger phrase test file `tests/triggers.yaml` and skill classification file `tiers.json`.
- Check flag `--check` in `scripts/make_integrity.py` for automated integrity manifest verification.
- Field adoption integration test suite `tests/test_field_adoption.py` verifying the full 10-step sequence across validation, salvage, adoption, synchronization, drift, doctor, and non-generated line survival property test.
- Field adoption test fixture `tests/fixtures/field-adoption` with invented stamped and unstamped convention skills, 60-line interface table, 200-line token table, oversized custom block, listed and unlisted vendor folders, and Scope guide table.
- Evaluation scenario 11 (`11-field-adoption`) in `tests/evals/scenarios/11-field-adoption/` with task specification, expectation matrix, setup script, and grader integration in `scripts/grade.py` and `tests/test_eval_grader.py`.
- Troubleshooting documentation in `README.md` covering lost content and salvage, collisions, false `check_sync` warnings, and unmatched glob/layer warnings.
- Maintainer guide additions in `MAINTAINING.md` covering skill contracts (`scripts/skill_contracts.py`) and Python AST linting rules (`scripts/lint_py.py`).
- Legacy import volume guard in `skills/project-bootstrap/scripts/legacy_import.py` quarantining folders producing > 100 statements or > 40% candidate share to `needs-decision`.
- Legacy import status grouping in `legacy_import.py` by source folder and class with selective exit 1 for pending local rule candidates, local derivables, or needs-decision sources.
- Blueprint contract routing via `legacy_import.py apply --route <ids>` and `apply --route-class derivable --yes` routing statements verbatim to `.agents/blueprints/<area>.md` under `contracts` blocks with evidence anchors.
- Multiline statement and interface table support in `legacy_import.py` preserving tables > 10 lines as 1 unit with roundtrip ledger escaping.
- Integration test suite `tests/test_legacy_import_routing.py` covering volume guard, interface table routing, evidence anchor generation, and selective exit 1 behavior.
- Content salvage and migration in `skills/project-bootstrap/scripts/render.py`: `--salvage` moves hand edits outside custom blocks into `salvaged` custom blocks, and `--migrate-custom` wraps unstamped skills into `legacy` blocks.
- Overflow routing in `render.py` moving blocks over limits (or unstamped files with tables/code blocks > 20 lines) through `blueprint adopt` or to `.agents/notes/<skill>.md`.
- Safeguards in `render.py`: `--force` behaves like `--salvage` by default; content discarding requires `--discard-edits` and `--yes-discard` together; uncommitted git changes guard with `--allow-dirty`; secret scan refusal.
- Deterministic render action ledger `.agents/render-log.md` recording paths, actions, and line counts without timestamps.
- Warning in `check_sync.py` when `salvaged` or `legacy` custom blocks exist.
- Test suite `tests/test_render_salvage.py` covering all 9 safeguard points, CRLF handling, git dirty tree fixtures, secret detection, idempotency, and non-generated line survival property test.
- Blueprint lifecycle commands `init`, `adopt`, `link-check`, and `drift` in `skills/project-blueprints/scripts/blueprint.py`.
- Canonical blueprint templates in `skills/project-blueprints/assets/templates/` for data, tokens, UI, and layout areas.
- Contract evidence anchor validation and custom block adoption pointers in `blueprint.py`.
- Test suite `tests/test_blueprint_lifecycle.py` verifying blueprint init idempotency, adopt atomicity, secret refusal, and anchor drift.
- Added `project-blueprints` pipeline skill (`skills/project-blueprints/`) with analyzers for data, tokens, UI, layout, auth, and config facts.
- Added `blueprint.py` CLI supporting `extract`, `verify`, `stale`, `show`, and `candidates` commands with line budget limits, secret scanning, and deterministic LF hashing.
- Added optional `blueprints` configuration and rule `evidence` path checking to `validate_profile.py`.
- Added blueprint querying hooks to `render.py` convention skills, `audit-and-planning`, `feature-delivery`, `check_sync.py`, and `targeted-module-testing`.
- Added integration test suite `tests/test_project_blueprints.py` and 4 test fixtures.
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
- Installer, update, and link commands skip `__pycache__`, `.pyc`, `.pyo`, and `.DS_Store` files, create `.agents/.gitignore` for Python caches, clean untracked caches in replaced skills, set `PYTHONDONTWRITEBYTECODE=1` for Python subprocesses, and warn on tracked or unignored caches in `doctor`.
- The package excludes python bytecode caches. Repo checks ignore untracked caches.
- Fixed `check_sync.py` stripping leading dots from paths like `.agents/**` by introducing `strip_dot_slash`.
- Restricted skill discovery in `check_sync.py` to the Areas table's Skill column, preventing false warnings from the Scope guide table.
- Restricted scope discovery in `check_sync.py` to the Scope guide table.
- Fixed prefix stripping in `legacy_import.py` for references starting with `.`.
- Added troubleshooting row to `README.md` for false warnings from `check_sync`.
- `update --dry-run` prints full update plan and `Blocked by:` list when local modifications exist instead of aborting immediately, exiting 0 if clean and 1 if blocked.
- Installed skills are explicitly tracked in `build-forge.lock.json` under `_installed`; `verify`, `doctor`, and `update` check installed skills only, ignoring uninstalled optional skills. Added `build-forge remove` command with core skill protection (`--force`).
- Obsolete pipeline files removed upstream are pruned on update across `update`, `update --restore`, and `install --force`, while user additions and locally modified files are preserved with warnings and backups.
- Unified integrity verification logic between `build-forge verify` and `build-forge doctor` using shared `checkSkillsIntegrity` to ensure consistent reporting of missing, modified, and extra files.
- Saved patch headers in `build-forge diff --patch` and `update --restore` use portable relative paths (`a/<path>`, `b/<path>`) compatible with `git apply`, and patches are skipped for unmodified upstream upgrades.
- Profile migration in `migrate_profile.py` uses line-based editing instead of `yaml.safe_dump`, preserving comments, quoting, indentation, line wrapping, and key order when bumping schema version to 2 and adding `blueprints`.
- Doctor blueprint check accepts "All blueprints are up to date." as clean status instead of reporting a false warning.
- Profile path validation in `validate_profile.py` and reference checking in `refs.py` warn instead of failing when referenced vendor paths are missing and `vendor_in_git` is false.
- Fresh install initializes `.agents/upgrade-state.json` with all current upgrade actions completed, and `update --dry-run` reports clean status when no updates are pending.
- Drift check `check_sync.py` ignores `.agents` directory during layer coverage scans.
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
