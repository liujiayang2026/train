# Run record

- 日期时间：2026-08-17 14:35 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & $py training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\code\screen_hex_lattice.py --output training-06-heliostat-field\process\q2\routes\r03-hexagonal-staggered-lattice\runs\run-20260817-1435-hex-lattice-feasibility-screen --samples 16 --seed 202308`
- 代码入口/版本：`code/screen_hex_lattice.py`、`code/lattice_model.py`，复用 r01 `q2_model.py`。
- 输入文件：题面约束；r01/r02 的不可行或低密度诊断。
- 关键参数：48 个六角点阵设计；宽 6.0--8.0 m；高为宽或宽减 0.6 m；塔 y=-60/-80/-100/-120 m；净距 0；16 光线；12 时点初筛和前 8 名全年复算；邻镜半径 70 m。
- 随机种子：202308。
- 环境/依赖：Codex bundled Python 3.12；NumPy、SciPy、openpyxl。
- 结果文件：`results/reduced_hex_screen.csv`、`results/full_year_hex_screen.csv`。
- 图表文件：不适用。
- 验证文件：距离、场界和禁建区检查字段写入 CSV。
- 是否成功完成：yes
- 异常与备注：48 个初筛和前 8 名全年复算全部完成。6.8 m 方镜在塔 y=-60/-80 m 时分别达到 61.8554/61.7548 MW；6.8 x 6.2 m 在 y=-80 m 时为 59.7260 MW、单位面积 0.4805 kW/m2，证明最优可行高度位于约 6.2--6.8 m 之间。
