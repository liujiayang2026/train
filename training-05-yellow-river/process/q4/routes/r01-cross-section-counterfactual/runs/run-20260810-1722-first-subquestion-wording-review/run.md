# Run record

- 日期时间：2026-08-10 17:22（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/evaluate_multiyear_regulation_effect.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1722-first-subquestion-wording-review`
- 代码入口/版本：`code/evaluate_multiyear_regulation_effect.py`；执行前SHA-256 `8f016e229a018dab3e9b86cd443d9790a118fd81b3189b867cdb60dd38423cad`
- 输入文件：只读使用 `source/attachments/附件1.xlsx`、`附件2.xlsx`、`附件3.xlsx`
- 关键参数：与 `run-20260810-1716-multiyear-final-evidence/` 完全相同；仅将局部响应结论从“目标达成/未显示”改成观测事实表述，并加入工程2002年开始、附件期全部处于长期运行期的解释边界。
- 随机种子：不适用（确定性计算）
- 环境/依赖：Windows；Python 3.12.10；NumPy 1.26.4；pandas 3.0.3；SciPy 1.13.1；Matplotlib 3.10.9
- 结果文件：`results/` 的多年河床、水沙、流速、逐年局部响应矩阵和分析说明。
- 图表文件：`figures/` 的3张图；数值图面与1716 run一致。
- 验证文件：`validation/` 的跨附件校验、PCHIP—线性敏感性和7项质量检查。
- 是否成功完成：yes
- 异常与备注：7/7质量检查通过。四个核心数值表与1716 run逐文件SHA-256一致，说明本run没有改变计算结果，只纠正解释范围和措辞。2020、2021现统一表述为“该断面观测窗口内未形成净冲刷，表现为净淤积”；2022表述为“7月高频观测期内形成净冲刷，但4月至7月累计仍为净淤积”。思路全文见 `notes/q4-first-subquestion-solution.md`。
