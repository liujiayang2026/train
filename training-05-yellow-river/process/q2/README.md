# Q2 process index

- Question requirement: 分析2016—2021年水沙通量的突变性、季节性和周期性，研究其变化规律。
- Current candidate route: `routes/r01-interpolated-daily-pattern/`，以问题一清洗序列为输入，构造小时/日尺度序列并进行季节、突变和频谱分析。
- Current reproduced evidence: `routes/r01-interpolated-daily-pattern/runs/run-20260809-2036-time-block-q1/`。该运行直接绑定 q1 的 2032 连续时间块成功运行，使用规范输入/输出路径，并附插值、突变参数及周期结论的稳健性检查。此前的 1940、1954 运行继续保留，分别记录历史 q1 输入与上一版 q1 canonical 输入的复现证据。
- Historical evidence: `routes/r01-interpolated-daily-pattern/runs/run-20260809-0000-imported-legacy/` 保留为迁移证据，状态仍为 `partial`，不由新运行覆盖。
- Known limitations: 沙通量继承问题一大量模型补全的含沙量；小时插值会改变洪峰形态；六年频谱只能支持有限样本内的年尺度证据；日序列不应未经时间隔离直接充当第三问预测的真实标签。
- Explicit human decisions: 尚无采用或否决本路线的正式人工决定。新增成功运行只提高可复现性，不代表 adopted。

每条路线的模型、代码、运行、结果、图表、验证与日志均保存在路线内部。旧导入材料和后续成功 run 并存，便于追溯；“当前证据”不等于人工 adopted 决定。
