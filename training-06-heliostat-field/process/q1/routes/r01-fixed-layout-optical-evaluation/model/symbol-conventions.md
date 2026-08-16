# 问题一符号说明与统一约定

本文统一问题一建模、程序实现和论文写作中的符号。除题面明确使用的
`d_HR` 外，不再用 `H` 表示定日镜，以免与场地海拔混淆。

## 1. 下标与索引

| 符号 | 含义 | 取值 |
|---|---|---|
| $i$ | 定日镜编号 | $i=1,2,\ldots,N$ |
| $m$ | 月份编号 | $m=1,2,\ldots,12$ |
| $j$ | 当月评价时刻编号 | $j=1,2,\ldots,5$ |
| $p$ | 定日镜面内采样点编号 | $p=1,2,\ldots,K$ |
| $q$ | 太阳圆盘采样方向编号 | 与同一四维联合样本中的 $p$ 对应 |
| $t_{m,j}$ | 第 $m$ 月第 $j$ 个评价时刻 | 9:00、10:30、12:00、13:30、15:00 |

## 2. 坐标系与固定参数

镜场坐标系原点位于圆形场地中心，$x$ 轴指向正东，$y$ 轴指向正北，
$z$ 轴竖直向上。

| 符号 | 含义 | 问题一取值/单位 |
|---|---|---|
| $\varphi$ | 场地纬度 | $39.4^\circ$ |
| $h_{\mathrm{alt}}$ | 场地海拔，仅用于 DNI 公式 | $3\ \mathrm{km}$ |
| $G_0$ | 太阳常数 | $1.366\ \mathrm{kW/m^2}$ |
| $N$ | 定日镜总数 | $1745$ |
| $A_i$ | 第 $i$ 面定日镜面积 | $36\ \mathrm{m^2}$ |
| $A_{\mathrm{tot}}$ | 定日镜总面积，$\sum_i A_i$ | $62820\ \mathrm{m^2}$ |
| $\boldsymbol M_i$ | 第 $i$ 面定日镜中心坐标 | $(x_i,y_i,4)$，单位 m |
| $\boldsymbol R$ | 集热器中心坐标 | $(0,0,80)$，单位 m |
| $r_R$ | 圆柱集热器半径 | $3.5\ \mathrm m$ |
| $h_R$ | 圆柱集热器高度 | $8\ \mathrm m$ |

集热器中心高度已经是 80 m，因此其圆柱侧面的高度范围为
$76\le z\le84$，计算集热器中心坐标时不再额外加 4 m。

## 3. 太阳位置符号

| 符号 | 含义 | 约定 |
|---|---|---|
| $D$ | 从春分日（3 月 21 日）起算的天数 | 按 365 天循环取值 |
| $ST$ | 题目给定的当地时间 | 单位 h，不另作经度或时差修正 |
| $\delta$ | 太阳赤纬角 | 北偏为正 |
| $\omega$ | 太阳时角 | 上午为负，下午为正 |
| $\alpha_s$ | 太阳高度角 | 地平面以上为正 |
| $\gamma_s$ | 太阳方位角 | 从正北方向顺时针计算 |
| $\theta_\odot$ | 太阳圆盘角半径 | $0.266^\circ\approx4.64\ \mathrm{mrad}$ |
| $\rho,\phi$ | 太阳圆盘采样方向的极角和方位参数 | $0\le\rho\le\theta_\odot$，$0\le\phi<2\pi$ |

太阳位置公式为

$$
\sin\delta=
\sin\left(\frac{2\pi D}{365}\right)\sin(23.45^\circ),
$$

$$
\omega=\frac{\pi}{12}(ST-12),
$$

$$
\sin\alpha_s=
\cos\delta\cos\varphi\cos\omega+
\sin\delta\sin\varphi,
$$

$$
\cos\gamma_s=
\frac{\sin\delta-\sin\alpha_s\sin\varphi}
{\cos\alpha_s\cos\varphi}.
$$

## 4. 方向向量

所有方向向量均为单位向量。

| 符号 | 方向定义 |
|---|---|
| $\boldsymbol s$ | 从定日镜指向太阳圆盘中心 |
| $\boldsymbol e_1,\boldsymbol e_2$ | 垂直于 $\boldsymbol s$ 的平面内的一组单位正交基 |
| $\boldsymbol s_q$ | 从定日镜指向太阳圆盘内第 $q$ 个采样位置的方向 |
| $\boldsymbol i_q$ | 第 $q$ 条太阳光的实际入射传播方向，$\boldsymbol i_q=-\boldsymbol s_q$ |
| $\boldsymbol t_i$ | 从第 $i$ 面定日镜中心指向集热器中心 |
| $\boldsymbol n_i$ | 第 $i$ 面定日镜的单位法向 |
| $\boldsymbol d_{r,i,q}$ | $\boldsymbol i_q$ 经第 $i$ 面镜反射后的传播方向 |

其中

$$
\boldsymbol s=
(\cos\alpha_s\sin\gamma_s,
 \cos\alpha_s\cos\gamma_s,
 \sin\alpha_s),
$$

$$
\boldsymbol t_i=
\frac{\boldsymbol R-\boldsymbol M_i}
{\|\boldsymbol R-\boldsymbol M_i\|},
\qquad
\boldsymbol n_i=
\frac{\boldsymbol s+\boldsymbol t_i}
{\|\boldsymbol s+\boldsymbol t_i\|}.
$$

太阳圆盘方向和对应反射方向为

$$
\boldsymbol s_q
=\cos\rho\,\boldsymbol s
+\sin\rho(\cos\phi\,\boldsymbol e_1+\sin\phi\,\boldsymbol e_2),
$$

$$
\boldsymbol d_{r,i,q}
=-\boldsymbol s_q
+2(\boldsymbol s_q\cdot\boldsymbol n_i)\boldsymbol n_i.
$$

注意：若程序使用 $\boldsymbol i_q$ 而非 $\boldsymbol s_q$，涉及点积的正负号必须
同步改变，不能混用两种方向定义。

## 5. 距离、辐照度与效率

| 符号 | 含义 | 单位/范围 |
|---|---|---|
| $d_{HR,i}$ | 第 $i$ 面定日镜中心到集热器中心的空间距离 | m |
| $DNI(t)$ | 时刻 $t$ 的法向直接辐射辐照度 | $\mathrm{kW/m^2}$ |
| $\eta_{\cos,i}(t)$ | 第 $i$ 面镜的余弦效率 | $[0,1]$ |
| $\eta_{at,i}$ | 第 $i$ 面镜到集热器的大气透射率 | $[0,1]$ |
| $\eta_{sb,i}(t)$ | 第 $i$ 面镜的阴影遮挡效率 | $[0,1]$ |
| $\eta_{\mathrm{trunc},i}(t)$ | 第 $i$ 面镜的集热器截断效率 | $[0,1]$ |
| $\eta_{\mathrm{ref}}$ | 镜面反射率 | $0.92$ |
| $\eta_i(t)$ | 第 $i$ 面镜的总光学效率 | $[0,1]$ |

距离与已明确的效率公式为

$$
d_{HR,i}=\|\boldsymbol R-\boldsymbol M_i\|
=\sqrt{x_i^2+y_i^2+76^2},
$$

$$
\eta_{\cos,i}
=\boldsymbol s\cdot\boldsymbol n_i
=\sqrt{\frac{1+\boldsymbol s\cdot\boldsymbol t_i}{2}},
$$

$$
\eta_{at,i}=
0.99321-0.0001176d_{HR,i}
+1.97\times10^{-8}d_{HR,i}^2,
$$

$$
\eta_i=
\eta_{sb,i}\eta_{\cos,i}\eta_{at,i}
\eta_{\mathrm{trunc},i}\eta_{\mathrm{ref}}.
$$

## 6. 功率与平均指标

| 符号 | 含义 | 单位 |
|---|---|---|
| $E_{\mathrm{field}}(t)$ | 时刻 $t$ 的镜场输出热功率 | kW |
| $P_A(t)$ | 时刻 $t$ 的单位镜面面积输出热功率 | $\mathrm{kW/m^2}$ |
| $\bar\eta_x(t)$ | 时刻 $t$ 的镜场面积加权平均效率 | 无量纲 |
| $\bar\eta_{x,m}$ | 第 $m$ 月 5 个时刻的平均效率 | 无量纲 |
| $\bar\eta_{x,\mathrm{year}}$ | 全部 60 个时刻的年平均效率 | 无量纲 |
| $\bar E_{\mathrm{year}}$ | 60 个时刻的年平均输出热功率 | kW 或 MW |
| $\bar P_{A,\mathrm{year}}$ | 单位镜面面积年平均输出热功率 | $\mathrm{kW/m^2}$ |

其中 $x$ 可代表总光学效率、余弦效率、阴影遮挡效率或截断效率。

$$
E_{\mathrm{field}}(t)
=DNI(t)\sum_{i=1}^{N}A_i\eta_i(t),
\qquad
P_A(t)=\frac{E_{\mathrm{field}}(t)}{A_{\mathrm{tot}}},
$$

$$
\bar\eta_x(t)=
\frac{\sum_i A_i\eta_{x,i}(t)}{A_{\mathrm{tot}}},
$$

$$
\bar\eta_{x,m}=\frac{1}{5}\sum_{j=1}^{5}\bar\eta_x(t_{m,j}),
\qquad
\bar\eta_{x,\mathrm{year}}=
\frac{1}{60}\sum_{m=1}^{12}\sum_{j=1}^{5}\bar\eta_x(t_{m,j}),
$$

$$
\bar E_{\mathrm{year}}=
\frac{1}{60}\sum_{m=1}^{12}\sum_{j=1}^{5}E_{\mathrm{field}}(t_{m,j}),
\qquad
\bar P_{A,\mathrm{year}}=
\frac{\bar E_{\mathrm{year}}}{A_{\mathrm{tot}}}.
$$

## 7. 单位约定

- 程序内部角度统一使用弧度，题面给出的角度先由度转换为弧度。
- 几何坐标与 $d_{HR}$ 使用 m；DNI 经验公式中的海拔使用 km。
- $DNI$ 使用 $\mathrm{kW/m^2}$，因此 $E_{\mathrm{field}}$ 默认得到 kW；填表时除以 1000 转为 MW。
- 年平均功率必须先逐时计算 $DNI(t)\eta_i(t)$ 后再平均，不能用平均 DNI 与平均效率的乘积代替。
