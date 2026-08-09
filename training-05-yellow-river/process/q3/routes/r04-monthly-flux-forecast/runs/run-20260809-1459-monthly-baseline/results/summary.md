# Run summary

## Selected monthly models

| target              | selected_model     | mean_rmse_log | mean_r2_log | mean_wape |
| ------------------- | ------------------ | ------------- | ----------- | --------- |
| water_volume_1e8_m3 | regime_climatology | 0.34637       | 0.65081     | 0.27078   |
| sediment_mass_1e4_t | regime_climatology | 0.7475        | 0.64899     | 0.45062   |

## Interval calibration

| target              | nominal_coverage | empirical_coverage | log_radius | calibration_months |
| ------------------- | ---------------- | ------------------ | ---------- | ------------------ |
| water_volume_1e8_m3 | 0.8              | 0.80556            | 0.37602    | 36                 |
| water_volume_1e8_m3 | 0.95             | 0.94444            | 0.90416    | 36                 |
| sediment_mass_1e4_t | 0.8              | 0.80556            | 0.72423    | 36                 |
| sediment_mass_1e4_t | 0.95             | 0.94444            | 1.7335     | 36                 |

## Annual forecast

| year | water_volume_1e8_m3 | water_volume_1e8_m3_lower80 | water_volume_1e8_m3_upper80 | water_volume_1e8_m3_lower95 | water_volume_1e8_m3_upper95 | sediment_mass_1e4_t | sediment_mass_1e4_t_lower80 | sediment_mass_1e4_t_upper80 | sediment_mass_1e4_t_lower95 | sediment_mass_1e4_t_upper95 | water_model        | sediment_model     |
| ---- | ------------------- | --------------------------- | --------------------------- | --------------------------- | --------------------------- | ------------------- | --------------------------- | --------------------------- | --------------------------- | --------------------------- | ------------------ | ------------------ |
| 2022 | 448.09              | 303.89                      | 658.1                       | 174.28                      | 1124.4                      | 29752               | 14415                       | 61395                       | 5246.3                      | 1.6846e+05                  | regime_climatology | regime_climatology |
| 2023 | 480.45              | 295.78                      | 775.93                      | 147.05                      | 1512.8                      | 31810               | 12858                       | 78672                       | 3632.8                      | 2.7782e+05                  | regime_climatology | regime_climatology |

## Quality checks

| check                            | passed | value                    | requirement                                            |
| -------------------------------- | ------ | ------------------------ | ------------------------------------------------------ |
| monthly_observation_count        | True   | 72                       | exactly 72                                             |
| monthly_calendar_complete        | True   | 2016-01-01 to 2021-12-01 | continuous 2016-01 through 2021-12                     |
| positive_totals                  | True   | True                     | all observed and forecast totals > 0                   |
| forecast_interval_nesting        | True   | True                     | lower95 <= lower80 <= point <= upper80 <= upper95      |
| second_year_intervals_wider      | True   | True                     | every 2023 log interval wider than matching 2022 month |
| annual_point_totals_match        | True   | True                     | annual points equal sums of monthly points             |
| schedule_has_no_daily_flux       | True   | none                     | sampling dates/times only                              |
| integration_reference_difference | True   | 0.364676%                | maximum difference <= 1%                               |

## Sampling intensity

| year | month | risk_level | risk_score | recommended_sample_times |
| ---- | ----- | ---------- | ---------- | ------------------------ |
| 2022 | 1     | low        | 0.0032431  | 4                        |
| 2022 | 2     | low        | 0.0506     | 3                        |
| 2022 | 3     | low        | 0.19736    | 4                        |
| 2022 | 4     | medium     | 0.23162    | 12                       |
| 2022 | 5     | medium     | 0.28265    | 14                       |
| 2022 | 6     | medium     | 0.59293    | 12                       |
| 2022 | 7     | high       | 0.75248    | 48                       |
| 2022 | 8     | medium     | 0.58598    | 14                       |
| 2022 | 9     | high       | 0.72466    | 45                       |
| 2022 | 10    | medium     | 0.69273    | 14                       |
| 2022 | 11    | medium     | 0.23318    | 12                       |
| 2022 | 12    | low        | 0.13665    | 4                        |
| 2023 | 1     | low        | 0.24747    | 4                        |
| 2023 | 2     | low        | 0.29422    | 3                        |
| 2023 | 3     | low        | 0.44028    | 4                        |
| 2023 | 4     | medium     | 0.47448    | 12                       |
| 2023 | 5     | medium     | 0.52546    | 14                       |
| 2023 | 6     | high       | 0.8357     | 45                       |
| 2023 | 7     | high       | 0.99523    | 48                       |
| 2023 | 8     | high       | 0.82881    | 48                       |
| 2023 | 9     | high       | 0.96743    | 45                       |
| 2023 | 10    | high       | 0.9355     | 48                       |
| 2023 | 11    | medium     | 0.47604    | 12                       |
| 2023 | 12    | low        | 0.37974    | 4                        |

The daily output is a sampling schedule only. No future daily water or sediment flux series is produced.
