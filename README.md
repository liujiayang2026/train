# train

数学建模训练的标准人工 Process 包集合，采用 `write-cumcm-paper` V3 intake 结构整理。

## 内容

- `training-01-logistics`：电商物流网络货量预测、关停分流与网络优化（q1-q4）
- `training-02-task-pricing`：“拍照赚钱”的任务定价（q1-q4）
- `training-03-mooring-system`：系泊系统的静力响应与鲁棒优化设计（q1-q3）
- `training-04-ancient-glass`：古代玻璃制品的成分分析与鉴别（q1-q4）
- `training-05-yellow-river`：黄河水沙监测数据分析（q1-q4，q4 尚未完成）

每个目录均为独立的 process-only intake，包含题面与附件、人工建模过程、逐问入口和原项目的 legacy 快照。当前未生成或批准 `final/`。

## 目录约定

- `source/`：官方题面、附件和有来源说明的外部资料。
- `process/common/`：至少被两个问题共同使用的过程材料。
- `process/qN/`：逐问入口、候选路线、比较和人工决定。
- `process/legacy-package/`：整理前项目的完整快照，供后续 Finalizer 盘点。
- `human-process.json`：V3 intake 元数据。
- `PROCESS_GUIDE.md`：人工 Process 包填写规范。

`process/` 中的材料不是论文写作的规范最终输入；后续应由 Finalizer 形成待人工审核的 `final/`。
