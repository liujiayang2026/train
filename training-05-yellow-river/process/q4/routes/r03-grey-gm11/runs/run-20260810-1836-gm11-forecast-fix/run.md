# Run record

- 日期时间：2026-08-10 18:36 +08:00
- 执行目录：`F:\train`
- 执行命令：`python training-05-yellow-river/process/q4/routes/r03-grey-gm11/code/forecast_gm11_no_regulation.py --attachment1 training-05-yellow-river/source/attachments/附件1.xlsx --attachment2 training-05-yellow-river/source/attachments/附件2.xlsx --attachment3 training-05-yellow-river/source/attachments/附件3.xlsx --output-dir training-05-yellow-river/process/q4/routes/r03-grey-gm11/runs/run-20260810-1836-gm11-forecast-fix`
- 代码入口/版本：`code/forecast_gm11_no_regulation.py`；执行后补充SHA-256
- 输入文件：只读附件1、附件2、附件3
- 关键参数：PCHIP；5 m网格；1820—2050 m；年化GM平移常数2.5、3、4、5 m/年，中心值3；原始差值GM平移常数1、1.5、2、3 m；预测10年。
- 随机种子：不适用
- 环境/依赖：Python 3；numpy、pandas、scipy、matplotlib、openpyxl
- 结果文件：执行后补充
- 图表文件：执行后补充
- 验证文件：执行后补充
- 是否成功完成：no
- 异常与备注：敏感性图已成功生成，但自动撰写分析文件时仍有多处以属性方式访问 `shift` 字段，导致中心情景筛选为空并报错。数值文件属于中断产物，不作为正式结果；所有同类访问一次性修复后转入 `run-20260810-1837-gm11-forecast-reviewed/`。
