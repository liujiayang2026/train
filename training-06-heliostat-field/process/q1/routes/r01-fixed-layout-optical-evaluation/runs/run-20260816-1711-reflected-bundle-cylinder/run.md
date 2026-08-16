# Run record

- 日期时间：2026-08-16 17:11（Asia/Shanghai）
- 执行目录：D:\jianmo\train
- 执行命令：设置 MPLBACKEND=Agg，将 D:\jianmo\project 2\B\shared\python-packages 加入 PYTHONPATH，再由 Codex bundled Python 执行 process/q1/routes/r01-fixed-layout-optical-evaluation/code/draw_reflected_bundle_to_cylinder.py --output-dir process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1711-reflected-bundle-cylinder/figures
- 代码入口/版本：process/q1/routes/r01-fixed-layout-optical-evaluation/code/draw_reflected_bundle_to_cylinder.py；SHA-256 90B559309CE97D34D64F64C4D7B1C15FA399BACBED18D5A449014953A12760FB
- 输入文件：无外部数据；采用问题一镜面尺寸、圆柱集热器半径 3.5 m 和高度范围 76–84 m
- 关键参数：输出分辨率 190 dpi；太阳锥角和空间距离在示意图中按比例夸张以保证可读性
- 随机种子：不适用
- 环境/依赖：Codex bundled Python；共享包目录中的 Matplotlib 3.11.1、NumPy；Agg 无界面后端；Windows 中文字体
- 结果文件：无数值结果，仅生成数学原理图
- 图表文件：figures/fig01-reflected-bundle-to-cylinder-process.png
- 验证文件：validation/image-check.txt
- 是否成功完成：yes
- 异常与备注：图中的射线位置用于说明命中与截断判定，不是附件镜场的计算结果。
