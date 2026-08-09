# Run record

- 日期时间：2026-08-09（迁移登记；原运行时间未记录）
- 执行目录：原process/legacy-package/question-1，现迁入process/q1/routes/r01-log-linear-sediment
- 执行命令：python code/analyze_question1.py（历史README记录；本次迁移未重新执行）
- 代码入口/版本：code/analyze_question1.py；source commit 669f848
- 输入文件：source/attachments/附件1.xlsx
- 关键参数：详见notes/question1-method.md和validation/model_validation.csv
- 随机种子：不适用，线性模型为确定性算法
- 环境/依赖：历史环境未完整记录；代码依赖Python、NumPy、pandas、openpyxl
- 结果文件：results/data/processed/cleaned_hydro_timeseries.csv；results/tables/*.csv
- 图表文件：不适用，导入材料未包含图表
- 验证文件：validation/model_validation.csv；validation/relationship_diagnostics.csv
- 是否成功完成：partial
- 异常与备注：机器结果已完整导入并由git mv保留历史；迁移后尚未在新目录复现，旧代码的输出路径仍按历史布局编写。
