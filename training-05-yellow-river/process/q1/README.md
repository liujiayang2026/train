# Q1 process index

- Question requirement: 研究含沙量与时间、水位、流量的关系，并估算2016-2021年逐年总水流量和总排沙量。
- Current candidate routes: `routes/r01-log-linear-sediment/`，四模型留一年比较、对数线性含沙量补全与通量积分方案。
- Current reference evidence: `routes/r01-log-linear-sediment/runs/run-20260809-2032-time-block-bootstrap/`；规范输入路径成功运行，13/13质量检查通过。72小时为事先指定主块长，24/72/168小时各完成500次按年真实时间移动块自助。
- Known conflicts: 87.13%的含沙量由模型补全；留一年稀疏观测网格输沙WAPE为28.85%-71.49%。72小时经验区间相对半宽为5.93%-22.51%，基准点仅落入2/6个区间，且结果对块长敏感。全时段拟合结果若供时间外推回测使用，需要按预测时点重新拟合以避免信息泄漏。这些经验区间仅覆盖当前模型内的训练样本和补全残差，不是完整真实误差区间或覆盖率验证。
- Explicit human decisions: 用户表示前两问当前没有明显问题，但尚未形成正式采用决定。

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.

历史材料保留在 `routes/r01-log-linear-sediment/runs/run-20260809-0000-imported-legacy/`；旧版7条记录块运行保留在 `routes/r01-log-linear-sediment/runs/run-20260809-1941-canonical-uncertainty/`，超时失败证据保留在 `routes/r01-log-linear-sediment/runs/run-20260809-2013-time-block-bootstrap/`。当前参考运行只补强可复现性和证据，不代表正式采用。
