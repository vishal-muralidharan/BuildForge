---
name: review-db-structure
description: Use this skill whenever you read, write or change data models, schemas, storage keys or payloads in Build Forge. Lists the invariants and the items that need approval to change.
---
<!-- build-forge:generated v1 body=7b24a51d96188cc1840da3c707ad86474d4a3d26ada48f78eaf086438c465bd7 -->

<!-- Generated from .agents/project-profile.yaml by project-bootstrap. Edit the profile, then re-render. -->

# Data rules for Build Forge

## Blueprint

Query codebase data models and storage facts on demand:
`python3 .agents/skills/project-blueprints/scripts/blueprint.py show --area data --paths <files>`

Storage: JSON and Markdown files.

## Invariants

- integrity.json keys equal the files under skills/
- the lock file key names are identical in integrity.json, the lock, bin/build-forge.js and verify_integrity.py
- every skills/ folder is in exactly 1 tier in tiers.json

## Ask before changing

- package.json version
- integrity.json format
- the lock file format
- profile schema_version and SUPPORTED_SCHEMA_VERSIONS
- skill names
- tiers.json

## Rules

- integrity.json must be kept up to date with files in skills/. (enforced by test) `[repo-integrity-hash]`
<!-- BEGIN CUSTOM: notes -->
<!-- END CUSTOM: notes -->
