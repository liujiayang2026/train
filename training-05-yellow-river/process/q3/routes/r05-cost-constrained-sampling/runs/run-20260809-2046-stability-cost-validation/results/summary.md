# Cost-constrained sampling run summary

This run optimizes monitoring timing only. It consumes the explicitly supplied r04 forecast/risk products and does not refit the forecast model.

## Pre-specified constraints

- Calibration water proxy WAPE <= 10%
- Calibration sediment proxy WAPE <= 25%
- Calibration abrupt-event capture >= 80%
- Base gap caps: high 5 days, medium 10 days, low 14 days

## Selected monthly policy

| month | risk_level | base_interval_days | trigger_threshold | cost_units | water_wape | sediment_wape | event_capture_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1.000 | low | 14.000 | 1.000 | 15.000 | 0.059 | 0.132 | nan |
| 2.000 | low | 14.000 | 2.500 | 11.667 | 0.102 | 0.293 | nan |
| 3.000 | low | 14.000 | 1.500 | 15.000 | 0.053 | 0.137 | nan |
| 4.000 | medium | 10.000 | 1.500 | 15.000 | 0.068 | 0.178 | nan |
| 5.000 | medium | 10.000 | 1.500 | 20.000 | 0.039 | 0.095 | nan |
| 6.000 | high | 5.000 | 2.500 | 38.333 | 0.043 | 0.114 | 1.000 |
| 7.000 | high | 5.000 | 2.500 | 43.333 | 0.062 | 0.107 | 0.000 |
| 8.000 | high | 5.000 | 2.500 | 56.667 | 0.076 | 0.149 | 1.000 |
| 9.000 | high | 5.000 | 2.500 | 46.667 | 0.064 | 0.117 | 1.000 |
| 10.000 | high | 5.000 | 2.000 | 43.333 | 0.051 | 0.117 | 1.000 |
| 11.000 | medium | 10.000 | 2.000 | 23.333 | 0.067 | 0.165 | nan |
| 12.000 | low | 14.000 | 2.500 | 18.333 | 0.103 | 0.319 | nan |

## Calibration aggregate

- Annual expected cost: 346.67 resource units
- Water proxy WAPE: 6.20%
- Sediment proxy WAPE: 12.52%
- Abrupt-event capture: 80.00%

## 2021 strategy-level conditional holdout and baselines

| policy | annual_cost_units | annual_visits | water_wape | sediment_wape | event_capture_rate | max_gap_days |
| --- | --- | --- | --- | --- | --- | --- |
| optimized_dynamic | 390.000 | 78.000 | 0.054 | 0.128 | 1.000 | 14.000 |
| optimized_base_only_ablation | 270.000 | 54.000 | 0.087 | 0.190 | 0.800 | 14.000 |
| old_r04_heuristic | 735.000 | 112.000 | 0.038 | 0.093 | 1.000 | 10.000 |
| uniform_3d | 635.000 | 127.000 | 0.036 | 0.096 | 1.000 | 3.000 |
| uniform_5d | 395.000 | 79.000 | 0.067 | 0.163 | 0.800 | 5.000 |
| uniform_7d | 295.000 | 59.000 | 0.107 | 0.296 | 0.200 | 7.000 |
| uniform_10d | 215.000 | 43.000 | 0.143 | 0.296 | 0.800 | 10.000 |
| uniform_14d | 175.000 | 35.000 | 0.129 | 0.274 | 0.200 | 14.000 |

This is conditional only at the r05 strategy layer: 2021 is excluded from r05 policy/threshold selection, but the supplied q1 completion and r04 risk products may contain information from the full historical span. It is not an end-to-end leakage-free holdout.

## Dynamic-trigger ablation (same base intervals)

| split | policy | annual_cost_units | water_wape | sediment_wape | event_capture_rate | delta_vs_dynamic_annual_cost_units |
| --- | --- | --- | --- | --- | --- | --- |
| calibration_2018_2020 | optimized_dynamic | 346.667 | 0.062 | 0.125 | 0.800 | 0.000 |
| calibration_2018_2020 | optimized_base_only_ablation | 271.667 | 0.081 | 0.170 | 0.200 | -75.000 |
| strategy_conditional_holdout_2021 | optimized_dynamic | 390.000 | 0.054 | 0.128 | 1.000 | 0.000 |
| strategy_conditional_holdout_2021 | optimized_base_only_ablation | 270.000 | 0.087 | 0.190 | 0.800 | -120.000 |

## Abrupt-event stability evidence

| split | event_count | captured_events | raw_capture_rate | raw_clopper_pearson_95_lower | raw_clopper_pearson_95_upper | stability_weighted_capture_rate | weighted_effective_event_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| calibration_2018_2020 | 5.000 | 4.000 | 0.800 | 0.284 | 0.995 | 0.930 | 4.141 |
| strategy_conditional_holdout_2021 | 5.000 | 5.000 | 1.000 | 0.478 | 1.000 | 1.000 | 4.053 |
| combined_2018_2021_descriptive | 10.000 | 9.000 | 0.900 | 0.555 | 0.997 | 0.963 | 8.178 |

Event counts are small. Exact raw binomial intervals and weighted effective counts are reported as uncertainty boundaries, not as proof of future capture performance.

## Operational dynamic protocol

- Historical q90 water log-change scale: 0.080677150
- Historical q90 sediment log-change scale: 0.331392003
- At daily 09:00 Asia/Shanghai, use only observations available by that time: W*=0.000864*Q and S*=0.00864*Q*C, where Q is instantaneous flow (m3/s) and C is the rapid turbidity/sediment proxy (kg/m3). Compare consecutive 09:00 log1p changes.
- The daily rapid trigger assumes Q and C are available from an existing automatic/remote station feed without an extra field visit. If 09:00 readings require manual attendance, that daily cost must be added and the optimization rerun.
- Formal assay results must return before next-day 09:00. If rapid C or the prior formal sediment result is late, use the flow component alone at the same threshold without waiting. A trigger adds samples on each of the next two days.
- Historical daily-total q90 scales are mapped to same-unit daily-equivalent instantaneous proxies; prospective fixed-time observations are still needed for recalibration, and no future daily total is assumed known.

## Future cost comparison

| year | optimized_base_cost_units | optimized_expected_cost_units | optimized_worst_case_cost_units | old_r04_cost_units | expected_cost_reduction_vs_old_pct |
| --- | --- | --- | --- | --- | --- |
| 2022 | 270.000 | 345.000 | 1825.000 | 527.000 | 34.535 |
| 2023 | 270.000 | 345.000 | 1825.000 | 735.000 | 53.061 |
| 2022-2023 total | 540.000 | 690.000 | 3650.000 | 1262.000 | 45.325 |

## Cost-coefficient sensitivity

| scenario | visit_cost_weight | assay_cost_weight | optimized_expected_cost | old_r04_cost | expected_cost_reduction_vs_old_pct |
| --- | --- | --- | --- | --- | --- |
| assay_heavy | 1.000 | 4.000 | 690.000 | 2093.000 | 67.033 |
| balanced | 1.000 | 1.000 | 276.000 | 671.000 | 58.867 |
| visit_light | 2.000 | 1.000 | 414.000 | 868.000 | 52.304 |
| pre_specified | 4.000 | 1.000 | 690.000 | 1262.000 | 45.325 |
| visit_heavy | 8.000 | 1.000 | 1242.000 | 2050.000 | 39.415 |

## Evidence boundary

The historical daily series is a proxy derived from q1 completion and q2 interpolation. Intraday benefits of the old 2/3-sample visits cannot be scored from daily data, so they are charged as cost but are not credited with invented accuracy. All candidate r05 options use one assay per visit, so changing cost coefficients does not change their within-r05 ranking; it changes the savings comparison against the multi-assay r04 schedule. This candidate run is not a human adoption decision.

Quality checks passed: 23/23.
