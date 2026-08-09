# Question 1 numerical solution

## Model additions requested

1. The 1200 kg ballast ball is treated as an independent concentrated load at
   the barrel-chain connection. Its buoyancy is neglected because its volume
   and material density are not supplied.
2. The buoy is assumed to remain upright under hydrostatic restoring action.
   Consequently, only its draft and horizontal displacement are solved.

The chain is represented by a continuous flexible cable. Chain buoyancy and
seabed friction are neglected. The four sealed pipes and the sealed barrel use
their external cylindrical volumes to calculate buoyancy.

## Governing relations

For buoy draft `h`, wind speed `v`, and horizontal cable tension `H`,

\[
H=0.625\,[2(2-h)]v^2.
\]

If the vertical load exerted by the lower system on the buoy is `V`,

\[
\rho g\pi h=1000g+V.
\]

For a member whose lower and upper vertical tensions are `V_l` and `V_u`,

\[
\tan\theta=\frac{2H}{V_l+V_u}.
\]

The ballast enters the barrel lower-end load separately:

\[
V_{l,c}=1200g+V_{\text{chain,top}}.
\]

For a partly grounded chain, let `x=0` be the lift-off point and set
`a=H/q`, where `q=7g`. The suspended segment is

\[
y=a\left[\cosh\left(\frac{x}{a}\right)-1\right].
\]

The water-depth closure equation is

\[
h+y_{\text{chain}}+\cos\theta_c+
\sum_{i=1}^{4}\cos\theta_i=18.
\]

## Results

| Quantity | 12 m/s | 24 m/s |
|---|---:|---:|
| Buoy draft (m) | 0.7348 | 0.7489 |
| Horizontal tension (N) | 227.74 | 900.79 |
| Pipe 1 angle (deg) | 0.9764 | 3.7324 |
| Pipe 2 angle (deg) | 0.9822 | 3.7536 |
| Pipe 3 angle (deg) | 0.9880 | 3.7751 |
| Pipe 4 angle (deg) | 0.9939 | 3.7968 |
| Barrel angle (deg) | 1.0073 | 3.8461 |
| Suspended chain (m) | 15.2254 | 21.7267 |
| Grounded chain (m) | 6.8246 | 0.3233 |
| Chain horizontal span (m) | 14.2165 | 17.0935 |
| Chain vertical rise (m) | 12.2660 | 12.2620 |
| Excursion radius (m) | 14.3029 | 17.4232 |
| Excursion disk area (m2) | 642.6843 | 953.6845 |

Pipe 1 is the top pipe attached to the buoy, and pipe 4 is the bottom pipe
attached to the barrel. In both cases a portion of the chain remains on the
seabed, so the anchor tangent angle is 0 degrees.

### Chain shape at 12 m/s

The grounded segment is

\[
y=0,\quad 0\le x\le6.8246.
\]

With `a=3.3164 m`, the suspended segment is approximately

\[
y=3.3164\left[\cosh\left(\frac{x-6.8246}{3.3164}\right)-1\right],
\quad6.8246\le x\le14.2165.
\]

### Chain shape at 24 m/s

The grounded segment is

\[
y=0,\quad0\le x\le0.3233.
\]

With `a=13.1176 m`, the suspended segment is approximately

\[
y=13.1176\left[\cosh\left(\frac{x-0.3233}{13.1176}\right)-1\right],
\quad0.3233\le x\le17.0935.
\]

The 24 m/s condition is close to the chain-lift transition, but the calculated
grounded length remains positive, so the partly grounded model is still
self-consistent.
