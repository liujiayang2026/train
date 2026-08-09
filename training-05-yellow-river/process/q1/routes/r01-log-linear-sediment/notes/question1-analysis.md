# Question 1 imported result summary

Input workbook: `source/attachments/附件1.xlsx`

This imported numerical summary is retained for readability. The current reproducible reference evidence, including real-time-block uncertainty and sensitivity validation, is under `../runs/run-20260809-2032-time-block-bootstrap/`.

## Data Cleaning

- Parsed the 2016-2021 sheets, forward-filled year/month/day cells, and converted `24:00` records to the next day.
- Water level and flow are nearly complete; missing water levels were time-interpolated before modeling.
- Sediment concentration is sparse, so missing concentration values were estimated with a log-linear regression model.

## Concentration Model

The machine-selected candidate within this run is `hydro_only_quadratic` and fits `log(C)` with: log_flow, water_level, log_flow_sq, water_level_sq, log_flow_x_water_level. This wording does not represent a human adopted decision.
A log transform is used because sediment concentration is positive and strongly right-skewed.

Best mean held-out-year RMSE on log concentration: `0.4637` for `hydro_only_quadratic`.

Key relationship diagnostics:

| item                        | value     | description                                                                                 |
| --------------------------- | --------- | ------------------------------------------------------------------------------------------- |
| corr_sediment_flow          | 0.624104  | Pearson correlation between observed sediment concentration and flow.                       |
| corr_log_sediment_log_flow  | 0.890267  | Pearson correlation after log transform.                                                    |
| corr_sediment_water_level   | 0.61525   | Pearson correlation between observed sediment concentration and water level.                |
| coef_log_flow               | -18.207   | Approximate raw-scale coefficient of log_flow in the log-concentration model.               |
| coef_water_level            | 32.9485   | Approximate raw-scale coefficient of water_level in the log-concentration model.            |
| coef_log_flow_sq            | 0.1863    | Approximate raw-scale coefficient of log_flow_sq in the log-concentration model.            |
| coef_water_level_sq         | -0.414949 | Approximate raw-scale coefficient of water_level_sq in the log-concentration model.         |
| coef_log_flow_x_water_level | 0.399901  | Approximate raw-scale coefficient of log_flow_x_water_level in the log-concentration model. |

Monthly time-pattern summary:

| month | records | observed_sediment_records | mean_flow_m3s | mean_observed_sediment_kgm3 | mean_used_sediment_kgm3 |
| ----- | ------- | ------------------------- | ------------- | --------------------------- | ----------------------- |
| 1     | 1165    | 176                       | 345.901       | 0.864369                    | 0.87366                 |
| 2     | 1320    | 143                       | 476.433       | 1.47507                     | 1.31923                 |
| 3     | 1279    | 159                       | 766.017       | 2.60872                     | 2.40556                 |
| 4     | 1121    | 148                       | 985.095       | 3.02355                     | 3.38931                 |
| 5     | 1128    | 158                       | 1069.82       | 2.46687                     | 3.88081                 |
| 6     | 1451    | 191                       | 1803.9        | 3.118                       | 6.15639                 |
| 7     | 1939    | 276                       | 2254.29       | 13.2005                     | 9.473                   |
| 8     | 1618    | 213                       | 1672.15       | 7.86732                     | 7.37116                 |
| 9     | 1582    | 189                       | 1786.15       | 4.64238                     | 6.91263                 |
| 10    | 1478    | 199                       | 1981.61       | 3.70751                     | 5.52383                 |
| 11    | 1246    | 148                       | 774.205       | 1.6908                      | 2.66097                 |
| 12    | 1408    | 154                       | 552.873       | 1.17245                     | 1.56205                 |

## Annual Estimates

| year | records | sediment_observed_records | water_volume_1e8_m3 | sediment_mass_1e4_t | mean_flow_m3s | mean_sediment_used_kgm3 |
| ---- | ------- | ------------------------- | ------------------- | ------------------- | ------------- | ----------------------- |
| 2016 | 2379    | 372                       | 143.752             | 2322.85             | 454.589       | 1.22535                 |
| 2017 | 2194    | 371                       | 153.355             | 2351.51             | 486.285       | 1.28822                 |
| 2018 | 3182    | 431                       | 388.908             | 27797.7             | 1233.22       | 5.49549                 |
| 2019 | 3063    | 403                       | 387.21              | 30144.6             | 1227.84       | 6.08779                 |
| 2020 | 3012    | 320                       | 433.795             | 36032               | 1371.8        | 6.25177                 |
| 2021 | 2905    | 257                       | 472.707             | 32735               | 1498.94       | 5.90364                 |

## Output Files

- `../runs/run-20260809-2032-time-block-bootstrap/results/data/cleaned_hydro_timeseries.csv`: cleaned series with observed/model/used concentration.
- `../runs/run-20260809-2032-time-block-bootstrap/validation/model_validation.csv`: four-model held-out-year comparison.
- `../runs/run-20260809-2032-time-block-bootstrap/validation/relationship_diagnostics.csv`: descriptive correlations and model coefficients.
- `../runs/run-20260809-2032-time-block-bootstrap/results/tables/monthly_relationship_summary.csv`: month-level summary.
- `../runs/run-20260809-2032-time-block-bootstrap/results/tables/annual_flux_estimates.csv`: annual total water volume and sediment load estimates.
- `../runs/run-20260809-2032-time-block-bootstrap/validation/bootstrap_block_length_sensitivity.csv`: 24/72/168-hour moving-block comparison.
- `../runs/run-20260809-2032-time-block-bootstrap/validation/validation_summary.md`: annual holdout, sensitivity, bootstrap interval definitions, and limitations.

## Interpretation boundary

The correlations above are descriptive, not significance or causal tests. About 87.13% of concentration records are modeled; annual sediment totals must therefore be reported together with the reference run's holdout error, sensitivity scenarios, and model-imputation uncertainty limits. The 72-hour baseline lies inside only 2 of 6 empirical percentile intervals, and the intervals change with block duration; these are not calibrated confidence intervals or coverage evidence.
