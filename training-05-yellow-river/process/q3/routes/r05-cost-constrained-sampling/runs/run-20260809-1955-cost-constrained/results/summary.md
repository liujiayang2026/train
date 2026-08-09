# Cost-constrained sampling run summary

This run optimizes monitoring timing only. It consumes the r04 canonical forecast and does not refit the forecast model.

## Canonical pre-specified constraints

- Calibration water proxy WAPE <= 10%
- Calibration sediment proxy WAPE <= 25%
- Calibration abrupt-event capture >= 80%
- Base gap caps: high 5 days, medium 10 days, low 14 days

## Selected monthly policy

| month | risk_level | base_interval_days | trigger_threshold | cost_units | water_wape | sediment_wape | event_capture_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1.000 | low | 14.000 | 1.000 | 15.000 | 0.059 | 0.132 | nan |
| 2.000 | low | 14.000 | 1.000 | 11.667 | 0.102 | 0.293 | nan |
| 3.000 | low | 14.000 | 1.000 | 15.000 | 0.053 | 0.137 | nan |
| 4.000 | medium | 10.000 | 1.000 | 15.000 | 0.068 | 0.178 | nan |
| 5.000 | medium | 10.000 | 1.000 | 20.000 | 0.039 | 0.095 | nan |
| 6.000 | high | 5.000 | 2.000 | 30.000 | 0.087 | 0.149 | 0.500 |
| 7.000 | high | 3.000 | 2.500 | 55.000 | 0.037 | 0.065 | 1.000 |
| 8.000 | high | 5.000 | 1.000 | 48.333 | 0.107 | 0.226 | 1.000 |
| 9.000 | high | 5.000 | 1.500 | 30.000 | 0.086 | 0.165 | 1.000 |
| 10.000 | high | 3.000 | 1.500 | 55.000 | 0.036 | 0.091 | 1.000 |
| 11.000 | medium | 10.000 | 1.000 | 15.000 | 0.096 | 0.273 | nan |
| 12.000 | low | 14.000 | 1.000 | 15.000 | 0.120 | 0.333 | nan |

## Calibration aggregate

- Annual expected cost: 325.00 resource units
- Water proxy WAPE: 6.91%
- Sediment proxy WAPE: 13.99%
- Abrupt-event capture: 88.89%

## 2021 holdout and baselines

| policy | annual_cost_units | annual_visits | water_wape | sediment_wape | event_capture_rate | max_gap_days |
| --- | --- | --- | --- | --- | --- | --- |
| optimized_dynamic | 340.000 | 68.000 | 0.073 | 0.154 | 1.000 | 14.000 |
| old_r04_heuristic | 735.000 | 112.000 | 0.038 | 0.093 | 1.000 | 10.000 |
| uniform_3d | 635.000 | 127.000 | 0.036 | 0.096 | 1.000 | 3.000 |
| uniform_5d | 395.000 | 79.000 | 0.067 | 0.163 | 0.800 | 5.000 |
| uniform_7d | 295.000 | 59.000 | 0.107 | 0.296 | 0.200 | 7.000 |
| uniform_10d | 215.000 | 43.000 | 0.143 | 0.296 | 0.800 | 10.000 |
| uniform_14d | 175.000 | 35.000 | 0.129 | 0.274 | 0.200 | 14.000 |

## Future cost comparison

| year | optimized_base_cost_units | optimized_expected_cost_units | optimized_worst_case_cost_units | old_r04_cost_units | expected_cost_reduction_vs_old_pct |
| --- | --- | --- | --- | --- | --- |
| 2022 | 310.000 | 323.333 | 910.000 | 526.000 | 38.530 |
| 2023 | 310.000 | 323.333 | 910.000 | 735.000 | 56.009 |
| 2022-2023 total | 620.000 | 646.667 | 1820.000 | 1261.000 | 48.718 |

## Evidence boundary

The historical daily series is a proxy derived from q1 completion and q2 interpolation. Intraday benefits of the old 2/3-sample visits cannot be scored from daily data, so they are charged as cost but are not credited with invented accuracy. The 2021 holdout is reported once and was not used by the optimizer. This candidate run is not a human adoption decision.

Quality checks passed: 12/12.
