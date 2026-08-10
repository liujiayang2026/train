# Human decision

- 日期：2026-08-10
- 涉及问题：q3
- 涉及路线/run：`routes/r01-monthly-flux-forecast/`（`run-20260809-1802-canonical-input-paths`）；`routes/r01-historical-ensemble/`；`routes/r02-random-forest/`；`routes/r03-stl-template-ensemble/`
- 决定：将 `r01-monthly-flux-forecast` 分类为当前交给 Finalizer 的采用候选；将三条 legacy 路线分类为 abandoned，仅保留其代码、运行、结果和验证证据，不用于当前第三问结论。
- 理由：月通量路线直接从原始不等间隔观测积分，不把插值日值当作独立样本，并使用 2019—2020 年扩展窗口选模和 2021 年完整留出检验；三条 legacy 路线的数据口径、逐日外推和验证目标不统一，且缺少未来降雨、调度等外生变量支撑。该分类落实 `d01-post-break-monthly-forecast.md`，不改变既有模型结果。
- 对结果或后续问题的影响：Q3 索引、路线状态和比较记录以月通量路线为当前答案入口；三条 abandoned 路线不删除、不覆盖、不移动既有 run。`process/_staging/` 与 `q3/inbox/` 没有第三问待分类材料，因此不追加 staging classification-log。
- 决定人：用户
