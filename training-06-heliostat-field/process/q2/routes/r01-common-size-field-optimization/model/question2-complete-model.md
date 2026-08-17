# 问题二：统一尺寸定日镜场优化模型

## 1. 设计目标与变量

问题要求在年平均输出热功率不低于 60 MW 的前提下，使单位镜面面积年平均输出热功率最大。采用交错环形参数化布局，设计向量为

\[
\boldsymbol{x}=(x_T,y_T,W,H,z_H,r_0,c_r,c_t,r_{\max},\theta_0),
\]

其中 \((x_T,y_T)\) 为吸收塔平面坐标，\(W,H\) 为所有定日镜统一的宽度和高度，\(z_H\) 为镜面中心安装高度，\(r_0\) 为首环半径，\(c_r,c_t\) 分别为径向和切向附加净距，\(r_{\max}\) 为相对塔心的最大生成半径，\(\theta_0\) 为首环相位。

## 2. 交错环形布局生成

令基础安全中心距为

\[
d_{\min}=W+5.
\]

径向环距与切向目标中心距分别为

\[
\Delta r=d_{\min}+c_r,\qquad d_t=d_{\min}+c_t.
\]

第 \(k\) 环半径和镜数取为

\[
r_k=r_0+k\Delta r,
\qquad
n_k=\left\lfloor\frac{\pi}{\arcsin[d_t/(2r_k)]}\right\rfloor.
\]

第 \(k\) 环采用相位

\[
\theta_k=\theta_0+(k\bmod 2)\frac{\pi}{n_k},
\]

第 \(j\) 面镜子的平面坐标为

\[
(x_{kj},y_{kj})=(x_T,y_T)+r_k\left(\cos\left(\theta_k+\frac{2\pi j}{n_k}\right),
\sin\left(\theta_k+\frac{2\pi j}{n_k}\right)\right).
\]

只保留满足 \(x_{kj}^2+y_{kj}^2\le350^2\) 的镜心。由于 \(r_0\ge100\)、相邻环径向距离不小于 \(d_{\min}\)，且同环弦长不小于 \(d_t\)，布局由构造保证塔周禁建区和最小中心距约束。

## 3. 太阳位置、DNI 与镜面姿态

60 个评价时点与问题一完全相同，即每月 21 日的 9:00、10:30、12:00、13:30、15:00。太阳高度角、太阳方位及 DNI 均使用题面附录公式。镜心 \(\boldsymbol H_i\) 到集热器中心 \(\boldsymbol R=(x_T,y_T,80)\) 的单位方向为

\[
\boldsymbol t_i=\frac{\boldsymbol R-\boldsymbol H_i}{\|\boldsymbol R-\boldsymbol H_i\|}.
\]

设太阳入射方向单位向量为 \(\boldsymbol s\)，镜面法向量由反射定律确定：

\[
\boldsymbol n_i=\frac{\boldsymbol s+\boldsymbol t_i}{\|\boldsymbol s+\boldsymbol t_i\|},
\qquad
\eta_{\cos,i}=\boldsymbol n_i\cdot\boldsymbol s.
\]

大气透射效率为

\[
\eta_{\mathrm{at},i}=0.99321-0.0001176d_{HR,i}+1.97\times10^{-8}d_{HR,i}^2.
\]

## 4. 太阳锥形光束与高精度效率评价

太阳不是点光源。计算中把半角 \(0.266^\circ\) 的太阳圆盘映射为一束锥形入射光，并用扰码 Sobol 序列同时采样镜面位置和太阳圆盘方向。每条样本光线依次判断：

1. 入射段是否先与邻镜相交；
2. 按反射定律得到的出射段是否被邻镜遮挡；
3. 未发生阴影或遮挡的反射光是否与半径 3.5 m、高度 8 m 的圆柱形集热器相交。

于是

\[
\eta_{\mathrm{sb},i}=\frac{N_{\mathrm{clear},i}}{N_s},
\qquad
\eta_{\mathrm{trunc},i}=\frac{N_{\mathrm{hit},i}}{N_{\mathrm{clear},i}},
\]

并按题面定义计算

\[
\eta_i=0.92\eta_{\mathrm{sb},i}\eta_{\cos,i}
\eta_{\mathrm{at},i}\eta_{\mathrm{trunc},i}.
\]

第 \(m,t\) 个评价时点的镜场输出为

\[
E_{m,t}=\mathrm{DNI}_{m,t}\,WH\sum_{i=1}^N\eta_{i,m,t}.
\]

年平均功率和单位面积年平均功率分别为

\[
\bar E=\frac1{60}\sum_{m,t}E_{m,t},
\qquad
\bar e=\frac{\bar E}{NWH}.
\]

## 5. 快速代理模型

直接在数千个设计上执行完整光线追迹代价过高，因此优化阶段保留精确的太阳位置、余弦效率和大气透射率，对阴影遮挡与截断效率使用连续几何代理：

\[
\widehat\eta_{\mathrm{sb}}
=1-\frac{0.10\rho_p}{\sin\alpha_s+0.18}
\left(0.85+0.15\frac{r}{r_{\max}}\right),
\quad
\rho_p=\frac{WH}{\Delta r\,d_t},
\]

\[
b_i=0.7d_{HR,i}\tan(0.266^\circ),
\quad
\widehat\eta_{\mathrm{trunc},i}
=\min\left(1,\frac7{W+2b_i}\right)
\min\left(1,\frac8{H+2b_i}\right).
\]

代理功率再用问题一 512 光线样本基线进行单点比例校准，使固定镜场在代理模型下的单位面积功率与问题一高精度结果 0.561865 kW/m2 一致。代理仅用于搜索排序，最终表格全部来自高精度锥形光束复算。

## 6. 约束多目标优化

使用 `pymoo` 的 NSGA-II，同时最小化

\[
f_1=-\widehat{\bar e},\qquad f_2=NWH,
\]

并满足

\[
\widehat{\bar E}\ge 60\ \mathrm{MW},\quad
2\le H\le W\le8,\quad
2\le z_H\le6,\quad z_H\ge H/2.
\]

为降低代理误差导致的功率不足，NSGA-II 按题意采用 60 MW 硬约束，候选选择时再要求代理功率保留小幅安全裕量。NSGA-II 的优选点由 SciPy 差分进化做局部边界内精修。最后对 Pareto 候选执行低样本光线复算检查代理误差，并对最终方案依次采用 32、64、128、256 条 Sobol 光线检验收敛；正式结果采用 256 条样本。

## 7. 可行性验证

最终方案必须同时通过以下检查：场区边界、塔周 100 m 禁建区、任意两镜心距离不小于 \(W+5\)、统一尺寸和高度、效率位于 \([0,1]\)、年平均功率不低于 60 MW，以及不同光线样本数下关键指标稳定。验证结果保存在同一运行目录的 `validation/` 中。
