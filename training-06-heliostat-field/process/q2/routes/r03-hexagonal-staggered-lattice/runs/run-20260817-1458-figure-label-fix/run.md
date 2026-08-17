# Run record

- 日期时间：2026-08-17 14:58 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\train\.codex-runtime\pymoo-deps;D:\jianmo\project 2\B\shared\python-packages"; & $py training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\code\render_final_figures.py --source-run training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1444-surrogate-nsga2-final-ray --output training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1458-figure-label-fix --q1-annual training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\runs\run-20260816-1812-sobol-512-convergence\results\annual_metrics.csv`
- 代码入口/版本：`code/render_final_figures.py`；调用修复单位标签后的绘图函数。
- 输入文件：`run-20260817-1444-surrogate-nsga2-final-ray/results/` 全部数值结果；问题一年平均结果。
- 关键参数：只把缺字的上标单位改为 ASCII `kW/m2` 和 `10^3 m2`；不改变数据、坐标、图形编码或结论。
- 随机种子：不适用。
- 环境/依赖：Codex bundled Python 3.12；NumPy、Matplotlib。
- 结果文件：不适用。
- 图表文件：`figures/fig01-...png` 至 `figures/fig07-...png`。
- 验证文件：`validation/image-check.json`。
- 是否成功完成：partial
- 异常与备注：正式数值仍由 1444 run 所有；本 run 仅修复 PNG 字体兼容性，不覆盖原图。
