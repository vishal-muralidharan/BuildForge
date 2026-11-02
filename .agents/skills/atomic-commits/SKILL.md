---
name: atomic-commits
description: Use whenever you are about to commit code in a project that has a .agents/project-profile.yaml. Enforces small, single purpose commits whose message follows the project's own format, scopes and push policy. Validates the message with a script. Use it after finishing any cohesive unit of work, before starting the next one, and whenever the user says commit, save my work, or wrap up.
compatibility: Needs Python 3 and PyYAML for the message checker. Git is required.
---

# Atomic commits

Stage 5 of the pipeline. One functional unit per commit makes rollbacks, reviews and bisects easy. Mixed commits make all three hard.

## Read first

`.agents/project-profile.yaml`, section `git`. It sets the message format, allowed types, allowed scopes, the push policy and the staging policy. Do not assume any of them.

## Principles

- **One unit per commit.** A unit is one function, step, module or file group that does one job. Do not batch unrelated changes because they were mentioned in the same prompt.
- **The plan sets the boundaries, not the prompt.** If the user gave broad phases, decompose them into units first (see `audit-and-planning`) and commit each unit on its own.
- **Never commit broken code.** The checks in the next section must pass first.
- **Respect the push policy.** If `git.push` is `never`, never run `git push`, even to be helpful, unless the user's current message tells you to push. If it is `ask`, ask first. If it is `allowed`, push only when the work is done.

## Workflow

### 1. Find the boundary

State the single unit you just finished and list the files that belong to it. Leave out build output, caches, `.DS_Store` and anything in `.gitignore`.

### 2. Verify

Run the cheapest commands that cover the change:

- `commands.lint` and `commands.build`.
- `commands.test_single` for each test you touched.
- If only `commands.check` is set, run it.

Run the full `commands.check` before the last commit of a task. Fix failures before you stage anything. Apply the same zero warnings standard as `verification.zero_warnings`.

Then run `git diff` and `git status`. Confirm that only intended changes are present.

### 2b. Make each commit stand alone

Every commit must pass the checks by itself, not only the last one. Two habits make that true:

- **Order units by dependency.** Commit the file that is called before the file that calls it. For example, commit a check script before the `package.json` entry that runs it.
- **Split shared files.** When 1 file serves 2 units (a manifest, a config, an index), stage only the hunks of the current unit with `git add -p`.

After a multi unit task, you can prove it with `git rebase -x "<commands.check>" <base-commit>`. It runs the check on every commit and stops at the first one that fails.

### 3. Stage

- If `git.stage` is `granular`: stage named paths only, with `git add <path> <path>`. Do not use `git add .` or `git add -A`.
- If `git.stage` is `all`: `git add -A` is allowed after you read `git status`.

### 4. Write the message

Use the format in `git.commit_format`. Use a type from `git.types`. If `git.scopes` has entries, pick one. If none fits, do not invent one silently. Use the closest scope, finish the commit, and tell the user a new scope is needed so `sync-skills-and-docs` can add it to the profile.

If `git.single_line` is true, write the subject line only. No body, no footer.

Write the subject in the present tense, in lowercase, with no final period. Keep the line under 72 characters.

Check the message before you commit:

```bash
python <this-skill>/scripts/check_commit_message.py --profile .agents/project-profile.yaml "feat(ui): add button"
```

Fix every error it reports. Warnings are advice.

### 5. Commit and confirm

```bash
git commit -m "<message>"
git log -n 1 --oneline
```

Do not push unless the push policy and the user's request allow it.

## Guardrails

1. One unit per commit.
2. Verification passes before staging, and each commit passes on its own.
3. The message passes the checker.
4. No build artifacts in any commit.
5. No push unless allowed.
6. Do not bypass the checks to save time.
