# Run record

- 日期时间：2026-08-17 15:14
- 执行目录：`F:\train-hxk`
- 执行命令：`python training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/code/draw_q1_narrative_figures.py --input training-06-heliostat-field/source/attachments/附件.xlsx --monthly-results training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1812-sobol-512-convergence/results/monthly_metrics.csv --annual-results training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1812-sobol-512-convergence/results/annual_metrics.csv --run-dir training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260817-1514-q1-narrative-figures`
- 代码入口/版本：`code/draw_q1_narrative_figures.py`；执行后在 `validation/geometry-checks.json` 记录 SHA-256。
- 输入文件：`source/attachments/附件.xlsx`；512 射线最终 run 的 `monthly_metrics.csv` 与 `annual_metrics.csv`。
- 关键参数：代表案例为 1 月 21 日 9:00、第 1660 面镜；联合 Sobol 样本数 512；扰码种子 202308；邻镜半径 45 m；太阳角半径 0.266 度。
- 随机种子：202308，仅用于复现与正式结果一致的扰码 Sobol 联合样本。
- 环境/依赖：Python 3.12；`numpy`、`scipy`、`openpyxl`、`matplotlib`。
- 结果文件：`results/design-philosophy.md`。
- 图表文件：`figures/fig01-q1-narrative-flow.png`、`figures/fig02-field-to-neighbor-scale.png`、`figures/fig03-shadow-vs-blocking-physical.png`、`figures/fig04-real-joint-sampling.png`、`figures/fig05-monthly-results-story.png`。
- 验证文件：`validation/geometry-checks.json`、`validation/image-check.txt`。
- 是否成功完成：yes
- 异常与备注：本 run 已成功生成并校验待用户审阅的候选论文图；候选图尚未被采用，不替换既有图，也不改变问题一数值结果。五张图已通过原尺寸人工检查和独立视觉检查；反射方向误差为 `3.33e-16`，阴影共线误差为 `2.22e-16`，详见 `validation/geometry-checks.json` 与 `validation/image-check.txt`。
