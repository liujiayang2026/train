# Repository Instructions for the Mathematical Modeling Training Packages

These rules apply to every training package in this repository. They supplement
the `PROCESS_GUIDE.md` inside each package.

## Process-first work

Modeling work must be recorded while it is performed, not reconstructed after
the fact. Before writing code or generating results, identify the package,
question, route, and run that own the work.

Use this state transition:

```text
new idea
  -> process/qN/routes/rNN-short-name/route.md
implementation
  -> process/qN/routes/rNN-short-name/code/
execution
  -> process/qN/routes/rNN-short-name/runs/run-YYYYMMDD-HHMM-label/
comparison
  -> process/qN/comparisons/compare-short-title.md
explicit human choice
  -> process/qN/decisions/dNN-short-title.md
```

Unclassified notes, screenshots, or chat exports may go to `process/qN/inbox/`.
Move them into a route when their ownership becomes clear.

## Mandatory route and run records

- Create `route.md` before implementing a materially new method. Use the
  package's `PROCESS_GUIDE.md` template and fill every field.
- A change to the objective, constraints, data convention, model family, or
  solution method requires a new route.
- Parameter tuning, a new seed, an implementation fix, or a rerun of the same
  method requires a new run under the existing route.
- Create `run.md` before or together with the execution. Record the exact
  command, working directory, code entry point/version, inputs, parameters,
  random seed, environment, outputs, and completion status.
- Put generated machine results, figures, validation evidence, and logs inside
  that same run's `results/`, `figures/`, `validation/`, and `logs/` folders.
- Never overwrite or repurpose an existing `run-*` directory. Failed runs are
  evidence and must remain recorded.
- When Git history is unavailable for a run, record a SHA-256 hash of its code
  entry point in `run.md`.

## Protected material

- Treat `source/` as official input. Do not clean, rewrite, or replace files in
  place; put derived data under `process/common/data/` or a route/run.
- Treat `process/legacy-package/` as an immutable historical snapshot. New work
  must go under canonical `process/qN/routes/` paths. A one-time removal is
  allowed only when the repository owner explicitly authorizes a complete
  `git mv` migration and the package records every mapping in
  `process/legacy-migration.json`.
- Do not create or hand-edit `final/` or `human-package.json` during intake.
- Do not infer adoption from names such as `final`, `new`, `best`, or `v2`.
  Adoption/rejection requires an explicit human decision file.
- Do not edit an existing decision record to reverse a choice. Add a new
  decision that supersedes it and explains why.

## Team and Git discipline

- Synchronize the branch before starting when the worktree is clean. Preserve
  and report unrelated teammate changes.
- Keep each commit scoped to one coherent process change when practical.
- Do not commit caches, temporary files, local environments, or unclassified
  generated outputs outside the process package.
- Before committing or handing off, run:

```powershell
python scripts/validate_process_intake.py
```

- For a focused check, pass one or more package directories:

```powershell
python scripts/validate_process_intake.py training-05-yellow-river
```

Fix validation errors before pushing. Git does not track empty directories, so
create each standard folder when it first receives content.
