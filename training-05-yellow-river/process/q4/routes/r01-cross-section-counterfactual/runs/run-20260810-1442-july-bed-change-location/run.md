# Run record

- 日期时间：2026-08-10 14:42（Asia/Shanghai）
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/code/analyze_july_bed_change.py --input training-05-yellow-river/source/attachments/附件3.xlsx --run-dir training-05-yellow-river/process/q4/routes/r01-cross-section-counterfactual/runs/run-20260810-1442-july-bed-change-location --grid-step-m 5`
- 代码入口/版本：`process/q4/routes/r01-cross-section-counterfactual/code/analyze_july_bed_change.py`；执行前 SHA-256 `B2E70034E9DF213E1C8B193EBF16674B01DC205AA730AB1080533B599FE160EE`。
- 输入文件：`training-05-yellow-river/source/attachments/附件3.xlsx`，只读。
- 关键参数：河底高程=`水位-水深`；2020、2021、2022年分别取7月首末测次；每年在线性与PCHIP各自严格共同覆盖区使用5 m网格；方法一致热点定义为两法均处于本年绝对变化最高25%且方向相同；跨年热点还要求至少2/3年方向一致。附件3全部19期及7月子集另做连续3点、5折空间区块验证。
- 随机种子：不适用。
- 环境/依赖：Windows PowerShell；Python 3.12.10；pandas 3.0.3；NumPy 1.26.4；SciPy 1.13.1；Matplotlib 3.10.9；openpyxl 3.1.5。
- 结果文件：计划写入附件3河底测站、7月拟合网格、变化网格、年度摘要、热点区间和跨年热点网格。
- 图表文件：计划生成7月首末断面、逐年净变化、变化热图、跨年热点和附件3方法验证共5张图。
- 验证文件：计划写入附件3全部19期和7月子集的线性/PCHIP空间区块验证及质量检查。
- 是否成功完成：yes
- 异常与备注：当前没有精确调水调沙起止时刻，本run只定位7月首末测次之间的描述性变化位置；热点不自动等于调水调沙因果作用位置。
- 结果解释：见 `results/analysis.md`。图件已逐张检查；PCHIP曲线穿过观测点且未见显著局部过冲。共同覆盖边缘的热点降低解释权重。
