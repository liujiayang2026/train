# Run record

- 日期时间：2026-08-17 19:25 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" training-06-heliostat-field\process\q2\routes\r06-zoned-low-power-relayout\code\run_zoned_relayout.py --baseline-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1606-square-region-multifidelity --spatial-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1726-spatial-power-zones-v2 --output training-06-heliostat-field\process\q2\routes\r06-zoned-low-power-relayout\runs\run-20260817-1925-constrained-unit-area-search --mode full --strategy zoned-absolute --samples 256 --seed 202308 --neighbor-radius 70`
- 代码入口/版本：`code/run_zoned_relayout.py`；代码哈希写入 `validation/code_hashes.json`。
- 输入文件：r05 正式镜位和设计参数；r05 的 11 个低功率分区、逐镜 256 光线年平均功率。
- 关键参数：30 个分区绝对旋转候选；直接删除最低贡献 `0/5/10/15/20/25/30` 面镜作为对照；12 时点 16 光线初筛、完整年 64/128 光线复筛、256 光线最终确认。
- 随机种子：202308。
- 环境/依赖：Codex bundled Python 3.12；共享 NumPy、SciPy 和 Matplotlib。
- 结果文件：计划生成各精度候选表、最终年/月/时点指标、最终镜位和逐镜指标。
- 图表文件：计划生成 r05/r06 镜位与单位面积功率对比图。
- 验证文件：计划生成 `validation/checks.json` 和 `validation/code_hashes.json`。
- 是否成功完成：yes
- 异常与备注：候选排序遵循 `年平均功率≥60 MW` 约束下最大化单位面积功率，不以镜数最多为目标。最终选择删除 30 面最低贡献镜面的方案，得到 `60.071002 MW / 0.482315 kW/m2`；满足题目约束，但未达到内部 `60.10 MW` 安全线。局部旋转重排候选虽然单位面积代理值较高，但完整年功率未达到 60 MW。
