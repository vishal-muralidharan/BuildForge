# Data Blueprint

Extracted database schemas, models, schemas, and storage keys.

## Generated facts

- **Policy: accounts_owner_policy on accounts**
  - Evidence: `tests/fixtures/blueprints/sql-ts-types/schema.sql:10` (confidence: high)
    - `CREATE POLICY accounts_owner_policy ON accounts FOR ALL USING (owner_id = current_user);`
- **RLS Enabled: accounts**
  - Evidence: `tests/fixtures/blueprints/sql-ts-types/schema.sql:8` (confidence: high)
    - `Row level security is enabled`
- **SQL Table: accounts**
  - Evidence: `tests/fixtures/blueprints/sql-ts-types/schema.sql:1` (confidence: high)
    - `id SERIAL PRIMARY KEY`
    - `owner_id TEXT NOT NULL`
    - `balance_cents INTEGER NOT NULL`
    - `created_at BIGINT NOT NULL`
- **Storage Key: pocket_session_id**
  - Evidence: `tests/fixtures/blueprints/js-tokens-storage/src/storage.js:9` (confidence: high)
    - `sessionStorage.setItem("pocket_session_id", sessionId);`
- **Storage Key: pocket_theme_mode**
  - Evidence: `tests/fixtures/blueprints/js-tokens-storage/src/storage.js:5` (confidence: high)
    - `Constant THEME_KEY resolves to 'pocket_theme_mode'`
- **Type/Interface: AccountSummary**
  - Evidence: `tests/fixtures/blueprints/sql-ts-types/src/types.ts:1` (confidence: high)
    - `id: string;`
    - `ownerId: string;`
    - `balanceCents: number;`

<!-- BEGIN CUSTOM: contracts -->
### Lock File and Integrity Schema
- Lock file key schema
  Evidence: `.agents/build-forge.lock.json:2` contains: `"skills/atomic-commits/SKILL.md"`
  - Mapping of skill file relative paths to SHA-256 hashes, with metadata fields `_version` and `_installed`.
- Integrity file key schema
  Evidence: `integrity.json:2` contains: `"skills/atomic-commits/SKILL.md"`
  - Mapping of all product skill file paths to SHA-256 hashes.

### Tier Definitions
- Tiers configuration
  Evidence: `tiers.json:2` contains: `"core": [`
  - Core tier: 7 skills (`atomic-commits`, `audit-and-planning`, `extend-pipeline`, `feature-delivery`, `project-blueprints`, `repo-search`, `sync-skills-and-docs`).
  - New-app tier: 5 skills (`legal-and-settings-pages`, `product-spec`, `project-bootstrap`, `rules-to-tests`, `scaffold-app`).
  - Module tier: 1 skill (`targeted-module-testing`).

### Upgrade Notes Format
- Upgrade notes schema
  Evidence: `upgrade-notes.json:3` contains: `"version": "0.2.0"`
  - Array of migration objects holding `version`, `since`, `notes`, and `actions` (id, title, command, risk, optional).
<!-- END CUSTOM: contracts -->
