# Run record

- 日期时间：2026-08-17 15:43
- 执行目录：`F:\train-hxk`
- 执行命令：`python training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/code/draw_q1_narrative_flow_split.py --input training-06-heliostat-field/source/attachments/附件.xlsx --monthly-results training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1812-sobol-512-convergence/results/monthly_metrics.csv --annual-results training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1812-sobol-512-convergence/results/annual_metrics.csv --run-dir training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260817-1543-q1-narrative-flow-split`
- 代码入口/版本：`code/draw_q1_narrative_flow_split.py`；执行后在 `validation/checks.json` 记录 SHA-256。
- 输入文件：`source/attachments/附件.xlsx`；512 射线最终 run 的 `monthly_metrics.csv` 与 `annual_metrics.csv`。
- 关键参数：将原六阶段总览拆为“评价对象与输入”“逐镜光学评价链”“汇总口径与表格对应”三张单义图；镜场坐标和结果数字均读取真实输入或正式结果文件。
- 随机种子：无。
- 环境/依赖：Python 3.12；`numpy`、`openpyxl`、`matplotlib`。
- 结果文件：`results/design-philosophy.md`、`results/paper-figure-usage.md`。
- 图表文件：`figures/scene-inputs.png`、`figures/per-mirror-optical-chain.png`、`figures/aggregation-to-tables.png`。
- 验证文件：`validation/checks.json`、`validation/image-check.txt`。
- 是否成功完成：no
- 异常与备注：`scene-inputs.png` 生成后，`per-mirror-optical-chain.png` 在渲染公式 `\mathbf n_i` 时触发 Matplotlib `ParseFatalException`，后续图和校验文件未生成。失败输出保留为证据；修复改为 `\mathbf{n}_i`，在新 run `run-20260817-1552-q1-narrative-flow-split-math-fix/` 重跑。
