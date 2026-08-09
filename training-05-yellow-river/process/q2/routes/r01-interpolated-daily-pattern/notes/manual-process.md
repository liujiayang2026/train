# Question 2 Manual Process

## Objective

检查问题二的路径、统计口径、图表单位和证据边界，使路线能够在规范 run 中复现，同时保留 candidate 状态。

## Completed review

1. 确认输入来自问题一某次运行的 `cleaned_hydro_timeseries.csv`，运行命令必须显式记录该路径。
2. 将全部生成物限定到同一个新 run，旧的 imported-legacy run 保持不变。
3. 明确基准小时线性插值，并增加“分量插值后相乘”“前值保持”两种对照。
4. 把突变规则补全为窗口、阈值、最小间隔和最多事件数四个参数，遍历 27 组组合。
5. 用完整六年序列和前后两个连续五年子区间检查年尺度频谱结论。
6. 把绝对流量与绝对沙通量拆成不同单位的图；归一化图仅比较形状。
7. 删除“显著增加”“稳定周期”“调水调沙相关”等超出现有证据的确定性措辞。

## Outputs checked

- 方法说明：`question2-method.md`
- 路线分析索引：`question2-analysis.md`
- 代码：`../code/analyze_question2.py`
- 当前复现运行：`../runs/run-20260809-2036-time-block-q1/`

## Remaining limitations

- 问题一含沙量模型补全的不确定性尚未端到端传播到问题二。
- 突变候选没有外部事件表进行真值核验。
- 六年长度限制了低频和长期周期判断。
- 尚无人工采用或否决决定。
