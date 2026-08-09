# 人工 Process 包填写手册

本手册面向建模人员。人工只负责提供 `source/` 和 `process/`，不创建 `final/`。Process 可以保留多版本和废方案，但必须让每条路线的模型、代码、运行结果和验证证据能够对应起来。

## 一、目录放什么

| 目录 | 应放内容 | 不应放内容 |
|---|---|---|
| `source/problem/` | 原始题面 PDF、题目文字版、竞赛规则 | 自己的解题笔记、计算结果 |
| `source/attachments/` | 官方附件、原始数据、题目提供的图片 | 清洗后数据、程序生成结果 |
| `source/external/` | 外部数据、参数依据、参考资料及来源说明 | 无法说明来源的数值 |
| `process/README.md` | 全局时间线、各问依赖、公共冲突、当前进展 | 某一条路线的详细推导 |
| `process/_staging/` | 暂时无法判断问题、路线或来源角色的散落材料 | 已经能够确定正式归属的材料 |
| `process/common/notes/` | 两问以上共用的假设、符号、统一口径 | 单问专属假设 |
| `process/common/data/` | 多问复用的清洗数据、数据字典、清洗说明 | 官方原始附件 |
| `process/common/code/` | 多问复用的预处理、共享函数 | 某问某路线的主求解代码 |
| `process/common/results/` | 多问共同依赖的中间结果 | 某条路线的最终输出 |
| `process/common/figures/` | 多问共用的探索图、数据质量图 | 某次运行专属图 |
| `process/qN/README.md` | 本问要求、候选路线清单、已知冲突、人工决定摘要 | 完整模型推导或大段日志 |
| `process/qN/inbox/` | 已知属于本问但尚未来得及确定路线的材料 | 已明确属于某条路线的正式材料 |
| `process/qN/routes/` | 按候选解法分别保存完整证据链 | 不区分路线的混合代码与结果 |
| `process/qN/comparisons/` | 多路线同口径对比表、对比图、比较说明 | 单路线自身验证 |
| `process/qN/decisions/` | 人工明确作出的选择、否定、修改要求及理由 | 仅凭文件名暗示的“最终版” |

空目录可以保留，不要求为了填满目录制造文件。

### 暂存区怎么用

直播建模或聊天导出时，如果暂时无法判断文件属于哪一问、哪条路线或哪种来源角色，先放入 `process/_staging/`。已知属于某问但路线未定的材料直接放入该问的 `qN/inbox/`。

交给 Finalizer 前，由 intake-organizer Agent 逐个检查暂存文件内容，原样移动到 `source/`、`process/common/`、对应 `qN/inbox/` 或具体 route/run，并在 `process/_staging/classification-log.md` 追加原路径、目标路径、理由、日期和整理者。不得依据文件名中的“最终版”“new”或时间戳判断权威性，也不得把未分类文件留在 `_staging/` 中移交。

## 二、每条路线怎么放

实质不同的方案各建一个目录，例如：

```text
process/q1/routes/r01-baseline/
  route.md
  notes/
  inputs/
  model/
  code/
  runs/
    run-20260808-1430-default/
      run.md
      results/
      figures/
      validation/
      logs/
```

- `route.md`：必需。说明这条路线解决什么、使用什么数据口径、模型是什么、代码入口在哪里、有哪些运行、当前有什么缺陷。
- `notes/`：推导草稿、假设讨论、聊天纪要、未整理公式。
- `inputs/`：本路线特有的输入说明、小型参数表或指向公共数据的说明。不要重复复制大型公共数据。
- `model/`：相对稳定的模型定义、正式公式、算法流程说明。
- `code/`：本路线代码、依赖说明、入口脚本。不要混入其他路线代码。
- `runs/`：每次实际执行单独建目录。修改参数、修复代码或重新运行时新建 run，不覆盖旧结果。

如果目标函数、关键约束、数据口径、模型类型或求解方法发生实质变化，应新建 route。只调整同一模型的参数、随机种子或实现细节，则在原 route 下新建 run。

## 三、一次运行怎么放

- `run.md`：必需。记录日期、命令、代码入口、输入、参数、环境、随机种子和输出位置。
- `results/`：CSV、JSON、XLSX、MAT 等机器结果，以及必要的数据字典。
- `figures/`：本次运行生成的图；文件名应能对应结果或指标。
- `validation/`：误差、约束检查、回测、敏感性、稳健性等证据。
- `logs/`：标准输出、错误日志、求解器日志和诊断信息。

运行目录命名为 `run-YYYYMMDD-HHMM-label`。不得使用 `latest`、`new`、`最终版` 作为权威标记。

## 四、可复制模板

### route.md

```markdown
# Route r01-baseline

- 对应问题：q1
- 过程状态：candidate | abandoned | uncertain
- 要回答的内容：
- 输入与数据口径：
- 核心模型/算法：
- 关键公式位置：
- 代码入口：
- 关联运行：
- 与其他问题/路线的关系：
- 当前优点：
- 已知缺陷或冲突：
- 放弃时的原因：
```

过程状态只是人工当时的记录，不等于 Finalizer 的最终采用结论。

### run.md

```markdown
# Run record

- 日期时间：
- 执行目录：
- 执行命令：
- 代码入口/版本：
- 输入文件：
- 关键参数：
- 随机种子：不适用 | 具体数值
- 环境/依赖：
- 结果文件：
- 图表文件：
- 验证文件：
- 是否成功完成：yes | no | partial
- 异常与备注：
```

### decisions/dNN-short-title.md

```markdown
# Human decision

- 日期：
- 涉及问题：
- 涉及路线/run：
- 决定：
- 理由：
- 对结果或后续问题的影响：
- 决定人：
```

### comparisons/compare-short-title.md

```markdown
# Route comparison

- 比较目的：
- 参与路线及 run：
- 统一输入和指标：
- 对比表/图文件：
- 可比性限制：
- 观察结论：
- 尚未解决的问题：
```

## 五、移交前最低检查

- 每问都有 `process/qN/README.md`。
- 每条已形成的路线都有规范命名的目录和非空 `route.md`。
- 每次被引用的运行都有 `run.md`，代码、结果、图、验证没有串到其他 run。
- 废方案和失败运行没有删除，失败原因有记录。
- 重要人工选择已经写入 `decisions/`，而不是只存在于聊天中。
- 题目原始材料仍在 `source/`，没有被清洗结果覆盖。
- `_staging/` 中只剩 `README.md` 和 `classification-log.md`，所有移动均已留痕。
- 没有人工创建 `final/`；把完整包交给 Finalizer Skill 即可。

移交前在 `train` 仓库根目录运行：

```powershell
python scripts/validate_process_intake.py <package> --ready-for-finalization
```
