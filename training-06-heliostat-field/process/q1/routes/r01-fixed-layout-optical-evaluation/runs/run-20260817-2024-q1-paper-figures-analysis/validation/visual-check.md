# Visual check

- 检查方式：对八张输出 PNG 进行原尺寸人工检查。
- 结论：未通过。
- 问题 1：`scene-inputs-paper.png`、`per-mirror-optical-chain-paper.png`、`aggregation-to-tables-paper.png` 的裁切上边界仍保留原审阅副标题。
- 问题 2：`aggregation-to-tables-paper.png` 的功率公式虽已由 `E` 改为 `P`，但 `field` 下标仍为数学斜体，未与正文的 `P_{\mathrm{field}}` 统一。
- 处置：不覆盖本 run；修改导出代码后建立新 run 重新生成。
