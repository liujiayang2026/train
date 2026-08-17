# Run record

- 日期时间：2026-08-17 14:44 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\train\.codex-runtime\pymoo-deps;D:\jianmo\project 2\B\shared\python-packages"; & $py training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\code\optimize_hex_lattice.py --output training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1444-surrogate-nsga2-final-ray --screen-run training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1435-hex-lattice-feasibility-screen --q1-annual training-06-heliostat-field\process\q1\routes\r01-fixed-layout-optical-evaluation\runs\run-20260816-1812-sobol-512-convergence\results\annual_metrics.csv --seed 202308 --population 56 --generations 40 --final-samples 256`
- 代码入口/版本：`code/optimize_hex_lattice.py`、`code/lattice_model.py`，复用 r01 `q2_model.py` 的光线评价器和通用结果图函数。
- 输入文件：r03 可行性筛选 CSV；问题一 512 样本年平均结果；题面参数；`result2.xlsx` 模板。
- 关键参数：新增 12 个 16 光线全年训练设计；RBF 代理留一法验证；NSGA-II 种群 56、40 代；代理功率约束 60.3 MW；真实 32 光线候选复核；正式 256 光线结果；邻镜半径 70 m。
- 随机种子：202308。
- 环境/依赖：Codex bundled Python 3.12；临时 `pymoo==0.6.1.5`、NumPy 2.5.2；共享 SciPy/Matplotlib/openpyxl。
- 结果文件：设计、镜位、训练集、Pareto、时点/月度/年度指标、收敛数据、结果表和工作簿数据均位于 `results/`。
- 图表文件：`figures/fig01-...png` 至 `figures/fig07-...png`。
- 验证文件：`validation/checks.json` 及后续工作簿验证文件。
- 是否成功完成：partial
- 异常与备注：最终解不由代理单独确定；NSGA-II 候选与真实训练集优选点共同接受 32 光线复核。
