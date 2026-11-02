# Build Forge

A build pipeline for agents. 11 skills, no third party content. npm package: `@v1006/build-forge`.

## Install

With npm:

1. In your project root run `npx @v1006/build-forge`. It copies the skills into `.agents/skills`. Existing skill folders are kept. Add `--force` to overwrite them.
2. Install the one dependency: `pip install pyyaml`
3. Ask your agent to run `project-bootstrap`.

By hand:

1. Copy the `skills` folder into `.agents/skills` in your project root. Merge it if the project already has one.
2. Do steps 2 and 3 above.

`package.json` and `bin/` in this folder exist only for npm publishing. Skip them when you copy by hand.

## Publish (maintainers)

1. Make sure you are logged in to npm as `v1006`, or as a member of the `@v1006` organization.
2. From this folder run `npm pack --dry-run` and check the file list.
3. Run `npm publish`. The package is set to public access.

## Pick your path

New app:
1. `product-spec`
2. `project-bootstrap`
3. `scaffold-app`
4. `feature-delivery` once per milestone

Existing project:
1. `project-bootstrap`
2. `rules-to-tests`
3. `feature-delivery` for every task

Settings page, privacy policy, terms, consent and account deletion: run `legal-and-settings-pages` through `feature-delivery`.

## What bootstrap creates

- `.agents/project-profile.yaml`: the single source of truth. Edit this, never the generated files.
- `AGENTS.md`: a short router, generated from the profile.
- Convention skills such as `build-ui` and `review-directory-structure`, generated into `.agents/skills/`.
- `.agents/repo-map.md`: a cache of where things live.

## How it adapts

Build Forge never edits itself. It reads each project and writes a project profile, AGENTS.md, convention skills and a repo map. To change behavior, edit the profile and re-render. Do not edit the pipeline skills.

## Script paths

Skills refer to scripts by skill name. In this folder they live here:

| Script | Path |
|---|---|
| Discover a repo | `.agents/skills/project-bootstrap/scripts/detect_stack.py` |
| Validate the profile | `.agents/skills/project-bootstrap/scripts/validate_profile.py` |
| Render guidance files | `.agents/skills/project-bootstrap/scripts/render.py` |
| Check a commit message | `.agents/skills/atomic-commits/scripts/check_commit_message.py` |
| Check for drift | `.agents/skills/sync-skills-and-docs/scripts/check_sync.py` |
| Run rule checks | `.agents/skills/rules-to-tests/scripts/run_rule_checks.py` |
| Add a check script | `.agents/skills/scaffold-app/scripts/ensure_check_script.py` |
| Find legal placeholders | `.agents/skills/legal-and-settings-pages/scripts/check_legal_placeholders.py` |

## Skills

| Skill | Job |
|---|---|
| `product-spec` | Idea to spec, milestones and non-goals |
| `project-bootstrap` | Creates the profile and generated guidance |
| `scaffold-app` | Green skeleton for a new app |
| `rules-to-tests` | Turns written rules into automatic checks |
| `feature-delivery` | Runs any task through 7 gated stages |
| `audit-and-planning` | Search, diagnose, atomic plan |
| `repo-search` | Read only discovery and repo map refresh |
| `atomic-commits` | One unit per commit, checked messages |
| `targeted-module-testing` | Verify, optional deploy, post build audit |
| `sync-skills-and-docs` | Keeps profile, skills and docs in step |
| `legal-and-settings-pages` | Settings, legal pages, consent, export, deletion |

Third party skills are never included. `project-bootstrap` asks whether you want to add any, and records only the repos you give it.

The legal pages are templates, not legal advice. Have a qualified person review them before launch.

## License

Build Forge is distributed under the Build Forge License. Below is a plain summary of its 9 terms (see [LICENSE](LICENSE) for the full text):

1. **Use**: Install and run on any number of projects and machines, for personal or commercial work, at no cost.
2. **No changes**: Do not modify, adapt, translate, or create derivative works of Build Forge (including its skill files, scripts, templates, references, and installer).
3. **Copies**: Keep complete, unmodified copies inside your projects and share with project collaborators. Do not publish, sell, sublicense, or distribute to anyone else.
4. **Adaptation and generated files**: All files generated for your project (project profile, AGENTS.md, convention skills, repo map) and code/documents produced belong to you and may be edited freely.
5. **Third party material**: Anything not written by the copyright holder is covered by its own terms.
6. **Ending**: The license ends automatically upon breach of any terms, requiring deletion of all copies.
7. **No warranty**: The software is provided "as is", without warranty of any kind.
8. **Limit of liability**: The copyright holder is not liable for any claims or damages arising from use.
9. **Governing law**: Subject to the governing law specified in [LICENSE](LICENSE).
