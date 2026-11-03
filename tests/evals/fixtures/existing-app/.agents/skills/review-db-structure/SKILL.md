---
name: review-db-structure
description: Use this skill whenever you read, write or change data models, schemas, storage keys or payloads in invented-notes-app. Lists the invariants and the items that need approval to change.
---

<!-- Generated from .agents/project-profile.yaml by project-bootstrap. Edit the profile, then re-render. -->

# Data rules for invented-notes-app


## Ask before changing

- data/users.json
- Storage keys

## Rules

- Never modify data/users.json without explicit human confirmation. `[data-protected-users]`
