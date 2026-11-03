Adopt Build Forge in this repository with legacy agent rules.
1. Run `python3 skills/project-bootstrap/scripts/legacy_import.py inventory` to catalog all legacy statements.
2. Review pending statements and apply or drop them using `legacy_import.py apply`.
3. Continue until `python3 skills/project-bootstrap/scripts/legacy_import.py status` exits with code 0.
4. Do not delete or modify any legacy instruction files.

