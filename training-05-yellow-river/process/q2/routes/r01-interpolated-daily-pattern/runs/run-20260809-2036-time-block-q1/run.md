# Run record

- 日期时间：2026-08-09 20:36 +08:00
- 执行目录：`training-05-yellow-river/`
- 执行命令：`python process/q2/routes/r01-interpolated-daily-pattern/code/analyze_question2.py --input process/q1/routes/r01-log-linear-sediment/runs/run-20260809-2032-time-block-bootstrap/results/data/cleaned_hydro_timeseries.csv --run-dir process/q2/routes/r01-interpolated-daily-pattern/runs/run-20260809-2036-time-block-q1`
- 代码入口/版本：`process/q2/routes/r01-interpolated-daily-pattern/code/analyze_question2.py`；执行前 SHA-256 `3C38977B8FF1F3CC9364D13F97A2D2C95336874580EBD8E245C3EA1A7F9CD2EE`
- 输入文件：`process/q1/routes/r01-log-linear-sediment/runs/run-20260809-2032-time-block-bootstrap/results/data/cleaned_hydro_timeseries.csv`；SHA-256 `97E320A85FC91A24B5D4CDDA61E18236C56D9BCBD5324B4147B749D1D7A23324`
- 关键参数：基准插值 `linear_flux_direct`；逐小时网格后日均聚合；突变窗口 7 日、得分阈值 3.0、最小间隔 20 日、最多 15 个；敏感性含 3 种插值口径、27 组突变参数和 3 个连续时间区间。
- 随机种子：不适用，分析流程为确定性算法。
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；Pillow 12.2.0。
- 结果文件：`results/data/processed/daily_flux_series.csv`；`results/tables/annual_flux_pattern.csv`、`monthly_flux_summary.csv`、`flood_season_concentration.csv`、`abrupt_change_events.csv`、`periodicity_summary.csv`、`autocorrelation_lags.csv`；`results/reports/question2-analysis.md`。
- 图表文件：`figures/monthly-water-sediment-share.png`、`monthly-normalized-flux.png`、`monthly-mean-flow.png`、`monthly-mean-sediment-flux.png`；绝对流量和沙通量使用不同图及各自单位。
- 验证文件：`validation/input_quality_summary.csv`、`interpolation_sensitivity_summary.csv`、`interpolation_sensitivity_annual.csv`、`interpolation_sensitivity_monthly.csv`、`interpolation_event_overlap.csv`、`abrupt_parameter_sensitivity.csv`、`abrupt_event_stability.csv`、`periodicity_robustness.csv`、`seasonality_by_year.csv`、`run_manifest.json`。
- 是否成功完成：yes
- 异常与备注：2026-08-09 20:37 +08:00 成功完成，生成 2192 个完整日记录和 11 个达到基准阈值的突变候选。三种插值口径相对基准的六年总排沙量最大绝对差异约 0.0372%；27 组突变参数对基准事件的 ±7 日覆盖率中位数为 63.6%；10 组插值/时间子区间与序列组合的频谱主峰均位于 300—450 日。相较 1954 run，新增的数值文本水位解析使日输沙量最多变化约 0.00481 万吨，但 11 个基准事件日期不变。本次绑定 q1 `run-20260809-2032-time-block-bootstrap`，并通过收紧后的直接子目录与禁止覆盖保护；不构成人工采用决定。
