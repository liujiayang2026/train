# Run record

- 日期时间：2026-08-10 17:16（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/evaluate_multiyear_regulation_effect.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1716-multiyear-final-evidence`
- 代码入口/版本：`code/evaluate_multiyear_regulation_effect.py`；执行前SHA-256 `81f19344fae3da253f4caf786c1f90a1df7dbca8c0c518b37de12a73fd18b2b4`
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`
- 关键参数：PCHIP主拟合；线性敏感性；5 m数值网格；A级双窗口；B/C级宽窗口；2018实际共同覆盖1965—2050 m；6—7月水沙按日聚合，并同时报告逐日覆盖率与含沙量相对流量记录的日内采样率。
- 随机种子：不适用（确定性计算）
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；SciPy 1.13.1；Matplotlib 3.10.9
- 结果文件：`results/multiyear_bed_effect_summary.csv`、`july_event_bed_effect_summary.csv`、`multiyear_bed_change_grid.csv`、`june_july_hydrosediment_summary.csv`、`june_july_hydrosediment_daily.csv`、`attachment3_velocity_sections.csv`、`april_july_velocity_comparison.csv`、`target_achievement_matrix.csv`、`analysis.md`。
- 图表文件：`figures/cross_attachment_calibration.png`、`multiyear_bed_change.png`、`multiyear_effect_summary.png`；三张图均已视觉复核，标题、图例、中文字体和覆盖范围说明清晰。
- 验证文件：`validation/cross_attachment_calibration_summary.csv`、`cross_attachment_calibration_grid.csv`、`pchip_linear_sensitivity.csv`、`all_method_domain_metrics.csv`、`quality_checks.csv`。
- 是否成功完成：yes
- 异常与备注：7/7质量检查通过。2019近同期跨附件校准后RMSE为0.109 m；内部稳健区7个年度PCHIP与线性净冲淤方向100%一致。2018仅覆盖1965—2050 m，数值不可与其余年份完整325 m宽度直接比较。2022年4月→7月末累计净淤积+31.0 m²，但7月首末净冲刷−169.9 m²，因此评价为局部减淤目标部分达成。累计过沙量属于日均流量与日均含沙量的估计；含沙逐日覆盖100%，但日内记录采样率仅11.3%—16.7%。
