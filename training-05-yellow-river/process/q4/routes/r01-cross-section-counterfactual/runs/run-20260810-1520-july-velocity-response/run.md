# Run record

- 日期时间：2026-08-10 15:20（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/analyze_july_velocity_response.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1520-july-velocity-response`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/analyze_july_velocity_response.py`；执行前SHA-256 `AA296F86E59F18473D8679D3B58F46F8BF74BF0035FBB033731BF75F31F5E208`。
- 输入文件：只读使用 `source/attachments/附件1.xlsx` 和 `附件3.xlsx`；河床PCHIP口径继承 `d03-adopt-pchip.md`。
- 关键参数：同日期同横向站点先求垂线算术平均流速；断面流速按代表宽度×总水深作面积加权；主槽2005—2040 m仅报告实际有效垂线；比较4月基线、7月各测次和7月首末测次。
- 随机种子：不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；SciPy 1.13.1；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：计划生成原始有效流速点、垂线平均流速、测次断面汇总、流速—主槽冲淤比较表。
- 图表文件：计划生成流速时间线、横向流速分布、流速—河床变化汇总及附件1流量对齐共4张图。
- 验证文件：计划检查19期流速测次、三年7月覆盖、面积加权数值、测点模式、主槽观测和附件1对齐。
- 是否成功完成：partial
- 异常与备注：附件1没有2022年；主槽每期通常只有1条有效垂线，因此主槽局部流速只作点位证据，不称为完整主槽面积平均。
