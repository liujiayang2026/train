# Run record

- 日期时间：2026-08-09 20:05 +08:00
- 执行目录：`training-05-yellow-river/process/q3/routes/r04-monthly-flux-forecast`
- 执行命令：`python code/monthly_flux_forecast.py --run-dir runs/run-20260809-2005-canonical-upstream --q1-series ../../../q1/routes/r01-log-linear-sediment/runs/run-20260809-1941-canonical-uncertainty/results/data/cleaned_hydro_timeseries.csv --q2-daily ../../../q2/routes/r01-interpolated-daily-pattern/runs/run-20260809-1954-canonical-q1-input/results/data/processed/daily_flux_series.csv --q2-events ../../../q2/routes/r01-interpolated-daily-pattern/runs/run-20260809-1954-canonical-q1-input/results/tables/abrupt_change_events.csv`
- 代码入口/版本：`code/monthly_flux_forecast.py`；执行前 SHA-256 `4C5E8C97E84FFE61A84457F585449386AA26565A0114F5560BB1637E642BF90B`
- 输入文件：q1 `run-20260809-1941-canonical-uncertainty/results/data/cleaned_hydro_timeseries.csv`，SHA-256 `07D45ADAA1F36FA5D1506E0D82EF66BE440835B6FAAA78ADDE0D6289F6712330`；q2 `run-20260809-1954-canonical-q1-input/results/data/processed/daily_flux_series.csv`，SHA-256 `D71C5CD4C2AFF0E7689C59432C37CA282521D085C4D7D9055A951147CB91584B`；q2 `results/tables/abrupt_change_events.csv`，SHA-256 `3CA5DB1EBDF8B26759184754DAC62DC8FBD1301439298CD1D8444BCB90B8E7EE`
- 关键参数：积分存档72个月；有效建模48个月（2018—2021）；2019—2020扩展窗口回测选模；2018—2020训练、2021完整留出；2019—2021经验区间80%和95%；2023年对数区间扩宽系数1.25。
- 随机种子：不适用，模型与区间计算均为确定性算法。
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；Pillow 12.2.0。
- 结果文件：`results/monthly_observed_totals.csv`、`monthly_forecast_2022_2023.csv`、`annual_forecast_2022_2023.csv`、`monthly_sampling_strategy.csv`、`sampling_schedule_2022_2023.csv`、`summary.md`。
- 图表文件：`figures/historical_backtest.png`、`monthly_forecast_intervals.png`、`sampling_intensity.png`。
- 验证文件：`validation/model_comparison.csv`、`backtest_predictions.csv`、`interval_coverage.csv`、`integration_consistency.csv`、`quality_checks.csv`。
- 是否成功完成：yes
- 异常与备注：9/9质量检查通过；72个月积分、48个月建模、模型选择、2021留出和2022—2023预测点值与此前 canonical 结果一致。q2 新突变表使风险采样表产生474个时次，而旧 run 为473个；本 run 是完整绑定 q1、q2 新成功 canonical runs 的当前复现证据，不构成人工 adopted 决定。
