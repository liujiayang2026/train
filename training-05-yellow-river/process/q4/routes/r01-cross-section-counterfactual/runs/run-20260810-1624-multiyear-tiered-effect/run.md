# Run record

- 日期时间：2026-08-10 16:24（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/evaluate_multiyear_regulation_effect.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1624-multiyear-tiered-effect`
- 代码入口/版本：`code/evaluate_multiyear_regulation_effect.py`；执行前SHA-256 `15d2745ebafb8f24d39ab63862342284d64b53b90ee4735ea0a601883a1964a7`
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`
- 关键参数：PCHIP主拟合；分段线性敏感性；5 m数值网格；内部稳健区1725—2050 m；主槽2005—2040 m；附件1水沙窗口为每年6月1日至7月31日；2019-04-13（附件2）与2019-04-17（附件3）作跨附件加性偏差校验；校准后RMSE 1 m为2018数值证据可接受规则。
- 随机种子：不适用（确定性计算）
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；SciPy 1.13.1；Matplotlib 3.10.9
- 结果文件：`results/` 的多年河床汇总、5 m网格、水沙汇总与日序列、流速汇总、目标达成矩阵和分析说明。
- 图表文件：`figures/cross_attachment_calibration.png`、`multiyear_bed_change.png`、`multiyear_effect_summary.png`。
- 验证文件：`validation/` 的跨附件校验、PCHIP—线性敏感性和质量检查。
- 是否成功完成：partial
- 异常与备注：程序成功且6/6质量检查通过；2019近同期跨附件校准后RMSE为0.109 m，2018通过预设1 m规则；7个年度内部稳健区的PCHIP与线性净冲淤方向100%一致。但复核目标矩阵时发现只使用“4月→7月末”会掩盖2022年7月首末测次间−169.9 m²强冲刷，使2022被过度简化为“减淤未显示”。本run数值有效但综合判定不采用，由新增7月事件内部双窗口的后续run取代。
