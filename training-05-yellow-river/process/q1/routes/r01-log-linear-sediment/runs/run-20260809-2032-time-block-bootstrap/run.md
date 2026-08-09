# Run record

- 日期时间：2026-08-09 20:32 +08:00
- 执行目录：`training-05-yellow-river/`
- 执行命令：`python process/q1/routes/r01-log-linear-sediment/code/analyze_question1.py --input source/attachments/附件1.xlsx --run-dir process/q1/routes/r01-log-linear-sediment/runs/run-20260809-2032-time-block-bootstrap --bootstrap-replicates 500 --seed 20260809 --canonical-block-hours 72 --block-sensitivity-hours 24 72 168`
- 代码入口/版本：`process/q1/routes/r01-log-linear-sediment/code/analyze_question1.py`；执行前 SHA-256 `5FFF269A3B18904AF448E53E3D7682A85C6CC3DE5C6B0AC4E1235EFCAAB72DF1`
- 输入文件：`source/attachments/附件1.xlsx`
- 关键参数：四模型按留一年平均 `RMSE_log` 选择本次补全模型；标准预测截尾为实测含沙量 `0.5×q0.001` 至 `1.5×q0.999`；年度积分采用梯形法；每种块长500次、随机种子20260809；72小时为事先指定主块长，同时比较24/72/168小时。
- 自助口径：系数pairs bootstrap与log残差路径均按年份在真实时间轴上抽取不跨年、非循环的连续移动块；不逐行独立重采样。残差块按块内相对时间最近邻映射到缺失时刻。
- 实现说明：与失败的2013 run统计口径相同；预先缓存源/目标块时间几何和年度梯形积分权重。单元测试已核对缓存积分与参考积分等价。
- 随机种子：20260809
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；openpyxl 3.1.5
- 结果文件：`results/data/cleaned_hydro_timeseries.csv`、`results/tables/annual_flux_estimates.csv`、`results/tables/monthly_relationship_summary.csv`、`results/analysis.md`
- 图表文件：不适用
- 验证文件：`validation/model_validation.csv`、`relationship_diagnostics.csv`、`annual_flux_holdout_validation.csv`、`annual_sensitivity_scenarios.csv`、`annual_sensitivity_summary.csv`、`bootstrap_annual_draws.csv`、`annual_sediment_uncertainty.csv`、`bootstrap_block_sensitivity_draws.csv`、`bootstrap_block_length_sensitivity.csv`、`bootstrap_time_block_diagnostics.csv`、`quality_checks.csv`、`validation_summary.md`
- 是否成功完成：yes
- 异常与备注：运行记录先于执行建立。实际运行约38.4秒，13/13质量检查通过。24/72/168小时各生成500×6条年度抽样；72小时主口径的相对半宽为5.93%-22.51%，基准点仅落入2/6个经验百分位区间，且长块区间更宽，说明块长与抽样口径敏感。1941与失败的2013 run均保持不变。该区间只属于当前模型内的经验不确定性证据，不是完整真实误差置信区间，也不是覆盖率验证。
