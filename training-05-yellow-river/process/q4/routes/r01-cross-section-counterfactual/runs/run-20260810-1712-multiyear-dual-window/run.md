# Run record

- 日期时间：2026-08-10 17:12（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/evaluate_multiyear_regulation_effect.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1712-multiyear-dual-window`
- 代码入口/版本：`code/evaluate_multiyear_regulation_effect.py`；执行前SHA-256 `701fbbb9d1e4021eaf86ed96986ad99586af23582790238de0a0ae37e98cb334`
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`
- 关键参数：PCHIP主拟合；分段线性敏感性；5 m数值网格；内部稳健区1725—2050 m；主槽2005—2040 m；附件1窗口为每年6月1日至7月31日；2019近同期跨附件校准；A级年份同时评价4月→7月末累计窗口与7月首测→末测事件内部窗口。
- 随机种子：不适用（确定性计算）
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；SciPy 1.13.1；Matplotlib 3.10.9
- 结果文件：`results/` 的多年双窗口河床、水沙、流速和目标达成矩阵。
- 图表文件：`figures/` 的跨附件校验、多年河床变化和综合指标图。
- 验证文件：`validation/` 的跨附件校验、PCHIP—线性敏感性和质量检查。
- 是否成功完成：partial
- 异常与备注：数值计算成功且7/7质量检查通过，已正确恢复2022年7月首末净冲刷−169.9 m²及“部分达成”结论。视觉复核发现多年河床图总标题与图例重叠；进一步发现2018年所谓内部稳健区结果实际只覆盖1965—2050 m，不能与其余年份325 m宽度的面积直接比较。数值证据保留，图面和2018限制表述由后续run修正。
