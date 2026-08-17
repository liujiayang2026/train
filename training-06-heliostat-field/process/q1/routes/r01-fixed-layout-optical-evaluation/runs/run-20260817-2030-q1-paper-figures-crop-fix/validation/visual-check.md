# Visual check

- 检查方式：对八张输出 PNG 进行原尺寸人工检查。
- 已通过：三张拆分图已去除审阅页眉，汇总图功率公式已统一为 `P_{\mathrm{field}}`；月度结果图和联合采样图清晰完整。
- 未通过 1：`field-to-neighbor-scale-paper.png` 底部露出被裁断的审阅说明。
- 未通过 2：`shadow-vs-blocking-paper.png` 中两条射线公式显示字面量下划线，没有渲染为数学下标。
- 未通过 3：`physical-ray-geometry-paper.png` 顶部仍残留上一版页眉的一条裁切痕迹。
- 处置：不覆盖本 run；改为绘图层直接生成无页眉物理图，并在新 run 中重新导出。
