---
name: cut-release
description: "Guidance for verifying release readiness, planning version bump, and printing maintainer release commands."
---

# Cut Release Playbook

Use this playbook to prepare a new package release of Build Forge.

## Strict Rules
- Never create git tags automatically.
- Never run git push automatically.
- Never publish to npm automatically.
- Always output manual commands for human execution.

## Steps

1. **Check release readiness**
   Run the release planner:
   ```bash
   python3 scripts/dev.py release-plan
   ```
   Inspect the report:
   - Verify commits since last tag are categorized correctly.
   - Note the recommended bump (major, minor, or patch).
   - Check that `CHANGELOG.md` has bullet entries under `## [Unreleased]`.
   - Check that git working tree is clean.

2. **Execute comprehensive verification**
   Run the full maintainer test suite through the installed pipeline:
   ```bash
   python3 scripts/dev.py check
   python3 scripts/dev.py dogfood check
   ```
   Ensure all checks pass with 0 failures.

3. **Verify packaging dry run**
   Confirm package contents:
   ```bash
   npm pack --dry-run
   ```
   Assert that `maintainers/` and `scripts/` are excluded from the package tarball.

4. **Verify integrity manifest**
   Confirm `integrity.json` matches current skills:
   ```bash
   python3 scripts/make_integrity.py --check
   ```

5. **Print instructions for maintainer**
   Print the exact steps for human execution:
   ```bash
   # 1. Update version in package.json
   # 2. Move Unreleased entries in CHANGELOG.md to release heading
   # 3. Commit release prep
   git commit -am "chore(release): prepare v<version>"
   # 4. Create annotated tag
   git tag v<version>
   # 5. Push tag to trigger release workflow
   git push origin v<version>
   ```

