# Q2 process index

- Question requirement: 分析近6年水沙通量的突变性、季节性和周期性，研究其变化规律。
- Current candidate routes: `routes/r01-interpolated-daily-pattern/`，历史逐小时插值、日聚合与周期分析方案。
- Known conflicts: 双向时间插值会平滑稀疏含沙量和洪峰过程；该日序列不应未经隔离直接充当第三问滚动预测的真实标签。
- Explicit human decisions: 用户表示前两问当前没有明显问题，但尚未形成正式采用决定。

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.

历史代码、说明、图表、结果与验证已迁入 `routes/r01-interpolated-daily-pattern/`，导入动作不代表正式采用。
