# Route r01-historical-ensemble

- 对应问题：q3
- 过程状态：uncertain
- 要回答的内容：预测 2022—2023 年月度、年度水沙通量，并给出采样安排。
- 输入与数据口径：继承 q2 插值后的日尺度水沙通量与 legacy 中的历史处理口径。
- 核心模型/算法：近期加权季节模板、趋势残差、历史留年验证与规则式采样。
- 关键公式位置：`notes/question3-method.md`、`notes/complete-solution.md`。
- 代码入口：`code/analyze_question3.py`；基础函数位于同一 `code/` 目录。
- 关联运行：`runs/run-20260809-0000-imported-legacy/`。
- 与其他问题/路线的关系：这是 `main` 中 `legacy-package/question-3` 的原样迁移；需与 r02、r03 统一比较。
- 当前优点：保留了较完整的方法说明、预测结果、采样计划和历史验证材料。
- 已知缺陷或冲突：继承插值日序列和规则式采样，且迁移后尚未在规范路径重新执行。
- 放弃时的原因：尚无正式采用或放弃决定；当前仅作为历史候选保留。
