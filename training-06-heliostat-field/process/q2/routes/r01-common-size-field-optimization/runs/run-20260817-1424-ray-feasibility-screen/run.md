# Run record

- 日期时间：2026-08-17 14:24 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\train\.codex-runtime\pymoo-deps;D:\jianmo\project 2\B\shared\python-packages"; & $py training-06-heliostat-field\process\q2\routes\r01-common-size-field-optimization\code\screen_ray_designs.py --output training-06-heliostat-field\process\q2\routes\r01-common-size-field-optimization\runs\run-20260817-1424-ray-feasibility-screen --samples 16 --seed 202308`
- 代码入口/版本：`code/screen_ray_designs.py`，调用 `code/q2_model.py`。
- 输入文件：题面几何约束和同路线锥形光束评价模型。
- 关键参数：17 个代表性设计；宽高 5.4--8.0 m；塔 y 坐标 -100/-140 m；附加净距 0/1.5 m；先用 12 个季节代表时点筛选，再对前 5 名计算全部 60 时点；每镜每时点 16 条 Sobol 光线。
- 随机种子：202308（代表性筛选按设计编号偏移种子，全年复算统一种子）。
- 环境/依赖：Codex bundled Python 3.12；NumPy、SciPy、openpyxl。
- 结果文件：`results/reduced_ray_screen.csv`、`results/full_year_ray_screen.csv`。
- 图表文件：不适用，本 run 为数值诊断。
- 验证文件：后续补充筛选结论。
- 是否成功完成：no
- 异常与备注：完成前 5 个代表设计后，在 7.4 m 镜面处保守邻镜半径下界为 55.086 m，超过配置值 55 m，评价器主动中止以避免漏算遮挡。下一 run 将邻镜半径提高到 65 m 后重跑。
