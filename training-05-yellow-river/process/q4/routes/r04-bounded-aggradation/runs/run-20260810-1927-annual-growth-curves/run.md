# Run record

- 日期时间：2026-08-10 19:27 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r04-bounded-aggradation/code/forecast_bounded_aggradation.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r04-bounded-aggradation/runs/run-20260810-1927-annual-growth-curves`
- 代码入口/版本：`code/forecast_bounded_aggradation.py`；SHA-256 `53B4034290A22FADFAE76DC43381349660E70BF2A6A03CCE9A7DF5E05628BCCD`
- 输入文件：只读附件1、附件2、附件3
- 关键参数：与`run-20260810-1922-bounded-aggradation/`相同；新增2023—2033逐年累计净断面变化和平均高程变化曲线。
- 随机种子：不适用
- 环境/依赖：Python 3；numpy、pandas、scipy、matplotlib、openpyxl
- 结果文件：`results/analysis.md`、`annualized_input_profiles.csv`、`input_interval_summary.csv`、`spatial_template.csv`、`bounded_forecast_2033_grid.csv`、`bounded_annual_forecast_grid.csv`、`bounded_forecast_summary.csv`、`attachment1_water_context.csv`
- 图表文件：`figures/observed_annualized_rates.png`、`bounded_forecast_2023_2033.png`、`bounded_sensitivity.png`、重点新增`bounded_annual_growth.png`
- 验证文件：`validation/spatial_template_loo_summary.csv`、`spatial_template_loo_grid.csv`、`quality_checks.csv`
- 是否成功完成：yes
- 异常与备注：参数与模型不变，仅增加逐年增长可视化并在独立run重跑；9/9质量检查通过。
