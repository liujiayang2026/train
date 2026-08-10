# Run record

- 日期时间：2026-08-10 15:07（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/visualize_june_july_effect_pchip.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1507-june-july-effect-core --grid-step-m 5`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/visualize_june_july_effect_pchip.py`；执行前SHA-256 `E009AE49678A8D6FD1848592DE329D6B753A0AD6C34D07EF5AAD6361FB07282C`。
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`。
- 关键参数：PCHIP主拟合；5 m计算网格；年度窗口与1501 run相同；新增1725—2050 m内部稳健区，并同时展示4月至7月末和7月首末两个窗口。
- 随机种子：不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；SciPy 1.13.1；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：计划生成完整共同区和内部稳健区双口径冲淤摘要，以及三附件派生表。
- 图表文件：计划生成边界标记后的年度断面、内部区热图、双窗口冲淤汇总、测次标注水沙过程及附件2背景共5张图。
- 验证文件：计划写入测次覆盖、数值有限性、网格步长和三附件读取检查。
- 是否成功完成：partial
- 异常与备注：这是1501 run的边界稳健性与图面修正版；1501 run不覆盖也不删除。
