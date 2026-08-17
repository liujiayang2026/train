# Run record

- 日期时间：2026-08-17 14:18 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\train\.codex-runtime\pymoo-deps;D:\jianmo\project 2\B\shared\python-packages"; & $py training-06-heliostat-field\process\q2\routes\r01-common-size-field-optimization\code\optimize_common_size.py --output training-06-heliostat-field\process\q2\routes\r01-common-size-field-optimization\runs\run-20260817-1418-q2-nsga2-feasible-seeds --q1-input training-06-heliostat-field\source\attachments\附件.xlsx --q1-annual training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\runs\run-20260816-1812-sobol-512-convergence\results\annual_metrics.csv --seed 202308 --population 56 --generations 36 --final-samples 256`
- 代码入口/版本：`code/optimize_common_size.py` 与 `code/q2_model.py`；执行结束后由 `validation/checks.json` 记录 SHA-256。
- 输入文件：题面、问题一坐标与 512 样本年平均结果、`result2.xlsx` 模板。
- 关键参数：NSGA-II 种群 56、代数 36；初始种群含 9 个已预筛可行锚点，其余为固定种子随机样本；代理硬约束 60 MW；候选选择安全线 60.4 MW；差分进化精修；最终 Sobol 样本 256；邻镜半径 55 m。
- 随机种子：202308
- 环境/依赖：Codex bundled Python 3.12；共享数值包；临时 `.codex-runtime/pymoo-deps` 中 `pymoo==0.6.1.5` 及依赖。
- 结果文件：预计位于 `results/`，包括设计、镜位、效率、Pareto、代理校验、收敛与结果表。
- 图表文件：预计 `figures/fig01-...png` 至 `figures/fig07-...png`。
- 验证文件：预计 `validation/checks.json`、工作簿检查与预览。
- 是否成功完成：no
- 异常与备注：可行锚点生效，第一代已出现严格可行解；第二代开始时 `pymoo 0.6.1.5` 调用 NumPy 2.5 已移除的 `np.row_stack`，触发兼容性异常。下一 run 将临时运行环境固定到 `numpy==1.26.4`，模型和优化参数不变。
