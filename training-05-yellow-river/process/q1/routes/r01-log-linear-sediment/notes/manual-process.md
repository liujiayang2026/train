# Question 1 manual process

## Objective

记录问题一数据口径、人工复核事项与当前参考运行的证据位置；本文件不替代人工adopted决定。

## Inputs and working directory

- 题面：`source/problem/E题.pdf`
- 官方数据：`source/attachments/附件1.xlsx`
- 执行目录：训练包根目录 `training-05-yellow-river/`
- 模型说明：`question1-method.md`
- 代码：`../code/analyze_question1.py`

## Manual review completed

1. 确认目标量为2016-2021年逐年总水量与总排沙量；
2. 确认流量单位 `m^3/s`、含沙量单位 `kg/m^3`，因此瞬时输沙率为 `kg/s`；
3. 确认实测含沙量优先保留，缺失位置才使用模型值；
4. 确认四个候选模型均有代码与 `model_validation.csv` 机器证据；
5. 确认年度积分、留一年年度聚合检验、敏感性和自助法均由同一参考run生成；
6. 确认自助法的系数样本与残差路径均使用不跨年的真实时间移动块，72小时为事先指定主口径，并同时比较24/72/168小时；
7. 没有人工改写结果或排除记录。

## Current reference evidence

- Run：`../runs/run-20260809-2032-time-block-bootstrap/`
- 结果：该run的 `results/`
- 验证与诊断：该run的 `validation/`
- 环境和执行摘要：该run的 `run.md` 与 `logs/run_summary.txt`

## Handoff boundaries

- 当前路线状态仍为candidate，尚无正式采用决定；
- 约87.13%的含沙量为模型补全，年度排沙量必须与验证限制共同报告；
- 72小时主口径的基准点仅落入2/6个经验区间，且24/72/168小时结果不同；不得表述为已校准置信区间或覆盖率证据；
- 若将本序列用于时间外推回测，必须按当时可得训练窗口重拟合，不能使用全时段补全值。
