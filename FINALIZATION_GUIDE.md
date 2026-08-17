# Train 人工建模包定稿与审批规范（V3）

## 职责边界

完整链路固定为：

```text
人工提供 source/ + process/
→ Finalizer Agent 盘点、比较、取舍并生成 final/
→ 人工审核 final/
→ 新的 Paper-writing Agent 只读已批准 final/
→ 生成论文
```

`F:\train` 对 `source/`、`process/`、`final/`、manifest 和审批记录负全责。Finalizer 不得批准自己的输出。论文写作 Agent 必须是未参与 finalization 的新 Agent，且不得读取 `process/` 来补写、改选或覆盖已批准结论。

## 生命周期与目录

```text
human-model-package/
  README.md
  human-process.json           # 人工 intake 元数据
  source/                      # 原始输入或输入说明
  process/                     # 全部探索过程，可杂乱、多版本、有废案
  final/                       # Finalizer 生成，intake 阶段不存在
    README.md
    common/
      assumptions.md
      notation.md
      dependency-map.md
      decision-log.md
    q1/
      solution.md
      code/
      results/
      figures/
      validation/
  human-package.json           # Finalizer 生成的规范 manifest
  approval.json                # pending / approved / rejected，绑定哈希
```

状态含义：

- `intake`：只有人工过程材料，尚未生成 final。
- `needs_decision`：存在会改变模型、数值或结论的冲突，等待人工选择。
- `ready_for_review`：Finalizer 已形成唯一、内部一致的 final，等待人工审核。
- `approved` / `rejected`：人工对当前哈希版本作出的决定，保存在 `approval.json`。

## 人工 process 分层规范

人工包采用“问题 → 候选路线 → 路线运行”的分层。不要采用全局 `code/`、`results/`、`figures/` 大仓库，因为那会切断模型、代码和结果之间的对应关系。

本仓库初始化器把 `templates/PROCESS_GUIDE.md` 复制为包根目录的 `PROCESS_GUIDE.md`。该手册包含逐目录用途、route/run/decision/comparison 模板和定稿前检查表。

```text
human-model-package/
  human-process.json
  README.md
  source/
    problem/                    # 题面、题目文字版、规则说明
    attachments/                # 官方附件和数据
    external/                   # 明确注明来源的外部资料或参数依据
  process/
    README.md                   # 全局时间线、问题依赖、已知冲突
    _staging/                   # 上游临时暂存；移交时必须只剩控制文件
    common/                     # 至少被两问共同使用的材料
      README.md
      notes/                    # 公共假设、统一口径、公共符号草稿
      data/                     # 公共清洗数据及数据说明
      code/                     # 公共预处理或共享函数
      results/                  # 公共中间结果
      figures/                  # 公共过程图
    q1/
      README.md                 # 本问入口、路线清单、冲突和人工决定摘要
      inbox/                    # 尚未分类的临时材料，不表示采用
      routes/
        r01-baseline/
          route.md              # 路线说明，必需
          notes/                # 推导、假设、公式草稿、讨论记录
          inputs/               # 本路线输入说明或引用，不复制公共大文件
          model/                # 模型定义、公式、算法说明
          code/                 # 本路线代码及入口说明
          runs/
            run-20260808-1430-default/
              run.md            # 命令、环境、代码入口、输入、参数、随机种子
              results/          # 该次运行的机器结果
              figures/          # 该次运行生成的过程图表
              validation/       # 检验结果、误差、可行性或稳健性证据
              logs/             # stdout、错误和诊断日志
        r02-alternative/ ...
      comparisons/              # 路线间同口径对比，不属于任何单一路线
      decisions/                # 人工明确作出的选择、否定和理由
    q2/ ...
```

### 最低必需内容

人工不需要为了“看起来完整”创建空文件。每问只强制保留 `README.md`、`inbox/`、`routes/`、`comparisons/` 和 `decisions/`。真正形成一条思路后，再创建 `routes/rNN-short-name/`；每条路线只有 `route.md` 是必需文件，其余子目录按实际材料创建。

`route.md` 至少说明：

- 路线要回答什么；
- 输入数据和口径；
- 核心模型或算法；
- 关键公式或公式文件；
- 代码入口；
- 对应运行目录；
- 当前已知优点、缺陷和冲突；
- 人工当时认为它是 `candidate`、`abandoned` 还是 `uncertain`。该标记只是过程记录，Finalizer 仍须独立核验。

每个实际运行使用独立 `runs/run-YYYYMMDD-HHMM-label/`，不得覆盖旧结果。`run.md` 至少记录执行命令、代码入口、输入、关键参数和输出位置；使用随机算法时必须记录随机种子。结果、图、验证和日志放在同一次 run 内，避免不同运行互相串用。

### 命名与归档规则

- 路线目录使用 `r01-short-name`、`r02-short-name`；编号只表示出现顺序，不表示优先级。
- 运行目录使用 `run-YYYYMMDD-HHMM-label`；不得使用 `latest`、`new`、`最终版` 作为权威标记。
- 模型、目标函数、关键约束、数据口径或求解方法发生实质变化时，新建 route；仅修复代码或调整同一模型参数时，在原 route 下新建 run。
- 人工明确决定放入 `decisions/dNN-short-title.md`，写清决定、理由、影响问题和日期。聊天中的一句话或文件名不算正式决定。
- 路线之间的统一指标对比放入 `comparisons/`，并注明参与比较的 route 和 run。
- 废案不删除、不搬出原 route；在 `route.md` 记录失败原因。`inbox/` 允许临时杂乱，但交给 Finalizer 前尽量在本问 README 中说明其来源和可能归属。
- 只有被两问以上复用的材料才能进入 `common/`；本问专属数据、代码和结果必须留在对应 route，防止跨问误用。

## Finalizer 工作流

1. 先运行 `python scripts/validate_process_intake.py <package-root> --ready-for-finalization`。只有无错误时才能继续；缺少 `_staging` 控制文件或仍有未分类文件时，由 `train` 内的 intake-organizer 整理，写作端不得代为分类。
2. 读取 `human-process.json`，盘点 `source/` 和已经分类的完整 `process/`；不得只看文件名中的 `new`、`v2`、日期或“最终”。
3. 按问题建立候选矩阵，至少记录路线、输入、模型、代码、结果、图表、验证证据、相互依赖和可复现性。
4. 将每条过程路线或材料分类为：
   - `adopted`：构成最终答案的主路线；
   - `supporting`：与主路线兼容并提供推导、验证或解释；
   - `rejected`：已证伪、不满足题意或证据不足；
   - `superseded`：被后续同一路线版本替代；
   - `unresolved`：材料不足以安全决定。
5. 比较真实证据：题意匹配、输入口径、公式与代码一致性、机器结果、验证强度、跨问题依赖和复现记录。文件名新旧只能作为线索，不能作为决定依据。
6. 只融合兼容组件。例如，同一模型的完整推导、最终代码和一致结果可以互补；目标函数不同、约束口径不同、数据版本不同或结果互相冲突的路线不得拼接。
7. 对每个 final 文件记录至少一个 `process/` 来源。`human-package.json` 中的 provenance 必须覆盖每一个 final 文件，且不能把 process 文件声明为论文证据。对 adopted/supporting 路线中已经完整、正确且彼此兼容的思路、推导和解题文档，优先原样复制到 `final/<question-id>/`，不要为了“统一口吻”重新压缩改写。
8. 把所有采用、支持、拒绝、替代和未决路线写入 `final/common/decision-log.md`。拒绝或替代路线的旧模型名、旧口径和危险旧数值，同时写入对应 `solution.md` 的“14 写作禁区”。废案保留在 `process/`，不删除。
9. 若冲突会改变模型、结果或结论，设置 `finalization_status=needs_decision`，列出 `unresolved_decisions` 和逐问 `unresolved` 路线，停止并请求人工决定；不得猜测，也不得批准。
10. 无实质冲突时设置 `finalization_status=ready_for_review`，运行结构校验，再用 `scripts/review_human_package.py --pending` 生成待审核记录，然后停止。不得继续写论文。

## final 的内容要求

每问只能有一个 `final/<question-id>/solution.md`，依次包含：

1. 题目要求
2. 直接答案
3. 与其他问题的关系
4. 数据与输入
5. 假设
6. 变量与符号
7. 模型选择及理由
8. 模型建立与公式
9. 求解过程
10. 最终结果
11. 图表与论文位置
12. 验证
13. 局限
14. 写作禁区

“求解过程”必须把数据进入模型、参数确定、算法执行和输出产生连成完整链条。“最终结果”必须与声明的机器结果一致。“写作禁区”必须明确列出被拒绝/替代的路线、旧数值、错误口径及容易混淆的解释。

### 完整思路保真规则

`final/` 是筛选后的完整写作材料，不是过程摘要。Finalizer 的职责是判断哪些材料权威、兼容并可交给写作端，不是把成熟思路重新缩写一遍。

- adopted 路线已有完整的问题分析、公式推导、算法说明、参数确定、求解步骤、结果解释或局限讨论时，可以并应优先逐字节复制到 `final/<question-id>/full-solution.md`、`reasoning/` 或其他清晰命名的 final 文件。
- `solution.md` 可以自身包含全部细节，也可以作为权威总入口，组织直接答案、统一口径、跨问关系、结果和写作禁区，并明确指出同问中的完整思路文件。无论采用哪种形式，写作端仅阅读 final 就必须能够恢复完整论证链。
- 不得只写“采用某模型并得到某结果”式摘要，也不得用几段重新概括的文字替代 process 中已有的完整推导。仅有结论、没有参数如何确定、算法如何执行、结果如何产生的 final 不得进入 `ready_for_review`。
- 原样复制只适用于已采用或作为 supporting 且与最终口径兼容的材料。若原文件混有废案、冲突数值或草稿指令，应保留正确部分的完整细节并做有记录的整理，不能整份盲拷。
- 所有复制或整理后的完整思路文件都必须列入 `human-package.json` 的问题材料并具有逐文件 provenance。仅在 provenance 中指向 process 不够，因为写作 Agent 永远不得读取 `process/`。
- Finalizer 不为文风而删减技术过程。语言润色、章节重排和篇幅取舍属于 `write-cumcm-paper`；Train 必须先把足量且不冲突的完整材料交出去。

`final/common/decision-log.md` 至少包含：候选矩阵摘要、采用路线及证据、融合边界、拒绝/替代路线及原因、未决项、危险旧数值。`final/` 中所有文件都必须被 manifest 引用；不得存在 `final2/`、`new-final/` 等并行正式入口。

## 校验与人工审批

Finalizer 完成后运行：

```powershell
python scripts/validate_human_package.py <package-root>
python scripts/review_human_package.py <package-root> --pending
```

人工审核应逐问核对直接答案、完整思路、公式链、参数确定与求解过程、结果、图表、验证、决策日志和写作禁区。若 final 只是 process 的简化摘要，或者写作端仍需回到 process 才能补全论证，应直接退回 Finalizer。审核通过或退回时，由人工执行或明确指示执行：

```powershell
python scripts/review_human_package.py <package-root> --approve --reviewer "<name>" --note "<review note>"
python scripts/review_human_package.py <package-root> --reject --reviewer "<name>" --note "<required reason>"
```

审批同时绑定 `human-package.json` 原始字节哈希和按相对路径排序的整棵 `final/` 哈希。批准后修改、增加、删除或重命名任一 final 文件，或修改 manifest，都会使审批失效并要求重新审核。

## 论文写作隔离

新的论文写作 Agent 必须先运行：

```powershell
python scripts/validate_process_intake.py <package-root> --ready-for-writing
```

只有退出码为 0 才能交给 `F:\write-cumcm-paper`。写作 Agent 只读取 `human-package.json`、`approval.json` 以及 manifest 声明的 `final/` 文件；不得读取 `process/`。若 final 缺失或疑似有误，应退回本仓库的 Finalizer/人工复审，不得自行进入 process 选方案。

## Legacy 与冻结材料

没有 `human-process.json` 和 `human-package.json` 的旧包标记为 `LEGACY`。不得原地修改冻结输入；应在独立目录创建 V3 intake，把旧包完整复制到新工作区的 `process/legacy-package/`，再运行 Finalizer。历史 benchmark 继续引用原冻结包，除非另行建立并冻结新的 benchmark。
