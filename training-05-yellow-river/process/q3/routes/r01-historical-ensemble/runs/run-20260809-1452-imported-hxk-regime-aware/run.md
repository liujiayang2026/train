# Run record

- 日期时间：2026-08-09 14:52 Asia/Shanghai（依据源提交时间）
- 执行目录：原 `process/legacy-package/question-3`；现迁入 `process/q3/routes/r01-historical-ensemble`
- 执行命令：`python code/regime_aware_question3.py`（依据代码入口推定；原终端命令未记录）
- 代码入口/版本：`code/regime_aware_question3.py`；source commit `31453e5`
- 输入文件：问题二历史日尺度水沙通量及 legacy 第三问基础脚本
- 关键参数：结构起点自动识别；`ridge_alpha=0.10`；`recent_shape_weight=0.60`；2019—2021 年滚动验证
- 随机种子：不适用，算法为确定性计算
- 环境/依赖：历史环境未完整记录；代码依赖 Python、NumPy、pandas、Pillow
- 结果文件：`results/data/processed/predicted_daily_flux_2022_2023.csv`；`results/tables/*.csv`
- 图表文件：`figures/*.png`
- 验证文件：`validation/*.csv`
- 是否成功完成：partial
- 异常与备注：本记录由 hxk 分支历史提交迁移建立，21 个结果文件在迁移前后经 SHA-256 逐一核对一致；迁移本身未重新执行，也不代表采用该路线。
