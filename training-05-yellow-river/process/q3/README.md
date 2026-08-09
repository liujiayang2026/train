# Q3 process index

- Question requirement: 基于2016-2021水沙数据预测未来两年月度与年度水沙通量，并提出监测采样方案。
- Current candidate routes: `routes/r01-monthly-flux-forecast/`，直接积分72个月识别结构跃迁，以2018-2021年48个月建模，输出80%/95%月度区间和采样时段。
- Known conflicts: legacy路线把插值后的逐日序列视为独立训练样本，并给出两年逐日确定性预测；r01不采用该口径。
- Explicit human decisions: 2016-2017作为突变前状态，不进入预测模型；2019-2020用于时间回测选模，使用2018-2020训练并完整留出2021作最终检验；日尺度只用于制定采样时段。

## Current documentation

- 完整解题思路：`routes/r01-monthly-flux-forecast/model/complete-solution.md`
- 人工决策记录：`decisions/d01-post-break-monthly-forecast.md`

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.

## Legacy intake pointers

- Main combined-model materials: `process/legacy-package/question-3/`.
- Random-forest alternative: `process/legacy-package/q3/`.
- Optimized-ensemble alternative: `process/legacy-package/q3-optimized/`.
- These are distinct candidate routes and must be compared before finalization.
