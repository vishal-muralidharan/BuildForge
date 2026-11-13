# Build Forge

A build pipeline of 12 agent skills for new and existing projects: spec, bootstrap, scaffold, rule checks, and gated delivery.

[![npm version](https://img.shields.io/npm/v/@v1006/build-forge)](https://www.npmjs.com/package/@v1006/build-forge)
[![CI](https://github.com/vishal-muralidharan/BuildForge/actions/workflows/ci.yml/badge.svg)](https://github.com/vishal-muralidharan/BuildForge/actions/workflows/ci.yml)

Distributed under the [Build Forge License](LICENSE).

## What it is

AI agents lose project context across sessions and drift from project rules. Every skill reads 1 project profile file as the single source of truth. New apps and existing projects then follow the same 7 gated pipeline stages from start to finish.

## How it adapts

Build Forge never edits itself. It reads your project and writes a project profile, AGENTS.md, convention skills and a repo map. To change behavior, edit the profile and re-render. Do not edit the pipeline skills.

```text
Project context -> project-bootstrap -> .agents/project-profile.yaml
                                                 |
                                                 v
                                              render.py
                                                 |
                          +----------------------+----------------------+
                          |                      |                      |
                          v                      v                      v
                      AGENTS.md           Convention skills        repo-map.md
```

## Works with

Build Forge works with coding agents that support the open Agent Skills format or read `AGENTS.md`. Confirmed agents include Claude Code, OpenAI Codex, Gemini CLI, GitHub Copilot, Cursor, and Windsurf. See [COMPATIBILITY.md](COMPATIBILITY.md) for setup details, pointer files, and verification status.

## Requirements

- Node.js >= 18 (from package.json engines)
- Python 3
- PyYAML (`pip install pyyaml`)
- git
- Agent capabilities: The agent must read files, edit files, and run shell commands.

## Install

### With npx

Run this command in your project root:

```bash
npx @v1006/build-forge
```

### By hand

Copy the `skills/` folder into `.agents/skills` in your project root:

```bash
mkdir -p .agents
cp -r skills .agents/skills
```

### What install writes

The installer copies the 13 pipeline skills into `.agents/skills/`. It writes `.agents/build-forge.lock.json` with a hash of every pipeline skill file.

### Overwrite existing skills

Existing skill folders are kept by default. To overwrite existing pipeline skills, pass `--force`:

```bash
npx @v1006/build-forge --force
```

### Linking skills for other agents

Skills live in 1 place: `.agents/skills`. To make them visible to agents that look in a tool-specific folder (such as Claude Code):

```bash
npx @v1006/build-forge link
```

To link specific agents or auto-detect based on existing configuration files:

```bash
npx @v1006/build-forge link --agents auto
npx @v1006/build-forge link --agents claude
```

You can also pass `--agents` during installation to install and link in 1 step:

```bash
npx @v1006/build-forge install --agents auto
```

### Unlinking agent folders

To remove only the symbolic links created by Build Forge without touching real folders or files:

```bash
npx @v1006/build-forge unlink
```

### Inspecting installation status

To check environment health, project profile, installed skills, lockfile integrity, vendor references, and agent links:

```bash
npx @v1006/build-forge status
```

### Comparing skills against the package

To see differences between installed skills and bundled package skills without overwriting:

```bash
npx @v1006/build-forge diff
```

## Lifecycle management

Build Forge provides lifecycle commands to diagnose environment issues, check for updates, upgrade skills safely, and migrate project profiles across schema versions.

### Diagnosing project health: doctor

Run `doctor` to verify your environment, dependencies, lockfile integrity, and project configuration without modifying anything:

```bash
npx @v1006/build-forge doctor
```

Add `--json` for machine-readable output:

```bash
npx @v1006/build-forge doctor --json
```

`doctor` checks:
- Node.js version (requires 18+)
- Python 3 availability (`python3`, `python`, or `py -3`)
- PyYAML installation
- Git availability
- Lockfile integrity and skill file modifications
- Project profile validity
- External references integrity (if configured)
- Blueprint staleness (if configured)
- Agent links and pointer files
- AGENTS.md existence
- Legacy parity status (if ledger exists)
- Pending upgrade actions from upgrade-notes.json

Prints OK, WARN, or FAIL with 1 fix hint each. Exits with code 1 on any FAIL.

### Checking for updates: outdated

Compare your installed Build Forge version against the latest release on npm:

```bash
npx @v1006/build-forge outdated
```

When offline or when npm is unreachable, it skips the check with an informational note. It never runs automatically in the background.

### Updating pipeline skills: update

Update installed pipeline skills safely to match the latest package version:

```bash
npx @v1006/build-forge update
```

`update` compares file hashes against packaged `integrity.json`, not only versions.
It follows a strict safety order:
1. **Verification**: If any pipeline skill was modified by hand, it stops and lists the modified files. Pass `--keep-modified <skill>` to keep your edits, or `--restore <skill>` to overwrite with the package version.
2. **Missing core skills**: Automatically installs missing core tier skills (`project-blueprints`).
3. **Reinstallation**: Reinstalls differing pipeline skills from the package.
4. **Lock update**: Writes `.agents/build-forge.lock.json` with updated hashes and version.
5. **Optional skills**: Lists new optional skills available to add with `npx @v1006/build-forge add <skill>`.
6. **Upgrade actions**: Displays applicable upgrade actions from `upgrade-notes.json` and links to [UPGRADING.md](UPGRADING.md).

Flags:
- `--dry-run`: Preview the update plan without modifying files.
- `--adopt`: Adopt an existing project without a lock file.
- `--keep-modified <skill>`: Preserve local edits in the specified pipeline skill.
- `--restore <skill>`: Overwrite the specified skill (or pass `--restore all`).

### Managing skills: list and add

View all bundled skills by tier and installation status:

```bash
npx @v1006/build-forge list
```

Install an optional skill:

```bash
npx @v1006/build-forge add <skill-name>
```

### Recording completed upgrade actions: upgrade

Mark an upgrade action as complete:

```bash
npx @v1006/build-forge upgrade done <action-id>
```

See [UPGRADING.md](UPGRADING.md) for step by step upgrade guidance across versions.

### Migrating the project profile: migrate

When a package update introduces a new `schema_version` for `.agents/project-profile.yaml`, inspect and apply migrations:

1. **Preview changes (plan)**:
   ```bash
   python3 .agents/skills/project-bootstrap/scripts/migrate_profile.py plan
   ```
2. **Apply changes**:
   ```bash
   python3 .agents/skills/project-bootstrap/scripts/migrate_profile.py apply --apply
   ```

A migration never deletes any rule or field added by the user. Unknown and custom fields are preserved intact. No backup files are created because git tracks the change.

## Quick start

### Path 1: New app

1. Run `product-spec`:
   > "Turn my app idea into a product spec with milestones and non-goals."
2. Run `project-bootstrap`:
   > "Run project-bootstrap to create the project profile and generated guidance."
3. Run `scaffold-app`:
   > "Create the first working skeleton of the app from the profile."
4. Run `feature-delivery`:
   > "Deliver milestone 1 through the build pipeline."

### Path 2: Existing project

1. Run `project-bootstrap`:
   > "Onboard this codebase and create .agents/project-profile.yaml."
2. Run `rules-to-tests`:
   > "Turn written project rules into automatic checks."
3. Run `feature-delivery`:
   > "Run this task end to end through the build pipeline."

## The pipeline

The pipeline is goal-oriented rather than task-oriented: it does not stop merely because a task checklist was completed. It defines measurable acceptance invariants upfront, verifies them iteratively, and loops until the goal is proven true.

| # | Stage | Skill to use | Gate: do not continue until |
|---|---|---|---|
| 0 | Pre-flight | git | Branch is checked against protected branches and working tree is clean. |
| 1 | Audit & Goal | `audit-and-planning` (phases 1 and 2), `repo-search` | Root cause diagnosed. Protected data identified. Current goal invariants defined in `.agents/work/CURRENT_GOAL.md` (updated for each task in a series). |
| 2 | Plan | `audit-and-planning` (phases 3 and 4) | Every step has a target, a verify command and a commit message. Plan approved if over 5 steps or touching protected items. |
| 3 | Build step | The convention skill for the area (`build-ui`, `review-db-structure`, and so on) | The step does 1 thing and follows the rules of its area. |
| 3a | Verify step | `targeted-module-testing`, step 1 | The step's checks pass with 0 errors and 0 warnings. Atomic rollback triggers after 2 consecutive check failures. |
| 3b | Commit step | `atomic-commits` | The message passes the checker. Step committed. |
| 4 | Sync | `sync-skills-and-docs`, and `rules-to-tests` if a new enforceable rule appeared | The profile, generated files and docs match the code. The drift checker is clean. |
| 5 | Full verify | `targeted-module-testing`, steps 1 to 3 | `commands.check` passes. Tests and browser checks pass. |
| 5a | Goal loop gate | `targeted-module-testing`, step 2b | All acceptance invariants from `CURRENT_GOAL.md` are evaluated. If all pass, proceed to stage 6. If any fail, re-enter loop at stage 3. |
| 6 | Deploy (optional) | `targeted-module-testing`, step 4 | Runs only if `capabilities.deploy.enabled` is true. |
| 7 | Report | `targeted-module-testing`, step 5 | The Post-Build Audit is written. `CURRENT_GOAL.md` marked completed; advances to next task if in a series. |

## What it creates in your project

```text
.agents/
  project-profile.yaml          # Generated: Single source of truth for the project
  repo-meta.yaml                # project-readme: GitHub description, homepage, and topics
  repo-map.md                   # Generated: Cache of where symbols and files live
  build-forge.lock.json         # Build Forge: Hash manifest of installed pipeline skills
  checks/                       # Generated / user: Project rule checks (run_rule_checks.py)
  skills/
    atomic-commits/             # Build Forge: Pipeline skill (read only)
    audit-and-planning/         # Build Forge: Pipeline skill (read only)
    extend-pipeline/            # Build Forge: Pipeline skill (read only)
    feature-delivery/           # Build Forge: Pipeline skill (read only)
    legal-and-settings-pages/   # Build Forge: Pipeline skill (read only)
    product-spec/               # Build Forge: Pipeline skill (read only)
    project-readme/             # Build Forge: Pipeline skill (read only)
    project-bootstrap/          # Build Forge: Pipeline skill (read only)
    repo-search/                # Build Forge: Pipeline skill (read only)
    rules-to-tests/             # Build Forge: Pipeline skill (read only)
    scaffold-app/               # Build Forge: Pipeline skill (read only)
    sync-skills-and-docs/       # Build Forge: Pipeline skill (read only)
    targeted-module-testing/    # Build Forge: Pipeline skill (read only)
    build-ui/                   # Generated: Project convention skill
    maintain-design-system/     # Generated: Project convention skill
AGENTS.md                       # Generated: Router read by agents
```

- **Build Forge files**: The 13 pipeline skills in `.agents/skills/` and `.agents/build-forge.lock.json`. These are read only files from the npm package.
- **Generated files**: `.agents/project-profile.yaml`, `AGENTS.md`, `.agents/repo-map.md`, `.agents/checks/`, and convention skills like `build-ui`. These files adapt to your project, belong to you, and may be edited freely.

## Skills

| Skill | What it does | When to use it |
|---|---|---|
| `project-readme` | Writes a README in a style that fits the project (technical, showcase, minimal, or api) from real facts, plus the GitHub description, homepage, and topics. Checks commands, links, secrets, and GitHub limits. | When a repo needs a README, a better first impression, or GitHub description and topics. |
| `atomic-commits` | Enforces small, single purpose commits with checked messages. | When committing code in a project with a profile, before starting the next unit of work. |
| `audit-and-planning` | Searches codebase, diagnoses root cause, checks rules, and writes an atomic plan. | Before starting any feature, bug fix or refactor, even for small tasks. |
| `extend-pipeline` | Extends the pipeline with vetted, pinned third party skills. | When adding external skills, review tools, hosting recipes, or updating references. |
| `feature-delivery` | Conductor for the build pipeline with gates between all 8 stages and opt-in branch mode. | For every task to add, build, fix, refactor or ship code in a project with a profile. |
| `legal-and-settings-pages` | Adds settings, legal pages, data management, terms consent, and account deletion. | When adding settings, privacy policies, terms, GDPR/CCPA pages, or account deletion. |
| `product-spec` | Turns rough app ideas into specs with users, core flows, milestones and steps. | At the very start of a new app, or to cut big features into milestones. |
| `project-blueprints` | Extracts verified facts (data, tokens, UI, layout, auth, config) into queryable blueprints. | When asking what is in this codebase, inspecting schemas or tokens, or regenerating context. |
| `project-bootstrap` | Sets up the build pipeline and creates the profile, AGENTS.md, skills, and repo map. | When onboarding a repo, starting a new app, or updating project guidelines. |
| `repo-search` | Performs read-only discovery of symbols, components, tokens, and fields. | Before creating new files or functions, or when refreshing the repo map. |
| `rules-to-tests` | Turns written project rules into automatic checks that fail the build when broken. | After bootstrap or scaffolding, or when conventions need automated enforcement. |
| `scaffold-app` | Creates the first green skeleton app from official framework generators. | Right after project-bootstrap in new mode, on empty repositories. |
| `sync-skills-and-docs` | Detects drift and updates profile, skills, README and repo map. | At the end of structural changes, or when docs and code get out of sync. |
| `targeted-module-testing` | Runs lint, test, build, rule checks, browser checks, and post-build audit. | Before marking any task done, after every build, and before deploy. |

## The project profile

The project profile is the single source of truth for the build pipeline. It lives at `.agents/project-profile.yaml`. Every pipeline skill reads this file first. Edit the profile to change rules, commands, or layouts, then re-render guidance files.

For schema details, see [profile-schema.md](skills/project-bootstrap/references/profile-schema.md).
For a full worked example, see [example-profile.yaml](skills/project-bootstrap/references/example-profile.yaml).

Here is a snippet from that example file:

```yaml
schema_version: 1

project:
  name: Pocketlog
  summary: Fast, offline-first personal journaling and habit tracking application.
  mode: existing
  platforms: [web, mobile]

stack:
  language: typescript
  framework: React 19
  bundler: Vite
  styling: Tailwind v4
  router: none
  state: React context
  package_manager: npm
  test_runner: Vitest
  linter: Oxlint
  backend: SQLite (local storage)
  auth: none
  database: SQLite
  hosting: static
```

### Branch workflow (opt-in)

Build Forge includes an opt-in task branch workflow managed by `branchflow.py`.

When enabled in `git.workflow`, tasks run on isolated feature branches, guard against commits on the default branch, provide manual testing handoff checklists, and merge or rebase cleanly with typed confirmation phrases.

```yaml
git:
  workflow:
    default_branch: main
    mode: ask            # off, ask, or always
    branch_format: "<type>/<slug>"
    sync: merge          # merge or rebase
    merge_method: squash # squash, merge, or rebase
    remote: origin
    cleanup: ask         # ask or keep
    worktree: false
```

## Automatic rule checks

`rules-to-tests` reads rules in `.agents/project-profile.yaml` and turns them into automatic checks. It copies a test runner (`run_rule_checks.py`) into `.agents/checks/` and connects it to the project check command.

A rule can define a `check` block with types such as `forbid`, `require_file`, `forbid_file`, or `root_only`. Checks support `hint` messages and `examples` (`bad` and `good`) verified with `run_rule_checks.py --selftest`:

```yaml
rules:
  - id: no-raw-hex-colors
    area: tokens
    text: "Use token variables instead of raw hex color codes."
    enforced_by: test
    check:
      type: forbid
      pattern: '(?<![\w&/])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b'
      include: ["src/**/*.{js,jsx,ts,tsx,css,html}"]
      exclude: ["src/index.css"]
      hint: "Use design token variables instead of raw hex values."
      examples:
        bad: ["color: #ffffff;"]
        good: ["color: var(--color-background);"]
    exceptions:
      - path: "src/legacy/badge.css"
        reason: "Legacy badge styles pending migration"
```

### Hazard sweep and rule packs

During bootstrap, `hazard_sweep.py` audits the codebase for common hazards (web hazards, native controls, raw colors, hex in styles, any in TypeScript, and storage leaks) with default-yes adoption.

When an unwritten convention is broken during delivery, the `incident-to-rule` workflow codifies the pattern into a tested rule with examples, selftest validation, and a separate atomic commit.

See [check-patterns.md](skills/rules-to-tests/references/check-patterns.md) for patterns and ready packs such as `native-controls` and `web-hazards`.

## Rule packs

Rule packs are curated collections of opt-in rules for common stacks and concerns. Packs are never applied automatically. You can accept, edit, or drop any rule.

The 9 available packs live under `skills/project-bootstrap/references/rule-packs/`:
1. `native-controls`: Prevent native browser form controls outside component folders (`ui-no-native-pickers`, `ui-no-native-selects`, `ui-no-browser-dialogs`).
2. `web-hazards`: Prevent common web security and hygiene hazards (`web-no-console`, `web-target-blank-rel`, `web-no-raw-eval`, `web-no-inner-html`, `web-no-committed-env`).
3. `ui-states`: Require loading skeletons for operations over 300ms, empty states with clear actions, and user-facing error alerts.
4. `mobile-web`: Require 16px minimum font size for inputs, 44px tap targets, viewport fit cover with safe area insets, and unrestricted pinch zoom.
5. `shortcuts`: Consistent keyboard shortcut modifiers across platforms, code labels, and focus guards.
6. `a11y-basics`: Semantic HTML tags, visible keyboard focus indicators, AA contrast ratios, and descriptive labels.
7. `motion-basics`: Honor reduced motion preferences, animate only transform and opacity, and keep transitions under 300ms.
8. `testing-practices`: Query elements by accessible role, wait for asynchronous UI instead of arbitrary sleeps, and avoid brittle style assertions.
9. `browser-checks`: Quality verification checks for zero console errors, contrast compliance, event listener cleanup, and viewport fit.

### Managing packs with packs.py

Manage rule packs using the `packs.py` CLI:

```bash
# List all available rule packs
python3 .agents/skills/project-bootstrap/scripts/packs.py list

# Show details, rules, and verify checks for a pack
python3 .agents/skills/project-bootstrap/scripts/packs.py show native-controls

# Plan changes and probe the codebase for existing violations
python3 .agents/skills/project-bootstrap/scripts/packs.py plan native-controls

# Apply pack rules to .agents/project-profile.yaml
python3 .agents/skills/project-bootstrap/scripts/packs.py apply native-controls --yes

# Diff installed pack rules against newer packaged versions
python3 .agents/skills/project-bootstrap/scripts/packs.py diff native-controls

# Lint rule pack definitions for schema conformance
python3 .agents/skills/project-bootstrap/scripts/packs.py lint
```

### How checks fail the build

Mechanical rules carry a `check` block executed by `run_rule_checks.py`. This runner is hooked into your single `check` command (such as `npm test` or `npm run check`). When an agent or developer violates a check pattern, the build fails immediately. The output shows the rule ID, offending file:line, and a hint explaining how to fix the violation. User-edited rule text is never overwritten on pack updates, and dropped rules remain permanently ignored.

## Project blueprints

Blueprints capture verifiable facts about a codebase so agents do not rescan files repeatedly. Facts are extracted from code with source file and line evidence. Rules and contracts are never derived automatically; they are proposed in `candidates.md` for the user to confirm.

Blueprints live in `.agents/blueprints/` and cover 6 areas:
- `data.md`: Database tables (SQL, Prisma), storage keys, and schema names.
- `tokens.md`: CSS variables, role mappings, and light and dark theme palettes.
- `ui.md`: Exported UI components, props types, variants, state primitives, and form controls status table.
- `layout.md`: Breakpoints, navigation shells, and mobile viewport constraints.
- `auth.md`: Authentication providers, route guards, and logout cleanup paths.
- `config.md`: Environment variable names and route mappings.

### Blueprint commands

1. **Scaffold (init)**: Scaffold missing canonical blueprint files from templates without overwriting:
   ```bash
   python3 .agents/skills/project-blueprints/scripts/blueprint.py init
   ```
2. **Extract**: Run analyzers and generate verified blueprints:
   ```bash
   python3 .agents/skills/project-blueprints/scripts/blueprint.py extract
   ```
3. **Adopt**: Move an over-limit custom block from a convention skill into blueprint contracts:
   ```bash
   python3 .agents/skills/project-blueprints/scripts/blueprint.py adopt --from .agents/skills/build-ui/SKILL.md --block contracts --area ui
   ```
4. **Link check**: Verify skills link to existing blueprints, index lists all files, and custom blocks are under 80 lines:
   ```bash
   python3 .agents/skills/project-blueprints/scripts/blueprint.py link-check
   ```
5. **Drift check**: Verify facts, detect stale sources, check links, and validate contract evidence anchors:
   ```bash
   python3 .agents/skills/project-blueprints/scripts/blueprint.py drift
   ```
6. **Verify**: Check that every evidence line in blueprints matches current code:
   ```bash
   python3 .agents/skills/project-blueprints/scripts/blueprint.py verify
   ```
7. **Stale check**: Check if sources changed since extraction:
   ```bash
   python3 .agents/skills/project-blueprints/scripts/blueprint.py stale
   ```
8. **Query (show)**: Query facts within a line budget:
   ```bash
   python3 .agents/skills/project-blueprints/scripts/blueprint.py show --area ui --paths src/components/Button.tsx --budget 120
   ```
9. **Candidates**: Review candidate rules proposed from codebase facts:
   ```bash
   python3 .agents/skills/project-blueprints/scripts/blueprint.py candidates
   ```

### Protection and budgets

- **Custom blocks**: Human contracts live in `<!-- BEGIN CUSTOM: contracts --> ... <!-- END CUSTOM: contracts -->`. They are preserved byte for byte on re-extraction.
- **Secret protection**: Secret values from `.env` files are never read or stored. Only variable names are recorded. Every output file is scanned for secrets before writing.
- **Budgets**: `index.md` is 60 lines or fewer. Generated sections are 250 lines or fewer per file. Larger areas split into `<area>-part-2.md` parts.

## Legacy rule parity

When adopting Build Forge in a codebase with existing agent files (`AGENTS.md`, `.cursor/rules`, `.claude/skills`, or custom skills), `legacy_import.py` audits and imports existing rules so nothing is lost.

### Commands

1. **Inventory**: Find existing agent files, split them into atomic statements, classify each statement, and record them in a ledger:
   ```bash
   python3 .agents/skills/project-bootstrap/scripts/legacy_import.py inventory
   ```
   This generates `.agents/legacy-parity.md` with statement IDs (`L001`, `L002`), source `file:line`, class, destination, and a coverage score.

2. **Review in batches**: Inspect pending statements for a specific area 15 at a time:
   ```bash
   python3 .agents/skills/project-bootstrap/scripts/legacy_import.py batch --area naming
   ```

3. **Apply decisions**: Accept rules into the profile with source evidence, drop obsolete statements with a reason, and send notes to `.agents/notes/<area>.md`:
   ```bash
   python3 .agents/skills/project-bootstrap/scripts/legacy_import.py apply --accept L001,L003 --drop L002 --reason "Handled by ESLint"
   ```

4. **Verify parity**: Confirm all rule candidates and derivable items are resolved:
   ```bash
   python3 .agents/skills/project-bootstrap/scripts/legacy_import.py status
   ```
   Exits 1 while any rule candidate or derivable statement remains pending.

Existing legacy files are never edited, moved, or deleted.

## Adding your own notes to generated skills

Generated files (`AGENTS.md`, convention skills in `.agents/skills/`, and the repo map) are derived views of `.agents/project-profile.yaml`. To add project-specific notes that survive re-rendering, use custom blocks.

### Custom blocks

Every generated file ends with an empty custom block named `notes`:

```markdown
<!-- BEGIN CUSTOM: notes -->
<!-- END CUSTOM: notes -->
```

Write notes, exceptions, or tips inside this block. Block names match `[a-z0-9-]{1,40}` and must be unique within their file.

### Safe updates

When the profile changes, update generated files without losing your notes:

```bash
python3 .agents/skills/project-bootstrap/scripts/render.py --profile .agents/project-profile.yaml --update
```

`--update` works as follows:

1. It checks the body hash in the stamp line (`<!-- build-forge:generated v1 body=<sha256> -->`).
2. If the file has no edits outside custom blocks, it updates the generated text and restores custom blocks byte for byte.
3. If edits exist outside custom blocks, it refuses the file, prints a unified diff, makes 0 changes, and exits 1.

### Salvaging hand edits and forcing updates

When a stamped file has hand edits outside custom blocks, `--update` refuses with exit 1.

To regenerate while salvaging all hand edits into a `salvaged` custom block (and routing overflow to blueprints):

```bash
python3 .agents/skills/project-bootstrap/scripts/render.py --profile .agents/project-profile.yaml --salvage
```

`--force` behaves like `--salvage` by default: no content is discarded, and the salvaged line count is printed.

To intentionally discard edits outside custom blocks, pass `--discard-edits` and `--yes-discard` together:

```bash
python3 .agents/skills/project-bootstrap/scripts/render.py --profile .agents/project-profile.yaml --force --discard-edits --yes-discard
```

To migrate an unstamped file with the same name as a generated skill:

```bash
python3 .agents/skills/project-bootstrap/scripts/render.py --profile .agents/project-profile.yaml --migrate-custom
```

Unstamped files are never overwritten silently. Overwriting unstamped files requires `--force --overwrite-unstamped`.

### Safety and limits

- **Orphans**: Custom blocks whose file or block name is no longer generated are saved to `.agents/custom-orphans.md`. No block is dropped silently.
- **Size limits**: Warns above 80 lines per block and 300 custom lines per file. Fails above 160 lines per block or 600 custom lines per file. Facts belong in `.agents/blueprints/` or `.agents/project-profile.yaml`.
- **Secret scanning**: Blocks are scanned for private keys and long credential strings. Fails on a match.

## Self-explaining commit scopes

In `.agents/project-profile.yaml`, `git.scopes` defines the allowed commit scopes. Scopes can be plain strings or mappings with `{name, purpose, paths}`:

```yaml
git:
  commit_format: "<type>(<scope>): <subject>"
  scopes:
    - name: ui
      purpose: Components, styles, and layout
      paths:
        - src/components/**
        - src/styles/**
    - name: data
      purpose: Database and storage models
      paths:
        - src/models/**
    - misc
```

### Suggesting scopes

To find the right scope for changed files:

```bash
# Suggest scopes for specific files
python3 .agents/skills/atomic-commits/scripts/suggest_scope.py --profile .agents/project-profile.yaml --files src/components/Button.jsx

# Suggest scopes for staged files
python3 .agents/skills/atomic-commits/scripts/suggest_scope.py --profile .agents/project-profile.yaml --staged
```

`suggest_scope.py` ranks scopes by file glob matches and prints the top 3 with their purpose. When no path matches, it prints the full list of available scopes.

## Third party skills

A third party skill is untrusted text that an agent will read. Only add sources you trust.

Build Forge includes 0 third party skills. Every external reference comes directly from a source you specify.

### How to add a reference

Ask your agent to run `extend-pipeline`, or run `refs.py` directly:

```bash
python3 .agents/skills/extend-pipeline/scripts/refs.py add \
  --name <name> \
  --source <git-url-or-path> \
  --category <category> \
  --purpose "Purpose of the skill" \
  --used-by audit,verify \
  --approved
```

Build Forge never auto-installs anything. The `extend-pipeline` workflow requires you to type `yes install <name>` before writing files.

### Categories

Assign each reference to 1 of 7 categories:
- `backend` or `database`
- `security`
- `deploy` or `hosting`
- `browser`
- `performance`
- `accessibility`
- `other`

### Activation: Pipeline-only vs native

References support 2 activation modes:
- `pipeline-only` (default): Installs into `.agents/vendor/<name>`. Coding agents do not load this folder into their active skill set. Pipeline skills consult it through `refs.py due` during relevant stages. `build-forge link` never links vendor folders into agent skill directories.
- `native`: Installs into `.agents/skills/<name>`. Coding agents load and run the skill directly.

### Running scripts

Scripts inside a third party reference never run by default. They run only if `allow_scripts: true` is explicitly configured in `.agents/references.yaml` for that reference. Otherwise, verification tools report bundled scripts as "Not run".

### Mode: Gate vs advisory

- `advisory` (default): Findings guide the plan or review. They do not block pipeline progress.
- `gate`: High or blocking findings stop the current stage until you decide.

### Security vetting

Before installation or update, `refs.py vet` scans the source files for 9 security risk patterns:
1. Executable scripts and binaries.
2. Network calls and external requests.
3. Shell and system execution commands.
4. Credential and secret token patterns.
5. File writes outside the project directory.
6. Git push and package publish commands.
7. Hidden, zero width, or bidirectional characters.
8. HTML comments.
9. Phrases that try to override instructions or hide actions from the user.

If the scan detects any high findings, `refs.py vet` exits with code 1. A clean scan is not proof of safety. Always review third party files yourself.

### Pinning

When a reference is added, Build Forge records:
- The exact git commit SHA in `.agents/references.yaml`.
- The SHA-256 hashes of all installed files in `.agents/references.lock.json`.

Run `refs.py verify` to confirm installed files match their hashes:

```bash
python3 .agents/skills/extend-pipeline/scripts/refs.py verify
```

If files were modified, run `refs.py restore` to re-fetch clean files from the pinned commit:

```bash
python3 .agents/skills/extend-pipeline/scripts/refs.py restore
```

### Update and remove

To preview changes and scan for new risks:

```bash
python3 .agents/skills/extend-pipeline/scripts/refs.py update <name>
```

To apply the update after reviewing the preview:

```bash
python3 .agents/skills/extend-pipeline/scripts/refs.py update <name> --approved
```

To remove a reference:

```bash
python3 .agents/skills/extend-pipeline/scripts/refs.py remove <name> --yes
```

Removing a reference deletes its installed folder and its configuration entry. It leaves all other files untouched.

## Legal and settings pages

`legal-and-settings-pages` creates a Settings page, public legal documents (terms of service, privacy policy), a manage-my-data export page, terms consent on signup, and server-side account deletion.

The generated pages are templates, not legal advice. Laws and regulations change across jurisdictions. Have a qualified person review all generated legal pages before launch.

## README and GitHub page

`project-readme` writes a README that fits the kind of project and stays true to the code. It picks 1 of 4 styles: `technical` for tools and libraries, `showcase` for apps people use, `minimal` for small static sites, and `api` for backend services. It also keeps the GitHub description, homepage, and topics in `.agents/repo-meta.yaml`.

```bash
npx @v1006/build-forge add project-readme
python3 .agents/skills/project-readme/scripts/readme_facts.py --root .
python3 .agents/skills/project-readme/scripts/check_readme.py --root .
python3 .agents/skills/project-readme/scripts/check_readme.py --root . --print-gh
```

The check fails on a missing section, a script that does not exist, a broken link or image, a secret-like value, or a description or topic over the GitHub limits. `--print-gh` prints the `gh repo edit` commands. You run them. The skill never changes GitHub settings.

## Verify your install

Install writes `.agents/build-forge.lock.json` with a hash of every pipeline skill file.

### Verification commands

Check skills with npx:

```bash
npx @v1006/build-forge verify
```

Or check offline with Python:

```bash
python .agents/skills/project-bootstrap/scripts/verify_integrity.py --root .
```

To pin a specific version during verification:

```bash
npx @v1006/build-forge@0.1.0 verify
```

### Exit codes and output

- Exit code 0: All pipeline skills match the lock file.
- Exit code 1: A skill was modified, missing, or holds extra files.
- Exit code 2: No lock file exists at `.agents/build-forge.lock.json`.

### Restoring skills

If skills show differences, restore clean copies with `--force`:

```bash
npx @v1006/build-forge install --force
```

This deletes and recopies pipeline skills. Any extra files added inside pipeline skill directories are lost.

### Scope and limits

- Generated files (the profile, AGENTS.md, `build-ui` and other convention skills, repo map) belong to you and are not checked.
- CRLF line endings are ignored during hash comparisons.
- This verification detects accidental edits only. It cannot stop someone who edits both the skills and the lock file.

## Update and uninstall

### Update

1. Install the latest package with `--force`:
   ```bash
   npx @v1006/build-forge install --force
   ```
2. Ask your agent to run `project-bootstrap` in update mode to refresh generated guidance files.

### Uninstall

1. Delete the 13 pipeline skill folders from `.agents/skills/`.
2. Delete `.agents/build-forge.lock.json`.

All generated files (`.agents/project-profile.yaml`, `AGENTS.md`, convention skills, and the repo map) remain in your repository and stay yours.

## Safety

- `project-bootstrap` writes only to `.agents/`, `AGENTS.md`, and the skills directory. It never edits application code.
- `render.py` never overwrites existing files unless `--update` or `--force` is passed. It preserves custom blocks byte for byte.
- Git push policy defaults to `never`.
- Automated deploy capability is disabled by default.
- `scaffold-app` runs official framework generators and requires network access during scaffolding.

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `PyYAML is required` | PyYAML package is not installed. | Run `pip install pyyaml` in your active Python environment. |
| `python: command not found` | `python` alias is not mapped to Python 3. | Use `python3` instead of `python` when running scripts. |
| `python3: command not found` | `python3` alias is not installed or not in PATH. | Use `python` or `py -3` in your shell, or install Python 3 and add it to your system PATH. |
| Agent does not see the skills | The agent scans a folder other than `.agents/skills`. | Run `npx @v1006/build-forge link`. Check the agent's skills folder in [COMPATIBILITY.md](COMPATIBILITY.md). |
| Windows symlink errors | Windows requires elevated permissions or developer mode for directory symlinks. | Build Forge uses directory junctions and copy fallbacks. Enable Windows Developer Mode if linking fails. |
| Validator reports `unexpected keys` | YAML parser split an unquoted string on commas. | Wrap string values containing commas in double quotes in `.agents/project-profile.yaml`. |
| `AGENTS.generated.md already exists` | `render.py` found an existing unstamped `AGENTS.md` and avoided overwriting it. | Merge changes from `AGENTS.generated.md` into `AGENTS.md`, or run `render.py --force --overwrite-unstamped`. |
| `verify` exits with code 2 | Lock file is missing. | Run `npx @v1006/build-forge install` to write `.agents/build-forge.lock.json`. |
| `verify` shows `modified` (exit code 1) | Skill files were altered or contain extra files. | Run `npx @v1006/build-forge install --force` to restore clean pipeline skills. |
| Lost content and salvage | `render.py` refuses to overwrite files with hand edits outside custom blocks or unstamped skills. | Run `python3 .agents/skills/project-bootstrap/scripts/render.py --profile .agents/project-profile.yaml --salvage` to preserve lines into `salvaged` custom blocks, or `--migrate-custom` to wrap unstamped skills in `legacy` blocks. Over-limit blocks (>160 lines) can be adopted into blueprint contracts via `python3 .agents/skills/project-blueprints/scripts/blueprint.py adopt`. |
| Dual-homed skill collision detected | A reference exists in both `.agents/vendor/<name>` and `.agents/skills/<name>`. | Run `python3 .agents/skills/extend-pipeline/scripts/refs.py dedupe` to inspect collisions, then pass `--approved` to remove identical duplicate copies. |
| False warning from `check_sync` | Markdown tables outside Areas or dotted paths like `.agents/**` triggered false missing skill or path warnings. | Update Build Forge. Skill names are now read only from the Areas section and scope names from the Scope guide section using `mdscan.py`. Leading path dots are preserved. |
| Unmatched glob or layer path warning | `validate_profile.py --strict-paths` or `check_sync.py` flags an unmatched path. | Check `structure.layers` and `git.scopes` in `.agents/project-profile.yaml`. Verify that paths exist on disk or remove unused globs. |

## License

Build Forge is distributed under the [Build Forge License](LICENSE). Below is a plain summary of its 9 terms:

1. **Use**: Install and run on any number of projects and machines, for personal or commercial work, at no cost.
2. **No changes**: Do not modify, adapt, translate or create derivative works of Build Forge (its skill files, scripts, templates, references or installer).
3. **Copies**: Keep complete, unmodified copies inside your projects and share with project collaborators. Do not publish, sell, sublicense or distribute to anyone else.
4. **Adaptation and generated files**: All files generated for your project (project profile, AGENTS.md, convention skills, repo map) and code or documents produced belong to you and may be edited freely.
5. **Third party material**: Anything not written by the copyright holder is covered by its own terms.
6. **Ending**: The license ends automatically upon breach of any terms, requiring deletion of all copies.
7. **No warranty**: The software is provided "as is", without warranty of any kind.
8. **Limit of liability**: The copyright holder is not liable for any claims or damages arising from use.
9. **Governing law**: [TODO: governing law and courts]

## Support

- Security issues: See [SECURITY.md](SECURITY.md) for reporting guidelines.
- Version history: See [CHANGELOG.md](CHANGELOG.md).
- Contributing: See [CONTRIBUTING.md](CONTRIBUTING.md). [CONFIRM: contribution policy]. The license does not allow derivative works.
- Bug reports: open an issue at https://github.com/vishal-muralidharan/BuildForge/issues

## Maintainers

For release steps, skill updates, and repo administration, see [MAINTAINING.md](MAINTAINING.md).
Maintainer tooling, playbooks, recipes, and templates live in [maintainers/README.md](maintainers/README.md).
Run maintainer workflows through `python3 scripts/dev.py`.
Internal maintainer tooling and scripts are excluded from npm packaging.
