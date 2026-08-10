# Run record

- 日期时间：2026-08-10 12:19（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/visualize_attachment2.py --input training-05-yellow-river/source/attachments/附件2.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1219-attachment2-figure-layout --grid-step-m 5`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/visualize_attachment2.py`；执行前 SHA-256 `3C46A5563CBC4C5E0AEA3EAA1D72AAA3C8BF9E0F0DEE289220F07644CE2F467F`。相对1217成功版本仅调整相邻测次变化图的标题、图例和边距。
- 输入文件：`training-05-yellow-river/source/attachments/附件2.xlsx`，只读；本次只探索附件2。
- 关键参数：共同覆盖区取全部9期原始距离范围的严格交集；线性插值网格步长5 m；插值不超出各期原始覆盖范围。
- 随机种子：不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：计划写入 `results/attachment2_long.csv`、`attachment2_common_grid.csv`、`survey_summary.csv`、`consecutive_change_summary.csv`。
- 图表文件：计划写入 `figures/attachment2_all_cross_sections.png`、`attachment2_cross_section_facets.png`、`attachment2_common_domain_overlay.png`、`attachment2_bed_elevation_heatmap.png`、`attachment2_consecutive_bed_changes.png`。
- 验证文件：计划写入 `validation/visualization_checks.csv`。
- 是否成功完成：yes
- 异常与备注：本次是图面布局修复运行；5张图均已人工视觉复核，标题、坐标、中文字体和图例正常。4个结果CSV和1个验证CSV的SHA-256与1217成功运行完全一致，说明布局调整未改变数值。变化图正值表示后期河底更高、负值表示后期河底更低，不构成调水调沙因果结论。探索性观察见 `results/analysis.md`。
