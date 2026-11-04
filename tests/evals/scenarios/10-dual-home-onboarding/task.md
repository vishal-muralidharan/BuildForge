Onboard an existing project with dual-homed external references:
1. Detect collisions between `.agents/vendor` and `.agents/skills`.
2. Dedupe the identical duplicate reference skill using `refs.py dedupe --approved`.
3. Preserve the modified duplicate reference skill with its diff for manual reconciliation.
4. Verify local legacy skills and vendor copies remain untouched.
5. Re-run legacy inventory to ensure statement counts match expected source classes.
