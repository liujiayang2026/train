# train

数学建模训练的标准人工 Process 包集合，采用 `write-cumcm-paper` V3 intake 结构整理。

## 内容

- `training-01-logistics`：电商物流网络货量预测、关停分流与网络优化（q1-q4）
- `training-02-task-pricing`：“拍照赚钱”的任务定价（q1-q4）
- `training-03-mooring-system`：系泊系统的静力响应与鲁棒优化设计（q1-q3）
- `training-04-ancient-glass`：古代玻璃制品的成分分析与鉴别（q1-q4）
- `training-05-yellow-river`：黄河水沙监测数据分析（q1-q4，q4 尚未完成）

每个目录均为独立的 process-only intake，包含题面与附件、人工建模过程和逐问入口。前四个训练包仍保留原项目的 legacy 快照；第五题已把历史材料迁入正式的 `qN/routes/` 与 `qN/inbox/`。当前未生成或批准 `final/`。

## 目录约定

- `source/`：官方题面、附件和有来源说明的外部资料。
- `process/common/`：至少被两个问题共同使用的过程材料。
- `process/qN/`：逐问入口、候选路线、比较和人工决定。
- `process/legacy-package/`：整理前项目的完整快照，供后续 Finalizer 盘点。
- `human-process.json`：V3 intake 元数据。
- `PROCESS_GUIDE.md`：人工 Process 包填写规范。

`process/` 中的材料不是论文写作的规范最终输入；后续应由 Finalizer 形成待人工审核的 `final/`。

## 团队协作与自动校验

仓库根目录的 `AGENTS.md` 规定了边做题边归档的统一流程。新模型先建立
`route.md`，同一模型的每次实际运行分别写入不可覆盖的 `run-*` 目录；原始
`source/` 和 `process/legacy-package/` 视为受保护材料。

提交前在仓库根目录运行：

```powershell
python scripts/validate_process_intake.py
```

也可以只检查一个训练包：

```powershell
python scripts/validate_process_intake.py training-05-yellow-river
```

校验器仅依赖 Python 标准库。GitHub Actions 会在推送和拉取请求中重复执行
结构检查，并对修改历史 `run-*`、人工决定、官方源文件和 legacy 快照的提交
报错；仓库启用分支保护后，可将该检查设为合并前的必需条件。
