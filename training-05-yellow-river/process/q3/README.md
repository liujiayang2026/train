# Q3 process index

- Question requirement: 基于 2016—2021 年水沙数据预测未来两年的月度、年度水沙通量，并提出监测采样方案。
- Current adopted candidate route: `routes/r01-monthly-flux-forecast/`，直接积分 72 个月识别结构跃迁，以 2018—2021 年 48 个月建模，输出 80%/95% 月度区间和采样时段。
- Abandoned historical routes: `routes/r01-historical-ensemble/`、`routes/r02-random-forest/`、`routes/r03-stl-template-ensemble/`；保留全部代码、运行和验证证据，但不用于当前作答。
- Known conflicts: 三条 legacy 路线不同程度继承插值日序列、逐日外推和规则式采样逻辑，验证口径也不统一；当前月通量路线不采用该数据口径。
- Explicit human decisions: `d01` 确定突变后月通量建模口径；`d02` 将月通量路线列为当前采用候选，并将三条 legacy 路线分类为 abandoned。

## Current documentation

- 完整解题思路：`routes/r01-monthly-flux-forecast/model/complete-solution.md`
- 人工决策记录：`decisions/d01-post-break-monthly-forecast.md`
- 路线分类决定：`decisions/d02-classify-q3-routes.md`

## Classification result

- `process/_staging/` 中没有第三问待分类文件，`q3/inbox/` 也没有未定路线材料，因此本次不产生 staging move，分类日志无需追加。
- 现有运行目录均为 append-only 证据，不因路线分类而移动、覆盖或删除。
- 两个 `r01-*` 路径来自分支合并前的独立编号；为保护既有 run 路径而保留原名，权威归属以完整路线目录名和人工决定为准。

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.
