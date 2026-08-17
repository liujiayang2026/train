# Run record

- 日期时间：2026-08-17 15:56 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\code\run_targeted_refinement.py --output training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1556-targeted-real-ray-refinement --r03-run training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1444-surrogate-nsga2-final-ray --seed 202308 --final-samples 256 --neighbor-radius 70`
- 代码入口/版本：`code/run_targeted_refinement.py`、`code/shifted_hex_model.py`；执行后记录 SHA-256。
- 输入文件：r03 正式结果；前三次 r05 运行定位出的高效率边界参数。
- 关键参数：16 个定向候选；代表时点 16 光线；前 8 个执行完整年 32 光线；前 3 个执行 64 光线；低贡献删镜；最终 32/64/128/256 光线收敛。
- 随机种子：202308
- 环境/依赖：Codex bundled Python 3.12；共享 NumPy、SciPy、Matplotlib、openpyxl。
- 结果文件：`results/reduced_screen.csv`、`results/full32_candidates.csv`；进程在完整结果写出前停止。
- 图表文件：未生成。
- 验证文件：`validation/early-stop-summary.json`。
- 是否成功完成：partial
- 异常与备注：32 光线下 `6.3 x 6.10 m` 达到 `60.316 MW / 0.4954 kW/m2`，但 64 光线降至 `59.393 MW / 0.4878 kW/m2`；另一平移候选 64 光线为 `59.430 MW / 0.4870 kW/m2`。确认先前 32 光线边界不稳健后停止，下一运行扩大到近方形镜面并直接采用 64/128 光线筛选。
