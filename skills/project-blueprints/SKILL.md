---
name: project-blueprints
description: Extract and query verified codebase blueprints for data models, tokens, UI primitives, layout rules, auth flows, and config. Use when asking what is in this codebase, blueprint, schema, tokens, component catalog, storage keys, or regenerate project context.
compatibility: Needs file read, file edit, shell, Python 3, and PyYAML.
---

# Project blueprints

Blueprints capture verifiable facts about a codebase so agents do not rescan the repository repeatedly. Facts are extracted directly from source code with explicit file and line evidence. Rules and product decisions are never derived automatically.

Blueprints live in `.agents/blueprints/` in the target project. Each area has a canonical blueprint file:
- `data.md`: SQL tables, Prisma models, Drizzle schemas, storage keys, and schema libraries.
- `tokens.md`: CSS variables, theme tokens, light and dark palettes, type scale, and motion.
- `ui.md`: Exported UI components, props, variants, and state primitives.
- `layout.md`: Breakpoints, navigation shells, viewport settings, and mobile constraints.
- `auth.md`: Authentication providers, route guards, auth context, and logout paths.
- `config.md`: Environment variable names, scripts, and route definitions.

## Commands

Run commands via the CLI script:
`python3 .agents/skills/project-blueprints/scripts/blueprint.py <command>`

| Command | Purpose |
|---|---|
| `extract [--areas a,b] [--root .]` | Run detected analyzers and generate blueprint files. |
| `verify [--root .]` | Verify every evidence reference exists and matches source lines. Exits 1 on failure. |
| `stale [--fail] [--root .]` | Check if source files changed since the last extraction. |
| `show --area <name> [--paths p1,p2] [--budget N]` | Query concise blueprint facts within a line budget (default 120 lines). |
| `candidates [--root .]` | Display rule candidates identified for user review. |

## Blueprint structure

Each blueprint file contains:
1. A brief header.
2. A generated section with evidence (`path:line`) and confidence (`high`, `medium`, `low`).
3. An optional custom contracts block:
   ```markdown
   <!-- BEGIN CUSTOM: contracts -->
   <!-- END CUSTOM: contracts -->
   ```
   Facts in custom blocks are preserved byte for byte on every re-extraction.
