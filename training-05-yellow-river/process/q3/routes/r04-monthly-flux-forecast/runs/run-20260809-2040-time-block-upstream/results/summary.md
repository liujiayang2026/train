# Run summary

## Selected monthly models

| target              | selected_model        | validation_rmse_log | validation_r2_log | validation_wape |
| ------------------- | --------------------- | ------------------- | ----------------- | --------------- |
| water_volume_1e8_m3 | fourier_ridge_alpha_1 | 0.22499             | 0.87069           | 0.19303         |
| sediment_mass_1e4_t | fourier_ridge_alpha_1 | 0.43564             | 0.91828           | 0.28407         |

## Interval calibration

| target              | nominal_coverage | empirical_coverage | log_radius | calibration_months |
| ------------------- | ---------------- | ------------------ | ---------- | ------------------ |
| water_volume_1e8_m3 | 0.8              | 0.77778            | 0.33919    | 36                 |
| water_volume_1e8_m3 | 0.95             | 0.94444            | 0.83986    | 36                 |
| sediment_mass_1e4_t | 0.8              | 0.77778            | 0.63581    | 36                 |
| sediment_mass_1e4_t | 0.95             | 0.94444            | 1.8047     | 36                 |

## Annual forecast

| year | water_volume_1e8_m3 | water_volume_1e8_m3_lower80 | water_volume_1e8_m3_upper80 | water_volume_1e8_m3_lower95 | water_volume_1e8_m3_upper95 | sediment_mass_1e4_t | sediment_mass_1e4_t_lower80 | sediment_mass_1e4_t_upper80 | sediment_mass_1e4_t_lower95 | sediment_mass_1e4_t_upper95 | water_model           | sediment_model        |
| ---- | ------------------- | --------------------------- | --------------------------- | --------------------------- | --------------------------- | ------------------- | --------------------------- | --------------------------- | --------------------------- | --------------------------- | --------------------- | --------------------- |
| 2022 | 458.39              | 323.08                      | 648.33                      | 191.1                       | 1077.4                      | 34164               | 18084                       | 64531                       | 5610.8                      | 2.0771e+05                  | fourier_ridge_alpha_1 | fourier_ridge_alpha_1 |
| 2023 | 483.88              | 312.52                      | 745.72                      | 161.56                      | 1404.8                      | 37735               | 17038                       | 83556                       | 3943.2                      | 3.6022e+05                  | fourier_ridge_alpha_1 | fourier_ridge_alpha_1 |

## Quality checks

| check                            | passed | value                    | requirement                                            |
| -------------------------------- | ------ | ------------------------ | ------------------------------------------------------ |
| monthly_observation_count        | True   | 72                       | exactly 72                                             |
| post_break_modeling_count        | True   | 48                       | exactly 48 months from 2018-01 through 2021-12         |
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
| 2022 | 1     | low        | 0.0023093  | 4                        |
| 2022 | 2     | low        | 0.057955   | 3                        |
| 2022 | 3     | low        | 0.1664     | 4                        |
| 2022 | 4     | medium     | 0.23922    | 12                       |
| 2022 | 5     | medium     | 0.26942    | 14                       |
| 2022 | 6     | medium     | 0.57445    | 12                       |
| 2022 | 7     | high       | 0.74596    | 48                       |
| 2022 | 8     | medium     | 0.68213    | 14                       |
| 2022 | 9     | medium     | 0.67678    | 12                       |
| 2022 | 10    | high       | 0.69983    | 48                       |
| 2022 | 11    | medium     | 0.17697    | 12                       |
| 2022 | 12    | low        | 0.07212    | 4                        |
| 2023 | 1     | low        | 0.25404    | 4                        |
| 2023 | 2     | low        | 0.30923    | 3                        |
| 2023 | 3     | low        | 0.41729    | 4                        |
| 2023 | 4     | medium     | 0.49       | 12                       |
| 2023 | 5     | medium     | 0.52018    | 14                       |
| 2023 | 6     | high       | 0.82517    | 45                       |
| 2023 | 7     | high       | 0.99667    | 48                       |
| 2023 | 8     | high       | 0.93285    | 48                       |
| 2023 | 9     | high       | 0.9275     | 45                       |
| 2023 | 10    | high       | 0.95055    | 48                       |
| 2023 | 11    | medium     | 0.42783    | 12                       |
| 2023 | 12    | low        | 0.32332    | 4                        |

The daily output is a sampling schedule only. No future daily water or sediment flux series is produced.
