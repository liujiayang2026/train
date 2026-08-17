# Run record

- 日期时间：2026-08-17 15:48 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\code\run_shifted_hex_experiment.py --output training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1548-direct-power-ranking --r03-run training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1444-surrogate-nsga2-final-ray --seed 202308 --random-designs 120 --screen-samples 16 --verify-samples 32 --final-samples 256 --neighbor-radius 70`
- 代码入口/版本：`code/run_shifted_hex_experiment.py`、`code/shifted_hex_model.py`；完整年候选直接按代表时点估计功率排序。
- 输入文件：同前两次运行。
- 关键参数：同前两次运行；取消失真的代表时点硬门槛。
- 随机种子：202308
- 环境/依赖：Codex bundled Python 3.12；共享 NumPy、SciPy、Matplotlib、openpyxl。
- 结果文件：`results/proxy_screen.csv`、`results/reduced_ray_screen.csv`、`results/full32_candidates.csv`。
- 图表文件：未生成。
- 验证文件：`validation/early-stop-summary.json`。
- 是否成功完成：partial
- 异常与备注：完成四个功率优先候选的 32 光线完整年复核，结果依次包括 `60.306/0.4900`、`60.241/0.4964`、`60.129/0.4980`、`60.053/0.4986`（MW 与 kW/m2）。程序原先用 60.25 MW 选局部起点，导致选中单位效率较低的第一项；在局部筛选阶段人工停止。后续改用独立的真实光线精修入口围绕后三项增加少量高度。
