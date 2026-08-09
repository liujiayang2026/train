# Question 2 Results Summary

## Data

- Corrected artifact records: 56.
- High-potassium records: 16.
- Lead-barium records: 40.

## Major-Type Classification

- Leave-one-out accuracy of the log-ratio threshold rule: 0.982.
- Leave-one-out accuracy of the CLR nearest-centroid model: 0.982.
- The main rule is based on log((PbO + BaO + eps) / (K2O + eps)).

## Subclasses

- 高钾 K-1 高钾钙铝型: n=15, artifacts=01;03;04;05;06;07;09;10;12;13;14;16;21;22;27.
- 高钾 K-2 高硅含锡特殊型: n=1, artifacts=18.
- 铅钡 LB-1 铅钡均衡型: n=19, artifacts=23;25;32;33;34;35;36;38;39;42;44;45;46;47;48;53;55;56;57.
- 铅钡 LB-2 富钡铜型: n=6, artifacts=08;11;20;24;26;37.
- 铅钡 LB-3 富铅型: n=15, artifacts=02;19;28;29;30;31;40;41;43;49;50;51;52;54;58.

## Sensitivity

- Raw-valid versus weathering-corrected adjusted Rand indices:
  - 高钾: ARI=1.000.
  - 铅钡: ARI=0.434.
- Pseudocount sensitivity adjusted Rand indices:
  - 高钾, eps=0.05: ARI=1.000.
  - 高钾, eps=0.1: ARI=1.000.
  - 高钾, eps=0.5: ARI=0.147.
  - 铅钡, eps=0.05: ARI=0.826.
  - 铅钡, eps=0.1: ARI=1.000.
  - 铅钡, eps=0.5: ARI=0.568.
- Feature-deletion sensitivity adjusted Rand indices:
  - 高钾, drop K2O: ARI=1.000.
  - 高钾, drop CaO: ARI=0.367.
  - 高钾, drop Al2O3: ARI=1.000.
  - 铅钡, drop PbO: ARI=0.477.
  - 铅钡, drop BaO: ARI=0.429.
  - 铅钡, drop P2O5: ARI=0.284.
