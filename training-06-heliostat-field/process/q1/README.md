# Q1 process index

- Question requirement: evaluate the fixed field in `附件.xlsx` with tower at (0, 0), mirror size 6 m x 6 m, and installation height 4 m; report monthly and annual optical efficiency components and thermal output.
- Current candidate routes: `routes/r01-fixed-layout-optical-evaluation/`.
- Known conflicts: none; r01 remains a candidate route until package finalization, but its model, 512-ray result, figure use, and paper-format revision are all recorded.
- Explicit human decisions: `decisions/d01-use-direct-cylinder-process-figure.md`, `decisions/d02-integrate-solar-cone-content.md`, `decisions/d03-adopt-physical-narrative-figure-suite.md`, and `decisions/d04-use-paper-figures-and-expanded-analysis.md`.

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.
