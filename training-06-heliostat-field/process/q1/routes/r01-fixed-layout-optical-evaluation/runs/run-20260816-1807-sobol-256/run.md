# Run record

- 日期时间：2026-08-16 18:07
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH='D:\jianmo\project 2\B\shared\python-packages'; & 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\code\evaluate_fixed_layout.py' --input 'training-06-heliostat-field\source\attachments\附件.xlsx' --output 'training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\runs\run-20260816-1807-sobol-256' --samples 256 --seed 202308 --neighbor-radius 45`
- 代码入口/版本：`code/evaluate_fixed_layout.py`；执行完成后由 `validation/checks.json` 记录 SHA-256。
- 输入文件：`source/attachments/附件.xlsx`
- 关键参数：每面镜每时刻 256 条四维扰码 Sobol 联合射线；太阳角半径 0.266 度；邻镜搜索半径 45 m；圆柱侧壁半径 3.5 m、高度 76--84 m；反射率 0.92。
- 随机种子：202308（仅用于 Sobol 扰码，可复现）
- 环境/依赖：Codex bundled Python；共享 `numpy 2.5.1`、`scipy 1.18.0`、`openpyxl`、`matplotlib 3.11.1`。
- 结果文件：已写入 `results/time_metrics.csv`、`results/mirror_time_metrics.csv`、`results/monthly_metrics.csv`、`results/annual_metrics.csv`、`results/result_summary.md`，但因运行最终失败，仅作为未完成证据。
- 图表文件：未生成。
- 验证文件：未生成。
- 是否成功完成：no
- 异常与备注：全场数值循环完成后，Matplotlib 默认 Tk 后端因运行环境缺少 `init.tcl` 而失败；退出码为 1。保留本运行全部文件，不作为最终结果；后续代码改用无界面 `Agg` 后端并建立新运行。
