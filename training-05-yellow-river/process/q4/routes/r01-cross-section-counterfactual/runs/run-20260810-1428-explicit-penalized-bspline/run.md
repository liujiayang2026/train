# Run record

- 日期时间：2026-08-10 14:28（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/compare_cross_section_methods.py --input training-05-yellow-river/source/attachments/附件2.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1428-explicit-penalized-bspline --grid-step-m 5`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/compare_cross_section_methods.py`；执行前 SHA-256 `0D2CFEF375D155B8542E705F2AA4A7FE7F0F4DBAD1FAB4FBB28A72EA6E19A3C0`。
- 输入文件：`training-05-yellow-river/source/attachments/附件2.xlsx`，只读。
- 关键参数：共同覆盖区0—4583 m；5 m计算网格；候选方法为分段线性、PCHIP、显式惩罚B样条、GCV全局平滑样条、Matérn-3/2高斯过程。P-spline使用三次B样条、10—28个分位数节点、B样条系数二阶差分惩罚，候选惩罚强度为 `10^-4` 至 `10^4` 共9档；每个外层连续空间块留出折只用其训练子集执行4折内层区块验证选参。
- 随机种子：20260810（高斯过程）；其余方法不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；SciPy 1.13.1；scikit-learn 1.7.1；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：计划写入 `results/fitted_common_grid.csv`、`fit_diagnostics.csv`、`gp_uncertainty.csv`。
- 图表文件：计划写入5张方法拟合、验证和差异图。
- 验证文件：计划写入空间区块预测、总体/逐期摘要和质量检查；`selected_penalty` 记录每个P-spline外层折及完整拟合的选定惩罚强度。
- 是否成功完成：yes
- 异常与备注：5/5质量检查通过，5种方法各完成1210个区块留出预测，无拟合失败，5张图已视觉复核。本run补上真正的显式惩罚B样条并保留GCV全局平滑样条以避免概念混淆；P-spline的嵌套选参与误差结论见 `results/analysis.md`。当前实现尚未加入分段单调或深槽位置硬约束，因此准确名称是“全断面惩罚B样条”，不是“分区约束B样条”。
