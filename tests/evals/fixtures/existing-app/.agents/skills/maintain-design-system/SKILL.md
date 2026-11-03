---
name: maintain-design-system
description: Use this skill when you add or change tokens, global styles or shared UI primitives in invented-notes-app. Defines the palette, type scale, spacing, radius and motion tokens.
---

<!-- Generated from .agents/project-profile.yaml by project-bootstrap. Edit the profile, then re-render. -->

# invented-notes-app design system

All tokens live in `src/tokens.css`.

## Token rules

- Never use raw hex colors in css files. Use tokens from src/tokens.css. (enforced by test) `[tokens-no-raw-hex]`

## Changing a token

1. Edit `src/tokens.css` for every theme or mode.
2. Check contrast in each mode.
3. Update `README.md` if it lists tokens.
4. Run `npm test`.
5. Confirm `python3 skills/rules-to-tests/scripts/run_rule_checks.py` still passes.
