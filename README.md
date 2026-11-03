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

The installer copies the 12 pipeline skills into `.agents/skills/`. It writes `.agents/build-forge.lock.json` with a hash of every pipeline skill file.

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
| 1 | Audit & Goal | `audit-and-planning` (phases 1 and 2), `repo-search` | Root cause diagnosed. Protected data identified. Goal invariants defined in `.agents/work/CURRENT_GOAL.md`. |
| 2 | Plan | `audit-and-planning` (phases 3 and 4) | Every step has a target, a verify command and a commit message. Plan approved if over 5 steps or touching protected items. |
| 3 | Build step | The convention skill for the area (`build-ui`, `review-db-structure`, and so on) | The step does 1 thing and follows the rules of its area. |
| 3a | Verify step | `targeted-module-testing`, step 1 | The step's checks pass with 0 errors and 0 warnings. Atomic rollback triggers after 2 consecutive check failures. |
| 3b | Commit step | `atomic-commits` | The message passes the checker. Step committed. |
| 4 | Sync | `sync-skills-and-docs`, and `rules-to-tests` if a new enforceable rule appeared | The profile, generated files and docs match the code. The drift checker is clean. |
| 5 | Full verify | `targeted-module-testing`, steps 1 to 3 | `commands.check` passes. Tests and browser checks pass. |
| 5a | Goal loop gate | `targeted-module-testing`, step 2b | All acceptance invariants from `CURRENT_GOAL.md` are evaluated. If all pass, proceed to stage 6. If any fail, re-enter loop at stage 3. |
| 6 | Deploy (optional) | `targeted-module-testing`, step 4 | Runs only if `capabilities.deploy.enabled` is true. |
| 7 | Report | `targeted-module-testing`, step 5 | The Post-Build Audit is written. `CURRENT_GOAL.md` marked completed. |

## What it creates in your project

```text
.agents/
  project-profile.yaml          # Generated: Single source of truth for the project
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

- **Build Forge files**: The 12 pipeline skills in `.agents/skills/` and `.agents/build-forge.lock.json`. These are read only files from the npm package.
- **Generated files**: `.agents/project-profile.yaml`, `AGENTS.md`, `.agents/repo-map.md`, `.agents/checks/`, and convention skills like `build-ui`. These files adapt to your project, belong to you, and may be edited freely.

## Skills

| Skill | What it does | When to use it |
|---|---|---|
| `atomic-commits` | Enforces small, single purpose commits with checked messages. | When committing code in a project with a profile, before starting the next unit of work. |
| `audit-and-planning` | Searches codebase, diagnoses root cause, checks rules, and writes an atomic plan. | Before starting any feature, bug fix or refactor, even for small tasks. |
| `extend-pipeline` | Extends the pipeline with vetted, pinned third party skills. | When adding external skills, review tools, hosting recipes, or updating references. |
| `feature-delivery` | Conductor for the build pipeline with gates between all 7 stages. | For every task to add, build, fix, refactor or ship code in a project with a profile. |
| `legal-and-settings-pages` | Adds settings, legal pages, data management, terms consent, and account deletion. | When adding settings, privacy policies, terms, GDPR/CCPA pages, or account deletion. |
| `product-spec` | Turns rough app ideas into specs with users, core flows, milestones and steps. | At the very start of a new app, or to cut big features into milestones. |
| `project-bootstrap` | Sets up the build pipeline and creates the profile, AGENTS.md, skills, and repo map. | When onboarding a repo, starting a new app, or updating project guidelines. |
| `repo-search` | Performs read-only discovery of symbols, components, tokens, and fields. | Before creating new files or functions, or when refreshing the repo map. |
| `rules-to-tests` | Turns written project rules into automatic checks that fail the build when broken. | After bootstrap or scaffolding, or when conventions need automated enforcement. |
| `scaffold-app` | Creates the first green skeleton app from official framework generators. | Right after project-bootstrap in new mode, on empty repositories. |
| `sync-skills-and-docs` | Detects drift and updates profile, skills, README and repo map. | At the end of structural changes, or when docs and code get out of sync. |
| `targeted-module-testing` | Runs lint, test, build, rule checks, browser checks, and post-build audit. | Before marking any task done, after every build, and before deploy. |

## The project profile

The project profile is the single source of truth for the build pipeline. It lives at `.agents/project-profile.yaml`. Every pipeline skill reads this file first. Edit the profile to change rules, commands, or layouts, then re-render guidance files.

For schema details, see [profile-schema.md](skills/project-bootstrap/references/profile-schema.md).
For a full worked example, see [example-nemo.project-profile.yaml](skills/project-bootstrap/references/example-nemo.project-profile.yaml).

Here is a snippet from that example file:

```yaml
schema_version: 1

project:
  name: NeMo
  summary: Fast, local first expense and income tracker.
  mode: existing
  platforms: [web, pwa]

stack:
  language: javascript
  framework: React 19
  bundler: Vite
  styling: Tailwind v4
  router: none
  state: React context
  package_manager: npm
  test_runner: Vitest
  linter: Oxlint
  backend: Supabase (optional sync)
  auth: Supabase
  database: Supabase Postgres
  hosting: Vercel
```

## Automatic rule checks

`rules-to-tests` reads rules in `.agents/project-profile.yaml` and turns them into automatic checks. It copies a test runner (`run_rule_checks.py`) into `.agents/checks/` and connects it to the project check command.

A rule can define a `check` block with types such as `forbid`, `require_file`, `forbid_file`, or `root_only`:

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
```

See [check-patterns.md](skills/rules-to-tests/references/check-patterns.md) for patterns.

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

1. Delete the 12 pipeline skill folders from `.agents/skills/`.
2. Delete `.agents/build-forge.lock.json`.

All generated files (`.agents/project-profile.yaml`, `AGENTS.md`, convention skills, and the repo map) remain in your repository and stay yours.

## Safety

- `project-bootstrap` writes only to `.agents/`, `AGENTS.md`, and the skills directory. It never edits application code.
- `render.py` never overwrites existing files unless `--force` is passed.
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
| `AGENTS.generated.md already exists` | `render.py` found an existing `AGENTS.md` and avoided overwriting it. | Merge changes from `AGENTS.generated.md` into `AGENTS.md`, or run `render.py --force`. |
| `verify` exits with code 2 | Lock file is missing. | Run `npx @v1006/build-forge install` to write `.agents/build-forge.lock.json`. |
| `verify` shows `modified` (exit code 1) | Skill files were altered or contain extra files. | Run `npx @v1006/build-forge install --force` to restore clean pipeline skills. |

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
- Bug reports: [CONFIRM: where to report bugs]

## Maintainers

For release steps, skill updates, and repo administration, see [MAINTAINING.md](MAINTAINING.md).
