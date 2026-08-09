# Question 1 legacy README handoff

该文件由旧目录README迁入。旧绝对路径和旧解释器命令已失效，历史执行状态见 `../runs/run-20260809-0000-imported-legacy/run.md`，不要据旧文件名推断正式采用。

从训练包根目录运行当前代码，并为每次执行提供一个新的 `run-*` 目录：

```powershell
python process/q1/routes/r01-log-linear-sediment/code/analyze_question1.py `
  --input source/attachments/附件1.xlsx `
  --run-dir process/q1/routes/r01-log-linear-sediment/runs/run-YYYYMMDD-HHMM-label `
  --bootstrap-replicates 500 `
  --seed 20260809 `
  --canonical-block-hours 72 `
  --block-sensitivity-hours 24 72 168
```

当前成功参考运行是 `../runs/run-20260809-2032-time-block-bootstrap/`。旧版7条记录块运行 `../runs/run-20260809-1941-canonical-uncertainty/` 只作历史证据，不再作为当前不确定性口径。参考运行的主要输出为：

- `results/data/cleaned_hydro_timeseries.csv`：清洗后的水位、流量、实测/拟合含沙量和输沙率序列；
- `results/tables/annual_flux_estimates.csv`：逐年总水量与总排沙量；
- `results/tables/monthly_relationship_summary.csv`：月度关系汇总；
- `validation/model_validation.csv`：四个已实现模型的留一年比较；
- `validation/annual_flux_holdout_validation.csv`：留一年稀疏观测网格年度输沙检验；
- `validation/annual_sensitivity_*.csv`：模型、截尾和训练窗口敏感性；
- `validation/annual_sediment_uncertainty.csv`：模型内自助法年度区间；
- `validation/bootstrap_block_length_sensitivity.csv`：24/72/168小时块长敏感性；
- `validation/bootstrap_time_block_diagnostics.csv`：逐年真实时间候选块诊断；
- `validation/validation_summary.md`：验证定义和解释边界。
