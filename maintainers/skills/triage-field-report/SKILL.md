---
name: triage-field-report
description: "Guidance for triaging external field reports, diagnosing root cause, and writing regression fixtures."
---

# Triage Field Report Playbook

Use this playbook when investigating a defect reported by users or agents in the field.

## Steps

1. **Classify root cause**
   Classify the problem into 1 of these 8 categories:
   - `generator overwrote content`: render or scaffold replaced user content.
   - `parser bug`: markdown, yaml, or glob parser failed on unexpected format.
   - `missing rule`: pipeline lacks an essential safety invariant.
   - `missing instruction`: skill instructions omit necessary operational detail.
   - `false enforcement claim`: checker reported an invalid failure on valid code.
   - `hidden dependency`: script required an unlisted package or tool.
   - `wrong example`: documentation example has incorrect syntax or invalid flags.
   - `other`: uncategorized anomaly or edge case.

2. **Locate nearest existing guard**
   Identify the script or check responsible for preventing this failure mode.
   Examples: `check_sync.py`, `validate_profile.py`, `run_rule_checks.py`, `ci_check.py`.

3. **Create invented fixture first**
   Scaffold an invented reproduction project under `tests/fixtures/<name>`:
   ```bash
   python3 scripts/dev.py fixture new <name>
   ```
   Rules for fixture content:
   - Invent all names, code snippets, and paths.
   - Never copy third party text, licensed headers, or proprietary code into the repo.
   - Use URLs only for example.com, example.org, localhost, and 127.0.0.1.
   - Keep all files under 50 KB.
   Verify the new fixture:
   ```bash
   python3 scripts/dev.py fixture check
   ```

4. **Reproduce the failure**
   Write a test in `tests/test_<area>.py` pointing to the fixture.
   Confirm the test fails before applying any fix.

5. **Implement the fix**
   Apply the minimal correction to the responsible script or skill.
   Confirm the test passes.

6. **Document troubleshooting**
   Add a troubleshooting row in `README.md` or a guidance note in the skill reference.
   Add an entry to `CHANGELOG.md` under `## [Unreleased]`.

7. **Generate 1 page summary**
   Output a 1 page summary for the maintainer:
   - Category: classified root cause.
   - Reproduction: test and fixture path.
   - Guard: script or check updated.
   - Risk: potential side effects.
   - PR plan: split large fixes into small pull requests.
