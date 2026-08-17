# Run record

- 日期时间：2026-08-18 01:23 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\code\export_q2_paper_figures.py --r05-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1606-square-region-multifidelity --spatial-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1726-spatial-power-zones-v2 --robust-run training-06-heliostat-field\process\q2\routes\r08-official-height-robust-validation\runs\run-20260818-0022-r05-256-three-seed --output training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260818-0123-q2-paper-figures`
- 代码入口/版本：`code/export_q2_paper_figures.py`；完成后在 `validation/paper-figure-checks.json` 记录代码和输入/输出 SHA-256。
- 输入文件：r05 正式设计、镜位、月度指标和光线收敛表；r05 逐镜 256 光线功率；r08 三种子 256 光线稳健性结果。
- 关键参数：白色论文背景；中文标题、坐标和图例；300 dpi PNG；功率统一使用 MW，单位面积功率统一使用 kW/m²；稳定性局部纵轴；不使用 r07 探索结果作为最终结论。
- 随机种子：不重新计算；读取 r05 seed 202308 和 r08 seeds 202308、202309、202310 的既有正式结果。
- 环境/依赖：Python 3.12；NumPy；Matplotlib；Pillow。
- 结果文件：已生成论文图用途说明和量纲/数据一致性摘要。
- 图表文件：已生成六张首轮论文版 PNG。
- 验证文件：已生成图片尺寸、哈希、功率守恒、稳定性和最低边缘高度检查。
- 是否成功完成：no
- 异常与备注：数值与图像检查通过，但视觉审阅发现 `candidate-selection-paper.png` 将 64 光线筛选候选与 256 光线正式结果置于同一横轴，容易把采样精度变化误读成设计改进；删镜面板使用双纵轴且曲线视觉交叉。该 run 作为首轮审阅证据保留，修订版另建 `run-20260818-0129-q2-paper-figures-final`，不覆盖本 run。
