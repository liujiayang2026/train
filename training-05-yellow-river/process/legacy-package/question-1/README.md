# Question 1

Run the analysis from the workspace root:

```powershell
& 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'D:\jianmo\project5\question-1\code\analyze_question1.py'
```

Main outputs:

- `results/annual_flux_estimates.csv`: annual total water volume and sediment load estimates.
- `results/monthly_relationship_summary.csv`: month-level time-pattern summary.
- `data/processed/cleaned_hydro_timeseries.csv`: cleaned water-level, flow, observed concentration, fitted concentration, and sediment flux series.
- `qa/model_validation.csv`: held-out-year model comparison.
- `qa/relationship_diagnostics.csv`: concentration relationship diagnostics.
- `docs/question1-analysis.md`: short method and result report.

Manual process notes:

- `docs/manual-process.md`
