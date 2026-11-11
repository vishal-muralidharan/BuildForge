# Design Tokens Blueprint

Extracted CSS custom properties, role mappings, and theme palettes.

## Token roles and theme values

| Token | Role | Light Value | Dark Value | Evidence |
|---|---|---|---|---|
| `--action` | action | `#000000` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:82` |
| `--color-action` | action | `#0066cc` | `#3399ff` | `tests/fixtures/blueprints/js-tokens-storage/src/theme.css:4` |
| `--color-primary` | action | `#0000ff` | `unknown` | `tests/fixtures/old-install/src/tokens.css:1` |
| `--on-action` | action | `#ffffff` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:83` |
| `--font-body` | font | `system-ui, sans-serif` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:44` |
| `--font-display` | font | `system-ui, sans-serif` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:45` |
| `--font-sans` | font | `"Inter", sans-serif` | `unknown` | `tests/fixtures/blueprints/tailwind-theme/src/theme.css:4` |
| `--ease-in-out` | motion | `cubic-bezier(0.65, 0, 0.35, 1)` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:41` |
| `--ease-out` | motion | `cubic-bezier(0.16, 1, 0.3, 1)` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:40` |
| `--color-brand` | other | `#ff0000` | `unknown` | `tests/fixtures/blueprints/tailwind-theme/src/theme.css:2` |
| `--color-brand-1` | other | `#000001` | `unknown` | `tests/fixtures/field-adoption/src/tokens.css:2` |
| `--dur-base` | other | `0ms` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:91` |
| `--dur-fast` | other | `0ms` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:90` |
| `--dur-slow` | other | `0ms` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:92` |
| `--line` | other | `#e5e5e5` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:77` |
| `--line-strong` | other | `#737373` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:78` |
| `--radius-full` | radius | `9999px` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:34` |
| `--radius-lg` | radius | `24px` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:33` |
| `--radius-md` | radius | `6px` | `unknown` | `tests/fixtures/blueprints/js-tokens-storage/src/theme.css:6` |
| `--radius-sm` | radius | `8px` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:31` |
| `--space-1` | spacing | `4px` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:23` |
| `--space-2` | spacing | `8px` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:24` |
| `--space-3` | spacing | `12px` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:25` |
| `--space-4` | spacing | `16px` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:26` |
| `--space-6` | spacing | `24px` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:27` |
| `--space-8` | spacing | `32px` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:28` |
| `--space-lg` | spacing | `24px` | `unknown` | `tests/evals/fixtures/existing-app/src/tokens.css:7` |
| `--space-md` | spacing | `16px` | `unknown` | `tests/evals/fixtures/existing-app/src/tokens.css:6` |
| `--space-sm` | spacing | `8px` | `unknown` | `tests/evals/fixtures/existing-app/src/tokens.css:5` |
| `--spacing-base` | spacing | `8px` | `unknown` | `tests/fixtures/blueprints/js-tokens-storage/src/theme.css:5` |
| `--spacing-container` | spacing | `1200px` | `unknown` | `tests/fixtures/blueprints/tailwind-theme/src/theme.css:5` |
| `--bg` | surface | `#ffffff` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:73` |
| `--color-bg` | surface | `#ffffff` | `unknown` | `tests/evals/fixtures/existing-app/src/tokens.css:3` |
| `--color-surface` | surface | `#f9f9f9` | `#1e1e1e` | `tests/fixtures/blueprints/js-tokens-storage/src/theme.css:2` |
| `--surface` | surface | `#fafafa` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:74` |
| `--surface-2` | surface | `#f5f5f5` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:75` |
| `--surface-3` | surface | `#e5e5e5` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:76` |
| `--color-text` | text | `#111111` | `#eeeeee` | `tests/fixtures/blueprints/js-tokens-storage/src/theme.css:3` |
| `--fg` | text | `#000000` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:79` |
| `--fg-faint` | text | `#737373` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:81` |
| `--fg-muted` | text | `#525252` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:80` |
| `--text-body` | text | `0.875rem` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:47` |
| `--text-label` | text | `0.75rem` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:46` |
| `--text-title` | text | `clamp(1.125rem, 1rem + 0.6vw, 1.5rem)` | `unknown` | `skills/scaffold-app/assets/tokens.base.css:48` |

## Typography tokens

- `--font-body`: `system-ui, sans-serif` (`skills/scaffold-app/assets/tokens.base.css:44`)
- `--font-display`: `system-ui, sans-serif` (`skills/scaffold-app/assets/tokens.base.css:45`)
- `--font-sans`: `"Inter", sans-serif` (`tests/fixtures/blueprints/tailwind-theme/src/theme.css:4`)

## Motion tokens

- `--ease-in-out`: `cubic-bezier(0.65, 0, 0.35, 1)` (`skills/scaffold-app/assets/tokens.base.css:41`)
- `--ease-out`: `cubic-bezier(0.16, 1, 0.3, 1)` (`skills/scaffold-app/assets/tokens.base.css:40`)

<!-- BEGIN CUSTOM: contracts -->
<!-- END CUSTOM: contracts -->
