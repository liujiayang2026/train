# 黄河水沙监测数据分析：写作人工包

本目录是 `F:\train` 从人工建模过程筛选出的唯一写作输入，不是过程摘要，也不是论文稿。

## 使用顺序

1. 先读 `common/decision-log.md`，确认采用、支持和拒绝路线。
2. 每问先读 `qN/solution.md` 获取权威直接答案、口径和材料索引。
3. 必须继续读取 `full-solution*.md`、`forecast-full-solution.md` 等完整思路文件；这些文件由 adopted process 材料保真复制，不能被入口摘要替代。
4. 数值只取 `results/`，验证强度与限制只取 `validation/` 和 solution 的边界说明。
5. `figures/` 是允许用于论文的图；`code/` 是产生结果的采用版本。

写作端不得读取 `process/`，不得重新运行代码或计算结果。若本目录内部发生冲突，应退回 Train 复审。
