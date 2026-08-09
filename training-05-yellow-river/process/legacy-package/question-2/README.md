# Question 2

Run the analysis from the workspace root:

```powershell
& 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'D:\jianmo\project5\question-2\code\analyze_question2.py'
```

Main outputs:

- `data/processed/daily_flux_series.csv`: daily water flux, sediment concentration, sediment flux, water volume, and sediment mass.
- `results/annual_flux_pattern.csv`: annual variation pattern of water and sediment fluxes.
- `results/monthly_flux_summary.csv`: monthly seasonality summary.
- `results/flood_season_concentration.csv`: flood-season concentration of water and sediment fluxes.
- `qa/abrupt_change_events.csv`: candidate abrupt change events based on 7-day before-after contrasts.
- `qa/periodicity_summary.csv`: dominant periods from frequency-domain analysis.
- `qa/autocorrelation_lags.csv`: autocorrelation at typical lags.
- `docs/question2-analysis.md`: short Chinese analysis report.
- `docs/question2-method.md`: complete Chinese method and solution process.
- `figures/monthly-water-sediment-share.png`: monthly water and sediment contribution chart.
- `figures/monthly-normalized-flux.png`: monthly normalized water-sediment flux chart.

Manual process notes:

- `docs/manual-process.md`
