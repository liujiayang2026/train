# Run record

- 日期时间：2026-08-10 14:22（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/compare_cross_section_methods.py --input training-05-yellow-river/source/attachments/附件2.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1422-cross-section-method-comparison --grid-step-m 5`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/compare_cross_section_methods.py`；执行前 SHA-256 `A7A56761C65EA00C5E03E9C4DA78B307605DD8E34949EB29C588EA1806910AB5`。
- 输入文件：`training-05-yellow-river/source/attachments/附件2.xlsx`，只读。
- 关键参数：共同覆盖区0—4583 m；5 m计算网格；候选方法为分段线性、PCHIP、GCV自动平滑样条、Matérn-3/2高斯过程；空间验证将内部测点组成连续3点块并轮换分配到5折，首末端点始终保留。
- 随机种子：20260810（高斯过程）；其余方法不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；SciPy 1.13.1；scikit-learn 1.7.1；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：计划写入 `results/fitted_common_grid.csv`、`fit_diagnostics.csv`、`gp_uncertainty.csv`。
- 图表文件：计划写入 `figures/method_fit_facets.png`、`method_cv_performance.png`、`method_cv_error_distribution.png`、`method_difference_from_linear.png`、`deep_channel_method_comparison.png`。
- 验证文件：计划写入 `validation/blocked_cv_predictions.csv`、`blocked_cv_summary.csv`、`blocked_cv_by_survey.csv`、`quality_checks.csv`。
- 是否成功完成：yes
- 异常与备注：5/5质量检查通过，四种方法均完成9期完整拟合和连续空间块验证，无拟合失败；5张图已视觉复核。分面图保留共同区外的黑色实测点以显示部分早期断面覆盖至6153 m，而四条拟合曲线只画到严格共同区4583 m。机器比较与分区诊断见 `results/analysis.md`。本次不进行时间预测，也不把天然深槽解释为调水调沙效果；5 m为数值网格而非实测分辨率。
