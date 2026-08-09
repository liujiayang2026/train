# Question 1 preliminary analysis

## Data checks

- Artifact records: 58.
- Sampling-point records: 69; valid records: 67.
- Invalid points: 15 (sum=79.47), 17 (sum=71.89).
- Missing component cells were treated as zero. Point names containing `未风化` override artifact-level weathering as unweathered.

## Association with surface weathering

### Unadjusted permutation tests

- 玻璃类型: chi-square=6.880, permutation p=0.0125, Cramer's V=0.344.
- 纹饰: chi-square=4.957, permutation p=0.1034, Cramer's V=0.292.
- 颜色: chi-square=9.432, permutation p=0.3172, Cramer's V=0.403.

### Multivariable Firth logistic model

- 玻璃类型: parameter-bootstrap global p=0.0002 (4899 successful simulations).
- 纹饰: parameter-bootstrap global p=0.0006 (4990 successful simulations).
- 颜色: parameter-bootstrap global p=0.0574 (4963 successful simulations).
- 铅钡 vs 高钾 adjusted OR=133.956 (bootstrap 95% CI 10.686 to 303.683).
- 铅钡 adjusted weathering probability=73.6% (95% CI 59.9% to 80.7%).
- 高钾 adjusted weathering probability=13.7% (95% CI 11.0% to 28.2%).
- Specification sensitivity: adjusted type OR ranges from 4.385 to 133.956; therefore adjusted probabilities and bootstrap intervals are preferred over interpreting the OR as a stable physical multiplier.

## Composition differences

- 铅钡: SiO2 (-28.87 points, q=0.0003), PbO (+22.02 points, q=0.0003), P2O5 (+3.79 points, q=0.0007), CaO (+1.34 points, q=0.0082), Na2O (-1.30 points, q=0.0305).
- 高钾: SiO2 (+26.19 points, q=0.0035), K2O (-9.02 points, q=0.0040), Al2O3 (-4.48 points, q=0.0040), CaO (-4.86 points, q=0.0066), MgO (-0.86 points, q=0.0258), Fe2O3 (-1.52 points, q=0.0258).

The component test uses one mean record per artifact and point-weathering state, reducing repeated-point weighting. Raw percentages are retained for interpretation.

## Pre-weathering prediction

- Primary model: type-specific median CLR shift, pseudocount=0.1, effect cap=+/-2.5 log units.
- Predicted valid weathered sampling points: 32; all predicted rows close to 100%.
- Capped type-component effects: 0 of 28.
- Pseudocount 0.05: mean absolute change versus 0.10 = 0.201 percentage points; maximum = 4.310.
- Pseudocount 0.10: mean absolute change versus 0.10 = 0.000 percentage points; maximum = 0.000.
- Pseudocount 0.50: mean absolute change versus 0.10 = 0.829 percentage points; maximum = 5.897.
- Paired-point check: artifact 49, MAE 3.696 -> 1.848; artifact 50, MAE 3.716 -> 2.058.

This is a group-level counterfactual correction rather than a direct before-after supervised model. Only artifacts with both point states could support true paired calibration, so paired information is reported separately and should be used as a robustness check rather than the sole estimator.
