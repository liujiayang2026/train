# Human decision

- 日期：2026-08-11
- 涉及问题：q3
- 涉及路线/run：预测采用`routes/r04-monthly-flux-forecast/`的`run-20260809-2103-figure-label-clarity/`；采样采用`routes/r05-cost-constrained-sampling/`的`run-20260809-2145-global-event-boundaries/`
- 决定：正式采用r04月尺度预测与r05成本约束动态采样组成问题三完整方案；以r05 `model/complete-solution.md`中已经融合两路线的完整解题思路作为final正文级材料，不得再次压缩重构。
- 理由：r04按时间顺序完成结构突变后的月尺度预测与条件留出；r05以连续日历MILP同时约束成本、重构误差、事件捕获和最大间隔。两路线输入输出兼容且分别回答预测与采样两个子任务。
- 对结果或后续问题的影响：r01—r03只在论文中作简短候选比较，说明其历史迁移、递归外推、实现/验证和成本目标问题，不展开废弃路线完整推导。
- 决定人：用户
