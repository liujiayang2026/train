# Run record

- 日期时间：2026-08-09（迁移登记；原运行时间未记录）
- 执行目录：原process/legacy-package/question-2，现迁入process/q2/routes/r01-interpolated-daily-pattern
- 执行命令：python code/analyze_question2.py（历史README记录；本次迁移未重新执行）
- 代码入口/版本：code/analyze_question2.py；source commit 669f848
- 输入文件：q1历史运行的cleaned_hydro_timeseries.csv
- 关键参数：逐小时网格、日均聚合、滑动突变窗口和周期分析参数详见notes/question2-method.md
- 随机种子：不适用，分析流程为确定性算法
- 环境/依赖：历史环境未完整记录；代码依赖Python、NumPy、pandas、Pillow
- 结果文件：results/data/processed/daily_flux_series.csv；results/tables/*.csv
- 图表文件：figures/monthly-absolute-flux.png；figures/monthly-normalized-flux.png；figures/monthly-water-sediment-share.png
- 验证文件：validation/abrupt_change_events.csv；validation/autocorrelation_lags.csv；validation/periodicity_summary.csv
- 是否成功完成：partial
- 异常与备注：历史结果已导入但未在新路径复现；插值口径的统计含义必须与原始观测覆盖率同时解释。
