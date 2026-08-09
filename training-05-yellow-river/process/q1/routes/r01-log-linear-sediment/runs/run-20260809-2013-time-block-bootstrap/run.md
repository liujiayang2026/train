# Run record

- 日期时间：2026-08-09 20:13 +08:00
- 执行目录：`training-05-yellow-river/`
- 执行命令：`python process/q1/routes/r01-log-linear-sediment/code/analyze_question1.py --input source/attachments/附件1.xlsx --run-dir process/q1/routes/r01-log-linear-sediment/runs/run-20260809-2013-time-block-bootstrap --bootstrap-replicates 500 --seed 20260809 --canonical-block-hours 72 --block-sensitivity-hours 24 72 168`
- 代码入口/版本：`process/q1/routes/r01-log-linear-sediment/code/analyze_question1.py`；执行前 SHA-256 `9019B1230C88AEAF0C1F273A6437EFE52060655113362A4953FCEADB0FE346C0`
- 输入文件：`source/attachments/附件1.xlsx`
- 关键参数：四模型按留一年平均 `RMSE_log` 选择本次补全模型；标准预测截尾为实测含沙量 `0.5×q0.001` 至 `1.5×q0.999`；年度积分采用梯形法；每种块长500次、随机种子20260809；72小时为事先指定主块长，同时比较24/72/168小时。
- 自助口径：系数pairs bootstrap与log残差路径均按年份在真实时间轴上抽取不跨年、非循环的连续移动块；不逐行独立重采样。残差块按块内相对时间最近邻映射到缺失时刻。
- 随机种子：20260809
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；openpyxl 3.1.5
- 结果文件：未生成；脚本在自助计算完成前尚未写表
- 图表文件：不适用
- 验证文件：未生成
- 是否成功完成：no
- 异常与备注：运行记录先于执行建立。1941 run保持不变。本次在工具运行约904秒后超时；Python进程仍成为无父、无子进程的后台任务。检查确认PID 20736的可执行文件和完整命令行只对应本run，且不是Codex、shell、终端宿主或必需父子进程后，仅终止该PID。超时前没有生成结果文件；诊断记录见 `logs/timeout.txt`。此失败run永久保留且不复用；后续以等价缓存/向量化实现另建run。
