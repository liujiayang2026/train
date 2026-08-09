# Question 4

This folder contains the full analysis for Project 4, Question 4.

Run from the workspace root:

```powershell
& 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'project4\question-4\code\run_question4.py'
```

The script reuses the artifact-level weathering-corrected compositions from
Question 2, performs CLR-based component correlation analysis by glass type,
compares the high-potassium and lead-barium correlation matrices, and writes
CSV tables plus SVG heatmaps.

Main outputs:

- `docs/question-4-methodology.md`: modeling plan.
- `docs/question-4-results-summary.md`: concise numerical summary.
- `results/clr-correlation-高钾.csv`: high-potassium CLR correlation matrix.
- `results/clr-correlation-铅钡.csv`: lead-barium CLR correlation matrix.
- `results/top-reliable-component-associations.csv`: strong associations with
  zero-rate reliability flags.
- `results/differential-correlations.csv`: pairwise correlation differences
  with permutation p values and BH q values.
- `results/global-correlation-difference.csv`: global matrix-difference
  permutation test.
- `results/raw-vs-corrected-correlation-sensitivity.csv`: weathering-correction
  sensitivity.
- `figures/clr-correlation-heatmap-高钾.svg`: high-potassium heatmap.
- `figures/clr-correlation-heatmap-铅钡.svg`: lead-barium heatmap.
- `figures/clr-correlation-difference-heatmap.svg`: difference heatmap.
