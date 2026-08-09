# Run record

- 日期时间：2026-08-09 14:59 Asia/Shanghai
- 执行目录：运行时为 `training-05-yellow-river/process/q3/routes/r01-monthly-flux-forecast`；编号去重后的当前规范路径为 `training-05-yellow-river/process/q3/routes/r04-monthly-flux-forecast`
- 执行命令：python code/monthly_flux_forecast.py --run-dir runs/run-20260809-1459-monthly-baseline
- 代码入口/版本：code/monthly_flux_forecast.py；首次月尺度候选实现
- 输入文件：process/legacy-package/question-1/data/processed/cleaned_hydro_timeseries.csv；process/legacy-package/question-2/data/processed/daily_flux_series.csv（仅积分一致性核验）；process/legacy-package/question-2/qa/abrupt_change_events.csv（仅采样风险月份）
- 关键参数：72个月；月周期12；滚动验证年2019-2021；状态气候衰减系数0.55；年趋势对数斜率截断水量0.08、输沙量0.12；经验区间80%和95%；2023年对数区间扩宽系数1.25
- 随机种子：不适用，模型与区间计算均为确定性算法
- 环境/依赖：Windows PowerShell；Python 3.12；numpy、pandas、Pillow
- 结果文件：results/monthly_observed_totals.csv；results/monthly_forecast_2022_2023.csv；results/annual_forecast_2022_2023.csv；results/sampling_schedule_2022_2023.csv
- 图表文件：figures/historical_backtest.png；figures/monthly_forecast_intervals.png；figures/sampling_intensity.png
- 验证文件：validation/model_comparison.csv；validation/backtest_predictions.csv；validation/interval_coverage.csv；validation/integration_consistency.csv；validation/quality_checks.csv
- 是否成功完成：yes
- 异常与备注：水量与输沙量均选择regime_climatology；平均对数RMSE分别为0.34637和0.74750。80%区间覆盖率均为80.56%，95%区间覆盖率均为94.44%；8项质量检查全部通过。直接月积分与问题二日汇总的最大差异为0.364676%，说明插值口径不是2021异常失配的主因。2021年8月反季节低谷缺少可用于未来预测的调度或降雨外生变量，整年提前预测仍不能精确命中，已由预测区间表达该风险。2022年点预测为水量448.09亿m3、输沙量29751.95万吨；2023年分别为480.45亿m3、31809.97万吨。日尺度仅输出473个建议采样时次，不输出逐日通量。
