# Human decision

- 日期：2026-08-10
- 涉及问题：q4
- 涉及路线/run：`routes/r01-cross-section-counterfactual/`；主要依据 `runs/run-20260810-1428-explicit-penalized-bspline/` 和 `runs/run-20260810-1442-july-bed-change-location/`。
- 决定：Q4后续河底高程连续化正式采用PCHIP作为主拟合方法。分段线性不再与PCHIP并列作为主结果，仅保留为敏感性和稳健性检验口径。
- 理由：附件2中PCHIP与线性总体表现接近，且PCHIP在主槽区略优；附件3全部19期空间区块验证中，PCHIP RMSE为0.382 m，低于线性的0.555 m，7月子集中PCHIP RMSE为0.390 m，低于线性的0.569 m。PCHIP同时保持观测点、局部单调性和断面曲率，更适合描述约2005—2040 m主槽高变化区。
- 对结果或后续问题的影响：后续断面高程、冲淤面积、主槽变化和调水调沙效果评价均以PCHIP结果作为正文主口径；分段线性结果进入敏感性分析。5 m仍只是计算网格，不代表实测分辨率；不在共同观测范围之外外推。
- 被取代决定：本决定取代 `d02-retain-linear-and-pchip.md` 中“二者并列进入后续冲淤量化”的阶段性安排，但保留该历史决定作为过程证据。
- 决定人：用户

