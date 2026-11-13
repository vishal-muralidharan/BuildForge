# Maintainer Guide

This guide covers publishing, skill changes, testing, and repository settings for maintainers of `@v1006/build-forge`.

The rules in the local `AGENTS.md` (see Local development pipeline below) and in this guide apply to all work in this repository.

This repository uses its own installed pipeline skills in `.agents/skills/`. For all development tasks, follow the pipeline skills (`audit-and-planning`, `feature-delivery`, `targeted-module-testing`, `atomic-commits`, `sync-skills-and-docs`). Never edit skills directly in `.agents/skills/`; always edit in `skills/` with maintainer approval and run `python3 scripts/dev.py dogfood sync`.

### Local development pipeline (not in git)

The installed pipeline (`.agents/`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and the other agent pointer files) is a local development aid. Git ignores it, so it does not show on GitHub and CI does not use it. After a fresh clone, create it with:

```bash
python3 scripts/dev.py dogfood sync
```

Then render the agent files with your coding agent, or copy them from your previous clone. Without them, every script and test in this repository still works. `python3 scripts/dev.py dogfood check` prints `not adopted` and still checks that the skill lists in `scripts/dogfood.py` match `skills/`.

## Maintainer toolkit (`scripts/dev.py`)

Maintainer tasks use `scripts/dev.py`:
- Scaffold a new skill: `python3 scripts/dev.py new-skill <name> --tier core|new-app|module [--scripts] [--refs]`
  `new-skill` also registers the skill in `scripts/dogfood.py` (`DOGFOOD_SET` for core, `DOGFOOD_EXCLUDED` otherwise) and in `ALLOWED_SKILLS` in `scripts/ci_check.py`, so CI does not fail on a missing entry. For a core skill, run `python3 scripts/dev.py dogfood sync` afterward.
- Run checks: `python3 scripts/dev.py check [--fast]`
- Search impact: `python3 scripts/dev.py impact <token>`
- Manage recipes: `python3 scripts/dev.py recipe list | show <name> | verify <name> --arg key=value`
- Manage fixtures: `python3 scripts/dev.py fixture new <name> | check`
- Release readiness: `python3 scripts/dev.py release-plan`

For playbooks, recipes, and templates, see [maintainers/README.md](maintainers/README.md).

## Release steps

Follow these steps to publish a new release:

1. Run `python3 scripts/dev.py release-plan` to inspect readiness and suggested bump.
2. Update the version number in `package.json`.
3. Run `python3 scripts/make_integrity.py` to refresh `integrity.json`.
4. Run `python3 scripts/dev.py check` to ensure all checks pass.
5. Run `python3 scripts/check_package.py` to verify package contents and clean-room installation.
6. Run `npm pack --dry-run` and inspect the packaged file list (assert `maintainers/` and `scripts/` are excluded).
7. Commit the version bump, integrity manifest, and doc updates on a task branch. Open a pull request and merge it with a merge commit (`gh pr merge <number> --merge`). A release tag always points at a merge commit on `main`. Never squash or rebase merge.
8. Switch to `main`, run `git pull --ff-only`, and create and push a git tag `v<version>` (for example, `git tag v0.2.0 && git push origin v0.2.0`).
9. In GitHub Actions, approve the deployment to the "release" environment so `publish.yml` executes.

## Merge policy

Build Forge enforces a strict merge trail policy to preserve a clear git history:

1. Every change reaches `main` only through a pull request, merged with a merge commit (GitHub "Create a merge commit", or `gh pr merge <number> --merge`). Never squash. Never rebase and merge.
2. Never push to `main` directly.
3. One branch per task, named `<type>/<slug>`.
4. Every commit on a branch is a meaningful unit with a conventional commit subject. No `WIP`, `fixup!`, `squash!`, or "address review" commits. Fix the last unpushed commit with `git commit --amend`. After a push, add new commits with real subjects.
5. Never merge `main` into a feature branch. If a branch falls behind `main`, ask the maintainer. Agents never rebase or force push.
6. Keep GitHub's default merge commit message so the trail reads like the existing history.
7. Dependabot PRs follow the same rules.
8. History on `main` is never rewritten. Direct commits that predate this policy are listed in `maintainers/history-baseline.txt` with the reason.
9. A release tag always points at a merge commit on `main`.

### Repository settings

Maintainers must configure GitHub repository settings to enforce this policy:
- **Merge commits**: On (allowed).
- **Squash merging**: Off (disabled).
- **Rebase merging**: Off (disabled).
- **Require linear history**: Off (disabled so merge commits are permitted).
- **Enforce on administrators**: On (admin bypass off).
- **Required status checks**: `CI` and `commit-lint` (note: `commit-lint` becomes a required check after it has run once).

Run `python3 scripts/dev.py repo-settings` to audit live repository settings against these requirements.

## How to change a skill

1. Changes to files under `skills/` require prior maintainer approval.
2. Read the playbook at `maintainers/skills/author-skill/SKILL.md`.
3. Make approved modifications.
4. Regenerate `integrity.json` by running `python3 scripts/make_integrity.py`.
5. Sync installed dogfood skills: `python3 scripts/dev.py dogfood sync`.
6. Add an entry describing the changes in [CHANGELOG.md](CHANGELOG.md).
7. Verify changes with `python3 scripts/dev.py check` and `python3 scripts/dev.py dogfood check`.

## How to test locally

1. Run `npm pack` in the repo root to create a tarball (`v1006-build-forge-<version>.tgz`).
2. In a temporary directory, extract the tarball:
   ```bash
   tar -xzf /path/to/v1006-build-forge-<version>.tgz
   ```
3. Run the installer from the extracted package into another test folder:
   ```bash
   node package/bin/build-forge.js
   ```
4. Run verification in the test folder:
   ```bash
   node package/bin/build-forge.js verify
   ```
5. Confirm that `.agents/build-forge.lock.json` was created and that verification exits with code 0.
6. Test agent linking and unlinking:
   ```bash
   node package/bin/build-forge.js link --agents claude
   node package/bin/build-forge.js verify
   node package/bin/build-forge.js unlink --agents claude
   ```
7. Confirm that `.claude/skills` was created as a symlink pointing to `.agents/skills`, that `verify` exited 0 through the link, and that `unlink` removed the symlink.
8. Test the references system with local fixtures:
   ```bash
   python3 scripts/ci_check.py
   ```
   The CI script tests `refs.py` against temporary local git fixtures without accessing the network. It verifies fetching, vetting, adding, listing, verification, updates, removal, and restoration.

## One time setup checklist

Complete this checklist when configuring the repository and npm publishing:

1. Log in to npm as `v1006` via terminal and confirm identity with `npm whoami`.
2. Turn on 2FA (two-factor authentication) on the npm account.
3. Perform the first package publish by hand from the repo root (`npm publish --access public`).
4. Configure branch protection on `main` in GitHub:
   - Require pull requests before merging.
   - Require code owner reviews.
   - Require the status check "CI" to pass before merging.
   - Do not allow force pushes.
5. Add a tag protection ruleset in GitHub for tags matching `v*`.
6. Create a GitHub environment named `release` with required reviewers enabled.
7. Generate an npm access token (`NPM_TOKEN`) as a granular token scoped only to `@v1006/build-forge` with an expiration date. Add it to GitHub repository secrets.
8. Turn on 2FA on the GitHub account.

## Versioning

Build Forge follows semantic versioning (MAJOR.MINOR.PATCH):

- **Major**: A skill is renamed or removed, the profile `schema_version` changes, or a CLI flag or exit code changes.
- **Minor**: A new skill is added, a new optional profile field is introduced, or a new check type is added.
- **Patch**: Wording fixes, documentation updates, and bug fixes.

## Writing a profile migration

When introducing a new `schema_version` to `.agents/project-profile.yaml`:

1. Define a migration function in `skills/project-bootstrap/scripts/migrate_profile.py`:
   ```python
   def migrate_vX_to_vY(profile: dict, root: Path) -> dict:
       updated = dict(profile)
       updated["schema_version"] = Y
       # Add new default fields or transform existing structures
       return updated
   ```
2. Register the function in the `MIGRATIONS` registry dictionary:
   ```python
   MIGRATIONS = {
       1: migrate_v1_to_v2,
       2: migrate_v2_to_v3,
   }
   ```
3. Migration rules:
   - Never delete or rename user-added rules.
   - Never delete fields added by the user. All unknown fields must survive.
   - Migrations must be deterministic.
   - Do not create backup files; git shows the diff.
4. Test the migration with:
   ```bash
   python3 skills/project-bootstrap/scripts/migrate_profile.py plan --profile <path>
   python3 skills/project-bootstrap/scripts/migrate_profile.py apply --profile <path> --apply
   ```
5. Update `tests/test_lifecycle.py` and run `python3 scripts/ci_check.py`.

## Skill contracts and AST linting

Build Forge enforces strict structural and script execution contracts across all skills:

1. **Skill contracts (`scripts/skill_contracts.py`)**:
   Verifies that every script mentioned in any `SKILL.md` exists on disk, that all subcommands invoked in examples and instructions are valid parser options, and that required tables (like Areas and Scope guide) conform to contract rules.
   Run contract verification with:
   ```bash
   python3 scripts/skill_contracts.py
   ```
2. **Python AST lint (`scripts/lint_py.py`)**:
   Enforces cross-platform and safe coding patterns across all Python scripts:
   - Prohibits multi-character string strip calls (e.g. `s.strip("abc")`) which behave as character sets rather than substring trims. If multi-character set stripping is genuinely intended, annotate the line with `# strip-chars-ok: <reason>`.
   - Disallows leading `./` in glob patterns (e.g. `Path.glob("./*.md")`), ensuring consistent cross-platform behavior on Windows and POSIX.
   Run AST lint checks with:
   ```bash
   python3 scripts/lint_py.py
   ```

## CI failure history and cross-platform prevention

To keep the test matrix (Ubuntu, macOS, Windows; Node 18, 22) green across all CI runners:

1. **Windows command spawning**:
   `npm` is a batch script (`npm.cmd`) on Windows. Always use `shell=(sys.platform == "win32")` when running `npm` via `subprocess.run`.
2. **Bare git remote default branches**:
   On Linux, `git init --bare` defaults `HEAD` to `master`. When testing push policies with bare remotes, always pass `-b main` and run `git symbolic-ref HEAD refs/heads/main`. In verification scripts, check `refs/heads/main` before falling back to `HEAD`.
3. **Python bytecode creation**:
   Test scripts importing internal modules must set `sys.dont_write_bytecode = True` and pass `PYTHONDONTWRITEBYTECODE=1` in subprocess environments to prevent creating `__pycache__` directories.
4. **Git author in CI runners**:
   Always provide `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` in test fixture environments so `git commit` succeeds in headless environments.
5. **Windows shell wildcard expansion**:
   `cmd.exe` on Windows does not expand wildcards like `tests/*.test.js` in `package.json` scripts. Use `node --test` with default recursive discovery rather than file path globs.
6. **New skills must be registered**:
   Every folder in `skills/` must appear in `DOGFOOD_SET` or `DOGFOOD_EXCLUDED` (`scripts/dogfood.py`) and in `ALLOWED_SKILLS` (`scripts/ci_check.py`). Use `python3 scripts/dev.py new-skill`, which does both. `tests/test_skill_registry.py` fails when scaffolding leaves a registry out of date.
7. **"No checks reported" is not proof that a repository has no CI**:
   GitHub needs several seconds to attach checks to a new pull request. After `gh pr create`, wait until checks appear (for example, poll `gh pr checks` for up to 60 seconds) before treating the pull request as having none.

[CHANGELOG.md](CHANGELOG.md) uses the Keep a Changelog headings.

Deprecation policy: [CONFIRM: deprecation policy]

Publishing roadmap: [CONFIRM: switch the publish workflow to npm trusted publishing, check the current npm docs]

Note on package provenance: npm provenance generation only works from a public repository. If the repository is ever made private, `--provenance` must be removed from `publish.yml`.

