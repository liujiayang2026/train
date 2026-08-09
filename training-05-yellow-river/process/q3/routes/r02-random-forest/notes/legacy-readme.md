# q3 random forest forecast

本文件夹是问题三的随机森林对照版本，独立于 `question-3` 原有 STL 组合预测版本。

## How to Run

```powershell
python .\code\random_forest_question3.py
```

脚本读取 `..\question-2\data\processed\daily_flux_series.csv`，输出 2022-2023 年逐日预测、年度/月度汇总、采样计划、验证表和 PNG 图件。

## Main Outputs

- `code/random_forest_question3.py`: 纯 NumPy 实现的随机森林回归脚本。
- `data/processed/rf_predicted_daily_flux_2022_2023.csv`: 2022-2023 年逐日预测序列。
- `results/rf_forecast_annual_flux_2022_2023.csv`: 年度水量、输沙量预测结果。
- `results/rf_forecast_monthly_flux_2022_2023.csv`: 月度水沙预测结果。
- `results/rf_sampling_plan_2022_2023.csv`: 逐日采样安排。
- `results/rf_sampling_monthly_counts_2022_2023.csv`: 月度采样次数汇总。
- `qa/rf_forecast_validation.csv`: 留一年交叉验证误差。
- `qa/rf_feature_importance.csv`: 置换重要性结果。
- `figures/rf-forecast-monthly-flux.png`: 月度水沙预测图。
- `figures/rf-sampling-monthly-counts.png`: 月度采样次数图。
- `docs/q3-random-forest-analysis.md`: 随机森林模型说明、结果和简要评价。

## Current Conclusion

随机森林版本可作为成熟机器学习方法的对照实验，但从留一年验证看，效果弱于前面的 STL 组合预测和近期加权季节模板。主要原因是训练数据只有 2016-2021 年，随机森林不擅长外推趋势，递归预测时滞后特征还会放大误差。因此，正式论文中更适合将随机森林作为比较模型，不建议替代原问题三主模型。
