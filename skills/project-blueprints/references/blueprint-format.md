# Blueprint format specification

Blueprints provide verified, compact, and structured facts about the codebase.

## Directory layout

Generated in the project root under `.agents/blueprints/`:
```text
.agents/blueprints/
├── index.md             # Blueprint index (maximum 60 lines)
├── manifest.json        # Deterministic file hashes and analyzer metadata
├── candidates.md        # Extracted candidate rules for confirmation
├── data.md              # Database schemas, storage keys, data models
├── tokens.md            # CSS and theme design tokens
├── ui.md                # UI component catalog and state primitives
├── layout.md            # Breakpoints, shell layout, and mobile rules
├── auth.md              # Auth providers, guards, and logout cleanup
└── config.md            # Environment variable names and route mappings
```

## File format

Every blueprint file follows this structure:

```markdown
# Area Blueprint

Brief area summary.

## Generated facts

- Item name
  - Evidence: `src/path/to/file.ts:42` (confidence: high)
  - Detail: short signature or property summary (12 lines or fewer)

<!-- BEGIN CUSTOM: contracts -->
Human-written facts that no analyzer can derive (e.g. payload shapes, state machines, UX contracts).
Rules never go here. Rules belong in the profile.
<!-- END CUSTOM: contracts -->
```

## Line budgets and overflow

- `index.md`: 60 lines or fewer.
- Generated section: 250 lines or fewer per file.
- If an area exceeds 250 generated lines, the generator splits it into `<area>-part-2.md`, `<area>-part-3.md`, and links each part from `index.md`.

## Evidence and confidence

Every fact must list:
1. Exact file and line: `path/to/file.ext:line`.
2. Confidence level:
   - `high`: Directly declared typed interface, SQL schema, or explicit token.
   - `medium`: Inferred component prop or pattern match.
   - `low`: Heuristic match.
3. If an analyzer cannot determine a fact, write `unknown`. Never guess.

## Determinism and hashing

- Content uses LF line endings.
- All lists, tables, and dictionary keys are sorted alphabetically.
- No timestamps appear in generated blueprint files.
- `manifest.json` stores LF-normalized SHA-256 hashes of every source file analyzed.

## Secret safety

- Blueprints never read `.env` or files named like secrets.
- Environment variable names are collected from source code (`process.env.VAR`, `import.meta.env.VAR`) or `.env.example`.
- Values are never saved.
- Secret patterns (API keys, private keys, tokens) are scanned before writing. Extraction aborts if a secret pattern matches.
