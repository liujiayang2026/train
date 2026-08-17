# Run record

- 日期时间：2026-08-17 14:33 +08:00
- 执行目录：`D:\jianmo\train`
- 执行命令：`$env:PYTHONPATH="D:\jianmo\project 2\B\shared\python-packages"; & $py training-06-heliostat-field\process\q2\routes\r02-close-packed-staggered-rings\code\screen_close_packed.py --output training-06-heliostat-field\process\q2\routes\r02-close-packed-staggered-rings\runs\run-20260817-1433-paired-ring-feasibility-screen --samples 16 --seed 202308`
- 代码入口/版本：`code/screen_close_packed.py`、修复后的 `code/hex_layout_model.py`，复用 r01 `q2_model.py`。
- 输入文件：题面几何与效率参数；上一失败运行的冲突筛选诊断。
- 关键参数：45 个设计；相邻两环共享镜数并半步交错；宽高 6.2--7.8 m；塔 y=-80/-100/-120 m；径向比 0.82/sqrt(3)/2/0.92；16 光线；12 时点初筛和前 6 名全年复算；邻镜半径 65 m。
- 随机种子：202308。
- 环境/依赖：Codex bundled Python 3.12；NumPy、SciPy、openpyxl。
- 结果文件：`results/reduced_close_packed_screen.csv`、`results/full_year_close_packed_screen.csv`。
- 图表文件：不适用。
- 验证文件：距离检查字段写入 CSV。
- 是否成功完成：no
- 异常与备注：执行正式光线筛选前先做几何预检；即使两环共享镜数，环组过渡处的角频率冲突仍使 7 m 布局从 2785 个边界内候选降到 1505 面，故未继续运行昂贵光线筛选。该极坐标拍频问题属于模型结构缺陷，后续转入 r03 的解析六角交错点阵。
