# Run record

- 日期时间：2026-08-17 20:35
- 执行目录：`F:\train-hxk`
- 执行命令：`python training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/code/export_q1_paper_figures.py --input training-06-heliostat-field/source/attachments/附件.xlsx --monthly-results training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1812-sobol-512-convergence/results/monthly_metrics.csv --annual-results training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1812-sobol-512-convergence/results/annual_metrics.csv --run-dir training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260817-2035-q1-paper-figures-final`
- 代码入口/版本：`code/export_q1_paper_figures.py`；三张拆分图采用已修正的裁切范围和正体功率符号，邻镜域图去除底部审阅说明，阴影/遮挡公式使用数学下标，物理光路图由绘图层直接生成无页眉论文布局；代码 SHA-256 由 `validation/paper-figure-checks.json` 记录。
- 输入文件：`source/attachments/附件.xlsx`；512 射线最终 run 的 `monthly_metrics.csv` 与 `annual_metrics.csv`。
- 关键参数：白色论文背景；去除审阅大标题、副标题、右上角内部编号和底部审阅说明；保留面板标题、坐标、图例、公式、物理标注及真实结果；PNG 写入 300 dpi 元数据。
- 随机种子：沿用代表镜联合采样的 Sobol seed 202308；不重新计算问题一正式数值结果。
- 环境/依赖：Python 3.12；`numpy`、`openpyxl`、`matplotlib`、`Pillow`。
- 结果文件：`results/paper-figure-usage.md`、`results/analysis-update.md`。
- 图表文件：`figures/` 下八张 `*-paper.png`。
- 验证文件：`validation/paper-figure-checks.json`、`validation/visual-check.md`。
- 是否成功完成：yes
- 异常与备注：八张论文版图均通过原尺寸人工检查；无审阅页眉、裁断文字、公式字面下划线或图文重叠。本 run 只改变论文叙述、功率符号和图形版式，不改变模型、采样参数或正式 CSV 数值。
