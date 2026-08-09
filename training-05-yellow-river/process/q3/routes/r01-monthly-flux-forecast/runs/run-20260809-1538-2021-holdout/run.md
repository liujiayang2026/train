# Run record

- 日期时间：2026-08-09 15:38 Asia/Shanghai
- 执行目录：training-05-yellow-river/process/q3/routes/r01-monthly-flux-forecast
- 执行命令：python code/monthly_flux_forecast.py --run-dir runs/run-20260809-1538-2021-holdout
- 代码入口/版本：code/monthly_flux_forecast.py；2018年后状态、2021单年留出验证
- 输入文件：process/legacy-package/question-1/data/processed/cleaned_hydro_timeseries.csv；process/legacy-package/question-2/data/processed/daily_flux_series.csv（仅积分一致性核验）；process/legacy-package/question-2/qa/abrupt_change_events.csv（仅采样风险月份）
- 关键参数：积分存档72个月；有效建模48个月（2018-2021）；2019-2020扩展窗口回测用于选模；2018-2020训练、2021完整留出作最终检验；候选岭惩罚参数网格；2019-2021经验区间80%和95%；2023年对数区间扩宽系数1.25
- 随机种子：不适用，模型与区间计算均为确定性算法
- 环境/依赖：Windows PowerShell；Python 3.12；numpy、pandas、Pillow
- 结果文件：results/monthly_observed_totals.csv；results/monthly_forecast_2022_2023.csv；results/annual_forecast_2022_2023.csv；results/sampling_schedule_2022_2023.csv
- 图表文件：figures/historical_backtest.png；figures/monthly_forecast_intervals.png；figures/sampling_intensity.png
- 验证文件：validation/model_comparison.csv；validation/backtest_predictions.csv；validation/interval_coverage.csv；validation/integration_consistency.csv；validation/quality_checks.csv
- 是否成功完成：yes
- 异常与备注：水量与输沙量均选择fourier_ridge_alpha_1。2019-2020选模回测平均对数RMSE分别为0.22499和0.43564，平均WAPE分别为19.30%和28.41%；2021最终留出对数RMSE分别为0.56272和1.29866，WAPE分别为43.22%和73.62%。2021年8月水量预测为实际值3.51倍、输沙量为25.32倍，仍不能依靠历史通量提前识别异常低谷。2019-2021校准中80%区间覆盖77.78%，95%区间覆盖94.44%。9项质量检查全部通过，直接积分与问题二日汇总最大差异0.364676%。2022年点预测为水量458.39亿m3、输沙量34164.10万吨；2023年分别为483.88亿m3、37734.81万吨。日尺度仅输出473个建议采样时次，不输出逐日通量。
