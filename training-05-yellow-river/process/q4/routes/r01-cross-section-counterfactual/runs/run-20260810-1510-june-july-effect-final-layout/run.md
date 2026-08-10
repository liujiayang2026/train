# Run record

- 日期时间：2026-08-10 15:10（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/visualize_june_july_effect_pchip.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1510-june-july-effect-final-layout --grid-step-m 5`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/visualize_june_july_effect_pchip.py`；执行前SHA-256 `96B8C438CF1B6E771D89538799F05960BE3950EAFBEC5F2E8B0A20D7C5ECE22B`。
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`。
- 关键参数：与1507 run相同；修正无淤积/无冲刷年份的方向极值语义，并微调汇总图标题。
- 随机种子：不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；SciPy 1.13.1；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：完整共同区和1725—2050 m内部稳健区双口径冲淤摘要，以及三附件派生表。
- 图表文件：年度前后断面、内部区热图、双窗口冲淤汇总、测次标注水沙过程及附件2背景共5张图。
- 验证文件：测次覆盖、数值有限性、网格步长和三附件读取检查。
- 是否成功完成：yes
- 异常与备注：5张图已逐张视觉检查，6/6质量检查通过。结果解释见 `results/analysis.md`。附件1无2022年，附件2的2019年前后测次包含8—10月变化，均已在图题和解释中降级处理。
