# 问题一论文图表使用清单（已采用）

## 使用原则

1. 用户已于 2026-08-17 明确审阅并采用本清单中的图，采用决定见 `process/q1/decisions/d03-adopt-physical-narrative-figure-suite.md`。
2. 本清单是问题一已采用图的唯一用途映射。写作仓库仍不得直接从 `process/` 选图；Finalizer 应按本清单把获选图及图注映射纳入批准的 `final/`，写作端只读取批准版本。
3. 输入图、方法图、诊断图不得写成“计算结果表明”；真正的结果数值只来自正式 CSV、题目表 1 / 表 2 和月年结果图。
4. PNG 内部大标题用于本轮审阅和辨认。正式论文排版时应采用下表的论文图注，并按版式需要导出无审阅页眉版本，不能把内部标题当作论文图号。

## 唯一用途映射

| 已采用文件 | 类型 | 正文位置 | 论文图注 | 禁止误用 |
|---|---|---|---|---|
| `scene-inputs.png` | 输入图 | 问题一“数据与评价时点”末尾 | 问题一评价时点与固定镜场布局 | 不得放在结果分析中；不表示太阳轨迹计算结果 |
| `per-mirror-optical-chain.png` | 方法图 | “光学效率模型”总公式之前 | 定日镜逐镜光学效率评价流程 | 色块只是效率因子，不是柱状结果；不得报告为仿真数值 |
| `aggregation-to-tables.png` | 口径图 | 正式表 1、表 2 之前 | 逐时镜场功率向月均与年均指标的汇总关系 | 只解释数据来源，不替代表 1、表 2，不得称为结果图 |
| `fig02-field-to-neighbor-scale.png` | 方法图 | “阴影遮挡效率”中的邻镜预筛选段 | 全镜场与 45 m 邻镜候选域 | 45 m 圆是搜索域，不是光斑或遮挡范围 |
| `fig03-shadow-vs-blocking-physical.png` | 方法图 | “阴影遮挡效率”的射线求交定义之后 | 阴影损失与遮挡损失对应的不同光路 | 示意交点不是某月统计结果 |
| `fig04-real-joint-sampling.png` | 诊断图 | “联合采样实现与代表案例验证” | 镜 1660 的 512 条联合射线分类及条件截断统计 | 只代表 1 月 21 日 9:00 的单镜案例，不得当作全场或年均结果 |
| `fig05-monthly-results-story.png` | 结果图 | 问题一“结果与分析”中，紧随表 1 / 表 2 | 月均光学效率与单位镜面面积输出热功率的季节变化 | 这是唯一推荐的综合结果图；不得用方法示意图替代 |
| `fig01-physical-ray-geometry.png` | 方法图 | “截断效率与接收器求交” | 太阳方向锥经定日镜反射并与圆柱接收器相交的几何关系 | 光束只说明几何和溢出，不表示实际能流密度分布 |

前三个文件来自本 run。`fig02` 至 `fig05` 来自 `run-20260817-1514-q1-narrative-figures/`；`fig01-physical-ray-geometry.png` 来自 `run-20260817-1451-physical-ray-geometry-redraw/`。上述八张图均已写入 `model/question1-complete-solution.md` 的对应章节。

## 已排除的过程图

- `run-20260817-1514-q1-narrative-figures/figures/fig01-q1-narrative-flow.png`：信息密集的六阶段总览，不属于论文图池；仅因 run 证据规则保留。
- `run-20260817-1543-q1-narrative-flow-split/`：公式渲染失败 run，不属于论文图池。
- `run-20260817-1552-q1-narrative-flow-split-math-fix/`：逐镜反射图越出分区，视觉验收未通过，不属于论文图池。
- `run-20260816-1711-reflected-bundle-cylinder/figures/fig01-reflected-bundle-to-cylinder-process.png`：已由物理校验后的 `fig01-physical-ray-geometry.png` 取代，不再用于正文；仅作为历史 run 证据保留。
- `process/common/figures/fig02-side-ray-geometry.png`：已被物理图替代并删除。
- `process/common/figures/fig03-efficiency-power-structure.png`：已被逐镜评价链和汇总口径图替代并删除。
- 其他历史 run 图均不在本清单中，Finalizer 和写作端不得自行选用。

## 表格对应关系

- 题目表 1：12 行月均指标，数据源为正式 `monthly_metrics.csv`。
- 题目表 2：1 行年均指标，数据源为正式 `annual_metrics.csv`。
- 年平均输出热功率单位为 MW；单位镜面面积年平均输出热功率单位为 `kW/m^2`。
- 必须先逐时计算 `DNI(t) × eta_opt(t)` 和镜场功率，再对 60 个规定时刻等权平均；不得用平均 DNI 与平均效率的乘积替代。
