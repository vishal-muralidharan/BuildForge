---
name: feature-delivery
description: Run any task in a project end to end through the build pipeline, with a gate between every stage. Audit, plan, build one atomic step at a time, verify, commit, sync docs, deploy if enabled, and report. Use it for every request to add, build, implement, fix, refactor, change or ship something in a repo that has a .agents/project-profile.yaml, including each milestone of a new app. Use it even for small tasks, so the stages and the report are never skipped.
compatibility: Needs file read, file edit, shell, git, and Python 3.
---

# Feature delivery

The conductor for the pipeline. It does not hold rules of its own. It decides which skill runs when, and it stops at each gate. The profile and the convention skills hold the rules.

## Read first

1. `.agents/project-profile.yaml`. If it is missing:
   - Existing code: run `project-bootstrap`.
   - New app: run `product-spec`, then `project-bootstrap`, then `scaffold-app`.
2. `git status`. If the working tree has changes you did not make, tell the user and ask whether to commit them, stash them or continue. Never mix someone else's changes into your commits.
3. The repo map at `docs.repo_map`.
4. Run `python3 .agents/skills/extend-pipeline/scripts/refs.py verify`. If it reports a difference, tell the user and ask.

Open only what each stage needs. Do not load every skill at the start. That wastes context and slows the work.

## Stages and gates

| # | Stage | Skill to use | Gate: do not continue until |
|---|---|---|---|
| 1 | Audit | `audit-and-planning` (phases 1 and 2), `repo-search` | Nothing in `data.protected` is touched without the user's yes. Open questions are answered or listed. |
| 2 | Plan | `audit-and-planning` (phases 3 and 4) | Every step has a target, a verify command and a commit message. The user approved the plan if it has more than 5 steps or touches a protected item. |
| 3 | Build, one step at a time | The convention skill for the area (`build-ui`, `review-db-structure`, and so on) | The step does one thing and follows the rules of its area. |
| 3a | Verify the step | `targeted-module-testing`, step 1 | The step's checks pass with 0 errors and 0 warnings. |
| 3b | Commit the step | `atomic-commits` | The message passes the checker. |
| 4 | Sync | `sync-skills-and-docs`, and `rules-to-tests` if a new enforceable rule appeared | The profile, generated files and docs match the code. The drift checker is clean. |
| 5 | Full verify | `targeted-module-testing`, steps 1 to 3 | `commands.check` passes. Browser checks ran, or are listed as not run. |
| 6 | Deploy (optional) | `targeted-module-testing`, step 4 | Runs only if `capabilities.deploy.enabled` is true. |
| 7 | Report | `targeted-module-testing`, step 5 | The Post-Build Audit is written. |

Stages 1, 5 and 6 consult references through `due`. A gate reference with a blocking finding stops the stage until the user decides.

Repeat stages 3, 3a and 3b for each step in the plan. Never start step N+1 while step N fails its checks or is uncommitted.

## Keeping track

- For a plan of 8 steps or fewer, keep the plan in the chat and tick steps off in your messages.
- For a longer plan, write it to `.agents/work/plan.md` as a checklist and update it after every commit. Tell the user to add `.agents/work/` to `.gitignore` if it is not there. Delete the file when the report is done.
- To resume after an interruption, read the plan file and `git log`. Continue at the first step with no commit.

## When to stop and ask

Stop and ask the user when:

- A step would change a protected item or do something destructive.
- A rule in the profile conflicts with what the user asked for. Name both. Do not pick silently.
- The same check fails twice for the same cause after a fix. Show the evidence.
- The work grew past the plan. Add the new steps to the plan, show them, and get a yes.
- You need a decision that is not in the profile or the spec.

## New app milestones

1. Read the milestone in `docs.spec`. Use its draft steps as the starting plan. `audit-and-planning` makes them concrete with real paths.
2. Run stages 1 to 7.
3. When the milestone ships, mark it done in the spec. Draft the steps for the next milestone and show the user. Do not start it without a yes.

## Final message

End with this:

```
Done: <what now works, in 1 or 2 sentences>
Commits: <short hash and message for each>
Checks: <what ran and the result>
Docs synced: <profile, generated files, README, repo map: yes or what remains>
Post-Build Audit: <known issues and open questions, from the verify skill>
Next: <1 sentence>
```

Do not push. Pushing follows the profile's push policy and the user's request.
