# Run record

- 日期时间：2026-08-10 17:14（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/evaluate_multiyear_regulation_effect.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1714-multiyear-final-layout`
- 代码入口/版本：`code/evaluate_multiyear_regulation_effect.py`；执行前SHA-256 `c03d99d0ea07c4538100e28e24a9678c6e594126e0a8989a72a05c316334b2f9`
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`
- 关键参数：PCHIP主拟合；分段线性敏感性；5 m数值网格；内部稳健区1725—2050 m；主槽2005—2040 m；A级双窗口；2018仅在实际共同覆盖1965—2050 m计算并显式标注不可直接比较面积大小。
- 随机种子：不适用（确定性计算）
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；SciPy 1.13.1；Matplotlib 3.10.9
- 结果文件：`results/` 的多年双窗口河床、水沙、流速和目标达成矩阵。
- 图表文件：`figures/` 的3张图，均已视觉复核，布局清晰。
- 验证文件：`validation/` 的跨附件校验、PCHIP—线性敏感性和质量检查。
- 是否成功完成：partial
- 异常与备注：数值计算和图面均成功，7/7质量检查通过；2018覆盖范围和A级双窗口已正确表达。最终数据质量复核发现“含沙观测日覆盖100%”仍可能掩盖同一天内含沙量记录少于流量记录的事实，因此本run的河床、流速和累计过沙数值仍有效，但水沙质量说明由后续run增加日内采样率后取代。
