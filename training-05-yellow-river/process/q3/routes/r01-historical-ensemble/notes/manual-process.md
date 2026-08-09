# Question 3 Manual Process

## Objective

Record the reproducible workflow for the current question 3 optimized ensemble model.

## Inputs

- Daily water and sediment flux series: `../question-2/data/processed/daily_flux_series.csv`
- Abrupt-change month risk from question 2: `../question-2/qa/abrupt_change_events.csv`
- Working folder: `project5/question-3`

## Manual Steps

1. Use question 2 daily series as the modeling basis.
2. Build two interpretable base predictors: recent weighted seasonal template and STL-style trend-residual model.
3. Use leave-one-year validation over 2018-2021 to choose ensemble weights separately for flow and sediment flux.
4. Generate low, normal, and high scenarios for 2022-2023.
5. Aggregate daily forecasts into monthly and annual water/sediment totals.
6. Build sampling risk scores from sediment flux level, high-scenario risk, change strength, flood-season indicators, and historical abrupt-month risk.
7. Export result tables, validation tables, model settings, figures, and Chinese method documentation.

## Run Command

```powershell
python .\code\analyze_question3.py
```

## Validation

- Standard entrance script runs successfully.
- Forecast validation is stored in `../qa/forecast_validation.csv`.
- Weight selection is stored in `../qa/weight_selection.csv`.
- Final model settings are stored in `../qa/model_settings.csv`.

## Handoff Notes

- Status: optimized ensemble version is active in `question-3`.
- Random forest comparison remains in `../q3`.
- Independent optimized development copy remains in `../q3-optimized`.
