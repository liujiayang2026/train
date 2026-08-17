# Run record

- 日期时间：2026-08-17 23:22 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-06-heliostat-field\process\q2\routes\r07-robust-optical-density-search\code\run_robust_density_search.py --output training-06-heliostat-field\process\q2\routes\r07-robust-optical-density-search\runs\run-20260817-2322-initial-robust-search --seed 202308 --designs 128 --screen-samples 16 --full-samples 64 --robust-samples 128 --neighbor-radius 70`
- 代码入口/版本：`code/run_robust_density_search.py`；执行完成后在 `validation/code_hashes.json` 记录 SHA-256。
- 输入文件：官方题面；q1/r01 光学评价定义；r05/r06 正式设计和比较结果。
- 关键参数：128 个外层 Sobol 参数候选；安装高度独立搜索且离地安全余量 0.10 m；中心距安全余量 0.05 m；代表时点 16 光线初筛；完整年 32/64 光线复筛；128 光线三种扰码种子稳健确认；删镜步长 5 面。
- 随机种子：202308、202309、202310。
- 环境/依赖：Python 3.12；NumPy 1.26.4；SciPy 1.13.1；Matplotlib；openpyxl。
- 结果文件：已生成全局候选、真实光线筛选、删镜比较、月/年指标、最终镜位和逐镜指标。
- 图表文件：已生成参数筛选、最终镜场和稳健功率/单位面积功率比较图。
- 验证文件：已生成几何检查、稳健性检查和代码哈希。
- 是否成功完成：no
- 异常与备注：程序正常退出，但暴露两处筛选实现问题：多排序规则被第一排序填满，删镜候选又只按全局设计参数去重，导致 17 个删镜量中只复算 `prune-80`。该候选的 128 光线三种扰码稳健均值为 `58.9766 MW`，下置信界为 `58.6067 MW`，不满足 60 MW 约束。本运行作为失败证据保留，修复后另建运行目录。
