# Config Blueprint

Extracted environment variables, project scripts, and route mappings.

## Environment variables

- `API_SECRET` (referenced: `tests/fixtures/blueprints/secret-env/src/index.js:2`)
- `DATABASE_URL` (referenced: `tests/fixtures/blueprints/secret-env/src/index.js:3`)

## Package scripts

- No package scripts found.


## Routes

- No explicit server routes detected.

<!-- BEGIN CUSTOM: contracts -->
### CLI Commands and Exit Codes
- Build Forge CLI command suite
  Evidence: `bin/build-forge.js:2263` contains: `console.log('Build Forge CLI');`
  - Commands: `install`, `link`, `unlink`, `verify`, `status`, `diff`, `doctor`, `outdated`, `update`, `upgrade`, `add`, `remove`, `list`, `help`.
  - Exit code 0: Command succeeded. Evidence: `bin/build-forge.js:856` contains: `process.exit(0);`
  - Exit code 1: Command failed, validation error, or drift. Evidence: `bin/build-forge.js:446` contains: `process.exit(1);`
  - Exit code 2: Not adopted state in status command. Evidence: `bin/build-forge.js:781` contains: `process.exit(2);`

### Profile Schema Version
- Profile schema version
  Evidence: `.agents/project-profile.yaml:2` contains: `schema_version: 1`
  - Current schema version in this repository is 1.
- Supported schema versions
  Evidence: `skills/project-bootstrap/scripts/validate_profile.py:30` contains: `SUPPORTED_SCHEMA_VERSIONS = (1, 2)`
  - Versions 1 and 2 are supported by the validator and migration scripts.
<!-- END CUSTOM: contracts -->
