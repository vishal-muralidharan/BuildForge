---
name: targeted-module-testing
description: Use after any change in a project that has a .agents/project-profile.yaml. Runs the verify, deploy and report stages. Runs the project's own lint, test and build commands, checks the rule-enforcing tests, runs browser checks and a deploy loop only if the profile enables them, and ends every task with a Post-Build Audit of open questions and known issues. Use it before you say a task is done, after every build, and whenever the user asks to verify, test, check, ship or deploy.
compatibility: Needs file read, shell, and network access if deploy checks are enabled.
---

# Verification, deploy and report

Stages 4, 7 and the optional deploy stage of the pipeline. A change is not done until these pass and the report is written.

## Read first

`.agents/project-profile.yaml`: sections `commands`, `verification` and `capabilities`. Use the commands exactly as written there. Do not substitute your own.

## 1. Run the checks

| Check | Source | Pass when |
|---|---|---|
| Complete check | `commands.check` | exits 0 |
| Lint | `commands.lint` | 0 errors, and 0 warnings if `verification.zero_warnings` |
| Tests | `commands.test` | all pass |
| One test file | `commands.test_single` with `{path}` | passes |
| Build | `commands.build` | completes |

If `commands.check` is empty, run lint, test and build in that order. Empty commands are skipped. Say which ones you skipped.

Fix every failure at its cause. Do not edit a test or loosen a rule just to get a pass.

## 2. Tests

- Add a test for each new behavior. Update tests when visible copy changes.
- Assert on roles, labels and test ids. Do not assert on class names or colors.
- If `design.enforced_by` is set, that test or lint rule enforces the design rules. It must pass. Do not edit it to make a change pass unless the user agrees the rule should change. If the rule should change, change the profile through `sync-skills-and-docs`.
- Know what your test environment fakes (timers, layout, device APIs). Note any behavior that only a real browser can confirm.

## 3. Browser checks (optional)

Run only if `capabilities.browser_inspection.enabled` is true. Use the linked reference, if any, to run each sentence in `verification.browser_checks` against a build or preview.

If the capability is off, do not skip silently. List the checks under "Not run" in the report so the user can do them by hand.

## 3b. Reference checks

Run `python3 .agents/skills/extend-pipeline/scripts/refs.py due --stage verify --paths <changed files>`. Apply each listed reference to the change. Run a bundled script only if the listing says allow_scripts is true. Otherwise list it under 'Not run'. If a reference has mode gate and reports a blocking finding, stop and ask the user. Report findings under 'Third party review' in the Post-Build Audit, with the reference name.

## 4. Deploy (optional)

Run only if `capabilities.deploy.enabled` is true, and only after step 1 passes. Never deploy a failing build.

1. Run `capabilities.deploy.command` (or `commands.deploy`).
2. Check success: the command exits 0, and `verify_url` returns HTTP 200 when it is set. For example `curl -s -o /dev/null -w "%{http_code}" <verify_url>`.
3. On failure, if `on_failure` is `report`: stop. Show the failing output and the likely cause.
4. On failure, if `on_failure` is `self-heal`: read the failing output. If a linked reference documents a log command, use it. Diagnose the root cause. Fix it in code or project config with your editing tools. Re-run `commands.check`. Deploy again. Stop after `max_attempts` tries (default 3) and report what you tried.

Never change secrets, environment variables, hosting settings or billing during a self-heal loop. Ask the user instead.

## 5. Post-Build Audit

End every task with this section when `verification.post_build_report` is true. Fill it from what you actually observed. Do not pad it.

```markdown
### Post-Build Audit: Open Questions & Known Issues
- **Checks:** <what ran and the result. Not run: <what was skipped and why>>
- **Known Issues:** <edge cases, quirks and limits you found>
- **Open Questions:** <decisions that need the user>
```

Look for known issues in these places, depending on the profile:

- Always: behavior that tests cannot prove, and edge cases of the new code.
- `responsive.enabled`: the width limits, virtual keyboard overlap, safe areas and zoom.
- `design.enabled`: legibility in every theme, focus visibility and icon clarity.
- `data.storage` is set: storage quota, offline retries, migrations and idempotent writes.
- Keyboard shortcuts were added: modifiers across operating systems, and capture while typing in inputs.

Open questions are choices the user should make: trade-offs, label or placement choices, and future schema changes.

## 6. Finish

Do not commit here. Hand off to `atomic-commits`.
