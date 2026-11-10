---
name: branch-dev-protocol
description: "Maintainer playbook for feature branch development, local verification, pull request creation, CI matrix monitoring, merge commit merging, and main branch synchronization."
---

# Branch Development Playbook

Use this playbook whenever developing changes on a separate branch in the Build Forge repository.

## Overview

All changes in the Build Forge repository follow a structured branch lifecycle:
1. Start from an up to date, clean `main` branch.
2. Develop on a dedicated task branch (`feat/<slug>` or `fix/<slug>`).
3. Commit in atomic steps with conventional commit messages.
4. Run full repository verification suites before pushing.
5. Push to GitHub and open a pull request via `gh`.
6. Watch GitHub Actions CI matrix across Ubuntu, macOS, and Windows.
7. Merge into `main` with a merge commit after all checks pass.
8. Switch to `main`, fast-forward pull, and clean up the local branch.

## Steps

### 1. Pre-flight and branch creation
Confirm working tree is clean:
```bash
git status
```

Switch to `main` and pull latest changes:
```bash
git switch main
git pull --ff-only
```

Create a new branch:
```bash
git switch -c feat/<slug>
```
Use `feat/<slug>` for features or `fix/<slug>` for bug fixes. Slug must be lowercase kebab-case, 40 characters or fewer.

### 2. Atomic commits
Commit changes in cohesive units:
- 1 commit per step.
- Follow conventional commit format: `<type>(<scope>): <subject>`.
- Keep commit message subject under 72 characters, lowercase, no trailing period.
- Do not commit broken code.

### 3. Verification suite
Run all verification checks before pushing:

```bash
# Refresh and verify integrity
python3 scripts/make_integrity.py
python3 scripts/make_integrity.py --check

# Clean python bytecode artifacts
find . -name "__pycache__" -exec rm -rf {} + && find . -name "*.pyc" -delete

# Run CI check suite
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/ci_check.py

# Run maintainer tool checks
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/dev.py check

# Check package boundaries
npm pack --dry-run
```

### 4. Push and open pull request
```bash
git push -u origin <branch-name>
gh pr create --base main --head <branch-name> --title "<type>(<scope>): <subject>" --body "<summary>"
```

### 5. Monitor CI matrix
Watch CI checks across Ubuntu, macOS, and Windows:
```bash
gh pr checks <pr-number> --watch
```

If checks fail:
- Run `gh run view <run-id> --log-failed` to diagnose.
- Remember: test repositories created during unit tests must configure `git config user.name` and `git config user.email` because runner environments lack global git user configuration.
- Address the failure on the branch, commit, push, and watch checks again.

### 6. Merge with a merge commit and sync main
Once all CI checks pass, merge with a merge commit:
```bash
gh pr merge <pr-number> --merge
git switch main
git pull --ff-only
git branch -d <branch-name>
```

Never use `--squash` or `--rebase`. Squash merging flattens atomic commits into one and destroys history. See `maintainers/skills/merge-trail/SKILL.md` for full policy details.

