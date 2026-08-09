# 问题二完整思路与解题过程

## 1. 目标与变量

问题二要求描述 2016—2021 年水沙通量的突变性、季节性和周期性。本文使用：

```text
流量（题目中的水通量表征）：Q(t)，单位 m^3/s
含沙量：C(t)，单位 kg/m^3
沙通量：F_s(t) = Q(t) C(t)，单位 kg/s
```

日水量和日排沙量分别为：

```text
W_d = mean_d[Q(t)] × 86400                (m^3)
M_d = mean_d[F_s(t)] × 86400              (kg)
```

## 2. 输入与证据边界

代码入口为 `../code/analyze_question2.py`，输入通过 `--input` 显式指定为问题一某次运行的：

```text
process/q1/routes/<route>/runs/<run>/results/data/cleaned_hydro_timeseries.csv
```

所需字段为 `datetime`、`flow_m3s`、`sediment_used_kgm3` 和 `sediment_flux_kg_s`。若存在 `sediment_filled_flag` 与 `sediment_obs_kgm3`，脚本会把问题一模型补全占比写入 `validation/input_quality_summary.csv`。

必须把这一覆盖率与沙通量结论一并解释：问题二的插值敏感性不等于问题一含沙量模型的误差传播，补全值也不等同于实测值。

## 3. 时间尺度统一与插值敏感性

基准口径 `linear_flux_direct` 为：

1. 构造 `[2016-01-01, 2022-01-01)` 的整点小时轴；
2. 对 `Q`、`C_used` 和原时刻已经计算的 `F_s=QC_used` 分别按真实时间线性插值；
3. 在每天 24 个整点上取均值并换算日水量、日排沙量。

该口径延续历史路线，但线性插值会平滑短时峰值。为检验处理选择的影响，同一运行还计算：

- `linear_components_product`：先线性插值 `Q` 和 `C_used`，再逐小时相乘；
- `previous_flux_direct`：逐小时采用最近前值，边界处仅作必要的后向补齐。

三种口径比较六年总量、逐年总量、月份占比、汛期占比、峰值月份和突变事件重合度。证据位于：

```text
validation/interpolation_sensitivity_summary.csv
validation/interpolation_sensitivity_annual.csv
validation/interpolation_sensitivity_monthly.csv
validation/interpolation_event_overlap.csv
```

## 4. 年际与季节性

年度汇总为：

```text
W_y = Σ_d W_d
M_y = Σ_d M_d
YoY_y = (X_y - X_{y-1}) / X_{y-1}
```

月份占比以六年同月累计量除以六年总量。另逐年计算 6—10 月水量/排沙量占比及各年峰值月份，避免仅凭合并样本推断每一年都完全相同。逐年检查位于 `validation/seasonality_by_year.csv`。

`figures/monthly-mean-flow.png` 和 `figures/monthly-mean-sediment-flux.png` 分别使用 `m^3/s`、`kg/s` 纵轴。两种不同量纲不放在同一绝对值纵轴上；归一化比较图明确标记每条序列自身最大值为 100。

## 5. 突变候选识别

对日均流量和日均沙通量分别作 `log(1+x)` 变换。对日期 `t`、窗口 `w` 计算：

```text
D(t;w) = mean[X_t, ..., X_{t+w-1}]
         - mean[X_{t-w}, ..., X_{t-1}]
Z(t;w) = D(t;w) / sd(D)
score(t) = max(|Z_Q(t)|, |Z_Fs(t)|)
```

基准参数为：

```text
w = 7 日
score 阈值 = 3.0
事件最小间隔 = 20 日
最多保留 = 15 个
```

算法先保留达到阈值的日期，再按得分从高到低去簇，避免同一过程连续多日重复入选。输出应称为“突变候选”；没有外部调度或水库运行记录时，不把日期直接归因于调水调沙。

稳健性检查遍历：

```text
窗口 w ∈ {3, 7, 14}
阈值 z ∈ {2.5, 3.0, 3.5}
最小间隔 g ∈ {10, 20, 30}
```

共 27 组参数。对每组报告事件数、6—9 月占比，以及与基准事件在 ±7 日内的双向匹配率；对每个基准事件报告跨参数匹配率。文件为 `validation/abrupt_parameter_sensitivity.csv` 和 `validation/abrupt_event_stability.csv`。

## 6. 周期性

对 `log(1+x)` 日序列线性去趋势、减均值并乘 Hann 窗，然后计算离散傅里叶频谱。在 20—800 日频带内报告前 10 个峰值。另计算 7、15、30、60、90、120、180 和 365 日滞后自相关。

为检查“年尺度成分”是否依赖单一处理，`validation/periodicity_robustness.csv` 比较：

- 三种插值口径的 2016—2021 完整序列；
- 基准口径的 2016—2020 与 2017—2021 两个连续五年子区间；
- 水流量和沙通量两条序列。

300—450 日定义为年尺度频带。这是描述性稳健性检查，不是严格的周期显著性检验。样本只有六年，因此即便主峰在约 365 日，也只能表述为“存在较强年尺度周期证据”，不能证明长期稳定周期；313、438、731 日等次级峰不在缺少外部证据时作确定性物理解释。

## 7. 运行和输出

从仓库根目录执行，且每次使用一个尚未承载输出的新 run：

```powershell
python training-05-yellow-river/process/q2/routes/r01-interpolated-daily-pattern/code/analyze_question2.py `
  --input training-05-yellow-river/process/q1/routes/<route>/runs/<run>/results/data/cleaned_hydro_timeseries.csv `
  --run-dir training-05-yellow-river/process/q2/routes/r01-interpolated-daily-pattern/runs/<new-run>
```

脚本只接受本路线 `runs/` 的直接子目录，且执行前除预建 `run.md` 外不得含有其他内容。结果、图、验证、日志及运行清单全部位于指定 run 内。当前直接绑定 q1 连续时间块成功运行的可复现证据见 `../runs/run-20260809-2036-time-block-q1/`；此前运行与历史迁移运行仍原样保留。

## 8. 写作边界

- 可描述数据口径下的年际差异、月份集中、突变候选和年尺度频谱证据。
- “显著”若未附统计检验，应改成“明显”或直接报告数值差异。
- 不将算法候选日期写成已证实的调度事件。
- 不将六年频谱写成长周期稳定性的证明。
- 不隐去问题一模型补全比例，也不把插值敏感性冒充完整误差传播。
