# Run record

- 日期时间：2026-08-10 15:28（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/analyze_july_velocity_response.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1528-july-velocity-layout`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/analyze_july_velocity_response.py`；执行前SHA-256 `07B9C8BB6ABC8474618DB6CD6E6278B51627A13759EC4AE10B822FDFA1667C36`。
- 输入文件：只读使用 `source/attachments/附件1.xlsx` 和 `附件3.xlsx`。
- 关键参数：与1520 run相同；本run只修正密集测次数字标注和日期刻度重叠。
- 随机种子：不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；SciPy 1.13.1；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：有效流速点、垂线平均流速、测次断面汇总、流速—主槽冲淤比较表。
- 图表文件：流速时间线、横向流速分布、流速—河床变化汇总及附件1流量对齐共4张图。
- 验证文件：19期流速测次、三年7月覆盖、面积加权数值、测点模式、主槽观测和附件1对齐检查。
- 是否成功完成：partial
- 异常与备注：作为当前流速分析图面交付候选，待执行和视觉核验。
