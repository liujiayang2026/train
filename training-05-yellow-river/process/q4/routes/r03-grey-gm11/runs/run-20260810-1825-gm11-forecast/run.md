# Run record

- 日期时间：2026-08-10 18:25 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r03-grey-gm11/code/forecast_gm11_no_regulation.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r03-grey-gm11/runs/run-20260810-1825-gm11-forecast`
- 代码入口/版本：`code/forecast_gm11_no_regulation.py`；执行后补充SHA-256
- 输入文件：只读附件1、附件2、附件3
- 关键参数：PCHIP；5 m网格；1820—2050 m；年化GM平移常数2.5、3、4、5 m/年，中心值3；原始差值GM平移常数1、1.5、2、3 m；预测10年。
- 随机种子：不适用
- 环境/依赖：Python 3；numpy、pandas、scipy、matplotlib、openpyxl
- 结果文件：执行后补充
- 图表文件：执行后补充
- 验证文件：执行后补充
- 是否成功完成：no
- 异常与备注：计算及部分结果写出后，在绘制平移常数敏感性图时，`group.shift`被pandas解释为DataFrame方法而非字段，触发x、y维数不一致错误。该失败run保留，不作为正式结果；修复后转入 `run-20260810-1836-gm11-forecast-fix/`。固定平移1 m不能保证全空间正序列，已保留失败诊断而未强行拟合。
