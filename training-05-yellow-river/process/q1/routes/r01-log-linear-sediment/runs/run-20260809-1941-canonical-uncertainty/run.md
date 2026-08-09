# Run record

- 日期时间：2026-08-09 19:41（Asia/Shanghai）
- 执行目录：`F:\train\training-05-yellow-river`
- 执行命令：`python process/q1/routes/r01-log-linear-sediment/code/analyze_question1.py --input source/attachments/附件1.xlsx --run-dir process/q1/routes/r01-log-linear-sediment/runs/run-20260809-1941-canonical-uncertainty --bootstrap-replicates 500 --seed 20260809 --residual-block-observations 7`
- 代码入口/版本：`process/q1/routes/r01-log-linear-sediment/code/analyze_question1.py`；SHA-256 `B72092AD77C0A4FBB8662C60AC73EBD67420AF20D5AAA34510985E1A911A02EE`
- 输入文件：`source/attachments/附件1.xlsx`；SHA-256 `C645086935A70CF5EA279D5EC07DC272CC5C8A2F57DD3F9D06362F2DB7E7DA50`
- 关键参数：四个候选模型按留一年平均 `RMSE_log` 选择本次补全模型；标准预测截尾为实测含沙量 `0.5×q0.001` 至 `1.5×q0.999`；年度积分采用梯形法；自助法500次、按年份分层重采样、log残差块长7个实测记录。
- 随机种子：`20260809`
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；openpyxl 3.1.5
- 结果文件：`results/data/cleaned_hydro_timeseries.csv`、`results/tables/annual_flux_estimates.csv`、`results/tables/monthly_relationship_summary.csv`、`results/analysis.md`
- 图表文件：不适用
- 验证文件：`validation/model_validation.csv`、`validation/relationship_diagnostics.csv`、`validation/annual_flux_holdout_validation.csv`、`validation/annual_sensitivity_scenarios.csv`、`validation/annual_sensitivity_summary.csv`、`validation/bootstrap_annual_draws.csv`、`validation/annual_sediment_uncertainty.csv`、`validation/quality_checks.csv`、`validation/validation_summary.md`
- 日志文件：`logs/run_summary.txt`
- 是否成功完成：yes
- 异常与备注：10/10质量检查通过。年度水量/排沙量、月度汇总和四模型CV文件与迁移前对应机器结果逐字节一致；清洗明细沿用相同数值口径，但不再附加仅供月度分组使用的冗余 `month` 列。留一年稀疏观测网格年度输沙误差为 -12.49% 至 +53.27%，说明年度排沙不能只报告点估计。排除目标年份训练的完整年度结果相对基准变化为2.34%至6.22%；500次自助法区间相对半宽为7.49%至10.05%。四候选模型全场景最大变化可达40.72%，主要来自验证表现较差的替代模型；三种截尾设置在当前预测范围内未触发边界，结果不变。本次机器比较结果不构成人工 adopted 决定。
