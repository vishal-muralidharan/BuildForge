Fix a bug in `src/storage.js`: `findNoteById` returns null when given a string ID for a note with a numeric ID.
Follow the feature-delivery fix-bug workflow:
1. Reproduce with a failing regression test first.
2. Find the root cause.
3. Make the minimal fix.
4. Verify that the regression test and existing tests pass with `npm test`.
