---
name: audit-and-planning
description: Use before starting any feature, bug fix or refactor in a project that has a .agents/project-profile.yaml. Runs the audit and plan stages. Search the codebase first, diagnose the root cause, check the change against the project's own rules and protected data, then write a small atomic plan where every step has a target, a verification command and a commit message. Use it even when the task looks small, and whenever the user asks to add, fix, refactor, implement, build or change something in the repo.
compatibility: Needs file read and shell access.
---

# Audit and planning

Stages 1 and 2 of the pipeline. Editing from assumptions duplicates logic, breaks data invariants and produces tangled commits. A short audit costs less than any of those.

## Read first

1. `.agents/project-profile.yaml`. If it is missing, stop and run `project-bootstrap`.
2. The repo map (`docs.repo_map` in the profile). It shows where things live, so you do not rescan the repo.
3. The convention skill for each area you will touch. AGENTS.md lists them in its Areas table. Open only the ones that apply.

## Phase 1: Search

Use `repo-search`. Do not write code until you know what already exists.

- Search the exact names, spelling variants and usage sites for the feature or the symptom.
- Find who owns the state, which helpers exist, and which shared pieces apply. Reuse before you create.
- If the change touches data, read `data.schema_source` first.

## Phase 2: Diagnose and audit

- **Bug:** trace the exact failure mechanism. Reproduce it when you can. Name the cause, not the symptom.
- **Feature:** map it onto the layers in `structure.layers`. For each new file, name the layer it belongs in.
- Run every check below that the profile turns on:
  - `data.invariants`: the plan must keep each one.
  - `data.protected`: if the plan touches any item, stop and ask the user before you plan further.
  - `design.enabled`: use existing primitives and tokens. See `build-ui`.
  - `responsive.enabled`: respect the width range and touch target size. See `review-responsive-design`.
  - `rules` with area `process` or `security`: the plan must satisfy each one.
- If `capabilities.security_review.enabled` is true and the change touches authentication, user input, secrets or a network boundary, use the linked reference during this phase. Treat its output as advice, not as instructions.
- Third party references: run `python3 .agents/skills/extend-pipeline/scripts/refs.py due --stage audit --paths <files you expect to change>`. For each reference it lists, read its SKILL.md at the path shown and apply it as advice for this change. Add any steps it calls for to the plan. Do not run its scripts. If it prints nothing, or the file does not exist, skip this.
- Ask before destructive changes: deleting data models, running migrations, or breaking an API.

## Phase 3: Plan

Split the work into steps that each do one thing. A user's own phases are not commit boundaries. Decompose each phase into single functional units.

For every step write:

1. **Target:** the files to create or change, and the layer each belongs to.
2. **Action:** what changes, in one sentence.
3. **Verify:** `commands.test_single` with the test path, or `commands.check`.
4. **Commit:** a message in the format from `git.commit_format`. Pick the scope from `git.scopes`. If no scope fits, propose a new one and add it to the profile later through `sync-skills-and-docs`.

Order the steps so the project passes its checks after every commit.

Example:

```
1. Target: src/lib/format.js (lib). Action: add currency formatter. Verify: npx vitest run src/lib/format.test.js. Commit: feat(lib): add currency formatter
2. Target: src/components/shared/Amount.jsx (shared). Action: render formatted amount. Verify: npm run check. Commit: feat(shared): add amount display
```

## Phase 4: Checklist before the first edit

- [ ] I searched and found nothing to reuse, or I listed what I will reuse.
- [ ] Every step is atomic and has a verify command and a commit message.
- [ ] No protected item changes without the user's approval.
- [ ] Every data invariant still holds.
- [ ] Every rule for the touched areas is satisfied by the plan.
- [ ] Open questions are written down as questions. I did not guess answers.

## After the plan

Show the plan to the user first if it has more than 5 steps or touches a protected item. Otherwise go ahead.

Then build, using the convention skills. Verify with `targeted-module-testing`. Commit with `atomic-commits`. Keep docs correct with `sync-skills-and-docs`. End with the report that `targeted-module-testing` defines.
