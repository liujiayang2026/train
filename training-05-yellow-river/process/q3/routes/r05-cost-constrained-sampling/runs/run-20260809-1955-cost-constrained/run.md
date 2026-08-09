# Run record

- 日期时间：2026-08-09 19:55（Asia/Shanghai）
- 执行目录：`training-05-yellow-river/process/q3/routes/r05-cost-constrained-sampling`
- 执行命令：`python code/cost_constrained_sampling.py --run-dir runs/run-20260809-1955-cost-constrained`
- 代码入口/版本：`code/cost_constrained_sampling.py`；SHA-256 `f696168ca7bb59564613df0c8cf09e0ba15816c160476cd931d726fb45b13620`
- 输入文件：r04 canonical `monthly_forecast_2022_2023.csv`、`monthly_sampling_strategy.csv`、`sampling_schedule_2022_2023.csv`；q2 legacy run 的 `daily_flux_series.csv`、`abrupt_change_events.csv`
- 关键参数：校准期 2018—2020；留出期 2021；基础间隔 `{3,5,7,10,14}` 天；动态阈值 `{1.0,1.5,2.0,2.5}`；触发后连续 2 天加采；水量 WAPE 上限 10%；输沙 WAPE 上限 25%；突变捕获率下限 80%；事件容差正负 1 天；出勤成本 4、样品成本 1（无量纲单位）
- 随机种子：不适用，确定性枚举与 MILP
- 环境/依赖：Python 3.12；numpy、pandas、scipy、matplotlib
- 结果文件：`results/selected_monthly_policy.csv`、`sampling_plan_2022_2023.csv`、`monthly_plan_2022_2023.csv`、`conditional_trigger_protocol_2022_2023.csv`、`cost_summary_2022_2023.csv`、`summary.md`
- 图表文件：`figures/pareto_cost_accuracy.png`、`holdout_baseline_comparison.png`、`sampling_calendar_2022_2023.png`
- 验证文件：`validation/candidate_option_performance.csv`、`threshold_sensitivity.csv`、`pareto_front.csv`、`historical_replay_metrics.csv`、`holdout_2021_daily_reconstruction.csv`、`holdout_2021_event_capture.csv`、`quality_checks.csv`
- 是否成功完成：yes
- 异常与备注：HiGHS 返回最优解；12/12 质量检查通过。校准期水量/输沙代理 WAPE 为 6.91%/13.99%，突变捕获率 88.89%；2021 留出为 7.27%/15.43%，5/5 突变事件被捕获。2022—2023 期望成本 646.67 单位，相对旧启发式 1261 单位低 48.72%。2021 留出不参与策略选择；不得据本记录推断人工 adopted。
