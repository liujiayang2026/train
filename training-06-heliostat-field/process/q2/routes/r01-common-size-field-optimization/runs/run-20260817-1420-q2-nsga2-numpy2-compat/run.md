# Run record

- 日期时间：2026-08-17 14:20 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\train\.codex-runtime\pymoo-deps;D:\jianmo\project 2\B\shared\python-packages"; & $py training-06-heliostat-field\process\q2\routes\r01-common-size-field-optimization\code\optimize_common_size.py --output training-06-heliostat-field\process\q2\routes\r01-common-size-field-optimization\runs\run-20260817-1420-q2-nsga2-numpy2-compat --q1-input training-06-heliostat-field\source\attachments\附件.xlsx --q1-annual training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\runs\run-20260816-1812-sobol-512-convergence\results\annual_metrics.csv --seed 202308 --population 56 --generations 36 --final-samples 256`
- 代码入口/版本：`code/optimize_common_size.py` 与 `code/q2_model.py`；执行结束后由 `validation/checks.json` 记录 SHA-256。
- 输入文件：题面、问题一坐标与 512 样本年平均结果、`result2.xlsx` 模板。
- 关键参数：NSGA-II 种群 56、代数 36；9 个可行锚点；代理约束 60 MW；候选安全线 60.4 MW；差分进化精修；最终 Sobol 样本 256；邻镜半径 55 m。
- 随机种子：202308
- 环境/依赖：Codex bundled Python 3.12；临时环境 `pymoo==0.6.1.5`、`numpy==2.5.2`、SciPy 1.18；入口提供 `np.row_stack=np.vstack` 等价兼容别名。
- 结果文件：预计位于 `results/`。
- 图表文件：预计 `figures/fig01-...png` 至 `figures/fig07-...png`。
- 验证文件：预计 `validation/checks.json`、工作簿检查与预览。
- 是否成功完成：no
- 异常与备注：NSGA-II 与差分进化已成功完成，选出代理功率 60.4218 MW、3161 面的候选；32 光线全时点预检仅为 52.208 MW，说明代理模型严重低估高密度场的阴影遮挡损失。外环已覆盖场区，增加 `r_max` 不再增加镜数，第四次重复预检后人工终止。下一 run 用低样本真实光线筛选尺寸、间距和塔位可行区间。
