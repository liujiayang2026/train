# train

数学建模训练与人工建模包的权威仓库。这里负责从题面、建模过程、路线决策一直到 `final/`、manifest 和人工审批的完整生命周期；`write-cumcm-paper` 只负责消费已批准包并写论文。

## 内容

- `training-01-logistics`：电商物流网络货量预测、关停分流与网络优化（q1-q4）
- `training-02-task-pricing`：“拍照赚钱”的任务定价（q1-q4）
- `training-03-mooring-system`：系泊系统的静力响应与鲁棒优化设计（q1-q3）
- `training-04-ancient-glass`：古代玻璃制品的成分分析与鉴别（q1-q4）
- `training-05-yellow-river`：黄河水沙监测数据分析（q1-q4，q4 尚未完成）

每个目录均为独立人工建模包，包含题面与附件、人工建模过程和逐问入口。包可处于 intake、待审核或已批准状态。前四个训练包仍保留原项目的 legacy 快照；第五题已有经人工批准的 `final/`。

## 目录约定

- `source/`：官方题面、附件和有来源说明的外部资料。
- `process/_staging/`：直播建模时暂时无法判断问题或材料角色的散落文件。
- `process/common/`：至少被两个问题共同使用的过程材料。
- `process/qN/`：逐问入口、候选路线、比较和人工决定。
- `process/legacy-package/`：整理前项目的完整快照，供后续 Finalizer 盘点。
- `human-process.json`：V3 intake 元数据。
- `PROCESS_GUIDE.md`：人工 Process 包填写规范。
- `final/`：Train Finalizer 根据已记录路线与人工决定筛选出的唯一完整写作输入；成熟且兼容的 adopted 思路文件优先从 `process/` 保真复制，不得压缩成只有结论的摘要。
- `human-package.json`：声明 final 文件、逐问证据与 provenance 的 manifest。
- `approval.json`：绑定 manifest 与整棵 final 哈希的人工审批。

`process/` 中的材料不是论文写作输入。`F:\write-cumcm-paper` 只能读取通过 `--ready-for-writing` 的批准包。

## 新建训练题

新训练包由本仓库自己的初始化器生成，不再依赖 `write-cumcm-paper` 的骨架脚本：

```powershell
python scripts/init_training_package.py training-06-short-name `
  --title "题目标题" --questions q1 q2 q3
```

生成后把官方题面和附件放入 `source/`，并在 `human-process.json` 的
`source_files` 中逐项登记。新骨架默认包含 `_staging`、分类日志、公共材料目录、
逐问 inbox/routes/comparisons/decisions，以及当前统一的 `PROCESS_GUIDE.md`。

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

过程 intake 校验仅依赖 Python 标准库；final 包 schema 校验还需要 `jsonschema`。GitHub Actions 会在推送和拉取请求中重复执行
结构检查，并对修改历史 `run-*`、人工决定、官方源文件和 legacy 快照的提交
报错；仓库启用分支保护后，可将该检查设为合并前的必需条件。

普通校验允许建模中的 `_staging` 文件继续存在，但会逐项警告。准备定稿前，必须先让 intake-organizer Agent 按内容
分类、原样移动并填写 `classification-log.md`，再运行严格检查：

```powershell
python scripts/apply_staging_classification.py <package> <plan.json>
python scripts/apply_staging_classification.py <package> <plan.json> --apply
```

第一条命令只预检 Agent 给出的分类计划，第二条才实际移动并记录文件。完成后运行：

```powershell
python scripts/validate_process_intake.py training-05-yellow-river --ready-for-finalization
```

之后由独立 Finalizer 按 `FINALIZATION_GUIDE.md` 生成 final 和 manifest，人工审核并记录决定。写作移交门禁为：

```powershell
python scripts/validate_process_intake.py training-05-yellow-river --ready-for-writing
```
