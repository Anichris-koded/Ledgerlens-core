# Benford Stratification

## Rationale

Wash-trading rings frequently concentrate on a single asset pair (e.g. a bot cycling through XLM/USDC to inflate 24-hour volume). When that ring's trades are aggregated with legitimate multi-asset trading activity, the Benford deviation signal is attenuated. Stratifying Benford analysis independently per `(wallet, asset_pair)` stratum enables targeted anomaly detection and reduces false negatives from cross-pair dilution.

## Asset-Pair Normalisation

Asset pairs are canonicalised by lexicographic ordering of the two asset symbols. This avoids treating `XLM/USDC` and `USDC/XLM` as distinct strata:

```
canonical_pair = "/".join(sorted([base_symbol, counter_symbol]))
```

Asset-pair strings are sanitised: strings longer than 30 characters or containing characters outside `[A-Z0-9/.\-:]` are rejected and their trades are excluded from stratified analysis.

## Minimum-N Requirement

A stratum must have N >= 30 valid trades before Benford statistics (chi-square, Z-scores, MAD) are computed. Strata below this threshold return `BenfordResult(valid=False, reason="insufficient_sample")`.

When **all** strata in a window have N < 30, the engine falls back to a global (unstratified) computation and sets `fallback_global=True` on the returned `StratifiedBenfordSummary`.

## Statistical Tests

Per stratum, three tests are computed:

| Test | Statistic | Flag threshold |
|------|-----------|----------------|
| Pearson chi-square | chi2 = sum((O_i - E_i)^2 / E_i), df=8 | chi2 > 15.507 (alpha=0.05) |
| Per-digit Z-score | Z_d = (obs_d - exp_d) / sqrt(exp_d * (1 - exp_d) / N) | abs(Z_d) > 1.96 |
| MAD | (1/9) * sum(abs(obs_d - exp_d)) | > 0.015 = non-conforming |

MAD conformity thresholds:
- < 0.006: close conformity
- 0.006-0.012: acceptable
- 0.012-0.015: marginal
- > 0.015: non-conforming

## Cross-Stratum Summary Features

Three summary features are derived per rolling window and appended to the feature vector:

| Feature | Description |
|---------|-------------|
| `max_stratum_chi2_{window}` | Highest chi-square across all valid strata |
| `max_stratum_MAD_{window}` | Highest MAD across all valid strata |
| `n_flagged_strata_{window}` | Count of strata where `benford_flag=True` |

These 15 features (3 per window x 5 windows) extend the feature vector without altering existing feature indices.
