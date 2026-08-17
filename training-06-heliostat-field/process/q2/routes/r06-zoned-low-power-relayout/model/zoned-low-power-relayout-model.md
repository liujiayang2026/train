# 分区低功率镜位重排模型

## 1. 基准镜场和重排区域

基准镜位集合记为

\[
\mathcal S_0=\{\boldsymbol p_i\}_{i=1}^{3168}.
\]

场地圆按 5 个径向环带和 12 个方位扇区划分。由 r05 的 256 光线空间诊断得到低功率分区集合

\[
\mathcal G_L=\{g:\bar P_g\le Q_{0.25},\ N_g\ge10\},
\]

其中 $Q_{0.25}=0.453341\ \mathrm{kW/m^2}$。

## 2. 过渡带和重排核心

若直接在分区边界拼接两套不同相位的点阵，会产生镜心距离冲突。对每个低功率分区，在径向边界和扇区边界保留宽度 $b$ 的原点阵过渡带。只有到所有分区边界的平面距离均大于 $b$ 的镜位进入重排核心 $\mathcal C_L(b)$。

固定镜位集合为

\[
\mathcal S_F=\mathcal S_0\setminus\mathcal C_L(b).
\]

## 3. 局部三角点阵

最小安全距离保持为

\[
d=11.35\ \mathrm m.
\]

给定局部旋转角 $\theta$ 和相位参数 $f_1,f_2\in[0,1)$，基向量为

\[
\boldsymbol b_1=d(\cos\theta,\sin\theta),
\]

\[
\boldsymbol b_2=d(\cos(\theta+60^\circ),\sin(\theta+60^\circ)).
\]

局部候选镜位写为

\[
\boldsymbol p_{mn}
=(m+f_1)\boldsymbol b_1+(n+f_2)\boldsymbol b_2.
\]

只保留位于重排核心、场地圆内和塔周禁建区外的格点，并删除与固定镜位距离小于 $d$ 的候选点。局部点阵自身的最近邻距离解析上等于 $d$。

## 4. 优化变量与目标

第一阶段使用所有低功率核心共享的参数

\[
\boldsymbol x=(b,\theta,f_1,f_2),
\]

以控制搜索规模。候选组合镜场为

\[
\mathcal S(\boldsymbol x)
=\mathcal S_F\cup\mathcal S_L(\boldsymbol x).
\]

优化目标为

\[
\max_{\boldsymbol x}
\bar P_A(\boldsymbol x)
=\frac{1000\bar E_{\mathrm{year}}(\boldsymbol x)}
{N(\boldsymbol x)WH},
\]

约束为

\[
\bar E_{\mathrm{year}}(\boldsymbol x)\ge60\ \mathrm{MW},
\]

\[
\|\boldsymbol p_i-\boldsymbol p_j\|\ge11.30\ \mathrm m,
\]

以及场地圆和塔周 100 m 禁建区约束。候选筛选阶段采用 $60.10\ \mathrm{MW}$ 内部安全线，最终仍以题目要求的 60 MW 为硬约束。

## 5. 多精度求解

1. 枚举过渡带宽度、局部旋转角和二维相位，先做纯几何预筛。
2. 对镜数和无阴影代理较好的候选执行 12 个代表时点、16 光线筛选。
3. 对前若干候选执行完整 60 时点、64 光线复核。
4. 对功率可行且单位面积功率较高的候选执行 128 和 256 光线确认。
5. 与 r05 同精度结果比较；若没有改进，则保留失败证据并维持 r05 为更合理方案。
