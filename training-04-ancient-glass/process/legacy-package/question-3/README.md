# Question 3

This folder contains the full analysis for Project 4, Question 3.

Run from the workspace root:

```powershell
& 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'project4\question-3\code\run_question3.py'
```

The script reads the unknown artifacts from worksheet 3 of the original
workbook, reuses the major-type rule and subclass centers from Question 2, and
uses the weathering effects from Question 1 for type-conditional correction of
weathered unknown samples.

Main outputs:

- `docs/question-3-methodology.md`: modeling plan.
- `docs/question-3-results-summary.md`: concise identification summary.
- `data/processed/unknown-artifact-compositions.csv`: cleaned unknown samples.
- `results/unknown-final-identification.csv`: final type and subclass decisions.
- `results/type-conditional-weathering-classification.csv`: conditional
  weathering-correction checks.
- `results/unknown-type-sensitivity.csv`: pseudocount sensitivity results.
- `figures/unknown-major-pca.svg`: unknown samples in the major-type PCA space.
