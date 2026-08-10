# Run record

- 日期时间：2026-08-10 15:01（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/visualize_june_july_effect_pchip.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1501-june-july-effect-pchip --grid-step-m 5`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/visualize_june_july_effect_pchip.py`；执行前SHA-256 `595F24C0B877B25155829128E7B33D19BD6C444BBA661B6C72870D94C5608756`。
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`。
- 关键参数：PCHIP主拟合；5 m计算网格；附件3年度窗口为2020-04-17至07-29、2021-04-16至07-22、2022-04-18至07-23；另计算各年7月首末测次；附件2以2019-04-13至10-15作为全断面背景。
- 随机种子：不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；SciPy 1.13.1；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：计划生成附件1日水沙序列、附件3 PCHIP前后网格与冲淤摘要、附件2全断面背景网格。
- 图表文件：计划生成年度前后断面、变化热图、冲淤面积汇总、水沙过程与测次、附件2全断面背景共5张图。
- 验证文件：计划写入测次覆盖、数值有限性、网格步长和三附件读取检查。
- 是否成功完成：partial
- 异常与备注：本run评价描述性前后效果，不把所有变化直接认定为严格因果调水调沙效应；附件1无2022年数据。
