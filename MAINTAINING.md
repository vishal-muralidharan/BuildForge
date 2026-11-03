# Maintainer Guide

This guide covers publishing, skill changes, testing, and repository settings for maintainers of `@v1006/build-forge`.

The rules in [AGENTS.md](AGENTS.md) apply to all work in this repository.

## Release steps

Follow these steps to publish a new release:

1. Update the version number in `package.json`.
2. Run `python3 scripts/make_integrity.py` to refresh `integrity.json`.
3. Run `python3 scripts/ci_check.py` to ensure all checks pass.
4. Run `npm pack --dry-run` and inspect the packaged file list.
5. Commit the version bump, integrity manifest, and any doc updates.
6. Create and push a git tag `v<version>` (for example, `git tag v0.2.0 && git push origin v0.2.0`).
7. In GitHub Actions, approve the deployment to the "release" environment so `publish.yml` executes.

## How to change a skill

1. Changes to files under `skills/` require prior maintainer approval.
2. Make the approved modifications.
3. Regenerate `integrity.json` by running `python3 scripts/make_integrity.py`.
4. Add an entry describing the changes in [CHANGELOG.md](CHANGELOG.md).
5. Verify changes with `python3 scripts/ci_check.py`.

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

[CHANGELOG.md](CHANGELOG.md) uses the Keep a Changelog headings.

Deprecation policy: [CONFIRM: deprecation policy]

Publishing roadmap: [CONFIRM: switch the publish workflow to npm trusted publishing, check the current npm docs]

Note on package provenance: npm provenance generation only works from a public repository. If the repository is ever made private, `--provenance` must be removed from `publish.yml`.

