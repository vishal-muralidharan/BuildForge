# Upgrading Build Forge

This guide explains how to upgrade an existing project using Build Forge to newer versions.

## How Update Works

Run:
```bash
npx @v1006/build-forge update
```

The `update` command verifies your project before making changes:
1. It compares installed pipeline skill hashes against the packaged `integrity.json`.
2. If you modified a pipeline skill locally, it stops and lists the file. You can keep your edits with `--keep-modified <skill>` or overwrite with `--restore <skill>`.
3. It installs missing core tier skills (`project-blueprints`).
4. It reinstalls differing pipeline skills from the package.
5. It updates `.agents/build-forge.lock.json` with the new file hashes and version.
6. It lists new optional skills available to add with `npx @v1006/build-forge add <skill>`.
7. It prints applicable upgrade actions from `upgrade-notes.json`.

Update never removes existing skills. It never modifies `.agents/vendor`, `.agents/references.yaml`, `.agents/blueprints`, your profile, or notes.

To preview changes without writing files:
```bash
npx @v1006/build-forge update --dry-run
```

If your project lacks a lock file:
```bash
npx @v1006/build-forge update --adopt
```
For skills that differ from the package, pass `--keep-modified <skill>` or `--restore <skill>` (or `--restore all`).

---

## Upgrading from 0.1.0 to 0.2.0

Build Forge 0.2.0 introduces project blueprints, curated rule packs, and integrity-verified updates.

Note on legacy parity: `legacy_import.py inventory` and `status` are read-only by default and print the ledger to the terminal. Pass `--write` only when the user asks for a ledger file (`.agents/legacy-parity.md`).

Running `npx @v1006/build-forge update` adds `.agents/.gitignore` to ignore Python bytecode caches and cleans untracked caches in replaced skills.
If `npx @v1006/build-forge doctor` warns about tracked cache files, untrack them with `git rm --cached <paths>`.

Follow these 5 steps after running `update`:

### Step 1: Migrate Project Profile (profile-migrate)

Check and apply the updated profile format:
```bash
python3 .agents/skills/project-bootstrap/scripts/migrate_profile.py plan --profile .agents/project-profile.yaml --root .
python3 .agents/skills/project-bootstrap/scripts/migrate_profile.py apply --profile .agents/project-profile.yaml --root . --apply
npx @v1006/build-forge upgrade done profile-migrate
```

### Step 2: Initialize Blueprints (blueprints-init)

Blueprints store extracted architecture facts in `.agents/blueprints/`:
```bash
python3 .agents/skills/project-blueprints/scripts/blueprint.py init
python3 .agents/skills/project-blueprints/scripts/blueprint.py extract
npx @v1006/build-forge upgrade done blueprints-init
```

### Step 3: Audit Code Hazards and Rule Packs (rule-packs)

Inspect curated rule packs:
```bash
python3 .agents/skills/project-bootstrap/scripts/packs.py list
npx @v1006/build-forge upgrade done rule-packs
```

### Step 4: Migrate External References (migrate-external-refs)

If your profile defines deprecated `external_references`, move them to `.agents/references.yaml`:
```bash
python3 .agents/skills/extend-pipeline/scripts/refs.py migrate
npx @v1006/build-forge upgrade done migrate-external-refs
```

### Step 5: Upgrade Unstamped Generated Convention Skills (upgrade-unstamped)

If you have convention skills generated under 0.1.0 that carry the old generator banner and no stamp:
```bash
# Preview salvaged edits and stamp placement
python3 .agents/skills/project-bootstrap/scripts/render.py --profile .agents/project-profile.yaml --root . --upgrade-unstamped --dry-run

# Apply upgrade
python3 .agents/skills/project-bootstrap/scripts/render.py --profile .agents/project-profile.yaml --root . --upgrade-unstamped
npx @v1006/build-forge upgrade done upgrade-unstamped
```

Hand edits outside custom blocks are preserved in a `salvaged` custom block.

---

## Branch Workflow (Opt-in, No Action Required)

Build Forge 0.2.0 includes an opt-in task branch workflow managed by `branchflow.py`.

Existing projects continue to work on main without any changes. No upgrade action is required.

To enable task branch workflows for a repository, add `git.workflow` to `.agents/project-profile.yaml`:

```yaml
git:
  workflow:
    default_branch: main
    mode: ask            # off, ask, or always
    branch_format: "<type>/<slug>"
    sync: merge          # merge or rebase
    merge_method: squash # squash, merge, or rebase
    remote: origin
    cleanup: ask         # ask or keep
    worktree: false
```

---

## Verifying Your Upgrade

Run the doctor command to verify your installation:
```bash
npx @v1006/build-forge doctor
```

Doctor checks Node.js, Python 3, PyYAML, Git, lockfile integrity, profile validity, blueprints, links, and pending upgrade actions.

