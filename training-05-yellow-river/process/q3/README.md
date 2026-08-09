# Q3 process index

- Question requirement: 基于 2016—2021 年水沙数据预测未来两年的月度、年度水沙通量，并提出监测采样方案。
- Current candidate routes: `r01-historical-ensemble`、`r02-random-forest`、`r03-stl-template-ensemble`。
- Known conflicts: 三条路线均来自 `main` 中原有 legacy 快照，继承了不同程度的插值日序列、逐日外推和规则式采样逻辑；现有验证口径尚未统一。
- Explicit human decisions: 用户认为原第三问存在问题并要求重做；本次迁移不采用任何候选路线。

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.
