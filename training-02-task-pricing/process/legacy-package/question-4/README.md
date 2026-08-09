# Question 4 File Guide

This folder contains the Attachment 3 pricing implementation for Project 2,
Problem B, Question 4.

## Run

From the project directory, run:

```powershell
python question-4/code/question4_complete.py
```

The script reuses the Question 2 historical completion model, caps the new
task-density input at the historical 95th percentile, applies a local
task/member congestion correction, forms compact packages, and compares
uniform, individual, and bundled pricing.

## Outputs

- `results/question4-task-pricing.csv`: task-level recommended prices,
  package assignment, spatial features, and predicted completion probability.
- `results/question4-scheme-comparison.csv`: overall scheme comparison.
- `results/question4-city-summary.csv`: city-level implementation summary.
- `results/question4-package-summary.csv`: package-level rewards and effects.
- `figures/question4-scheme-comparison.png`: main comparison chart.
- `docs/run-summary.txt`: compact run log and model assumptions.

## Optimized bundled run

`code/question4_optimized.py` adds effective member supply, adaptive package
sizes, global MILP package selection, and explicit member quota constraints.
It preserves the original results and writes separate `optimized-*` outputs
for comparison.
