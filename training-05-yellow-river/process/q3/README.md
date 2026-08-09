# Q3 process index

- Question requirement: 基于 2016—2021 年水沙数据预测未来两年的月度、年度水沙通量，并提出监测采样方案。
- Current candidate route: `routes/r01-monthly-flux-forecast/`，直接积分 72 个月识别结构跃迁，以 2018—2021 年 48 个月建模，输出 80%/95% 月度区间和采样时段。
- Migrated historical routes: `routes/r01-historical-ensemble/`、`routes/r02-random-forest/`、`routes/r03-stl-template-ensemble/`；仅作为历史证据保留，不因迁移而采用。
- Known conflicts: 三条 legacy 路线不同程度继承插值日序列、逐日外推和规则式采样逻辑，验证口径也不统一；当前月通量路线不采用该数据口径。
- Explicit human decisions: 2016—2017 年作为突变前状态，不进入预测模型；2019—2020 年用于时间回测选模，使用 2018—2020 年训练并完整留出 2021 年作最终检验；日尺度只用于制定采样时段。

## Current documentation

- 完整解题思路：`routes/r01-monthly-flux-forecast/model/complete-solution.md`
- 人工决策记录：`decisions/d01-post-break-monthly-forecast.md`

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.
