# Run record

- 日期时间：2026-08-09（迁移登记；原运行时间未记录）
- 执行目录：原 `process/legacy-package/question-3`，现迁入 `process/q3/routes/r01-historical-ensemble`
- 执行命令：`python code/analyze_question3.py`（依据 legacy README；本次迁移未重新执行）
- 代码入口/版本：`code/analyze_question3.py`；source commit `669f848`
- 输入文件：q2 历史日尺度水沙通量及相关分析结果
- 关键参数：见 `notes/question3-method.md` 与 `validation/model_settings.csv`
- 随机种子：不适用；legacy 记录未声明随机采样
- 环境/依赖：历史环境未完整记录；代码依赖 Python、NumPy、pandas、Pillow
- 结果文件：`results/data/processed/predicted_daily_flux_2022_2023.csv`、`results/tables/*.csv`
- 图表文件：`figures/*.png`
- 验证文件：`validation/*.csv`
- 是否成功完成：partial
- 异常与备注：仅迁移 `main` 中已有输出和验证证据；迁移本身未重新运行，也不代表采用该路线。
