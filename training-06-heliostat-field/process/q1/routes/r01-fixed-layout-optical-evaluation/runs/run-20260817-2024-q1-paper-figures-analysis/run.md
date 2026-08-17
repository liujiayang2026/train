# Run record

- 日期时间：2026-08-17 20:24
- 执行目录：`F:\train-hxk`
- 执行命令：`python training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/code/export_q1_paper_figures.py --input training-06-heliostat-field/source/attachments/附件.xlsx --monthly-results training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1812-sobol-512-convergence/results/monthly_metrics.csv --annual-results training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1812-sobol-512-convergence/results/annual_metrics.csv --run-dir training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260817-2024-q1-paper-figures-analysis`
- 代码入口/版本：`code/export_q1_paper_figures.py`；该入口调用现有三套物理校验绘图代码重新生成图形，再统一导出无审阅页眉的论文版 PNG；代码 SHA-256 由 `validation/paper-figure-checks.json` 记录。
- 输入文件：`source/attachments/附件.xlsx`；512 射线最终 run 的 `monthly_metrics.csv` 与 `annual_metrics.csv`。
- 关键参数：白色论文背景；去除审阅大标题、副标题、右上角内部编号和底部审阅说明；保留面板标题、坐标、图例、公式、物理标注及真实结果；PNG 写入 300 dpi 元数据。
- 随机种子：沿用代表镜联合采样的 Sobol seed 202308；不重新计算问题一正式数值结果。
- 环境/依赖：Python 3.12；`numpy`、`openpyxl`、`matplotlib`、`Pillow`。
- 结果文件：待生成 `results/paper-figure-usage.md` 与结果分析更新说明。
- 图表文件：待生成 `figures/` 下八张 `*-paper.png`。
- 验证文件：待生成 `validation/paper-figure-checks.json` 与视觉检查记录。
- 是否成功完成：no
- 异常与备注：首次原尺寸视觉检查发现三张拆分图的上裁切线仍保留审阅副标题，汇总图中的 `field` 下标也未采用正体。该 run 保留为失败证据，不进入正文；修正见后续 `run-20260817-2030-q1-paper-figures-crop-fix`。本 run 未改变模型、采样参数或正式 CSV 数值。
