# Run record

- 日期时间：2026-08-16 18:12
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH='D:\jianmo\project 2\B\shared\python-packages'; & 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\code\evaluate_fixed_layout.py' --input 'training-06-heliostat-field\source\attachments\附件.xlsx' --output 'training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\runs\run-20260816-1812-sobol-512-convergence' --samples 512 --seed 202308 --neighbor-radius 45`
- 代码入口/版本：`code/evaluate_fixed_layout.py`；SHA-256 由 `validation/checks.json` 记录。
- 输入文件：`source/attachments/附件.xlsx`
- 关键参数：每面镜每时刻 512 条四维扰码 Sobol 联合射线；太阳角半径 0.266 度；邻镜搜索半径 45 m；圆柱侧壁半径 3.5 m、高度 76--84 m；反射率 0.92。
- 随机种子：202308（与 256 射线基准一致，Sobol 样本嵌套）
- 环境/依赖：Codex bundled Python；共享 `numpy 2.5.1`、`scipy 1.18.0`、`openpyxl`、`matplotlib 3.11.1`；无界面 `Agg` 绘图后端。
- 结果文件：`results/time_metrics.csv`、`results/mirror_time_metrics.csv`、`results/monthly_metrics.csv`、`results/annual_metrics.csv`、`results/result_summary.md`。
- 图表文件：`figures/monthly_performance.png`。
- 验证文件：`validation/checks.json`；收敛比较见 `process/q1/comparisons/compare-sobol-256-vs-512.md`。
- 是否成功完成：yes
- 异常与备注：运行成功，退出码为 0。年平均光学效率 0.57739865，年平均输出热功率 35.29638519 MW；相对 256 射线基准，年平均功率变化 0.0062%，采用本运行数值填入问题一结果表。
