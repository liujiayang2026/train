# Run record

- 日期时间：2026-08-09 18:02 Asia/Shanghai
- 执行目录：运行时为 `training-05-yellow-river/process/q3/routes/r01-monthly-flux-forecast`；编号去重后的当前规范路径为 `training-05-yellow-river/process/q3/routes/r04-monthly-flux-forecast`
- 执行命令：`python code/monthly_flux_forecast.py --run-dir runs/run-20260809-1802-canonical-input-paths`
- 代码入口/版本：`code/monthly_flux_forecast.py`；SHA-256 `AAFB741DD03C0C26D1CC8F639FDDC54E30E136C77C5E1118F747C6E0D58A3A26`
- 输入文件：`process/q1/routes/r01-log-linear-sediment/runs/run-20260809-0000-imported-legacy/results/data/processed/cleaned_hydro_timeseries.csv`；`process/q2/routes/r01-interpolated-daily-pattern/runs/run-20260809-0000-imported-legacy/results/data/processed/daily_flux_series.csv`；`process/q2/routes/r01-interpolated-daily-pattern/runs/run-20260809-0000-imported-legacy/validation/abrupt_change_events.csv`
- 关键参数：积分存档 72 个月；有效建模 48 个月（2018—2021）；2019—2020 扩展窗口回测选模；2018—2020 训练、2021 完整留出检验；2019—2021 经验区间 80% 和 95%；2023 年对数区间扩宽系数 1.25
- 随机种子：不适用，模型与区间计算均为确定性算法
- 环境/依赖：Windows PowerShell；Codex bundled Python 3.12；NumPy、pandas、Pillow
- 结果文件：`results/monthly_observed_totals.csv`；`results/monthly_forecast_2022_2023.csv`；`results/annual_forecast_2022_2023.csv`；`results/sampling_schedule_2022_2023.csv`
- 图表文件：`figures/historical_backtest.png`；`figures/monthly_forecast_intervals.png`；`figures/sampling_intensity.png`
- 验证文件：`validation/model_comparison.csv`；`validation/backtest_predictions.csv`；`validation/interval_coverage.csv`；`validation/integration_consistency.csv`；`validation/quality_checks.csv`
- 是否成功完成：yes
- 异常与备注：本次运行用于验证主仓库 canonical route 迁移后的输入路径，模型与参数不变；72 个月积分、48 个月建模、水沙模型选择、预测值、区间覆盖和 473 个采样时次均与上一版一致，9 项质量检查全部通过。
