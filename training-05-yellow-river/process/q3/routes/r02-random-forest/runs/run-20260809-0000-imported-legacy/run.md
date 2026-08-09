# Run record

- 日期时间：2026-08-09（迁移登记；原运行时间未记录）
- 执行目录：原 `process/legacy-package/q3`，现迁入 `process/q3/routes/r02-random-forest`
- 执行命令：`python code/random_forest_question3.py`（依据 legacy README；本次迁移未重新执行）
- 代码入口/版本：`code/random_forest_question3.py`；source commit `669f848`
- 输入文件：q2 历史运行的 `daily_flux_series.csv` 与 `abrupt_change_events.csv`
- 关键参数：见 `validation/rf_model_settings.csv`
- 随机种子：见 `validation/rf_model_settings.csv`；迁移过程不重新采样
- 环境/依赖：历史环境未完整记录；代码依赖 Python、NumPy、pandas、Pillow
- 结果文件：`results/data/processed/rf_predicted_daily_flux_2022_2023.csv`、`results/tables/*.csv`
- 图表文件：`figures/rf-forecast-monthly-flux.png`、`figures/rf-sampling-monthly-counts.png`
- 验证文件：`validation/rf_forecast_validation.csv`、`validation/rf_feature_importance.csv`、`validation/rf_model_settings.csv`
- 是否成功完成：partial
- 异常与备注：legacy 结果已导入但未在规范路径复现；当前仅保留为历史对照候选。
