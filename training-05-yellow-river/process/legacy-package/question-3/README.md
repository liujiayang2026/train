# question 3 optimized ensemble forecast

本文件夹是问题三当前采用的主模型版本：STL 趋势残差模型与近期加权季节模板模型的交叉验证加权组合。

## How to Run

```powershell
python .\code\analyze_question3.py
```

## Main Outputs

- `code/analyze_question3.py`: 当前优化组合模型的标准运行入口。
- `code/stl_base_question3.py`: 原 STL/季节模板基础函数，供当前入口复用。
- `data/processed/predicted_daily_flux_2022_2023.csv`: 2022-2023 年逐日预测序列。
- `results/forecast_annual_flux_2022_2023.csv`: 年度预测结果。
- `results/forecast_monthly_flux_2022_2023.csv`: 月度预测结果。
- `results/sampling_plan_2022_2023.csv`: 逐日采样计划。
- `results/sampling_monthly_counts_2022_2023.csv`: 月度采样次数汇总。
- `results/sampling_schedule_2022_2023.csv`: 具体到日期和小时的采样明细。
- `results/sampling_schedule_monthly_counts_2022_2023.csv`: 按实际采样时次统计的月度次数。
- `qa/forecast_validation.csv`: 基模型与组合模型留一年验证比较。
- `qa/weight_selection.csv`: 组合权重网格搜索结果。
- `qa/model_settings.csv`: 最终模型设置。
- `figures/forecast-monthly-flux.png`: 月度水沙预测图。
- `figures/sampling-monthly-counts.png`: 月度采样次数图。
- `docs/question3-method.md`: 完整方法与解题过程。
- `docs/question3-analysis.md`: 运行结果、验证和采样方案。
- `docs/sampling-schedule-detail.md`: 按年月展开的逐次采样日期和时刻清单。
