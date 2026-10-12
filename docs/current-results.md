# Current results

> **Generated file — do not edit.** Written by `src/build_current_results.py` from the committed model and results JSON. Every number below is read from the file named beside it.

This is the current-results reference for the analysis behind the manuscript. `scaling_analysis_writeup.md` is a **development archive** and is not maintained against these numbers; where the two differ, this file and the manuscript are correct.

## Adopted model

Two-regime robust Bayesian pooling with a floor, fitted by NUTS, with the concentration exponent $\gamma$ fixed at 0 in the likelihood (the headline since the author's decision of 10 October 2026, option B). Source: `model/dispersion_calibration_ritc.json`.

| Quantity | Posterior mean |
|---|---:|
| pooling exponent $k$ | 0.586 |
| undiversifiable floor $\sigma_{\text{undiv}}$ | 0.0319 |
| diversifiable scale $\sigma_{\text{div}}$ | 0.0518 |
| clean-regime tail $\nu_{\text{clean}}$ | 4.91 |
| RITC-regime tail $\nu_{\text{RITC}}$ | 7.47 |
| RITC tail shift $\lambda_{\text{RITC}}$ | -0.261 |
| RITC scale term $\beta_{\text{RITC}}$ | -0.207 |
| concentration exponent $\gamma$ | 0 (fixed in the likelihood) |

Fitted on n = 674 syndicate-years (38 RITC) across 11 reporting years, seed 42. Diagnostics: 0 divergences, max $\hat R$ = 1.00, min bulk ESS = 1963.0.

## The gamma-free fit (the concentration overlay's source)

The same model with $\gamma \sim \text{HalfNormal}(1)$. Source: `model/dispersion_calibration_ritc_gamma_free.json`. Its fitted $\gamma$, with its own $k$, $\sigma_{\text{undiv}}$, $\sigma_{\text{div}}$ and $\nu$, is the concentration overlay, a labelled sensitivity; no headline figure uses it.

| Quantity | Posterior mean |
|---|---:|
| concentration exponent $\gamma$ | 0.356 [0.000, 0.809] |
| pooling exponent $k$ | 0.588 |
| undiversifiable floor $\sigma_{\text{undiv}}$ | 0.0337 |
| diversifiable scale $\sigma_{\text{div}}$ | 0.0582 |

$P(\gamma > 0.05) = 0.933$ against a prior mass of 0.960; 0 divergences, max $\hat R$ = 1.00.

## What the posterior does and does not settle

| Statement | Posterior | Prior | Status |
|---|---:|---:|---|
| $P(\nu_{\text{RITC}} < \nu_{\text{clean}})$ | 0.337 | 0.500 | the data move it below its prior mass, so the RITC tail reads as the lighter; the ordering is not imposed (the prior on $\lambda_{\text{RITC}}$ admits both signs) |
| $P(\nu_{\text{RITC}} < 2)$ | 0.015 | 0.036 | posterior probability that the RITC regime lacks a finite variance; within 0.05 of its prior mass, so its size is the prior's, not a finding |
| $P(k > \tfrac12)$, $P(k < 1)$ | $1$ by construction | $1$ | theory bounds $k$ to $[\tfrac12,1]$ (finite-variance independent $\sqrt N$ pooling to comonotonic pooling) and the prior keeps it there, so these are not findings; the endpoints are scored by syndicate as fixed alternatives |
| $P(|\beta_{\text{RITC}}| > 0.1)$ | 0.769 | 0.841 | the data move it below its prior mass; fitted in the likelihood, and the transfer operator omits it, not shown to be zero |

## Pooling comparison

Source: `results/pooling_compare_results.json`.

| Model | $k$ | elpd$_{\text{LOO}}$ |
|---|---:|---:|
| `M1_blended` | 0.589 | 680.40 |
| `M2_independent` | 0.500 | 680.44 |

**Observation-level PSIS-LOO** (`results/pooling_compare_results.json`): $\Delta$elpd (M1 blended $-$ M2 finite-variance independent $\sqrt N$) = -0.04, SE 1.65.

**By-syndicate cross-validation, Bayesian bootstrap over syndicate totals** (`results/check_cv_clustered_se_results.json`) --- the criterion the manuscript rests on, because observations within a syndicate are not independent and a plain SE understates the clustering. $\Delta$ELPD (free $k$ $-$ $k=\tfrac12$+floor) = 0.23, 95% credible interval $[-3.0, 3.4]$, $P(\text{free }k\text{ predicts better}) = 0.56$.

Neither criterion separates the two forms, so the free exponent is **not** separated from $k=\tfrac12$-plus-floor on either. That is why pooling slower than the finite-variance independent $\sqrt N$ benchmark is treated as unresolved (independence alone does not give $k=\tfrac12$ under infinite-variance aggregation).

## Size-loaded co-movement (M4)

Source: `model/dispersion_calibration_hetscale.json`. Specification as fitted:

```
log sigma_it = 0.5*log[sd_undiv^2 + sd_div^2*exp(2(k-1)*x_it)] + (1 + psi_s*(x_it - c)) * s_t + beta_ritc*1[RITC], with x_it = log(R_it/Rref) - gamma*log H_it, the dimensionless log effective size (the adopted base scale, floor included; the M4 departure is the loading on s_t); gamma = 0 in the likelihood (the headline's), so x_it = log(R_it/Rref); c = mean(log(R/Rref) - gamma_c*log H) with gamma_c = 0, the model's gamma, so the loading's sample mean is one; psi_s ~ N(0,0.5) is a linear loading coefficient, not a power elasticity; psi_s=0 => uniform-scale headline model
```

Loading $\psi_s$ = -0.019, $P(\psi_s > 0)$ = 0.472. This is a **linear loading coefficient on centred log effective size**, not a power elasticity.

M3 and M4 load a **common** reporting-year factor on size. Pair-specific shared-slip or residual-noise dependence is not fitted anywhere in this analysis, so these simulations diagnose that common-factor channel only; they do not bound residual dependence.

## Between-syndicate level differences

Source: `results/check_syndicate_random_effect_results.json`. $\tau_\alpha$ = 0.046 against $\sigma_{\text{div}}$ = 0.052 at the reference size (ratio 0.88): persistent between-syndicate level differences are real and material.

## Missingness

Source: `results/missingness_check_results.json`. Every filing is assigned one inferential disposition before any selection diagnostic is calculated.

- Of 1065 filings: **107** have no eligible outcome structurally, **20** have economic eligibility unresolved because the extraction has no deterministic reading of them (its parsers found no prior-year figure and its models were not run, which says nothing about the filings), **230** are scientific exclusions, **9** have an eligible but unavailable outcome, **25** have the outcome but no usable composition, and **674** enter the model.
- The response is membership in the 674-record model sample within the 708-record supported disclosure-defined target. The broader potential target is 728 if all unresolved filings were eligible. Included records have median size £411.4m, against £29.2m for target-population records not included (Mann-Whitney p < 0.001).
- The 230 scientific exclusions are, by detail: 128 development on a net or unstated basis; 41 the filing prints no premium amount for any non-life line of business (a contract form or distribution channels only; scope); 28 a run-off year; 23 life business (scope); 5 adjudicated a take-on, not development; 4 no opening-reserve base above the floor; 1 adjudicated a movement in the provision, not development. 64 of them are scope exclusions: a record is out of scope only if its filing prints no premium amount for any non-life line of business (life books are out of scope as life business; a page reading of the filing decides, and outranks the models' readings in both directions). 12 records stay in the target as composition unavailable because the filing prints premium by line although every model's mix names none (the extraction lost the lines), and 0 because another model's reading names a line the adopted block's mix lost, for a record no page has been read for; they get no weights.
- The former 128-case structural grouping is withdrawn: the 20 records with no deterministic reading (the extraction's parsers found no prior-year figure and its models were not run) establish only that the extraction did not read them, not economic ineligibility. Missing-at-random cannot be established.

Three sensitivities are reported instead of resting on it. Bounded inverse-probability weighting with the disclosed 0.15 probability floor moves the pooling exponent from $k = 0.586$ to $0.611$ and leaves the concentration exponent and the floor within 0.003 of the adopted fit; 0.10 and 0.20 cap fits report the cap sensitivity, and intervals condition on the fitted weights. The high-volatility eligible-outcome stress moves the conditional bracketed estimate from $k = 0.582$ at $c=1$ to $0.554$ at $c=5$, between $0.554$ and $0.582$ across the grid --- a construction that makes the predominantly small missing books more volatile, so it cannot test the adverse-to-sub-linearity direction --- and moves the concentration exponent and the clean-regime tail materially, so the tail is **not** unaffected. A separate broader-potential-target stress assumes all 20 eligibility-unresolved filings were eligible, appends them with the 9 known unavailable outcomes, and moves $k$ from $0.560$ at $c=1$ to $0.534$ at $c=5$; it is not a bound or an eligibility estimate. See the manuscript for all three.

## Open questions

These are unresolved on public data and nothing downstream rests on them. The manuscript states each where it arises; `paper/audit_numbers.py` gate M keeps that list and the register in step.

- whether pooling is slower than the finite-variance independent $\sqrt N$ benchmark -- a floor-plus-$\sqrt N$ alternative is not predictively separable;
- the exact value of $k$ inside its theoretical bracket $[\tfrac12, 1]$: fixing $k = \tfrac12$ moves Vignette 1's VaR$_{99.5}$ by -1.8% under the size-only headline operator, and the 100m/2,000m scale ratio from 2.45 to 2.38 under that operator (the same at every $H$: both fits have $\gamma = 0$ in the likelihood);
- whether the size-dispersion decline continues past about GBP 1bn;
- the within-book concentration--location slope, which is unresolved rather than zero;
- the long-tail share slope, not distinguishable from zero ($\beta_{\text{LT}} = +0.29$ $[-0.01, +0.57]$);
- the concentration functional form, which is indeterminate.

The floor is retained as a **structural choice about extrapolation**, not as an adjudicated asymptote: a floorless law is not predictively separable from the floored one, and the floor's posterior is conditional on having fitted a floored model. $\mu = 0$ is a **fitting restriction**, not a transfer principle: the operator rescales the raw severity, so a **clean** donor's persistent level is carried across and scaled by the size ratio, while an **RITC** donor's realised level is carried through the nonlinear rank map, where it is neither separable as a scaled location nor identified or removed.
