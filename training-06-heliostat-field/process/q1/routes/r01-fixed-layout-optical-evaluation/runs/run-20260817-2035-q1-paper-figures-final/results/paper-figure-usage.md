# 问题一论文版图表使用清单

## 使用原则

1. 本 run 的八张 PNG 是 `d03` 已采用图的无审阅页眉论文版，并由 `d04` 明确替换正文中的旧版文件引用。
2. 图片内部只保留面板标题、坐标、图例、必要公式和物理标注；正式图号与下列图注由论文排版系统统一生成。
3. 输入图、方法图和诊断图不作为计算结论；正式数值只来自 512 射线 run 的 CSV、题目表 1、题目表 2 和月度结果图。

## 正文映射

| 文件 | 类型 | 论文图注 | 正文位置 |
|---|---|---|---|
| `scene-inputs-paper.png` | 输入图 | 问题一评价时点与固定镜场布局 | 数据与评价时点 |
| `per-mirror-optical-chain-paper.png` | 方法图 | 定日镜逐镜光学效率评价流程 | 光学效率总公式之前 |
| `shadow-vs-blocking-paper.png` | 方法图 | 阴影损失与遮挡损失对应的不同光路 | 阴影遮挡效率 |
| `physical-ray-geometry-paper.png` | 方法图 | 太阳方向锥经定日镜反射并与圆柱接收器相交的几何关系 | 截断效率与接收器求交 |
| `real-joint-sampling-paper.png` | 诊断图 | 镜 1660 的 512 条联合射线分类及条件截断统计 | 联合采样实现 |
| `field-to-neighbor-scale-paper.png` | 方法图 | 全镜场与 45 m 邻镜候选域 | 邻镜预筛选 |
| `aggregation-to-tables-paper.png` | 口径图 | 逐时镜场功率向月均与年均指标的汇总关系 | 表 1、表 2 之前 |
| `monthly-performance-paper.png` | 结果图 | 月均光学效率与单位镜面面积输出热功率的季节变化 | 结果分析 |

全部图片位于本 run 的 `figures/`；裁切范围、输入与输出 SHA-256、像素尺寸和绘图代码 SHA-256 见 `validation/paper-figure-checks.json`。
