# Q2 process index

- Question requirement: design tower location, common mirror size, common installation height, mirror count, and mirror positions to reach annual average thermal output at least 60 MW while maximizing annual average unit-area thermal output.
- Current candidate routes: `routes/r01-common-size-field-optimization/` uses conservative radial spacing; `routes/r02-close-packed-staggered-rings/` tests polar close packing but suffers ring-transition conflicts; `routes/r03-hexagonal-staggered-lattice/` provides the first feasible analytic hexagonal baseline; `routes/r04-variable-density-radial-layout/` was abandoned after geometric preflight repeated the ring-transition density loss; `routes/r05-shifted-hex-optical-pruning/` refines the hexagonal family with a spacing margin and multi-fidelity real-ray search; `routes/r06-zoned-low-power-relayout/` tests local sub-lattice replacement and constrained low-contribution pruning, and currently gives the highest validated unit-area result under the 60 MW hard constraint, with only 0.071 MW power margin.
- Known conflicts: tower-centered 100 m exclusion interpretation and common-width spacing convention need to be made explicit before optimization runs.
- Explicit human decisions: none yet.

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.
