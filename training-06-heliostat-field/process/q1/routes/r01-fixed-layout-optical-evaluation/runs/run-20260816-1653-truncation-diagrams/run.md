# Run record

- 日期时间：2026-08-16 16:53（Asia/Shanghai）
- 执行目录：D:\jianmo\train
- 执行命令：设置 MPLBACKEND=Agg，将 D:\jianmo\project 2\B\shared\python-packages 加入 PYTHONPATH，再由 Codex bundled Python 执行 process/q1/routes/r01-fixed-layout-optical-evaluation/code/draw_truncation_diagrams.py --output-dir process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1653-truncation-diagrams/figures
- 代码入口/版本：process/q1/routes/r01-fixed-layout-optical-evaluation/code/draw_truncation_diagrams.py；SHA-256 D67D9E9044A0044DF5778AB8B87E8D14644F7F123BFC29340A23CE4C3EBBA4B6
- 输入文件：无外部数据；采用问题一圆柱集热器半径 3.5 m、高度范围 76–84 m，以及既定光线方向符号
- 关键参数：输出分辨率 180 dpi；太阳角扩散在第一张图中为便于观察而夸张；第三张图使用 100、85、68 条示意射线
- 随机种子：不适用
- 环境/依赖：Codex bundled Python；共享包目录中的 Matplotlib 3.11.1、NumPy；Agg 无界面后端；Windows 中文字体
- 结果文件：无数值结果，仅生成数学原理图
- 图表文件：figures/fig01-flat-mirror-footprint-overflow.png；figures/fig02-ray-cylinder-intersection.png；figures/fig03-conditional-truncation-efficiency.png
- 验证文件：validation/image-check.txt
- 是否成功完成：yes
- 异常与备注：所有效率数值均为教学示意，不是附件镜场的计算结果。
