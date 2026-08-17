# Run record

- 日期时间：2026-08-17 14:30 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & $py training-06-heliostat-field\process\q2\routes\r02-close-packed-staggered-rings\code\screen_close_packed.py --output training-06-heliostat-field\process\q2\routes\r02-close-packed-staggered-rings\runs\run-20260817-1430-close-packed-feasibility-screen --samples 16 --seed 202308`
- 代码入口/版本：`code/screen_close_packed.py`、`code/hex_layout_model.py`，复用 r01 的 `q2_model.py` 光线评价器。
- 输入文件：r01 真实光线不可行筛选结论；题面几何与效率参数。
- 关键参数：45 个近密排设计；宽高 6.2--7.8 m；塔 y=-80/-100/-120 m；径向比 0.82/sqrt(3)/2/0.92；16 光线；12 时点初筛与前 6 名 60 时点复算；邻镜半径 65 m。
- 随机种子：202308。
- 环境/依赖：Codex bundled Python 3.12；NumPy、SciPy、openpyxl。
- 结果文件：`results/reduced_close_packed_screen.csv`、`results/full_year_close_packed_screen.csv`。
- 图表文件：不适用。
- 验证文件：距离检查字段写入筛选 CSV。
- 是否成功完成：no
- 异常与备注：首版每环独立取整镜数，造成相邻环角步长不同，精确距离筛选剔除过多镜面，代表布局仅剩约 1500--1800 面；在第 13/45 个初筛设计后人工终止。下一 run 改为相邻两环共享镜数、组内半步交错，只在环组过渡处调整镜数。
