# Run record

- 日期时间：2026-08-17 16:06 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\code\run_targeted_refinement.py --output training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1606-square-region-multifidelity --r03-run training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1444-surrogate-nsga2-final-ray --seed 202308 --final-samples 256 --neighbor-radius 70`
- 代码入口/版本：`code/run_targeted_refinement.py`、`code/shifted_hex_model.py`；SHA-256 记录于 `validation/code_hashes.json`。
- 输入文件：r03 正式结果；r05 前序运行的真实光线误差诊断。
- 关键参数：塔 `y=-55/-60 m`；宽 `6.15/6.20/6.25/6.30 m`；高宽差 `0/0.05/0.10/0.15 m`；32 个代表时点候选、前 6 个完整年 64 光线、前 2 个 128 光线、低贡献删镜、最终 256 光线。
- 随机种子：202308
- 环境/依赖：Codex bundled Python 3.12；共享 NumPy、SciPy、Matplotlib、openpyxl。
- 结果文件：候选筛选、64/128 光线复核、删镜比较、最终年/月/时点指标、单镜指标、镜位和收敛数据均位于 `results/`；汇总见 `results/result_tables.md`。
- 图表文件：`figures/fig01-targeted-candidates.png` 至 `figures/fig04-r03-r05-comparison.png`。
- 验证文件：`validation/checks.json`、`validation/code_hashes.json`。
- 是否成功完成：yes
- 异常与备注：最终方案为塔 `(0,-60)`、镜面 `6.3 x 6.3 m`、中心高度 `3.15 m`、净距 `0.05 m`、3168 面。低贡献删镜在 64 光线下使功率跌破 `60.10 MW` 安全线，故不采用；局部移动无满足约束且改善代理贡献的可接受动作。正式 256 光线结果为 `60.40797 MW / 0.480428 kW/m2`。
