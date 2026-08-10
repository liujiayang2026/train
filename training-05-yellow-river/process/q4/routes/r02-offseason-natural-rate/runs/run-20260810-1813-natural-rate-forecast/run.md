# Run record

- 日期时间：2026-08-10 18:13（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r02-offseason-natural-rate/code/forecast_no_regulation_natural_rate.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r02-offseason-natural-rate/runs/run-20260810-1813-natural-rate-forecast`
- 代码入口/版本：`code/forecast_no_regulation_natural_rate.py`；执行前SHA-256 `888b2d56be8505b1e77819b1b9469ebf87fa81eb56b8d6d33c4f22413f803ff8`
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`
- 关键参数：PCHIP主拟合、线性敏感性；5 m网格；主范围1725—2050 m；主槽2005—2040 m；自然率区间为2020-07-29→2021-04-16（261天）和2021-07-22→2022-04-18（270天）；验证为2022-07-23→2023-02-26（218天）；预测为2023-02-26→2033-02-26（3653天）。
- 随机种子：不适用（确定性计算）
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；SciPy 1.13.1；Matplotlib 3.10.9
- 结果文件：`results/` 的自然率、逐年预测、2033断面、汇总及附件1/2背景表。
- 图表文件：`figures/` 的自然率、独立验证和2033预测图。
- 验证文件：`validation/` 的218天独立验证和7项质量检查。
- 是否成功完成：partial
- 异常与备注：计算成功且7/7质量检查通过，首轮结果为净冲刷主导。但结果表把目标区误命名为1725—2050 m；由于2023基准断面从1818 m开始，实际严格共同5 m网格是1820—2050 m。首轮分析结尾也只写了“若净淤积”的解释，未明确本次实际为净冲刷及长期外推风险。数值证据保留，范围标签和解释由后续run修正。
