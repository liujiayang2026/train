# Finalizer 路线决策日志

## q1

- adopted：`process/q1/routes/r01-log-linear-sediment/route.md`。人工 d01 指定 `notes/question1-method.md` 为完整思路，并绑定 `run-20260809-2032-time-block-bootstrap` 的结果与时间块验证。
- 融合边界：完整思路逐字节复制；运行分析、年度表和验证证据分别复制，不重算数值。
- 未决项：无。

## q2

- adopted：`process/q2/routes/r01-interpolated-daily-pattern/route.md`。人工 d01 指定 `notes/question2-method.md` 为完整思路，并绑定 `run-20260809-2036-time-block-q1`。
- 融合边界：保留三种插值口径、突变参数敏感性和周期稳健性；不得把插值敏感性说成 q1 补全误差已经完全传播。
- 未决项：无。

## q3

- adopted：`process/q3/routes/r04-monthly-flux-forecast/route.md`，负责结构突变后的月尺度水沙预测；采用 run 为 `run-20260809-2103-figure-label-clarity`。
- adopted：`process/q3/routes/r05-cost-constrained-sampling/route.md`，负责连续日历下的成本约束动态采样；采用 run 为 `run-20260809-2145-global-event-boundaries`。
- rejected：`process/q3/routes/r01-historical-ensemble/route.md`，历史迁移方案没有当前条件留出和未来不确定性口径。
- rejected：`process/q3/routes/r02-random-forest/route.md`，当前实现与时间验证证据不足，不作为正文模型。
- rejected：`process/q3/routes/r03-stl-template-ensemble/route.md`，不是人工最终采用的预测—采样组合。
- 融合边界：r05 的完整方案已经衔接 r04 预测和 r05 采样；不得混入 r01—r03 的旧预测数值或旧采样频率。
- 未决项：无。

## q4

- adopted：`process/q4/routes/r01-cross-section-counterfactual/route.md`，用于三附件证据链、PCHIP 断面重建和 2016—2023 分级局部效果评价；采用 run 为 `run-20260810-1722-first-subquestion-wording-review`。
- adopted：`process/q4/routes/r04-bounded-aggradation/route.md`，用于无调水调沙十年条件反事实；采用 run 为 `run-20260810-1927-annual-growth-curves`。
- supporting：`process/q4/routes/r02-offseason-natural-rate/route.md`，只作为无约束线性基准和模型敏感性参照。
- rejected：`process/q4/routes/r03-grey-gm11/route.md`，级比检验通过率为 0%，长期预测指数爆炸。
- superseded：d03 已取代 d02 的 PCHIP/线性并列主口径；正文使用 PCHIP，线性仅作敏感性。
- 危险旧数值：不得使用 r02 的十年净冲刷 `-889.7 m²` 作为主预测，不得使用 r03 的 `+58940.3 m²` 或平均抬升 `280.8 m`。
- 未决项：无。
