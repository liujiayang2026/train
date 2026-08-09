# Q1 process index

- Question requirement: 研究含沙量与时间、水位、流量的关系，并估算2016-2021年逐年总水流量和总排沙量。
- Current candidate routes: `routes/r01-log-linear-sediment/`，历史对数线性含沙量补全与通量积分方案。
- Known conflicts: 历史方案用全时段观测拟合缺失含沙量；若结果供时间外推回测使用，需要按预测时点重新拟合以避免信息泄漏。
- Explicit human decisions: 用户表示前两问当前没有明显问题，但尚未形成正式采用决定。

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.

历史代码、说明、结果与验证已迁入 `routes/r01-log-linear-sediment/`，导入动作不代表正式采用。
