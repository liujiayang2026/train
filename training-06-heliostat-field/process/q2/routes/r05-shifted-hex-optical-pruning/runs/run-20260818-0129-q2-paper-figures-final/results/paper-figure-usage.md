# Q2 论文图使用说明

| 图文件 | 建议位置 | 主要用途 | 数据口径 |
|---|---|---|---|
| `layout-and-spacing-paper.png` | 模型建立/方案描述 | 说明塔位、场界、禁建区和六角错列间距 | r05 正式镜位 |
| `candidate-selection-paper.png` | 求解算法 | 说明多精度候选筛选与不删镜决策 | 64 光线筛选 + 256 光线正式复核 |
| `monthly-performance-paper.png` | 结果分析 | 解释季节变化、效率与功率关系 | r05 seed 202308，256 光线 |
| `spatial-power-paper.png` | 结果分析 | 解释逐镜功率的空间非均匀性 | r05 seed 202308，256 光线 |
| `ray-convergence-paper.png` | 稳定性分析 | 展示 32/64/128/256 光线收敛 | 相同 Sobol 扰码种子 |
| `robustness-paper.png` | 稳定性分析 | 展示三个 256 光线扰码种子及保守下界 | r08 对 r05 的复核 |

探索路线 r07、旧 r03/r05 柱图和未标注安全线的旧删镜图不进入 Q2 最终论文图组。
