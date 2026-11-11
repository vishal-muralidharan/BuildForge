# Maintainer Kit

This directory contains internal maintainer tooling, playbooks, recipes, and templates for `@v1006/build-forge`.

Nothing in `maintainers/` or `scripts/` is packaged or shipped to end users.
CI asserts that `npm pack --dry-run` excludes both folders.

## Entry Point

All maintainer operations run through `scripts/dev.py`:
- `python3 scripts/dev.py new-skill <name> --tier core|new-app|module [--scripts] [--refs]`
- `python3 scripts/dev.py check [--fast]`
- `python3 scripts/dev.py impact <token>`
- `python3 scripts/dev.py recipe list | show <name> | verify <name> --arg key=value`
- `python3 scripts/dev.py fixture new <name> | check`
- `python3 scripts/dev.py release-plan`
- `python3 scripts/dev.py trail [--since REF] [--limit N] [--json]`
- `python3 scripts/dev.py repo-settings`

## Hard Rules

Hard rules for any AI agent or maintainer working here:
- Never run `gh pr merge` with `--squash` or `--rebase`. Always merge with `--merge`.
- Never push to `main` directly.
- Never merge `main` into a feature branch.

## Playbooks

The 6 maintainer playbooks live under `maintainers/skills/`:
- `author-skill`: create a new skill, configure triggers, and update manifests.
- `author-extension`: extend runners, check types, analyzers, or profile schemas.
- `triage-field-report`: diagnose root causes, build failing fixtures, and write fixes.
- `cut-release`: check release readiness, plan version bump, and print commands.
- `branch-dev-protocol`: develop on task branches, verify locally, raise pull requests, monitor CI matrix, and sync main.
- `merge-trail`: open PRs, merge with merge commits, view the trail, and preserve history.

These playbooks use standard `SKILL.md` frontmatter and neutral phrasing so any coding agent can follow them.
They are internal playbooks, not product skills, and must never be copied into `.agents/skills`.

## Rollout and Adoption

When adopting Build Forge in existing projects:
- `legacy_import.py inventory` and `status` are read only by default and print the ledger to the terminal.
- Pass `--write` only when the user asks for a ledger file (`.agents/legacy-parity.md`).

## Recipes

Repeatable change recipes live under `maintainers/recipes/`:
- `add-skill.yaml`
- `add-check-type.yaml`
- `add-analyzer.yaml`
- `add-rule-pack.yaml`
- `add-migration.yaml`
- `add-cli-command.yaml`
- `add-profile-field.yaml`
- `add-render-section.yaml`

Run `python3 scripts/dev.py recipe show <name>` to view required touchpoints before implementing changes.
Run `python3 scripts/dev.py recipe verify <name> --arg key=value` to confirm all touchpoints are in place.

## Templates

Scaffolding templates live under `maintainers/templates/`:
- `templates/skill/SKILL.md`: base template for new skills.

