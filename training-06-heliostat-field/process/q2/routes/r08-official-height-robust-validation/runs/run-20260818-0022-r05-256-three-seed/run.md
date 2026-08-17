# Run record

- 日期时间：2026-08-18 00:22 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-06-heliostat-field\process\q2\routes\r08-official-height-robust-validation\code\validate_existing_design.py --design-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1606-square-region-multifidelity --output training-06-heliostat-field\process\q2\routes\r08-official-height-robust-validation\runs\run-20260818-0022-r05-256-three-seed --samples 256 --seeds 202308 202309 202310 --neighbor-radius 70`
- 代码入口/版本：`code/validate_existing_design.py`；完成后记录入口与 q2 评价器 SHA-256。
- 输入文件：r05 正式 `design.json` 与 `final_positions.csv`。
- 关键参数：60 个题定时点；每镜每时点 256 个四维 Sobol 联合样本；完整阴影遮挡并集与有限圆柱截断；邻镜半径 70 m。
- 随机种子：202308、202309、202310。
- 环境/依赖：Python 3.12；NumPy 1.26.4；SciPy 1.13.1；Matplotlib。
- 结果文件：已生成三个种子的逐时点指标、`seed_metrics.csv` 和 `summary.json`。
- 图表文件：已生成 `figures/seed-power-validation.png`。
- 验证文件：已生成 `validation/checks.json` 和 `validation/code_hashes.json`。
- 是否成功完成：yes
- 异常与备注：三个 256 光线种子的年平均功率依次为 `60.40797`、`60.54009`、`60.39715 MW`；均值 `60.44840 MW`，样本标准差 `0.07959 MW`，最小种子值 `60.39715 MW`，`mean-2sd=60.28923 MW`。所有种子与保守下界均满足 60 MW，r05 的功率可行性得到高精度稳健确认。
