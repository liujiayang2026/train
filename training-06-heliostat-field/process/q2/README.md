# Q2 process index

- Question requirement: design tower location, common mirror size, common installation height, mirror count, and mirror positions to reach annual average thermal output at least 60 MW while maximizing annual average unit-area thermal output.
- Current candidate routes: `routes/r01-common-size-field-optimization/`.
- Known conflicts: tower-centered 100 m exclusion interpretation and common-width spacing convention need to be made explicit before optimization runs.
- Explicit human decisions: none yet.

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.
