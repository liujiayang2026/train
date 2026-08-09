# Question 2

This folder contains the full analysis for Project 4, Question 2.

Run from the workspace root:

```powershell
& 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'project4\question-2\code\run_question2.py'
```

The script reads the original workbook under `project4`, reuses the
pre-weathering predictions from Question 1, and writes processed data, result
tables, SVG figures, and a short results summary under this folder.

Main outputs:

- `docs/question-2-methodology.md`: modeling plan.
- `docs/question-2-results-summary.md`: concise numerical summary.
- `data/processed/corrected-artifact-compositions.csv`: artifact-level
  weathering-corrected compositions.
- `results/major-type-classification-summary.csv`: high-potassium vs
  lead-barium classification performance.
- `results/subclass-assignments.csv`: subclass assignment for each artifact.
- `results/subclass-centers.csv`: subclass center compositions and names.
- `results/*sensitivity.csv`: robustness checks.
- `figures/major-type-log-ratio.svg`: major-type classification rule.
- `figures/high-k-subclass-pca.svg`: high-potassium subclass PCA view.
- `figures/lead-barium-subclass-pca.svg`: lead-barium subclass PCA view.
