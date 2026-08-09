# Process index

This directory is noncanonical. Record the global timeline, question dependencies, competing routes, failed attempts, and unresolved conflicts here.

- `common/`: materials reused by two or more questions.
- `qN/inbox/`: unsorted imports awaiting classification.
- `qN/routes/`: one self-contained directory per materially different solution route.
- `qN/comparisons/`: explicit cross-route comparisons.
- `qN/decisions/`: human decisions and reasons; never infer decisions from filenames.

Nothing here may be used directly by the paper-writing Agent.

## Canonical migration status

The former pre-V3 `legacy-package/` was migrated into the canonical question
structure on 2026-08-09. Historical candidate models are now explicit routes
with imported run evidence; the unresolved Q4 placeholder is in `q4/inbox/`.
See `legacy-migration.json` for the complete path mapping. Migration does not
mean that any route has been adopted.
