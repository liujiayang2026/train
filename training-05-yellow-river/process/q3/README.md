# Q3 process index

- Question requirement: 基于2016-2021水沙数据预测未来两年月度与年度水沙通量，并提出监测采样方案。
- Current candidate routes: `routes/r01-monthly-flux-forecast/`，以72个月直接积分总量建模，输出80%/95%月度区间和采样时段。
- Known conflicts: legacy路线把插值后的逐日序列视为独立训练样本，并给出两年逐日确定性预测；r01不采用该口径。
- Explicit human decisions: 使用72个月总量建模并给月度预测区间；日尺度只用于制定采样时段。

Create one `routes/rNN-short-name/` directory per materially different route. Keep each route's model, code, runs, results, figures, validation, and logs together.

## Legacy intake pointers

- Main combined-model materials: `process/legacy-package/question-3/`.
- Random-forest alternative: `process/legacy-package/q3/`.
- Optimized-ensemble alternative: `process/legacy-package/q3-optimized/`.
- These are distinct candidate routes and must be compared before finalization.
