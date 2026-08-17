# Run record

- 日期时间：2026-08-18 01:32 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\code\export_q2_paper_figures.py --r05-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1606-square-region-multifidelity --spatial-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1726-spatial-power-zones-v2 --robust-run training-06-heliostat-field\process\q2\routes\r08-official-height-robust-validation\runs\run-20260818-0022-r05-256-three-seed --output training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260818-0132-q2-paper-figures-final-fix`
- 代码入口/版本：`code/export_q2_paper_figures.py`；完成后由 `validation/paper-figure-checks.json` 记录 SHA-256。
- 输入文件：同前两轮论文图 run，读取 r05 正式结果、逐镜功率和 r08 三种子验证。
- 关键参数：候选图只比较同为 64 光线的设计；删镜图首尾橙色标签朝绘图区内侧放置；对数横轴使用固定刻度及标签；稳健性图例位于绘图区右侧；PNG 为 RGB、白底、300 dpi。
- 随机种子：不重新计算；沿用输入 run。
- 环境/依赖：Python 3.12；NumPy；SciPy；Matplotlib；Pillow。
- 结果文件：`results/paper-figure-usage.md`；`results/paper-result-summary.md`。
- 图表文件：`figures/layout-and-spacing-paper.png`；`figures/candidate-selection-paper.png`；`figures/monthly-performance-paper.png`；`figures/spatial-power-paper.png`；`figures/ray-convergence-paper.png`；`figures/robustness-paper.png`。
- 验证文件：`validation/paper-figure-checks.json`；`validation/visual-check.md`。
- 是否成功完成：yes
- 异常与备注：运行无警告。六张图均经逐张视觉审阅；第二轮图中的首尾数值裁切和固定刻度警告已消除。正式数值仍来自既有 r05/r08 输入，本 run 未重新计算光学结果。
