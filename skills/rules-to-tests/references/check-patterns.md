# Check patterns

Ready patterns for the `check` block. Adjust `include` and `exclude` to the project. Prove every pattern on both sides before you trust it (see the skill steps).

YAML tip: write regexes in single quotes so backslashes stay literal.

## Contents

1. Patterns
2. Narrowing a noisy pattern
3. What a script cannot judge

## 1. Patterns

### No raw hex colors outside the tokens file

```yaml
check:
  type: forbid
  pattern: '(?<![\w&/])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b'
  include: ["src/**/*.{js,jsx,ts,tsx,css,html}"]
  exclude: ["src/index.css"]
```

### No rgb() or hsl() color functions

```yaml
check:
  type: forbid
  pattern: '\b(?:rgb|rgba|hsl|hsla)\('
  include: ["src/**/*.{js,jsx,ts,tsx,css}"]
  exclude: ["src/index.css"]
```

### No emojis

```yaml
check:
  type: forbid
  pattern: '[\U0001F300-\U0001FAFF\u2600-\u27BF]'
  include: ["src/**/*.{js,jsx,ts,tsx,css,html,md}", "README.md"]
```

### No palette color classes (Tailwind)

```yaml
check:
  type: forbid
  pattern: '\b(?:bg|text|border|ring|fill|stroke|from|to|via)-(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-\d{2,3}\b'
  include: ["src/**/*.{js,jsx,ts,tsx,html}"]
```

### Native controls only inside the shared primitives

```yaml
check:
  type: forbid
  pattern: '<select\b'
  include: ["src/**/*.{jsx,tsx}"]
  exclude: ["src/components/ui/**"]
```

### No console logging in shipped code

```yaml
check:
  type: forbid
  pattern: '\bconsole\.(?:log|debug)\('
  include: ["src/**/*.{js,jsx,ts,tsx}"]
  exclude: ["**/*.test.*", "src/test/**"]
```

### Storage only through the storage layer

```yaml
check:
  type: forbid
  pattern: '\b(?:localStorage|sessionStorage|indexedDB)\b'
  include: ["src/**/*.{js,jsx,ts,tsx}"]
  exclude: ["src/lib/storage.js", "src/test/**", "**/*.test.*"]
```

### No `any` in TypeScript

```yaml
check:
  type: forbid
  pattern: ':\s*any\b'
  include: ["src/**/*.{ts,tsx}"]
```

### A clean repo root

```yaml
check:
  type: root_only
```

Needs `structure.root_allowed` in the profile.

### No dual-homed skills

```yaml
check:
  type: no_dual_homed_skills
```

What it checks: Fails when any skill or reference exists in both `.agents/vendor` and `.agents/skills`, or when frontmatter names collide.
When it runs: Runs during automated rule checks in CI, pre-commit checks, or when running `run_rule_checks.py`. Takes no parameters.

### A required file exists

```yaml
check:
  type: require_file
  path: README.md
```

### A removed folder stays removed

```yaml
check:
  type: forbid_file
  include: ["src/pages/**"]
```

## 2. Narrowing a noisy pattern

- **Too many hits on valid code:** tighten with lookbehind, such as `(?<![\w&/])`, or require a surrounding character.
- **A known safe file:** add it to `exclude`. List it by path. Never exclude a whole source folder.
- **Generated files:** exclude the generated folder explicitly.
- **Tests that must contain the bad value:** exclude `**/*.test.*`.

## 3. What a script cannot judge

Leave these as `manual`, or cover them with browser checks if that capability is on:

- Copy quality, tone and length.
- Visual layout, spacing and polish.
- Color contrast (needs rendering).
- Whether a component is used correctly.
- Performance and memory behavior.
- Whether a name is meaningful.
