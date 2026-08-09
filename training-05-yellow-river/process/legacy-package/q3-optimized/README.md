# q3 optimized ensemble forecast

本文件夹是问题三的优化组合预测版本，独立于 `question-3` 原 STL 版本和 `q3` 随机森林版本。

## How to Run

```powershell
python .\code\optimized_question3.py
```

## Main Outputs

- `code/optimized_question3.py`: STL 与近期加权季节模板的交叉验证加权组合脚本。
- `data/processed/optimized_predicted_daily_flux_2022_2023.csv`: 2022-2023 年逐日预测序列。
- `results/optimized_forecast_annual_flux_2022_2023.csv`: 年度预测结果。
- `results/optimized_forecast_monthly_flux_2022_2023.csv`: 月度预测结果。
- `results/optimized_sampling_plan_2022_2023.csv`: 逐日采样计划。
- `qa/optimized_forecast_validation.csv`: 基模型与组合模型留一年验证比较。
- `qa/optimized_weight_selection.csv`: 组合权重网格搜索结果。
- `figures/optimized-forecast-monthly-flux.png`: 月度水沙预测图。
- `figures/optimized-sampling-monthly-counts.png`: 月度采样次数图。
- `docs/optimized-question3-analysis.md`: 中文方法、结果和结论说明。
