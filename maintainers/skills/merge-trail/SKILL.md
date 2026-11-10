---
name: merge-trail
description: "Maintainer playbook to open a PR, merge a pull request with a merge commit, keep history clean, view the merge trail, handle squash or rebase questions, and point a release tag."
---

# Merge Trail Playbook

Follow this playbook when opening, reviewing, or merging pull requests in Build Forge.

## Merge Policy

1. Every change reaches `main` only through a pull request, merged with a merge commit (`gh pr merge <number> --merge` or GitHub "Create a merge commit"). Never squash. Never rebase and merge.
2. Never push to `main` directly.
3. One branch per task, named `<type>/<slug>`.
4. Every commit on a branch is a meaningful unit with a conventional commit subject. No WIP, fixup!, squash! or "address review" commits. Fix the last unpushed commit with `git commit --amend`. After a push, add new commits with real subjects.
5. Never merge `main` into a feature branch. If a branch falls behind `main`, ask the maintainer. Agents never rebase or force push.
6. Keep GitHub's default merge commit message so the trail reads like the existing history.
7. Dependabot PRs follow the same rules.
8. History on `main` is never rewritten. Direct commits that predate this policy are listed in `maintainers/history-baseline.txt` with the reason.
9. A release tag always points at a merge commit on `main`.

## Workflow

### 1. Open a Pull Request
Push your branch and open a PR against `main`:
```bash
git push -u origin <branch-name>
gh pr create --base main --head <branch-name> --title "<type>(<scope>): <subject>" --body "<body>"
```

### 2. Wait for Green CI
Run local commit lint and history checks before pushing:
```bash
python3 scripts/check_commits.py --base origin/main --head HEAD
python3 scripts/check_history.py --ref main
python3 scripts/dev.py repo-settings
```

Monitor checks until all pass:
```bash
gh pr checks <number> --watch
```
All status checks must pass, including `commit-lint`.

### 3. Merge with a Merge Commit
Run:
```bash
gh pr merge <number> --merge
```
Never use `--squash` or `--rebase`. Squash loses atomic commit history and breaks the merge trail.

### 4. Sync Main Afterward
```bash
git switch main
git pull --ff-only
git branch -d <branch-name>
```

### 5. View the Trail
Verify the merge trail:
```bash
python3 scripts/dev.py trail
git log --graph --oneline --decorate -30
```

## Special Situations

- **Branch is behind main**: Do not merge `main` into the branch. Ask the maintainer to assist. Agents never rebase or force push.
- **Commits are messy**: If unpushed, clean up with `git commit --amend`. If already pushed, do not force push or rebase. Add new commits with conventional subjects explaining the fix.
- **Dependabot PRs**: Merge them using `gh pr merge <number> --merge`. Never squash them.

## Prohibited Agent Actions

- Never push directly to `main`.
- Never run `gh pr merge` with `--squash`, `--rebase`, `--admin`, or `--auto`.
- Never run `git push --force` or `--force-with-lease`.
- Never run `git rebase` or `git reset --hard` on shared branches.
- Never merge `main` into a feature branch.
