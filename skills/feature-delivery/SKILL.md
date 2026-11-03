---
name: feature-delivery
description: Run any goal in a project end to end through the build pipeline with an iterative verification loop that runs until the goal is achieved. Audit, plan, build one atomic step at a time, verify, commit, sync docs, verify goal invariants, deploy if enabled, and report. Use it for every request to add, build, implement, fix, refactor, change or ship something in a repo that has a .agents/project-profile.yaml.
compatibility: Needs file read, file edit, shell, git, and Python 3.
---

# Feature delivery

The conductor for the pipeline. It does not hold rules of its own. It decides which skill runs when, and it enforces gates between stages. The profile and convention skills hold the rules.

## Core Principle: Goal-Oriented, Not Task-Oriented

Agents often stop once a task checklist is complete, even if the user's ultimate goal remains unmet or broken. This pipeline is goal-oriented:
1. Define verifiable acceptance criteria and invariants for the goal before starting.
2. Execute the steps incrementally with atomic commits.
3. Run an evaluation loop after verification. If any acceptance invariant fails, the agent diagnoses the delta, adjusts the plan, and loops until the goal is fully achieved.

## Read first

1. `.agents/project-profile.yaml`. If it is missing:
   - Existing code: run `project-bootstrap`.
   - New app: run `product-spec`, then `project-bootstrap`, then `scaffold-app`.
2. Pre-flight branch gate: Check `git branch --show-current`. If on `main` or `master` and the task is a feature or non-trivial fix, check `git.protected_branches` in the profile. Ask the user or create a feature branch (`feat/<name>` or `fix/<name>`) before writing code.
3. `git status`. If the working tree has uncommitted changes you did not make, tell the user and ask whether to commit them, stash them or continue. Never mix someone else's changes into your commits.
4. The repo map at `docs.repo_map`.
5. Run `python3 .agents/skills/extend-pipeline/scripts/refs.py verify`. If it reports a difference, tell the user and ask.

Open only what each stage needs. Do not load every skill at the start. That wastes context and slows the work.

## Task router

Pick the workflow matching the request type:

| Request type | Workflow file |
|---|---|
| Bug fix or regression | `references/workflows/fix-bug.md` |
| Code review or diff audit | `references/workflows/review-changes.md` |
| Release preparation or version bump | `references/workflows/release-prep.md` |
| Feature or general delivery | Stages 0 to 7 below |

## Stages and gates

| # | Stage | Skill to use | Gate: do not continue until |
|---|---|---|---|
| 0 | Pre-flight | git | Branch is verified and working tree is clean. |
| 1 | Audit & Goal Definition | `audit-and-planning` (phases 1 and 2), `repo-search` | Root cause diagnosed. Protected data identified. Goal invariants and measurable acceptance criteria written to `.agents/work/CURRENT_GOAL.md`. |
| 2 | Plan | `audit-and-planning` (phases 3 and 4) | Every step has a target, a verify command, and a commit message. Plan approved if over 5 steps or touching protected items. |
| 3 | Build step | Area convention skill (`build-ui`, etc.) | The step does 1 thing and follows the rules of its area. |
| 3a | Verify step | `targeted-module-testing`, step 1 | The step's checks pass with 0 errors and 0 warnings. |
| 3b | Commit step | `atomic-commits` | Message passes checker. Step committed. |
| 4 | Sync | `sync-skills-and-docs`, `rules-to-tests` | Profile, generated files, docs match code. Drift checker clean. |
| 5 | Full verify | `targeted-module-testing`, steps 1 to 3 | `commands.check` passes. Tests and browser checks pass. |
| 5a | Goal loop gate | `targeted-module-testing`, step 3b | All acceptance invariants from `CURRENT_GOAL.md` are evaluated. If all pass, proceed to stage 6. If any fail, re-enter loop. |
| 6 | Deploy (optional) | `targeted-module-testing`, step 4 | Runs only if `capabilities.deploy.enabled` is true. |
| 7 | Report | `targeted-module-testing`, step 5 | Post-Build Audit written. `CURRENT_GOAL.md` marked completed. |

Stages 1, 5 and 6 consult references through `due`. A gate reference with a blocking finding stops the stage until the user decides.

Repeat stages 3, 3a and 3b for each step in the plan. Never start step N+1 while step N fails its checks or is uncommitted.

## The Goal Loop

After Stage 5 (Full verify), do not assume the task is finished just because tests exited with code 0. Evaluate the goal:

1. Check every acceptance invariant in `.agents/work/CURRENT_GOAL.md`.
2. Inspect the live behavior, output data, or rendered UI against the goal.
3. Decision:
   - **Goal Achieved**: All invariants proven true. Proceed to stage 6 and 7.
   - **Goal Not Achieved**: Identify the gap between current behavior and the desired goal. Add corrective steps to the plan, increment iteration count in `CURRENT_GOAL.md`, and loop back to Stage 3.
   - **Safety Limit**: If the goal is not met after 3 corrective iterations, pause. Present the exact gap, current test status, and options to the user for direction.

## Atomic Rollback Protocol

When working on Stage 3 and 3a:
- If a step fails verification, fix the issue and re-verify.
- If the same step fails verification 2 times in a row, do not fix forward blindly. Piling edits onto broken code causes compound failures.
- Roll back the failed step to the last clean commit with `git restore .` or `git reset --hard HEAD`.
- Re-read the step requirements, rethink the approach, and attempt a clean implementation.

## Keeping track with CURRENT_GOAL.md

Always record task progress in `.agents/work/CURRENT_GOAL.md`:

```markdown
# Goal: <objective description>
Iteration: 1
Status: in_progress

## Acceptance Invariants
- [ ] Invariant 1: <measurable outcome>
- [ ] Invariant 2: <expected behavior or contract>

## Plan Steps
- [x] Step 1: <target> (commit: <hash>)
- [ ] Step 2: <target> (current)
- [ ] Step 3: <target>
```

Update the checkboxes after each commit. If a session is interrupted or context is compacted, read `CURRENT_GOAL.md` and `git log` to resume immediately at the first uncompleted step.

## When to stop and ask

Stop and ask the user when:

- A step would change a protected item or do something destructive.
- A rule in the profile conflicts with what the user asked for. Name both. Do not pick silently.
- A step fails verification twice and rollback does not resolve it. Show the evidence.
- The goal loop reached 3 iterations without achieving all acceptance invariants.
- You need a decision that is not in the profile or the spec.

## New app milestones

1. Read the milestone in `docs.spec`. Use its draft steps as the starting plan. `audit-and-planning` makes them concrete with real paths.
2. Run stages 0 to 7 through the goal loop.
3. When the milestone ships and its acceptance invariants pass, mark it done in the spec. Draft steps for the next milestone and show the user. Do not start without a yes.

## Final message

End with this:

```
Goal: <what was achieved and verified, in 1 or 2 sentences>
Iterations: <count of goal loop cycles>
Commits: <short hash and message for each>
Checks: <what ran and the result>
Docs synced: <profile, generated files, README, repo map: yes or what remains>
Post-Build Audit: <known issues and open questions, from verify skill>
Next: <1 sentence>
```

Do not push. Pushing follows the profile's push policy and the user's request.
