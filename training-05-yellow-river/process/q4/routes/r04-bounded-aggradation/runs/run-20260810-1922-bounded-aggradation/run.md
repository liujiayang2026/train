# Run record

- 日期时间：2026-08-10 19:22 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r04-bounded-aggradation/code/forecast_bounded_aggradation.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r04-bounded-aggradation/runs/run-20260810-1922-bounded-aggradation`
- 代码入口/版本：`code/forecast_bounded_aggradation.py`；SHA-256 `51AAFDA43BDBB282DAC88A91C6A4915223864AC4BA594A6C3D9D373DD1DDB52C`
- 输入文件：只读附件1、附件2、附件3
- 关键参数：PCHIP；5 m网格；1820—2050 m；低/中/高净淤积率取三个正净变化样本的最小值/中位数/最大值；中心形态调整时间常数10年，敏感性5年和20年；预测期10年。
- 随机种子：不适用
- 环境/依赖：Python 3；numpy、pandas、scipy、matplotlib、openpyxl
- 结果文件：`results/analysis.md`、`annualized_input_profiles.csv`、`input_interval_summary.csv`、`spatial_template.csv`、`bounded_forecast_2033_grid.csv`、`bounded_annual_forecast_grid.csv`、`bounded_forecast_summary.csv`、`attachment1_water_context.csv`
- 图表文件：`figures/observed_annualized_rates.png`、`bounded_forecast_2023_2033.png`、`bounded_sensitivity.png`
- 验证文件：`validation/spatial_template_loo_summary.csv`、`spatial_template_loo_grid.csv`、`quality_checks.csv`
- 是否成功完成：yes
- 异常与备注：9/9质量检查通过。中心情景净断面变化+561.3 m²、平均高程变化+2.403 m；低—高情景与时间常数敏感性均已完整保留。
