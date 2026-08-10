# Run record

- 日期时间：2026-08-10 12:17（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/visualize_attachment2.py --input training-05-yellow-river/source/attachments/附件2.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1217-attachment2-visualization-fix --grid-step-m 5`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/visualize_attachment2.py`；执行前 SHA-256 `AFD83BE4808518B8B4BD5C42190FD1C24A313412E2FACAE7D72D96F5BAC752DF`。相对1214失败版本仅将NumPy 2.x的 `np.trapezoid` 改为兼容NumPy 1.26.4的 `np.trapz`。
- 输入文件：`training-05-yellow-river/source/attachments/附件2.xlsx`，只读；本次只探索附件2，不把附件3坐标强行拼接进图。
- 关键参数：共同覆盖区取全部9期原始距离范围的严格交集；线性插值网格步长5 m；插值不超出各期原始覆盖范围。
- 随机种子：不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：计划写入 `results/attachment2_long.csv`、`attachment2_common_grid.csv`、`survey_summary.csv`、`consecutive_change_summary.csv`。
- 图表文件：计划写入 `figures/attachment2_all_cross_sections.png`、`attachment2_cross_section_facets.png`、`attachment2_common_domain_overlay.png`、`attachment2_bed_elevation_heatmap.png`、`attachment2_consecutive_bed_changes.png`。
- 验证文件：计划写入 `validation/visualization_checks.csv`。
- 是否成功完成：yes
- 异常与备注：数值输出和5张图片均成功生成，完整性检查通过。视觉复核发现 `attachment2_consecutive_bed_changes.png` 的总标题与图例重叠，因此该图不作为交付图，后续仅调整布局的新run取代其图面版本；其余图和全部数值结果有效。相邻测次变化仍只是共同覆盖区上的探索性线性插值结果，尚不构成调水调沙因果结论。
