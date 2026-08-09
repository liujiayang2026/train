# question 3 optimized ensemble forecast

本文件夹是问题三当前采用的主模型版本：变点后的 Fourier 月尺度模型与 STL/近期季节模板的交叉验证加权组合。月尺度负责两年趋势外推，日尺度负责采样风险分配。

## How to Run

```powershell
python .\code\regime_aware_question3.py
```

## Main Outputs

- `code/regime_aware_question3.py`: 当前变点感知混合模型的标准运行入口。
- `code/analyze_question3.py`: 上一版 STL/季节模板组合模型，保留用于对照。
- `code/stl_base_question3.py`: 原 STL/季节模板基础函数，供当前入口复用。
- `data/processed/predicted_daily_flux_2022_2023.csv`: 2022-2023 年逐日预测序列。
- `results/forecast_annual_flux_2022_2023.csv`: 年度预测结果。
- `results/forecast_monthly_flux_2022_2023.csv`: 月度预测结果。
- `results/history_forecast_monthly_comparison.csv`: 2016-2021 历史值与 2022-2023 预测值连续对照数据。
- `results/sampling_plan_2022_2023.csv`: 逐日采样计划。
- `results/sampling_monthly_counts_2022_2023.csv`: 月度采样次数汇总。
- `results/sampling_schedule_2022_2023.csv`: 具体到日期和小时的采样明细。
- `results/sampling_schedule_monthly_counts_2022_2023.csv`: 按实际采样时次统计的月度次数。
- `qa/forecast_validation.csv`: 2019-2021 月尺度滚动验证及模型比较。
- `qa/monthly_validation_actual_vs_predicted.csv`: 月尺度实际值、预测值与经验区间。
- `qa/historical_backtest_2018_2021.csv`: 严格按时间顺序得到的 2018-2021 月度实际值与预测值。
- `qa/historical_backtest_metrics_2018_2021.csv`: 2018-2021 各年的回测误差指标。
- `qa/weight_selection.csv`: Fourier 与原组合模型的权重搜索结果。
- `qa/structural_change_detection.csv`: 年均水沙状态及 2018 年变点识别结果。
- `qa/recent_regime_sensitivity.csv`: 最新年型权重 40%/60%/80% 的峰谷敏感性。
- `qa/model_settings.csv`: 最终模型设置。
- `figures/forecast-monthly-flux.png`: 月度水沙预测图。
- `figures/regime-hybrid-monthly-validation.png`: 2019-2021 月尺度滚动验证图。
- `figures/history-vs-forecast-monthly.png`: 历史水沙过程与未来预测连续对照图。
- `figures/historical-backtest-2018-2021.png`: 2018-2021 历史实际值与无数据泄漏预测值对照图。
- `figures/sampling-monthly-counts.png`: 月度采样次数图。
- `docs/question3-method.md`: 完整方法与解题过程。
- `docs/question3-analysis.md`: 运行结果、验证和采样方案。
- `docs/sampling-schedule-detail.md`: 按年月展开的逐次采样日期和时刻清单。
