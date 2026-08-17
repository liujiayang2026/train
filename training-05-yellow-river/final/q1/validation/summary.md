# Q1 年度排沙端到端验证与敏感性说明

## 验证对象

验证链为：实测水位/流量与稀疏含沙量 → 含沙量模型 → 缺失值补全 → Q×C → 梯形年度积分。水量积分不依赖含沙量模型。

## 留一年年度聚合检验

每次完全排除目标年份的含沙量观测后拟合，再在该年份所有实测含沙量时刻预测，并在同一稀疏时间网格上分别积分实测 Q×C 与预测 Q×C。这避免了目标年份浓度进入拟合，但稀疏网格不等于完整年度真值。

| heldout_year | observed_records | grid_start          | grid_end            | observed_grid_mass_1e4_t | predicted_grid_mass_1e4_t | signed_error_pct | flux_wape_pct |
| ------------ | ---------------- | ------------------- | ------------------- | ------------------------ | ------------------------- | ---------------- | ------------- |
| 2016         | 372              | 2016-01-01 00:00:00 | 2016-12-31 08:00:00 | 1823.72                  | 2490.79                   | 36.5778          | 46.0008       |
| 2017         | 371              | 2017-01-01 00:00:00 | 2017-12-31 08:00:00 | 1907.21                  | 2628.7                    | 37.8301          | 41.2319       |
| 2018         | 431              | 2018-01-01 00:00:00 | 2018-12-31 08:00:00 | 29451                    | 25771.5                   | -12.4936         | 58.2748       |
| 2019         | 403              | 2019-01-01 00:00:00 | 2019-12-31 08:00:00 | 30576.5                  | 29258.4                   | -4.3109          | 35.2809       |
| 2020         | 320              | 2020-01-01 00:00:00 | 2020-12-31 08:00:00 | 35279.8                  | 35547.7                   | 0.759563         | 28.8539       |
| 2021         | 257              | 2021-01-01 00:00:00 | 2021-12-31 08:00:00 | 22843.3                  | 35011.7                   | 53.2694          | 71.4854       |

## 完整年度敏感性

逐年比较四模型、预测截尾边界以及排除目标年份训练三类扰动。`all_scenarios_max_abs_change_pct` 是列入场景相对基准的最大绝对变化，并非概率区间。

| year | baseline_sediment_mass_1e4_t | all_scenarios_min_1e4_t | all_scenarios_max_1e4_t | all_scenarios_max_abs_change_pct | candidate_model_max_abs_change_pct | prediction_clip_max_abs_change_pct | training_window_max_abs_change_pct |
| ---- | ---------------------------- | ----------------------- | ----------------------- | -------------------------------- | ---------------------------------- | ---------------------------------- | ---------------------------------- |
| 2016 | 2322.85                      | 2322.85                 | 2402.58                 | 3.43247                          | 3.43247                            | 0                                  | 2.96481                            |
| 2017 | 2351.51                      | 2141.34                 | 3081.09                 | 31.0258                          | 31.0258                            | 0                                  | 6.21747                            |
| 2018 | 27797.7                      | 16477.1                 | 27797.7                 | 40.7248                          | 40.7248                            | 0                                  | 3.95671                            |
| 2019 | 30144.6                      | 20410.2                 | 30144.6                 | 32.2924                          | 32.2924                            | 0                                  | 2.34053                            |
| 2020 | 36032                        | 32001.9                 | 37080.6                 | 11.1847                          | 11.1847                            | 0                                  | 2.37431                            |
| 2021 | 32735                        | 30952.4                 | 41019.8                 | 25.3088                          | 25.3088                            | 0                                  | 3.95135                            |

## 自助法不确定性

预先指定 72 小时为主块长，每个块长各运行 500 次，随机种子 20260809。系数的pairs bootstrap按年份从原始实测记录的真实时间轴抽取不跨年、非循环的连续移动块，按块拼接到原年份样本量；没有逐行独立重采样。每次重新拟合后，在原始实测时刻计算中心化log残差；目标年份按同样时长划分日历块，从同一年抽源残差块，并按块内相对时间最近邻映射到缺失时刻。

| year | baseline_sediment_mass_1e4_t | bootstrap_median_1e4_t | bootstrap_p2_5_1e4_t | bootstrap_p97_5_1e4_t | relative_half_width_pct | baseline_inside_interval | bootstrap_replicates | random_seed | time_block_hours | pairs_resampling                    | residual_resampling                                         | is_canonical |
| ---- | ---------------------------- | ---------------------- | -------------------- | --------------------- | ----------------------- | ------------------------ | -------------------- | ----------- | ---------------- | ----------------------------------- | ----------------------------------------------------------- | ------------ |
| 2016 | 2322.85                      | 2149.44                | 1935.64              | 2451.1                | 11.0955                 | True                     | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2017 | 2351.51                      | 2100.81                | 1971.61              | 2250.3                | 5.9257                  | False                    | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2018 | 27797.7                      | 33973.1                | 28820.1              | 41158.9               | 22.194                  | False                    | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2019 | 30144.6                      | 38249.5                | 32804.1              | 46374.7               | 22.5092                 | False                    | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2020 | 36032                        | 45443                  | 39201.8              | 52719.4               | 18.7577                 | False                    | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2021 | 32735                        | 31544.8                | 26380.9              | 37312.4               | 16.6968                 | True                     | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |

以上是当前模型内的经验百分位区间，不是覆盖所有误差源的置信区间。

## 块长敏感性

预先要求比较 24, 72, 168 小时；72小时不是查看结果后选出的最窄区间。

| year | baseline_sediment_mass_1e4_t | bootstrap_median_1e4_t | bootstrap_p2_5_1e4_t | bootstrap_p97_5_1e4_t | relative_half_width_pct | baseline_inside_interval | bootstrap_replicates | random_seed | time_block_hours | pairs_resampling                    | residual_resampling                                         | is_canonical |
| ---- | ---------------------------- | ---------------------- | -------------------- | --------------------- | ----------------------- | ------------------------ | -------------------- | ----------- | ---------------- | ----------------------------------- | ----------------------------------------------------------- | ------------ |
| 2016 | 2322.85                      | 2192.45                | 2038.05              | 2372.78               | 7.20512                 | True                     | 500                  | 20260809    | 24               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2017 | 2351.51                      | 2105.88                | 2017.22              | 2197.83               | 3.84035                 | False                    | 500                  | 20260809    | 24               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2018 | 27797.7                      | 34747.7                | 30783.8              | 38973.6               | 14.7312                 | False                    | 500                  | 20260809    | 24               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2019 | 30144.6                      | 39460.7                | 35398.2              | 44056.4               | 14.3612                 | False                    | 500                  | 20260809    | 24               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2020 | 36032                        | 46353.5                | 42084.2              | 51536.1               | 13.116                  | False                    | 500                  | 20260809    | 24               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2021 | 32735                        | 32598.3                | 29100.6              | 36265.5               | 10.9438                 | True                     | 500                  | 20260809    | 24               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2016 | 2322.85                      | 2149.44                | 1935.64              | 2451.1                | 11.0955                 | True                     | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2017 | 2351.51                      | 2100.81                | 1971.61              | 2250.3                | 5.9257                  | False                    | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2018 | 27797.7                      | 33973.1                | 28820.1              | 41158.9               | 22.194                  | False                    | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2019 | 30144.6                      | 38249.5                | 32804.1              | 46374.7               | 22.5092                 | False                    | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2020 | 36032                        | 45443                  | 39201.8              | 52719.4               | 18.7577                 | False                    | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2021 | 32735                        | 31544.8                | 26380.9              | 37312.4               | 16.6968                 | True                     | 500                  | 20260809    | 72               | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | True         |
| 2016 | 2322.85                      | 2096.11                | 1817.95              | 2540.77               | 15.5588                 | True                     | 500                  | 20260809    | 168              | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2017 | 2351.51                      | 2072.44                | 1900.84              | 2288.47               | 8.24223                 | False                    | 500                  | 20260809    | 168              | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2018 | 27797.7                      | 33305.2                | 26559                | 42558.5               | 28.7784                 | True                     | 500                  | 20260809    | 168              | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2019 | 30144.6                      | 37733.8                | 30762.2              | 48813.1               | 29.9405                 | False                    | 500                  | 20260809    | 168              | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2020 | 36032                        | 43846.5                | 37249.2              | 53763.1               | 22.9157                 | False                    | 500                  | 20260809    | 168              | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |
| 2021 | 32735                        | 29908                  | 24558.5              | 36865.8               | 18.7984                 | True                     | 500                  | 20260809    | 168              | within-year moving real-time blocks | within-year moving real-time blocks mapped by relative time | False        |

## 时间块诊断

每个候选块都由同一年真实时间窗口 `[start, start+B)` 内按时间排序的实测记录组成，不在年末循环回卷。记录数因原始采样不等间隔而自然变化。

| time_block_hours | is_canonical | year | observed_records | candidate_blocks | records_per_block_min | records_per_block_median | records_per_block_max | block_scope                               |
| ---------------- | ------------ | ---- | ---------------- | ---------------- | --------------------- | ------------------------ | --------------------- | ----------------------------------------- |
| 24               | False        | 2016 | 372              | 371              | 1                     | 1                        | 2                     | non-circular within-year real-time window |
| 24               | False        | 2017 | 371              | 370              | 1                     | 1                        | 2                     | non-circular within-year real-time window |
| 24               | False        | 2018 | 431              | 430              | 1                     | 1                        | 6                     | non-circular within-year real-time window |
| 24               | False        | 2019 | 403              | 402              | 1                     | 1                        | 5                     | non-circular within-year real-time window |
| 24               | False        | 2020 | 320              | 319              | 1                     | 1                        | 7                     | non-circular within-year real-time window |
| 24               | False        | 2021 | 257              | 256              | 1                     | 1                        | 8                     | non-circular within-year real-time window |
| 72               | True         | 2016 | 372              | 369              | 3                     | 3                        | 4                     | non-circular within-year real-time window |
| 72               | True         | 2017 | 371              | 368              | 3                     | 3                        | 4                     | non-circular within-year real-time window |
| 72               | True         | 2018 | 431              | 428              | 3                     | 3                        | 13                    | non-circular within-year real-time window |
| 72               | True         | 2019 | 403              | 400              | 2                     | 3                        | 11                    | non-circular within-year real-time window |
| 72               | True         | 2020 | 320              | 318              | 1                     | 3                        | 12                    | non-circular within-year real-time window |
| 72               | True         | 2021 | 257              | 255              | 1                     | 3                        | 17                    | non-circular within-year real-time window |
| 168              | False        | 2016 | 372              | 365              | 7                     | 7                        | 9                     | non-circular within-year real-time window |
| 168              | False        | 2017 | 371              | 364              | 7                     | 7                        | 9                     | non-circular within-year real-time window |
| 168              | False        | 2018 | 431              | 424              | 7                     | 7                        | 25                    | non-circular within-year real-time window |
| 168              | False        | 2019 | 403              | 396              | 6                     | 7                        | 19                    | non-circular within-year real-time window |
| 168              | False        | 2020 | 320              | 315              | 2                     | 7                        | 20                    | non-circular within-year real-time window |
| 168              | False        | 2021 | 257              | 254              | 2                     | 7                        | 21                    | non-circular within-year real-time window |

## 解释边界

- 自助区间只反映当前二次水动力模型下、所列移动时间块口径中的训练样本与残差补全不确定性。
- 未纳入流量/水位仪器误差、模型族选择、长时间相关结构及未观测洪峰的系统偏差。
- 最近邻映射保持了源块内残差的时间次序和经验取值，但稀疏实测无法恢复块内未观测的连续残差轨迹。
- 因 87% 左右含沙量由模型补全，年度排沙量应连同区间、场景敏感性和上述限制一起报告。
- 相关系数仅为描述性统计；没有显著性或因果识别证据时，不使用“显著影响”措辞。
