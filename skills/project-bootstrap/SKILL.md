---
name: project-bootstrap
description: Set up the build pipeline for any project, whether it is an existing codebase or a brand new app. Creates .agents/project-profile.yaml (the single source of truth for stack, commands, folder layout, naming, design, data and git rules), then generates AGENTS.md, convention skills and a repo map from it. Use this whenever the user wants to add the pipeline, agent guidelines, AGENTS.md, project rules or skills to a repo, start a new app with the pipeline, onboard an existing codebase, regenerate or update the project profile, or says things like "bootstrap", "set up my project for agents", "generalize my skills" or "make my AGENTS.md reusable", even if they do not name this skill.
compatibility: Needs file read, file edit, shell, git, Python 3, and PyYAML.
---

# Project bootstrap

Every other pipeline skill reads one file first: `.agents/project-profile.yaml`. This skill creates and maintains that file. It works the same way for an existing repo and for a new app. Only the first stage differs. After the profile exists, audit, plan, build, verify, commit and docs all behave identically. That is why one pipeline stays efficient in both cases.

The profile holds facts (stack, commands, layers, naming, breakpoints, commit scopes) and rules. Each rule is written once, in the profile. AGENTS.md and the convention skills are generated views of it. This prevents the drift that happens when the same rule is copied into 3 files by hand.

The 5 process skills (`audit-and-planning`, `repo-search`, `atomic-commits`, `targeted-module-testing`, `sync-skills-and-docs`) ship in the same pipeline pack. Install them next to this skill. The renderer warns if any are missing.

Bootstrap never edits application source code. It writes only `.agents/`, the AGENTS.md router and the skills folder.

Scripts live in this skill's `scripts/` folder. Run them with the full path to that folder. If python3 is not found, use python or py -3.

## Step 0: Pick the mode

1. If `.agents/project-profile.yaml` exists, use **update mode**. Run discovery again, compare with the profile, and show the user each difference. Never change a rule silently.
2. Otherwise run `python3 .agents/skills/project-bootstrap/scripts/detect_stack.py <repo_root>`. Read `suggested_mode`.
3. If the user says this is a new app, or discovery finds no manifest and fewer than 3 source files, use **new mode**. If the repo has code, use **existing mode**. When unsure, ask in 1 question.

## Existing mode

1. Run legacy inventory:
   Run `python3 .agents/skills/project-bootstrap/scripts/legacy_import.py inventory --root <repo_root>`.
   This inventories statements from existing agent instruction files and legacy skills into `.agents/legacy-parity.md`. Never delete or move the legacy files.
2. Read the discovery JSON and the legacy parity ledger. Also read `AGENTS.md`, `CONTRIBUTING.md`, `README.md`, and any agent instruction files when they exist. They hold rules the code cannot show.
3. Copy `assets/project-profile.template.yaml` to `.agents/project-profile.yaml`. Fill only what the evidence supports.
   - Commands: use `commands_suggested`. If there is no single `check` command, propose one that chains lint, test and build, and ask before adding it to `package.json`.
   - Naming: state a style only when it covers at least 80% of files of that kind. Otherwise leave a TODO and ask.
   - Commit rules: copy the style from `git` facts only when `conventional_ratio` is at least 0.8. Seed `git.scopes` from `detect_stack` git facts (`most_used_scopes` in history) and from layer names. Ask the user for a purpose for each scope, with a default taken from the matching layer purpose.
   - Layers: use `layers`. Write one plain purpose per folder. Mark a guessed purpose as TODO.
4. Reconcile legacy statements:
   Run `python3 .agents/skills/project-bootstrap/scripts/legacy_import.py batch --area <area>` for each area with pending items. Propose defaults and ask the user whether to accept or drop each item:
   `python3 .agents/skills/project-bootstrap/scripts/legacy_import.py apply --accept <ids> --drop <ids> --reason "<reason>"`
   Do not finish bootstrap while `python3 .agents/skills/project-bootstrap/scripts/legacy_import.py status` exits 1.
5. Move every remaining uninventoried rule from guideline files into the `rules` list. One sentence each, imperative, with an id and an area. Set `enforced_by` to `test` or `lint` only after you find the test or lint rule that enforces it. Otherwise use `manual`.
6. Ask the user about gaps in 1 batch of 5 questions or fewer. Offer your best guess as the default for each. See `references/interview.md` for the gap questions.
7. Run the external references step below.
8. Validate, render and report (see "Finish").

## New mode

1. If `docs.spec` names a file, or `docs/product-spec.md` exists, read it and prefill every answer it covers. If there is no spec and the idea is vague, suggest running `product-spec` first. Then interview in at most 3 short rounds using `references/interview.md`: product, stack, then design and data. Ask only what the spec leaves open. Offer a default for every question. Accept "you decide".
2. Write the profile with `mode: new`. Turn each decision into a rule. For example, "monochrome design" becomes a design rule with an id.
3. Fill `structure.layers` with the folders the stack needs. Fill `commands` with the commands the chosen tooling will provide.
4. Run the external references step below.
5. Validate and render.
6. Scaffolding: if the `scaffold-app` skill is available, hand off to it. Otherwise create only the empty folders from `structure.layers` and tell the user that code scaffolding is the next step. Do not generate application code here.

Order for a new app: `product-spec`, then `project-bootstrap`, then `scaffold-app`, then `feature-delivery` once per milestone.

## External references (both modes)

Ask once whether the user wants third party skills. If yes, run the extend-pipeline skill. If no, record nothing.

- Skipping is a valid answer. Record nothing and leave the capability slots disabled. The pipeline then skips those stages.
- Never recommend or suggest third party repositories on your own.
- Deploy is opt in. Set `capabilities.deploy.enabled` to true only when the user asks for it or already has a deploy command they want in the pipeline. Never add a mandatory production deploy rule by default.

## Finish

1. In existing mode, run `python3 .agents/skills/project-bootstrap/scripts/legacy_import.py status --root <repo_root>`. It must exit 0. Do not finish while status exits 1.
2. Run `python3 .agents/skills/project-bootstrap/scripts/validate_profile.py --profile .agents/project-profile.yaml --root <repo_root>`. Fix every error. Show the user any remaining TODO.
3. Run `python3 .agents/skills/project-bootstrap/scripts/render.py --profile .agents/project-profile.yaml --root <repo_root>`. It never overwrites existing files. If `AGENTS.md` exists it writes `AGENTS.generated.md`. Help the user merge it, then offer to delete the generated copy.
4. Report in this shape:

```
Detected: <stack and commands found, with the file each came from>
Legacy parity: <coverage percent and summary counts>
Asked and answered: <questions and the user's answers>
Still TODO: <unresolved fields>
Files written: <paths>
External references: <declared, installed, or none>
Next step: <one sentence>
```

5. Do not commit. The user commits, or the commit stage of the pipeline does.

## Reference files

- `references/profile-schema.md`: every field, allowed values, and which pipeline stage reads which field. Read it when you fill or change a profile.
- `references/interview.md`: question banks for new mode and for gaps in existing mode.
- `references/external-references.md`: how to install and vet a third party skill repo.
- `references/example-nemo.project-profile.yaml`: a complete worked profile.
- `assets/project-profile.template.yaml`: the blank profile to copy.

## Quoting in the profile

Quote any YAML string that contains a comma, a colon or a leading symbol. An unquoted comma inside a one line mapping silently splits the value. The validator reports stray keys for this reason.
