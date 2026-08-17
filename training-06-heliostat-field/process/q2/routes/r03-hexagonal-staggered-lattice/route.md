# Route r03-hexagonal-staggered-lattice

- 对应问题：q2
- 过程状态：candidate
- 要回答的内容：采用解析六角交错点阵布置统一尺寸定日镜，达到 60 MW 并最大化单位面积年平均功率。
- 输入与数据口径：题面、60 个年均时点、锥形太阳光束、圆柱集热器和效率定义均与 q1/r01 相同。
- 核心模型/算法：以 `d=W+5+c` 为水平点距，行距取 `sqrt(3)/2*d`，奇偶行错开 `d/2`；旋转、平移后裁剪场区和禁建区。先真实光线筛选，再以真实光线校准代理运行约束 NSGA-II 和差分进化精修。
- 关键公式位置：`model/hexagonal-lattice-model.md`。
- 代码入口：几何为 `code/lattice_model.py`；正式优化入口为 `code/optimize_hex_lattice.py`。
- 关联运行：`runs/run-20260817-1435-hex-lattice-feasibility-screen/` 验证可行性；`runs/run-20260817-1444-surrogate-nsga2-final-ray/` 为正式优化与复算。
- 与其他问题/路线的关系：复用 r01 的锥形光束评价器；r01 因保守环距不能达到 60 MW，r02 因环组过渡冲突密度不足。
- 当前优点：最小中心距由解析结构保证，理论单元面积仅为 `sqrt(3)/2*d^2`。
- 已知缺陷或冲突：最终布局不再是严格同心环，需要用最终镜场图说明其空间结构。
- 放弃时的原因：不适用。
