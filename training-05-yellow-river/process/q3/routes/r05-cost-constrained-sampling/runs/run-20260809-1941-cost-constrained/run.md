# Run record

- 日期时间：2026-08-09 19:41（Asia/Shanghai）
- 执行目录：`training-05-yellow-river/process/q3/routes/r05-cost-constrained-sampling`
- 执行命令：`python code/cost_constrained_sampling.py --run-dir runs/run-20260809-1941-cost-constrained`
- 代码入口/版本：`code/cost_constrained_sampling.py`；失败时 SHA-256 `1897ef9aebe887b8f052d5735e8bb427c03f929e717f4d01404d06ad7cbda196`
- 输入文件：r04 canonical `monthly_forecast_2022_2023.csv`、`monthly_sampling_strategy.csv`；q2 legacy run 的 `daily_flux_series.csv`、`abrupt_change_events.csv`
- 关键参数：校准期 2018—2020；留出期 2021；基础间隔 `{3,5,7,10,14}` 天；动态阈值 `{1.0,1.5,2.0,2.5}`；触发后连续 2 天加采；水量 WAPE 上限 10%；输沙 WAPE 上限 25%；突变捕获率下限 80%；事件容差正负 1 天；出勤成本 4、样品成本 1（无量纲单位）
- 随机种子：不适用，确定性枚举与 MILP
- 环境/依赖：Python 3.12；numpy、pandas、scipy、matplotlib
- 结果文件：无
- 图表文件：无
- 验证文件：无；错误记录见 `logs/error.txt`
- 是否成功完成：no
- 异常与备注：读取 r04 旧采样表时错误地假设存在 `sample_date` 字段；实际字段名为 `date`。异常发生在求解和任何结果写入之前。此失败 run 保留，不再复用；修复后转入 `run-20260809-1955-cost-constrained`。
