# Run record

- 日期时间：2026-08-16 16:34（Asia/Shanghai）
- 执行目录：`D:\jianmo\train`
- 执行命令：设置 `MPLBACKEND=Agg`，将 `D:\jianmo\project 2\B\shared\python-packages` 加入 `PYTHONPATH`，再由 Codex bundled Python 执行 `process/q1/routes/r01-fixed-layout-optical-evaluation/code/draw_shadow_blocking_diagrams.py --output-dir process/q1/routes/r01-fixed-layout-optical-evaluation/runs/run-20260816-1634-shadow-blocking-diagrams/figures`
- 代码入口/版本：`process/q1/routes/r01-fixed-layout-optical-evaluation/code/draw_shadow_blocking_diagrams.py`；SHA-256 `BA31356D2D48FAE353883C5402C496BDEE27367779129F3DC65E7A34E2828743`
- 输入文件：无外部数据；使用问题一的 6 m x 6 m 镜面尺寸与既定方向符号
- 关键参数：输出分辨率 180 dpi；采样统计示意采用 20 x 20 分层网格
- 随机种子：不适用
- 环境/依赖：Codex bundled Python；共享包目录中的 Matplotlib 3.11.1、NumPy；`Agg` 无界面后端；Windows 中文字体
- 结果文件：无数值结果，仅生成数学原理图
- 图表文件：`figures/fig01-shadow-vs-blocking-paths.png`；`figures/fig02-ray-plane-intersection.png`；`figures/fig03-sampling-and-union-efficiency.png`
- 验证文件：`validation/image-check.txt`
- 是否成功完成：yes
- 异常与备注：Codex bundled Python 默认环境不含 Matplotlib，运行时复用了本机共享包目录。第三张图中的分类区域和效率数值仅为教学示意，不是附件镜场的计算结果。
