# Run record

- 日期时间：2026-08-09 20:40 +08:00
- 执行目录：`training-05-yellow-river/process/q3/routes/r04-monthly-flux-forecast/`
- 执行命令：`python code/monthly_flux_forecast.py --run-dir runs/run-20260809-2040-time-block-upstream --q1-series ../../../q1/routes/r01-log-linear-sediment/runs/run-20260809-2032-time-block-bootstrap/results/data/cleaned_hydro_timeseries.csv --q2-daily ../../../q2/routes/r01-interpolated-daily-pattern/runs/run-20260809-2036-time-block-q1/results/data/processed/daily_flux_series.csv --q2-events ../../../q2/routes/r01-interpolated-daily-pattern/runs/run-20260809-2036-time-block-q1/results/tables/abrupt_change_events.csv`
- 代码入口/版本：`code/monthly_flux_forecast.py`；执行前 SHA-256 `9D90A1183F3BF1FAC4F64A2E5D7D3165CFE13BF413B0CA43706D70DA1EFFCA6A`
- 输入文件：q1 `run-20260809-2032-time-block-bootstrap/results/data/cleaned_hydro_timeseries.csv`，SHA-256 `97E320A85FC91A24B5D4CDDA61E18236C56D9BCBD5324B4147B749D1D7A23324`；q2 `run-20260809-2036-time-block-q1/results/data/processed/daily_flux_series.csv`，SHA-256 `2DDBED3537B140648ADC9356A27AB414E44DF0DAA8EEBBC58C97A301ECE6F76B`；q2 `results/tables/abrupt_change_events.csv`，SHA-256 `ED7C4141EF4A690CF5093E060AD7CEB0F2AB2B17E9573DD0248283A3A563735B`
- 关键参数：积分存档 72 个月；有效建模 48 个月（2018—2021）；2019—2020 扩展窗口回测选模；2018—2020 训练、2021 完整预测留出；2019—2021 经验区间 80% 和 95%；2023 年对数区间扩宽系数 1.25。
- 随机种子：不适用；模型与规则均为确定性实现。
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；Pillow 12.2.0。
- 结果文件：`results/monthly_observed_totals.csv`、`monthly_forecast_2022_2023.csv`、`annual_forecast_2022_2023.csv`、`monthly_sampling_strategy.csv`、`sampling_schedule_2022_2023.csv`、`summary.md`。
- 图表文件：`figures/historical_backtest.png`、`monthly_forecast_intervals.png`、`sampling_intensity.png`。
- 验证文件：`validation/model_comparison.csv`、`backtest_predictions.csv`、`interval_coverage.csv`、`integration_consistency.csv`、`quality_checks.csv`。
- 是否成功完成：yes
- 异常与备注：2026-08-09 20:40 +08:00 成功完成，9/9 质量检查通过；72 个月积分、48 个月建模及水沙模型选择保持稳定。2022 年预测水量 458.39 亿 m³、输沙量 34164.05 万吨，2023 年分别为 483.88 亿 m³、37734.75 万吨；修正后的 q2 事件输入仍产生 474 个旧启发式采样时次。本次绑定 q1 2032 与 q2 2036 成功 run，并验证 NumPy 1.x/2.x 梯形积分兼容、直接子目录保护及完整上游 provenance；不构成人工 adopted 决定。
