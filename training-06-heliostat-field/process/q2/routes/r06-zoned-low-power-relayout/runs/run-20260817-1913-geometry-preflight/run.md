# Run record

- 日期时间：2026-08-17 19:13 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" training-06-heliostat-field\process\q2\routes\r06-zoned-low-power-relayout\code\run_zoned_relayout.py --baseline-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1606-square-region-multifidelity --spatial-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1726-spatial-power-zones-v2 --output training-06-heliostat-field\process\q2\routes\r06-zoned-low-power-relayout\runs\run-20260817-1913-geometry-preflight --mode geometry --seed 202308`
- 代码入口/版本：`code/run_zoned_relayout.py`；代码哈希写入 `validation/code_hashes.json`。
- 输入文件：r05 正式镜位和设计参数；r05 空间功率分析识别的 11 个低功率分区。
- 关键参数：过渡带宽度 `11.35/17.025/22.70 m`；局部旋转角 `0/5/10/15/20/25/30°`；二维相位各取 `0/0.25/0.5/0.75`；共 336 组参数。
- 随机种子：202308；纯几何预筛阶段不使用随机数。
- 环境/依赖：Codex bundled Python 3.12；共享 NumPy、SciPy 和 Matplotlib。
- 结果文件：计划生成 `results/geometry_candidates.csv` 和 `results/selected_for_ray_screen.csv`。
- 图表文件：计划生成 `figures/fig01-geometry-candidate-counts.png`。
- 验证文件：计划生成 `validation/checks.json` 和 `validation/code_hashes.json`。
- 是否成功完成：yes
- 异常与备注：336 组候选全部满足几何约束，但非零旋转的最优候选仍减少 148 面镜，说明多个低功率区共享同一相位的拼接损失过大；下一运行改为每区独立选择相位。
