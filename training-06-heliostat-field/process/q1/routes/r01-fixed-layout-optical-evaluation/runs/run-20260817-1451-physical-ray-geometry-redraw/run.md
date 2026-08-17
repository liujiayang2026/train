# Run record

- 日期时间：2026-08-17 14:51
- 执行目录：`F:\train-hxk`
- 执行命令：`python training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/code/draw_physical_ray_geometry.py --run-dir training-06-heliostat-field/process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260817-1451-physical-ray-geometry-redraw`
- 代码入口/版本：`code/draw_physical_ray_geometry.py`；执行后在 `validation/geometry-checks.json` 记录 SHA-256。
- 输入文件：无外部数据文件；使用问题一固定参数和脚本内声明的代表性侧视几何。
- 关键参数：太阳角半径 `0.266 deg`；镜面边长 `6 m`；镜面中心高 `4 m`；接收器中心高 `80 m`；接收器有效高度 `76--84 m`；主图水平距离 `340 m`。
- 随机种子：不适用；图形完全由确定性向量计算生成。
- 环境/依赖：Python 3.12；`numpy`、`matplotlib`。
- 结果文件：`results/design-philosophy.md`，记录本次重绘采用的视觉哲学。
- 图表文件：`figures/fig01-physical-ray-geometry.png`。
- 验证文件：`validation/geometry-checks.json`、`validation/image-check.txt`。
- 是否成功完成：yes
- 异常与备注：执行成功，退出码为 0。旧图保留不变；本 run 用于替代 `process/common/figures/fig02-side-ray-geometry.png` 的教学表达，不改变问题一数值模型。中心反射方向误差为 `5.55e-17`，太阳方向锥反射前后半角最大差为 `2.39e-14 rad`；21 条代表射线中 19 条命中侧壁、2 条从有限高度外溢出。
