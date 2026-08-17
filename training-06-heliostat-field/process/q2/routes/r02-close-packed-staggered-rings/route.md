# Route r02-close-packed-staggered-rings

- 对应问题：q2
- 过程状态：candidate
- 要回答的内容：在统一镜面尺寸和高度约束下，以近六角密排交错环提高场区利用率，达到 60 MW 后最大化单位面积年平均功率。
- 输入与数据口径：与 q1、r01 完全相同的题面、60 时点、锥形太阳光束和圆柱集热器定义；使用 `source/attachments/result2.xlsx` 模板。
- 核心模型/算法：环间距允许降至约 `sqrt(3)/2*(W+5)`，交错生成后用空间哈希逐点筛除所有小于 `W+5` 的冲突；低样本真实光线筛选可行区后，以真实光线校准代理并运行约束 NSGA-II。
- 关键公式位置：`model/close-packed-staggered-model.md`。
- 代码入口：`code/optimize_close_packed.py`（待建立）；布局公共函数为 `code/hex_layout_model.py`。
- 关联运行：`runs/run-20260817-1430-close-packed-feasibility-screen/` 首先验证 60 MW 可行区间。
- 与其他问题/路线的关系：继承 r01 的光线评价器；r01 真实光线筛选表明保守径向间距最高仅 55.3545 MW，因此新建本路线。
- 当前优点：在严格保持最小中心距的同时提高镜面面积装填率。
- 已知缺陷或冲突：贪心冲突筛选会造成局部缺口，需在优化和最终空间效率图中检查。
- 放弃时的原因：不适用。
