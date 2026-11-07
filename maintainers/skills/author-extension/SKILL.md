---
name: author-extension
description: "Guidance for extending Build Forge with new check types, analyzers, rule packs, migrations, or CLI commands."
---

# Author Extension Playbook

Use this playbook when adding an extension to an existing Build Forge skill or runner.

## Steps

1. **Pick the recipe**
   List available maintainer extension recipes:
   ```bash
   python3 scripts/dev.py recipe list
   ```
   Identify the matching recipe:
   - `add-check-type`: new machine check in `run_rule_checks.py`.
   - `add-analyzer`: new static analyzer in `project-blueprints`.
   - `add-rule-pack`: new preset rule collection in bootstrap.
   - `add-migration`: new profile schema migration.
   - `add-cli-command`: new subcommand in `bin/build-forge.js`.
   - `add-profile-field`: new configuration field in project profile.
   - `add-render-section`: new generated view section in `render.py`.

2. **Inspect touchpoints**
   View all required touchpoints for the chosen recipe:
   ```bash
   python3 scripts/dev.py recipe show <recipe-name>
   ```

3. **Implement the extension**
   Follow each touchpoint listed in the recipe.
   Keep changes focused and atomic.
   - When modifying `run_rule_checks.py`, increment `RUNNER_VERSION` by 1.
   - When modifying profile schema structure or breaking backward compatibility, define a migration in `migrate_profile.py` and increment `schema_version`.

4. **Verify touchpoints**
   Run the recipe verification command:
   ```bash
   python3 scripts/dev.py recipe verify <recipe-name> --arg <key>=<value>
   ```
   Ensure 0 missing touchpoints remain.

5. **Add tests proving both sides**
   Write unit and integration tests under `tests/`:
   - Positive test: valid input passes with exit code 0.
   - Negative test: invalid input fails with expected error and exit code 1.
   - Ensure all tests pass on POSIX and Windows.

6. **Run maintainer verification**
   ```bash
   python3 scripts/dev.py check
   ```
   Update `CHANGELOG.md` under `## [Unreleased]`.

