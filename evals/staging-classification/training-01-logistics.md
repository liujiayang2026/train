# Training 01 legacy staging-classification validation

Date: 2026-08-09

## Purpose

Validate the enforced `train -> write-cumcm-paper` handoff with a real messy
legacy package. The immutable source was:

`training-01-logistics/process/legacy-package/`

The source snapshot was never modified. All work used the ignored workspace:

`tmp/training-01-logistics-classification-validation/`

## Method

1. Generate a fresh four-question package with `scripts/init_training_package.py`.
2. Copy the complete legacy snapshot into `process/_staging/legacy/`.
3. Verify all 178 copied files against the immutable source with SHA-256.
4. Inspect representative question notes and integrated code by content.
5. Render and inspect the official problem PDF and the first-training paper PDF.
6. Author a semantic classification plan using file and directory-prefix mappings.
7. Preflight and apply the plan with `scripts/apply_staging_classification.py`.
8. Recheck all moved files against the immutable source with SHA-256.
9. Run both the strict `train` gate and the `write-cumcm-paper` receiving gate.

## Classification result

| Destination class | Files |
|---|---:|
| `source/` | 3 |
| `process/common/` | 15 |
| `process/q1/inbox/` | 57 |
| `process/q2/inbox/` | 34 |
| `process/q3/inbox/` | 46 |
| `process/q4/inbox/` | 23 |
| Total | 178 |

The official statement, contest template, and spreadsheet became declared
`source_files`. Cross-question paper drafts, paper-building utilities, and the
historical full paper moved to `process/common/`. Question-specific code,
results, figures, and notes moved to their corresponding question inbox while
preserving the original bundle hierarchy.

Plan SHA-256:
`24F2D45943EFDCE9D87BAE95EC94C409318D8140E82DC09AC11D040A9B3EF5DC`

Classification-log SHA-256:
`9B34D594E181628E5E9ABEDE732513DE42A6342C6DAD2D5B6B0B8CBF9DEF891E`

## Acceptance evidence

- Copied files: 178/178.
- Initial copy hash mismatches: 0.
- Classification-plan coverage: 178/178.
- Post-move hash mismatches: 0.
- Unclassified staging files after application: 0.
- Classification-log rows: 178.
- Declared source files: 3.
- `train --ready-for-finalization`: 0 errors, 0 warnings.
- `write-cumcm-paper` receiving gate: clean `INTAKE` state.

## Honest scope

This run validates source/common/question ownership and the mechanical safety of
Agent-authored classification. It deliberately does not infer route adoption
from names such as `revised`, `optimized`, `complete`, or `final`. The legacy
package contains competing and duplicated model versions, so those bundles stay
in the relevant `qN/inbox/` until a separate route-comparison task creates
`route.md`, run records, and explicit human decisions. Treating that unresolved
material as already adopted would be a classification failure, not a success.
