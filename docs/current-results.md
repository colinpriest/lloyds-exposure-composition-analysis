# Current results

> **Generated file — do not edit.** Written by `src/build_current_results.py` from the committed model and results JSON. Every number below is read from the file named beside it.

This is the current-results reference for the analysis behind the manuscript. `scaling_analysis_writeup.md` is a **development archive** and is not maintained against these numbers; where the two differ, this file and the manuscript are correct.

## Adopted model

Two-regime robust Bayesian pooling with a floor, fitted by NUTS, with the concentration exponent $\gamma$ fixed at 0 in the likelihood (the headline since the author's decision of 10 October 2026, option B). Source: `model/dispersion_calibration_ritc.json`.

| Quantity | Posterior mean |
|---|---:|
| pooling exponent $k$ | 0.586 |
| undiversifiable floor $\sigma_{\text{undiv}}$ | 0.0326 |
| diversifiable scale $\sigma_{\text{div}}$ | 0.0517 |
| clean-regime tail $\nu_{\text{clean}}$ | 4.93 |
| RITC-regime tail $\nu_{\text{RITC}}$ | 7.58 |
| RITC tail shift $\lambda_{\text{RITC}}$ | -0.272 |
| RITC scale term $\beta_{\text{RITC}}$ | -0.210 |
| concentration exponent $\gamma$ | 0 (fixed in the likelihood) |

Fitted on n = 672 syndicate-years (38 RITC) across 11 reporting years, seed 42. Diagnostics: 0 divergences, max $\hat R$ = 1.01, min bulk ESS = 1363.0.

## The gamma-free fit (the concentration overlay's source)

The same model with $\gamma \sim \text{HalfNormal}(1)$. Source: `model/dispersion_calibration_ritc_gamma_free.json`. Its fitted $\gamma$, with its own $k$, $\sigma_{\text{undiv}}$, $\sigma_{\text{div}}$ and $\nu$, is the concentration overlay, a labelled sensitivity; no headline figure uses it.

| Quantity | Posterior mean |
|---|---:|
| concentration exponent $\gamma$ | 0.388 [0.001, 0.856] |
| pooling exponent $k$ | 0.589 |
| undiversifiable floor $\sigma_{\text{undiv}}$ | 0.0343 |
| diversifiable scale $\sigma_{\text{div}}$ | 0.0591 |

$P(\gamma > 0.05) = 0.952$ against a prior mass of 0.960; 0 divergences, max $\hat R$ = 1.00.

## What the posterior does and does not settle

| Statement | Posterior | Prior | Status |
|---|---:|---:|---|
| $P(\nu_{\text{RITC}} < \nu_{\text{clean}})$ | 0.335 | 0.500 | the data move it below its prior mass, so the RITC tail reads as the lighter; the ordering is not imposed (the prior on $\lambda_{\text{RITC}}$ admits both signs) |
| $P(\nu_{\text{RITC}} < 2)$ | 0.011 | 0.036 | posterior probability that the RITC regime lacks a finite variance; within 0.05 of its prior mass, so its size is the prior's, not a finding |
| $P(k > \tfrac12)$, $P(k < 1)$ | $1$ by construction | $1$ | theory bounds $k$ to $[\tfrac12,1]$ (finite-variance independent $\sqrt N$ pooling to comonotonic pooling) and the prior keeps it there, so these are not findings; the endpoints are scored by syndicate as fixed alternatives |
| $P(|\beta_{\text{RITC}}| > 0.1)$ | 0.781 | 0.841 | the data move it below its prior mass; fitted in the likelihood, and the transfer operator omits it, not shown to be zero |

## Pooling comparison

Source: `results/pooling_compare_results.json`.

| Model | $k$ | elpd$_{\text{LOO}}$ |
|---|---:|---:|
| `M1_blended` | 0.588 | 675.25 |
| `M2_independent` | 0.500 | 675.34 |

**Observation-level PSIS-LOO** (`results/pooling_compare_results.json`): $\Delta$elpd (M1 blended $-$ M2 finite-variance independent $\sqrt N$) = -0.09, SE 1.61.

**By-syndicate cross-validation, Bayesian bootstrap over syndicate totals** (`results/check_cv_clustered_se_results.json`) --- the criterion the manuscript rests on, because observations within a syndicate are not independent and a plain SE understates the clustering. $\Delta$ELPD (free $k$ $-$ $k=\tfrac12$+floor) = 0.30, 95% credible interval $[-3.1, 3.6]$, $P(\text{free }k\text{ predicts better}) = 0.58$.

Neither criterion separates the two forms, so the free exponent is **not** separated from $k=\tfrac12$-plus-floor on either. That is why pooling slower than the finite-variance independent $\sqrt N$ benchmark is treated as unresolved (independence alone does not give $k=\tfrac12$ under infinite-variance aggregation).

## Size-loaded co-movement (M4)

Source: `model/dispersion_calibration_hetscale.json`. Specification as fitted:

```
log sigma_it = 0.5*log[sd_undiv^2 + sd_div^2*exp(2(k-1)*x_it)] + (1 + psi_s*(x_it - c)) * s_t + beta_ritc*1[RITC], with x_it = log(R_it/Rref) - gamma*log H_it, the dimensionless log effective size (the adopted base scale, floor included; the M4 departure is the loading on s_t); gamma = 0 in the likelihood (the headline's), so x_it = log(R_it/Rref); c = mean(log(R/Rref) - gamma_c*log H) with gamma_c = 0, the model's gamma, so the loading's sample mean is one; psi_s ~ N(0,0.5) is a linear loading coefficient, not a power elasticity; psi_s=0 => uniform-scale headline model
```

Loading $\psi_s$ = -0.030, $P(\psi_s > 0)$ = 0.452. This is a **linear loading coefficient on centred log effective size**, not a power elasticity.

M3 and M4 load a **common** reporting-year factor on size. Pair-specific shared-slip or residual-noise dependence is not fitted anywhere in this analysis, so these simulations diagnose that common-factor channel only; they do not bound residual dependence.

## Between-syndicate level differences

Source: `results/check_syndicate_random_effect_results.json`. $\tau_\alpha$ = 0.047 against $\sigma_{\text{div}}$ = 0.052 at the reference size (ratio 0.90): persistent between-syndicate level differences are real and material.

## Missingness

Source: `results/missingness_check_results.json`. Every filing is assigned one inferential disposition before any selection diagnostic is calculated.

- Of 1065 filings: **107** have no eligible outcome structurally, **20** have economic eligibility unresolved because the extraction has no deterministic reading of them (its parsers found no prior-year figure and its models were not run, which says nothing about the filings), **232** are scientific exclusions, **9** have an eligible but unavailable outcome, **25** have the outcome but no usable composition, and **672** enter the model.
- The response is membership in the 672-record model sample within the 706-record supported disclosure-defined target. The broader potential target is 726 if all unresolved filings were eligible. Included records have median size £407.6m, against £29.2m for target-population records not included (Mann-Whitney p < 0.001).
- The 232 scientific exclusions are, by detail: 129 development on a net or unstated basis; 41 the filing prints no premium amount for any non-life line of business (a contract form or distribution channels only; scope); 28 a run-off year; 23 life business (scope); 5 adjudicated a take-on, not development; 4 no opening-reserve base above the floor; 1 the filing's gross triangle does not reconcile to its own totals, and no precedence rule puts another figure in the triangle's place; 1 adjudicated a movement in the provision, not development. 64 of them are scope exclusions: a record is out of scope only if its filing prints no premium amount for any non-life line of business (life books are out of scope as life business; a page reading of the filing decides, and outranks the models' readings in both directions). 12 records stay in the target as composition unavailable because the filing prints premium by line although every model's mix names none (the extraction lost the lines), and 0 because another model's reading names a line the adopted block's mix lost, for a record no page has been read for; they get no weights.
- The former 128-case structural grouping is withdrawn: the 20 records with no deterministic reading (the extraction's parsers found no prior-year figure and its models were not run) establish only that the extraction did not read them, not economic ineligibility. Missing-at-random cannot be established.

Three sensitivities are reported instead of resting on it. Bounded inverse-probability weighting with the disclosed 0.15 probability floor moves the pooling exponent from $k = 0.586$ to $0.613$ and leaves the concentration exponent and the floor within 0.003 of the adopted fit; 0.10 and 0.20 cap fits report the cap sensitivity, and intervals condition on the fitted weights. The high-volatility eligible-outcome stress moves the conditional bracketed estimate from $k = 0.581$ at $c=1$ to $0.553$ at $c=5$, between $0.553$ and $0.581$ across the grid --- a construction that makes the predominantly small missing books more volatile, so it cannot test the adverse-to-sub-linearity direction --- and moves the concentration exponent and the clean-regime tail materially, so the tail is **not** unaffected. A separate broader-potential-target stress assumes all 20 eligibility-unresolved filings were eligible, appends them with the 9 known unavailable outcomes, and moves $k$ from $0.560$ at $c=1$ to $0.534$ at $c=5$; it is not a bound or an eligibility estimate. See the manuscript for all three.

## Open questions

These are unresolved on public data and nothing downstream rests on them. The manuscript states each where it arises; `paper/audit_numbers.py` gate M keeps that list and the register in step.

- whether pooling is slower than the finite-variance independent $\sqrt N$ benchmark -- a floor-plus-$\sqrt N$ alternative is not predictively separable;
- the exact value of $k$ inside its theoretical bracket $[\tfrac12, 1]$: fixing $k = \tfrac12$ moves Vignette 1's VaR$_{99.5}$ by -1.2% under the size-only headline operator, and the 100m/2,000m scale ratio from 2.42 to 2.36 under that operator (the same at every $H$: both fits have $\gamma = 0$ in the likelihood);
- whether the size-dispersion decline continues past about GBP 1bn;
- the within-book concentration--location slope, which is unresolved rather than zero;
- whether the long-tail share matters for transfer: its slope is resolved positive ($\beta_{\text{LT}} = +0.30$ $[+0.01, +0.59]$) but it does not improve prediction of unseen syndicates (the composition model without the share scores $+0.0$ higher by-syndicate held-out ELPD than with it, Bayesian-bootstrap 95% credible interval $[-5.5, +6.0]$, $P = 0.49$ that the model without it predicts better), and the operator does not carry it;
- the concentration functional form, which is indeterminate.

The floor is retained as a **structural choice about extrapolation**, not as an adjudicated asymptote: a floorless law is not predictively separable from the floored one, and the floor's posterior is conditional on having fitted a floored model. $\mu = 0$ is a **fitting restriction**, not a transfer principle: the operator rescales the raw severity, so a **clean** donor's persistent level is carried across and scaled by the size ratio, while an **RITC** donor's realised level is carried through the nonlinear rank map, where it is neither separable as a scaled location nor identified or removed.
