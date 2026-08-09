# Q3 process index

- Question requirement: 基于 2016—2021 年水沙数据预测未来两年的月度、年度水沙通量，并在能够动态掌握变化的前提下尽量降低监测成本。
- Forecast candidate: `routes/r04-monthly-flux-forecast/`。直接积分 72 个月识别结构跃迁，以 2018—2021 年 48 个月建模；当前复现证据为 `run-20260809-2103-figure-label-clarity`，显式绑定 q1 2032 与 q2 2036 成功 run。2040 为数值一致的上一版成功证据。
- Sampling candidate: `routes/r05-cost-constrained-sampling/`。以 r04 2103 预测为上游输入，显式最小化资源成本并约束重构误差、突变捕获率和风险月最大基础间隔；当前成功证据为 `run-20260809-2145-global-event-boundaries`，采用跨月、跨年不重置的连续日历阈值转移 MILP，并在每个验证切分合并后的全局采样日历上评分事件 ±1 日捕获，28/28 质量检查和 9/9 单元测试通过。2124 已修复动态状态和动作的月界连续性，但其两条描述性基线仍按事件所在月评分，现只作历史证据；2105 与 2046 还存在按月重置动态判定、遗漏跨月加采的问题；1955 为旧输入和旧验证口径下的成功历史运行，1941 为保留的失败运行。
- Migrated historical routes: `routes/r01-historical-ensemble/`、`routes/r02-random-forest/`、`routes/r03-stl-template-ensemble/`；仅作为历史证据保留，不因迁移而采用。
- Known conflicts: 三条 legacy 路线不同程度继承插值日序列、逐日外推和规则式采样逻辑，验证口径不统一；r04 不采用逐日伪观测进行预测。r04 的 2021 证据只在预测模型层条件成立，r05 的 2021 证据只在策略层条件成立，二者都不是包含 q1 补全在内的端到端无泄漏验证。r05 历史回放使用 q2 日序列作为监测设计代理，不能消除 q1 补值与 q2 插值误差，也不能验证日内多时段样本的额外收益；每日 09:00 快速触发还假设现有自动站/远程传感器无需新增人工出勤。
- Explicit human decisions: `d01` 确定预测尺度、突变后建模期和时间验证逻辑；`d02` 记录用户要求开展成本约束采样整改，并明确 r04/r05 的证据关系。`d02` 只授权整改，不构成对 r05 的最终 adopted 批准。

## Current documentation

- 第三问预测—采样综合完整思路：`routes/r05-cost-constrained-sampling/model/complete-solution.md`
- 预测完整解题思路：`routes/r04-monthly-flux-forecast/model/complete-solution.md`
- 成本约束采样模型：`routes/r05-cost-constrained-sampling/model/method.md`
- 路线与基线比较：`comparisons/compare-q3-forecast-routes.md`
- 人工决定记录：`decisions/d01-post-break-monthly-forecast.md`、`decisions/d02-request-cost-constrained-sampling.md`

当前过程包含完整候选证据，但最终采用仍须后续人工审核，不得依据 `candidate`、当前复现或运行成功状态推断 adopted。
