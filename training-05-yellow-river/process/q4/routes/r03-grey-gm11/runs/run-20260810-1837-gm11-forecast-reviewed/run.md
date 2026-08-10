# Run record

- 日期时间：2026-08-10 18:37 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r03-grey-gm11/code/forecast_gm11_no_regulation.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r03-grey-gm11/runs/run-20260810-1837-gm11-forecast-reviewed`
- 代码入口/版本：`code/forecast_gm11_no_regulation.py`；SHA-256 `F2B5CBEF39FDBA6510066FF3AFA502FE2F6D37C05963A33421D9C68CAC1CFEB7`
- 输入文件：只读附件1、附件2、附件3
- 关键参数：PCHIP；5 m网格；1820—2050 m；年化GM平移常数2.5、3、4、5 m/年，中心值3；原始差值GM平移常数1、1.5、2、3 m；预测10年。
- 随机种子：不适用
- 环境/依赖：Python 3；numpy、pandas、scipy、matplotlib、openpyxl
- 结果文件：`results/analysis.md`、`gm11_input_intervals.csv`、`gm11_forecast_2033_grid.csv`、`gm11_annual_forecast_grid.csv`、`gm11_forecast_summary.csv`、`attachment1_water_context.csv`
- 图表文件：`figures/gm11_input_profiles.png`、`gm11_forecast_2023_2033.png`、`gm11_shift_sensitivity.png`
- 验证文件：`validation/gm11_diagnostics.csv`、`gm11_hindcast_summary.csv`、`gm11_hindcast_grid.csv`、`quality_checks.csv`
- 是否成功完成：yes
- 异常与备注：7/7质量检查通过。固定平移1 m不能保证完整断面为正；中心年化模型平移3 m/年预测净淤积，但幅度严重失真且级比检验通过率为0%，只宜作为不稳定对照模型。
