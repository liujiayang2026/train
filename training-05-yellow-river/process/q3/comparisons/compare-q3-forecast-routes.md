# Route comparison

- 比较目的：登记三条 legacy 路线与重做后的月通量路线，说明当前人工选择及其证据边界。
- 参与路线及 run：`r01-historical-ensemble/run-20260809-0000-imported-legacy`、`r01-historical-ensemble/run-20260809-1452-imported-hxk-regime-aware`、`r02-random-forest/run-20260809-0000-imported-legacy`、`r03-stl-template-ensemble/run-20260809-0000-imported-legacy`、`r01-monthly-flux-forecast/run-20260809-1538-2021-holdout`。
- 统一输入和指标：legacy 路线沿用插值日序列且验证口径不一，不能与月通量路线直接横向排名；月通量路线使用原始观测直接积分，并以 2019—2020 年扩展窗口对数 RMSE 选模、2021 年完整留出检验。
- 对比表/图文件：月通量路线的候选模型、历史预测与区间覆盖证据位于 `r01-monthly-flux-forecast/runs/run-20260809-1538-2021-holdout/validation/` 和 `figures/`；legacy 路线证据位于各自 run。
- 可比性限制：legacy 路线的数据处理、验证目标和采样规则不完全一致；当前选择依据数据口径与无泄漏时间验证，不声称已有 legacy 分数与新路线分数完全可比。
- 观察结论：月通量路线在 2019—2020 年选模回测中，水量和输沙量 WAPE 分别为 19.30% 和 28.41%；2021 年留出 WAPE 分别为 43.22% 和 73.62%，揭示缺少降雨、调度等外生变量时无法提前识别异常低谷。根据 `decisions/d01-post-break-monthly-forecast.md`，当前采用该路线继续作答，三条 legacy 路线仅保留为历史候选。
- 尚未解决的问题：极端调度事件的外生变量缺失、第二预测年区间扩宽的经验性，以及未来新增监测数据后的滚动更新。
