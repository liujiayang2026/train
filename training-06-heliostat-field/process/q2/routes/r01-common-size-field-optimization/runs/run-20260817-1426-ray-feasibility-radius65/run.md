# Run record

- 日期时间：2026-08-17 14:26 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\train\.codex-runtime\pymoo-deps;D:\jianmo\project 2\B\shared\python-packages"; & $py training-06-heliostat-field\process\q2\routes\r01-common-size-field-optimization\code\screen_ray_designs.py --output training-06-heliostat-field\process\q2\routes\r01-common-size-field-optimization\runs\run-20260817-1426-ray-feasibility-radius65 --samples 16 --seed 202308 --neighbor-radius 65`
- 代码入口/版本：`code/screen_ray_designs.py`，调用 `code/q2_model.py`。
- 输入文件：题面几何约束和同路线锥形光束评价模型。
- 关键参数：17 个代表设计；宽高 5.4--8.0 m；塔 y 坐标 -100/-140 m；附加净距 0/1.5 m；12 时点初筛和前 5 名 60 时点复算；16 条 Sobol 光线；邻镜半径 65 m。
- 随机种子：202308。
- 环境/依赖：Codex bundled Python 3.12；NumPy、SciPy、openpyxl。
- 结果文件：`results/reduced_ray_screen.csv`、`results/full_year_ray_screen.csv`。
- 图表文件：不适用。
- 验证文件：后续补充筛选结论。
- 是否成功完成：yes
- 异常与备注：17 个设计和前 5 名全年复算均完成。常规径向间距 `Delta r >= W+5` 的最高全年功率为 55.3545 MW（7 m 方镜、2471 面、121079 m2），未达到 60 MW；因此该保守布局不可行，后续转入 r02 的近六角密排交错环布局。
