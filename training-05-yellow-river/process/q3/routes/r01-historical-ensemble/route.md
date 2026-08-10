# Route r01-historical-ensemble

- 对应问题：q3
- 过程状态：abandoned
- 要回答的内容：预测 2022—2023 年月度、年度水沙通量，并给出采样安排。
- 输入与数据口径：继承 q2 插值后的日尺度水沙通量与 legacy 中的历史处理口径。
- 核心模型/算法：初始版本采用近期加权季节模板、趋势残差、历史留年验证与规则式采样；hxk 历史版本增加结构起点识别、Fourier-STL 混合和近期形状修正。
- 关键公式位置：`notes/question3-method.md`、`notes/complete-solution.md`。
- 代码入口：`code/analyze_question3.py`；hxk 历史版本入口为 `code/regime_aware_question3.py`。
- 关联运行：`runs/run-20260809-0000-imported-legacy/`；`runs/run-20260809-1452-imported-hxk-regime-aware/`。
- 与其他问题/路线的关系：保留 `main` 与 hxk 中 `legacy-package/question-3` 的历史证据；当前重做方案位于 `../r01-monthly-flux-forecast/`。
- 当前优点：保留了较完整的方法说明、预测结果、采样计划和历史验证材料。
- 已知缺陷或冲突：继承插值日序列和规则式采样；两个历史运行均为迁移记录，尚未在规范路径重新执行。
- 放弃时的原因：依据 `../../decisions/d02-classify-q3-routes.md`，该路线依赖插值日序列、验证口径未与当前路线统一，且逐日确定性外推缺少未来外生变量支撑；当前作答不采用，但完整历史证据继续保留。
