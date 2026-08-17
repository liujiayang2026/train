# Run record

- 日期时间：2026-08-17 17:19 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\code\analyze_spatial_power.py --input-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1606-square-region-multifidelity --output-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1719-spatial-power-zones --samples 256 --seed 202308 --neighbor-radius 70 --radial-bins 5 --sector-count 12`
- 代码入口/版本：`code/analyze_spatial_power.py`；运行后在 `validation/code_hashes.json` 记录代码哈希。
- 输入文件：r05 正式运行的 `results/design.json` 与 `results/final_positions.csv`；光学模型沿用 `r01/code/q2_model.py`。
- 分区参数：场地圆心极坐标；5 个 70 m 环带；12 个 30° 扇区；共 60 个区域。
- 光线参数：每镜每时点 256 条四维 Sobol 联合光线；60 个评价时点；随机种子 202308；邻域半径 70 m。
- 关键参数：最终塔位 `(0,-60) m`、镜面 `6.3 x 6.3 m`、3168 面；5 个径向环带、12 个方位扇区；低功率阈值取有效分区后 25%。
- 随机种子：202308。
- 环境/依赖：Codex bundled Python 3.12；共享 NumPy、SciPy 和 Matplotlib。
- 低功率定义：镜数不少于 10 且区域单镜年平均功率位于全部有效分区后 25%。
- 预期结果：逐镜功率、分区指标、低功率区清单、3 张 PNG 和功率守恒验证。
- 是否成功完成：no
- 结果文件：`results/mirror_power.csv`、`results/zone_metrics.csv`、`results/low_power_zones.csv` 和 `results/spatial_power_summary.md`。
- 图表文件：`figures/fig01-mirror-power-map.png`、`figures/fig02-zone-power-heatmap.png` 和 `figures/fig03-low-power-zones.png`。
- 验证文件：`validation/checks.json` 和 `validation/code_hashes.json`。
- 异常与备注：数值结果与功率守恒验证均完成，但视觉检查发现分区图内圈标注拥挤、排序图图例遮挡条形；该运行保留为可复现的部分结果，修正后的正式图见后续 `run-20260817-1726-spatial-power-zones-v2/`。
