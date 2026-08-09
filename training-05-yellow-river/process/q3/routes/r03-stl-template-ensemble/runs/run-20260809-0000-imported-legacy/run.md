# Run record

- 日期时间：2026-08-09（迁移登记；原运行时间未记录）
- 执行目录：原 `process/legacy-package/q3-optimized`，现迁入 `process/q3/routes/r03-stl-template-ensemble`
- 执行命令：`python code/optimized_question3.py`（依据 legacy README；本次迁移未重新执行）
- 代码入口/版本：`code/optimized_question3.py`；source commit `669f848`
- 输入文件：q2 历史日尺度水沙通量；历史 question-3 基础预测函数
- 关键参数：见 `validation/optimized_model_settings.csv`
- 随机种子：不适用；组合与权重搜索为确定性算法
- 环境/依赖：历史环境未完整记录；代码依赖 Python、NumPy、pandas、Pillow
- 结果文件：`results/data/processed/optimized_predicted_daily_flux_2022_2023.csv`、`results/tables/*.csv`
- 图表文件：`figures/optimized-forecast-monthly-flux.png`、`figures/optimized-sampling-monthly-counts.png`
- 验证文件：`validation/optimized_forecast_validation.csv`、`validation/optimized_weight_selection.csv`、`validation/optimized_model_settings.csv`
- 是否成功完成：partial
- 异常与备注：legacy 结果已导入但未在规范路径复现；代码中的旧路径依赖需在未来正式重跑前重构。
