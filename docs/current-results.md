# Current results

> **Generated file — do not edit.** Written by `src/build_current_results.py` from the committed model and results JSON. Every number below is read from the file named beside it.

This is the current-results reference for the analysis behind the manuscript. `scaling_analysis_writeup.md` is a **development archive** and is not maintained against these numbers; where the two differ, this file and the manuscript are correct.

## Adopted model

Two-regime robust Bayesian pooling with a floor, fitted by NUTS. Source: `model/dispersion_calibration_ritc.json`.

| Quantity | Posterior mean |
|---|---:|
| pooling exponent $k$ | 0.614 |
| concentration exponent $\gamma$ | 0.240 |
| undiversifiable floor $\sigma_{\text{undiv}}$ | 0.0219 |
| diversifiable scale $\sigma_{\text{div}}$ | 0.0608 |
| clean-regime tail $\nu_{\text{clean}}$ | 2.57 |
| RITC-regime tail $\nu_{\text{RITC}}$ | 1.52 |
| RITC tail shift $\lambda_{\text{RITC}}$ | 0.532 |
| RITC scale term $\beta_{\text{RITC}}$ | -0.184 |

Fitted on n = 726 syndicate-years (133 RITC) across 11 reporting years, seed 42. Diagnostics: 0 divergences, max $\hat R$ = 1.00, min bulk ESS = 1752.0.

## What the posterior does and does not settle

| Statement | Value | Status |
|---|---:|---|
| $P(\nu_{\text{RITC}} < \nu_{\text{clean}})$ | 0.994 | RITC tails are heavier |
| $P(\nu_{\text{RITC}} < 2)$ | 0.944 | posterior probability that the RITC regime lacks a finite variance |
| $P(k < 1)$ | $1$ by construction | **tautological** on the bracketed support $[\tfrac12,1]$; stated structurally, not computed from draws |
| $P(k > \tfrac12)$, unconstrained refit | 0.982 | against a prior of 0.50 |
| $P(k < 1)$, unconstrained refit | all 6,000 draws | none of the 6,000 post-warmup draws reached the boundary, at the available Monte Carlo resolution: a simulation count, not a bound on the posterior probability; against a prior of 0.84 |
| $P(|\beta_{\text{RITC}}| > 0.1)$ | 0.757 | fitted in the likelihood; the transfer operator omits it, not shown to be zero |

## Pooling comparison

Source: `results/pooling_compare_results.json`.

| Model | $k$ | elpd$_{\text{LOO}}$ |
|---|---:|---:|
| `M1_blended` | 0.616 | 548.07 |
| `M2_independent` | 0.500 | 546.27 |

**Observation-level PSIS-LOO** (`results/pooling_compare_results.json`): $\Delta$elpd (M1 blended $-$ M2 finite-variance independent $\sqrt N$) = 1.80, SE 2.03.

**By-syndicate cross-validation, Bayesian bootstrap over syndicate totals** (`results/check_cv_clustered_se_results.json`) --- the criterion the manuscript rests on, because observations within a syndicate are not independent and a plain SE understates the clustering. $\Delta$ELPD (free $k$ $-$ $k=\tfrac12$+floor) = 1.73, 95% credible interval $[-3.2, 6.9]$, $P(\text{free }k\text{ predicts better}) = 0.75$.

Neither criterion separates the two forms, so the free exponent is **not** separated from $k=\tfrac12$-plus-floor on either. That is why pooling slower than the finite-variance independent $\sqrt N$ benchmark is treated as unresolved (independence alone does not give $k=\tfrac12$ under infinite-variance aggregation).

## Size-loaded co-movement (M4)

Source: `model/dispersion_calibration_hetscale.json`. Specification as fitted:

```
log sigma_it = (1 + psi_s*(log Reff_it - c)) * s_t + beta_ritc*1[RITC]; c = mean(log(R/Rref) - 0.264*log H), a FIXED centring offset built with a legacy gamma_c and NOT the free gamma, so the loading is 1 at mean log effective size; psi_s ~ N(0,0.5) is a linear loading coefficient, not a power elasticity; psi_s=0 => uniform-scale headline model
```

Loading $\psi_s$ = 0.016, $P(\psi_s > 0)$ = 0.516. This is a **linear loading coefficient on centred log effective size**, not a power elasticity.

M3 and M4 load a **common** reporting-year factor on size. Pair-specific shared-slip or residual-noise dependence is not fitted anywhere in this analysis, so these sensitivities bound the common-factor channel only.

## Between-syndicate level differences

Source: `results/check_syndicate_random_effect_results.json`. $\tau_\alpha$ = 0.043 against $\sigma_{\text{div}}$ = 0.061 at the reference size (ratio 0.70): persistent between-syndicate level differences are real and material.

## Missingness

Source: `results/missingness_check_results.json`. These figures are read from that file; prose copies of them drift and have.

- 1065 filings, 925 extracted successfully, **140 without the reserves field the diagnostic needs**. That is not the same count as the wholly empty extractions reported in the collection flow, and the two have been conflated before.
- Syndicates with at least one failed year: median size \pounds119.2m against \pounds361.9m for never-fail syndicates ($p = 0.0011$).
- Failed filings' syndicates are smaller than successful ones: \pounds106.6m against \pounds342.3m. **37 orphan filings** come from syndicates never observed at all, so no outcome exists for them by construction.
- Dispersion given size, failure-prone indicator: coefficient -0.0131, $p = 0.239$. **No association was detected among syndicates observed at least once.** That is the whole of what this diagnostic supports: a failure to reject is not a demonstration, and it is silent about the orphans, so **missing-at-random cannot be established**.

Two sensitivities are reported instead of resting on it. Inverse-probability weighting leaves the fit essentially unchanged. The high-volatility orphan stress moves the conditional bracketed estimate from $k = 0.592$ at $c=1$ to $0.571$ at $c=5$ --- a construction that makes the predominantly small missing books more volatile, so it cannot test the adverse-to-sub-linearity direction --- and moves the concentration exponent and the clean-regime tail materially, so the tail is **not** unaffected. See the manuscript for both.

## Open questions

These are unresolved on public data and nothing downstream rests on them. The manuscript states each where it arises; `paper/audit_numbers.py` gate M keeps that list and the register in step.

- whether pooling is slower than the finite-variance independent $\sqrt N$ benchmark -- a floor-plus-$\sqrt N$ alternative is not predictively separable;
- the exact value of $k$; $k > \tfrac12$ is suggestive, not established;
- whether the size-dispersion decline continues past about GBP 1bn;
- the within-book concentration--location slope, which is unresolved rather than zero;
- the long-tail share slope, not distinguishable from zero;
- the concentration functional form, which is indeterminate.

The floor is retained as a **structural choice about extrapolation**, not as an adjudicated asymptote: a floorless law is not predictively separable from the floored one, and the floor's posterior is conditional on having fitted a floored model. $\mu = 0$ is a **fitting restriction**, not a transfer principle: the operator rescales the raw severity, so a **clean** donor's persistent level is carried across and scaled by the size ratio, while an **RITC** donor's realised level is carried through the nonlinear rank map, where it is neither separable as a scaled location nor identified or removed.
