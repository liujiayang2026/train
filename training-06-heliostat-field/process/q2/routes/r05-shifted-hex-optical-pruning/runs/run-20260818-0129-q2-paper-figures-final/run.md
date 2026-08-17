# Run record

- 日期时间：2026-08-18 01:29 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\code\export_q2_paper_figures.py --r05-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1606-square-region-multifidelity --spatial-run training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260817-1726-spatial-power-zones-v2 --robust-run training-06-heliostat-field\process\q2\routes\r08-official-height-robust-validation\runs\run-20260818-0022-r05-256-three-seed --output training-06-heliostat-field\process\q2\routes\r05-shifted-hex-optical-pruning\runs\run-20260818-0129-q2-paper-figures-final`
- 代码入口/版本：`code/export_q2_paper_figures.py`；完成后由 `validation/paper-figure-checks.json` 记录 SHA-256。
- 输入文件：同首轮论文图 run，读取 r05 正式结果、逐镜功率和 r08 三种子验证。
- 关键参数：候选图只比较同为 64 光线的设计；入选候选单独突出；删镜图使用单功率轴并以橙色数值标出单位面积功率；收敛横轴显示实际光线数；稳健性图例移至绘图区外；PNG 转换为 RGB、白底、300 dpi。
- 随机种子：不重新计算；沿用输入 run。
- 环境/依赖：Python 3.12；NumPy；SciPy；Matplotlib；Pillow。
- 结果文件：计划生成最终论文图用途说明和结果摘要。
- 图表文件：计划生成六张最终论文版 PNG。
- 验证文件：计划生成最终图片与数据一致性检查、视觉检查记录。
- 是否成功完成：no
- 异常与备注：本 run 修复了首轮视觉审阅发现的采样口径混排和双纵轴误导问题，但复核时发现删镜面板的橙色单位面积功率标签在删除 0 面和 15 面处分别贴近上下边框并被裁切；收敛图还产生 `set_ticklabels()` 固定刻度警告。该 run 保留为第二轮审阅证据，最终修订另建 `run-20260818-0132-q2-paper-figures-final-fix`。
