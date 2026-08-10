# Run record

- 日期时间：2026-08-10 18:16（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r02-offseason-natural-rate/code/forecast_no_regulation_natural_rate.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r02-offseason-natural-rate/runs/run-20260810-1816-natural-rate-forecast-reviewed`
- 代码入口/版本：`code/forecast_no_regulation_natural_rate.py`；执行前SHA-256 `d1a74f1124481b3967aa3cb906f1cad05dd125fa16d864d0caad2e90b341a297`
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`
- 关键参数：与1813 run相同；主预测域修正为全部所需测次的严格共同网格1820—2050 m，并在分析中按实际净方向解释验证和长期外推风险。
- 随机种子：不适用（确定性计算）
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；SciPy 1.13.1；Matplotlib 3.10.9
- 结果文件：`results/natural_rate_grid.csv`、`forecast_2033_grid.csv`、`annual_forecast_grid.csv`、`forecast_summary.csv`、`attachment1_water_flux_context.csv`、`attachment2_offseason_context.csv`、`analysis.md`。
- 图表文件：`figures/natural_rate_profiles.png`、`independent_validation.png`、`forecast_2023_2033.png`；三张图均已视觉复核。
- 验证文件：`validation/independent_validation_grid.csv`、`independent_validation_summary.csv`、`quality_checks.csv`。
- 是否成功完成：yes
- 异常与备注：7/7质量检查通过。PCHIP与线性中心净方向均为冲刷，两段自然率单独外推也均为净冲刷；中心预测严格共同区净变化−889.7 m²，85.1%网格为负。218天验证的总体净面积预测接近实际，但逐点方向一致率仅34.0%；十年最大局部下切12.42 m，说明长期逐点外推风险很高。详细解释见 `notes/q4-second-subquestion-solution.md`。
