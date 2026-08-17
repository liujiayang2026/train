# Run record

- 日期时间：2026-08-17 23:44 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-06-heliostat-field\process\q2\routes\r07-robust-optical-density-search\code\run_robust_density_search.py --output training-06-heliostat-field\process\q2\routes\r07-robust-optical-density-search\runs\run-20260817-2344-balanced-selection-fix --seed 202308 --designs 128 --screen-samples 16 --full-samples 64 --robust-samples 128 --neighbor-radius 70`
- 代码入口/版本：`code/run_robust_density_search.py`；执行完成后在 `validation/code_hashes.json` 记录 SHA-256。
- 输入文件：官方题面；q1/r01 光学评价定义；r05/r06 正式设计和比较结果；上一失败运行的筛选缺陷诊断。
- 关键参数：128 个外层 Sobol 参数候选；安装高度独立搜索且离地安全余量 0.10 m；中心距安全余量 0.05 m；候选按总功率与单位面积功率轮换选择；删镜量纳入候选唯一标识；代表时点 16 光线初筛；完整年 32/64 光线复筛；128 光线三种扰码种子稳健确认；删镜步长 5 面。
- 随机种子：202308、202309、202310。
- 环境/依赖：Python 3.12；NumPy 1.26.4；SciPy 1.13.1；Matplotlib；openpyxl。
- 结果文件：已生成全局候选、真实光线筛选、4 个删镜量比较、月/年指标、最终镜位和逐镜指标。
- 图表文件：已生成参数筛选、最终镜场和稳健功率/单位面积功率比较图。
- 验证文件：已生成几何检查、稳健性检查和代码哈希。
- 是否成功完成：yes
- 异常与备注：程序正常退出，筛选修复有效。最终选择不删镜的 `d002`：三个 128 光线种子分别得到 `60.3067`、`60.1589`、`60.5630 MW`，均值 `60.3429 MW`，样本标准差 `0.2045 MW`，预设保守下界 `mean-2sd=59.9339 MW`。三次离散验证均满足题目功率约束，但额外的保守下界尚差 `0.0661 MW`；该方案受额外离地净空约束影响，未优于 r05 的题面约束方案。
