# Run record

- 日期时间：2026-08-16 18:10
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH='D:\jianmo\project 2\B\shared\python-packages'; & 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\code\evaluate_fixed_layout.py' --input 'training-06-heliostat-field\source\attachments\附件.xlsx' --output 'training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\runs\run-20260816-1810-sobol-256-agg-fix' --samples 256 --seed 202308 --neighbor-radius 45`
- 代码入口/版本：`code/evaluate_fixed_layout.py`；在绘图函数中固定使用 Matplotlib `Agg` 后端；执行完成后由 `validation/checks.json` 记录 SHA-256。
- 输入文件：`source/attachments/附件.xlsx`
- 关键参数：每面镜每时刻 256 条四维扰码 Sobol 联合射线；太阳角半径 0.266 度；邻镜搜索半径 45 m；圆柱侧壁半径 3.5 m、高度 76--84 m；反射率 0.92。
- 随机种子：202308（仅用于 Sobol 扰码，可复现）
- 环境/依赖：Codex bundled Python；共享 `numpy 2.5.1`、`scipy 1.18.0`、`openpyxl`、`matplotlib 3.11.1`；无界面 `Agg` 绘图后端。
- 结果文件：`results/time_metrics.csv`、`results/mirror_time_metrics.csv`、`results/monthly_metrics.csv`、`results/annual_metrics.csv`、`results/result_summary.md`。
- 图表文件：`figures/monthly_performance.png`。
- 验证文件：`validation/checks.json`。
- 是否成功完成：yes
- 异常与备注：运行成功，退出码为 0。60 个评价时刻和 104700 个镜时记录齐全；最大几何必要邻镜半径为 35.6891 m，小于配置的 45 m。该运行作为 256 射线收敛基准，最终结果由后续 512 射线运行确认。
