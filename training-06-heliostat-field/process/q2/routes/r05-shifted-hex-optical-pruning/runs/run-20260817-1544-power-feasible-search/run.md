# Run record

- 日期时间：2026-08-17 15:44 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\code\run_shifted_hex_experiment.py --output training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1544-power-feasible-search --r03-run training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1444-surrogate-nsga2-final-ray --seed 202308 --random-designs 120 --screen-samples 16 --verify-samples 32 --final-samples 256 --neighbor-radius 70`
- 代码入口/版本：`code/run_shifted_hex_experiment.py`、`code/shifted_hex_model.py`；代理候选改为功率优先排序。
- 输入文件：同前一运行。
- 关键参数：同前一运行；首先选择代理功率最高的 12 个候选，再在真实光线可行候选中最大化单位面积功率。
- 随机种子：202308
- 环境/依赖：Codex bundled Python 3.12；共享 NumPy、SciPy、Matplotlib、openpyxl。
- 结果文件：`results/proxy_screen.csv`、`results/reduced_ray_screen.csv`；进程在完整结果写出前停止。
- 图表文件：未生成。
- 验证文件：`validation/early-stop-summary.json`。
- 是否成功完成：no
- 异常与备注：功率优先的 12 个代表时点候选估计为 58.2--59.46 MW，但代码要求估计值先达到 59.8 MW；由于该估计相对完整年复核系统性偏低，候选集为空后错误回退到单位效率排序。完成的首个 32 光线候选为 `59.528 MW / 0.5060 kW/m2`。下一运行取消预门槛，直接按估计功率排序。
