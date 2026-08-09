# Question 1 Quantitative Cause Analysis

## 1. Revision purpose

The original analysis identified spatial clustering but could not directly
infer that Shenzhen's low completion rate was caused by congestion, parking
difficulty, or population density. Those variables were not contained in the
competition attachments. This revision separates three levels of evidence:

1. task-level statistical evidence from Attachments 1 and 2;
2. residual city effects after controlling for observed task factors;
3. city-level population and traffic context from public 2017 statistics.

Only the first two levels enter the task completion model. Population and
traffic indicators are contextual evidence rather than task-level causal
variables.

## 2. Task-level model

For each of the 835 tasks, the analysis calculates price, nearest-member
distance, members and tasks within 2 km, mean local booking quota, price
difference from the local mean, the share of higher-priced neighbors, and city.

\[
\operatorname{logit}\Pr(Y_i=1)=\beta_0+\beta_1P_i+\beta_2D_i+
\beta_3\log_2(N_i+1)+\beta_4\log_2(G_i+1)+
\beta_5\log_2(\bar Q_i+1)+\beta_6\Delta P_i+
\beta_7H_i+\gamma_{city(i)}.
\]

Confidence intervals use 240 bootstrap resamples. The adjusted odds ratios are
observational associations, not causal effects.

## 3. Quantitative results

The task-only model has an AUC of 0.700 and Brier score of 0.207. Adding city
fixed effects raises AUC to 0.829 and lowers the Brier score to 0.163. Thus,
location contains important information not captured by observed platform
variables.

| Variable and unit | Adjusted OR | 95% bootstrap interval | Result |
|---|---:|---:|---|
| Price, +5 yuan | 1.228 | 0.925–1.574 | Positive estimate, uncertain after city controls |
| Nearest member, +1 km | 1.081 | 0.957–1.249 | Uncertain |
| Members within 2 km, doubling | 0.664 | 0.542–0.809 | Registered members are not effective supply |
| Tasks within 2 km, doubling | 1.371 | 1.117–1.692 | Density alone is not harmful competition |
| Mean member quota, doubling | 1.031 | 0.857–1.234 | Uncertain |
| Relative price, +5 yuan | 0.892 | 0.584–1.458 | Uncertain |
| Higher-priced neighbor share, +10 pp | 1.012 | 0.951–1.089 | Independent competition effect not established |

This corrects two overstatements in the original draft: registered-member
density cannot be interpreted as effective supply, and the grouped decline
across the old competition index is not a stable independent negative effect
after city and other controls.

## 4. Shenzhen residual analysis

Administrative-boundary matching identifies 161 Shenzhen tasks, with 35
completed. The observed rate is 21.74%, while the task-only model predicts
48.95% from observed platform variables. The residual gap is:

\[
21.74\%-48.95\%=-27.21\text{ percentage points}.
\]

| City | Tasks | Observed rate | Task-model expected rate | Residual gap |
|---|---:|---:|---:|---:|
| Shenzhen | 161 | 21.74% | 48.95% | −27.21 pp |
| Guangzhou | 320 | 60.94% | 59.49% | +1.44 pp |
| Foshan | 173 | 65.90% | 74.94% | −9.05 pp |
| Dongguan | 178 | 99.44% | 67.81% | +31.62 pp |

This establishes that the observed task variables do not explain the Shenzhen
shortfall. It does not identify the missing mechanism as congestion.

## 5. Population and traffic context

| City | Population density (person/km²) | 2017-Q2 peak delay index | Peak speed (km/h) | Task completion |
|---|---:|---:|---:|---:|
| Shenzhen | 6272 | 1.783 | 27.24 | 21.74% |
| Guangzhou | 1950 | 1.883 | 24.96 | 60.94% |
| Foshan | 2016 | 1.793 | 24.94 | 65.90% |
| Dongguan | 3391 | 1.598 | 31.71 | 99.44% |

Across four cities, Spearman correlation is −0.40 between peak delay and task
completion, and −0.20 between population density and task completion. With
only four aggregated observations, neither supports inference or causality.
Guangzhou's delay index is higher than Shenzhen's while its completion rate is
much higher; Dongguan's density exceeds Guangzhou's while its completion rate
is the highest. Therefore neither congestion nor density alone explains the
pattern.

## 6. Revised paper conclusion

After controlling for price, registered-member supply, booking quota, local
task density, and relative price, substantial city differences remain.
Shenzhen has a 27.21-percentage-point negative residual completion gap,
indicating omitted regional execution conditions. Public 2017 statistics show
high population density and material peak traffic delay in Shenzhen, making
urban travel cost a plausible mechanism. However, the four-city comparison is
too small and aggregated to identify a causal traffic effect. The defensible
conclusion is that the original pricing scheme failed to account for regional
composite execution conditions; their components require road-segment speed,
parking, task-time, and active-member data for verification.

## 7. Reproduction

Run `code/question1-quantitative-causes.py`. It writes task indicators to
`data/processed`, numerical results to `results`, and figures to `figures`.
