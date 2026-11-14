# Contributing to Build Forge

Bug reports and suggestions are welcome.

Code contributions: Pull requests from outside contributors are not accepted at this time, because the license does not allow derivative works. If you want to change something, open an issue first and describe it. A code change can be considered after a written agreement with the copyright holder.

## Pull requests

These rules apply to maintainers, and to anyone who has a written agreement to contribute. All changes must go through a pull request merged with a merge commit. Follow these requirements:

- One branch per task, named `<type>/<slug>`.
- Commits are clean units with conventional commit subjects (`<type>(<scope>): <subject>`).
- No `WIP`, `fixup!`, `squash!`, or "address review" commits.
- Do not merge `main` into your feature branch.
- Never squash or rebase merge.
- `python3 scripts/dev.py dogfood check` passes.

## Reporting security vulnerabilities

Do not open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md) for instructions on reporting security issues privately.

## How to report a bug

Before filing a bug report, search existing issues to see if the problem was already reported.

When opening an issue, include:

1. Build Forge version (from `.agents/build-forge.lock.json`).
2. Operating system and version.
3. Node.js version (`node --version`) and Python version (`python3 --version`).
4. Exact command run.
5. Full output of `npx @v1006/build-forge verify`.
6. Expected behavior and actual behavior.
7. Agent tool used (if applicable).
