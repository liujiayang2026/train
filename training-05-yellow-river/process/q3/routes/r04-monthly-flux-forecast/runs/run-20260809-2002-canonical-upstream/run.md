# Run record

- 日期时间：2026-08-09 20:02 +08:00
- 执行目录：`training-05-yellow-river/process/q3/routes/r04-monthly-flux-forecast`
- 执行命令：`python code/monthly_flux_forecast.py --run-dir runs/run-20260809-2002-canonical-upstream --q1-series ../../../q1/routes/r01-log-linear-sediment/runs/run-20260809-1941-canonical-uncertainty/results/data/cleaned_hydro_timeseries.csv --q2-daily ../../../q2/routes/r01-interpolated-daily-pattern/runs/run-20260809-1954-canonical-q1-input/results/data/processed/daily_flux_series.csv --q2-events ../../../q2/routes/r01-interpolated-daily-pattern/runs/run-20260809-1954-canonical-q1-input/results/tables/abrupt_change_events.csv`
- 代码入口/版本：`code/monthly_flux_forecast.py`；执行前 SHA-256 `FDD372A421475A81004B5EBBC3E267DF85921FCD652E2BC9312C4428137E56AA`
- 输入文件：q1 `run-20260809-1941-canonical-uncertainty/results/data/cleaned_hydro_timeseries.csv`，SHA-256 `07D45ADAA1F36FA5D1506E0D82EF66BE440835B6FAAA78ADDE0D6289F6712330`；q2 `run-20260809-1954-canonical-q1-input/results/data/processed/daily_flux_series.csv`，SHA-256 `D71C5CD4C2AFF0E7689C59432C37CA282521D085C4D7D9055A951147CB91584B`；q2 `results/tables/abrupt_change_events.csv`，SHA-256 `3CA5DB1EBDF8B26759184754DAC62DC8FBD1301439298CD1D8444BCB90B8E7EE`
- 关键参数：积分存档72个月；有效建模48个月（2018—2021）；2019—2020扩展窗口回测选模；2018—2020训练、2021完整留出；2019—2021经验区间80%和95%；2023年对数区间扩宽系数1.25。
- 随机种子：不适用，模型与区间计算均为确定性算法。
- 环境/依赖：Windows；Python 3.12；NumPy、pandas、Pillow。
- 结果文件：无。
- 图表文件：无。
- 验证文件：无；错误证据见 `logs/error.txt`。
- 是否成功完成：no
- 异常与备注：在月积分阶段触发 `AttributeError: numpy has no attribute trapezoid`；当前 NumPy 1.26.4 只提供 `np.trapz`。失败发生在写出结果前，本目录保留且不再复用；兼容修复后转入新 run。本记录不构成人工 adopted 决定。
