# Run record

- 日期时间：2026-08-17 15:34 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\code\run_shifted_hex_experiment.py --output training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1534-focused-search --r03-run training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1444-surrogate-nsga2-final-ray --seed 202308 --random-designs 120 --screen-samples 16 --verify-samples 32 --final-samples 256 --neighbor-radius 70`
- 代码入口/版本：`code/run_shifted_hex_experiment.py`、`code/shifted_hex_model.py`；执行后记录 SHA-256。
- 输入文件：r01 锥形光线评价器；r03 正式 256 光线结果和镜位；题面几何约束。
- 关键参数：安全净距 0.05 m；重点尺寸范围约 `W=6.15--6.45 m`、`H=W-(0.25--0.50) m`；塔 `y=-40--75 m`；旋转角和基本单元二维偏移；多精度真实光线复核。
- 随机种子：202308
- 环境/依赖：Codex bundled Python 3.12；共享 NumPy、SciPy、Matplotlib、openpyxl。
- 结果文件：`results/proxy_screen.csv`、`results/reduced_ray_screen.csv`；进程在完整结果写出前停止。
- 图表文件：未生成。
- 验证文件：`validation/early-stop-summary.json`。
- 是否成功完成：no
- 异常与备注：代理排序先按单位面积功率选择，导致 12 个代表时点候选的完整年估计仅为 57.6--58.5 MW。前两个 32 光线完整年复核分别为 `58.807 MW / 0.5149 kW/m2` 和 `58.856 MW / 0.5170 kW/m2`，确认效率高但功率缺口过大，故人工终止。下一运行把代理功率作为第一排序键。
