# Referee checks — tail support, currency entanglement, pooling CV, maturity, size-only operator, mean-zero boundary

> **Status: review record, generated.** This logs the checks requested across successive
> review rounds, each with its pre-agreed decision rule. Every section is written from its
> result file by `src/build_current_results.py` at each manifest run, and each decision is
> worded from the current values: a record that no longer supports a decision's words stops
> the build. Where the decision taken when a check was first run has since been withdrawn, a
> note says so. For the full current results use the generated `docs/current-results.md` in the
> analysis repository; the manuscript governs wherever the two differ. The manuscript does not
> cite this file.

9 checks, each with a pre-agreed decision rule. All run on the
single-currency (GBP) dataset. Scripts: `check_*.py`; results: `check_*_results.json`.

---

## 1. Effective independent support in the Vignette-1 tail (`check_tail_support_syndicate.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_tail_support_syndicate_results.json` at each manifest run.

**Concern.** Top transferred severities can repeat syndicates, so "about four donors" may be
fewer than four independent syndicates.

**Result** (de-RITC shape-aware, posterior-mean parameters; 691 donors, 120 syndicates):

- **(a) Exceedance sets.** VaR99.5: **4 syndicate-years = 3 distinct syndicates** (1991_2020, 1884_2016, 1991_2018, 1856_2018; 1991 appears in 2020 and 2018).
  VaR99: 7 syndicate-years = **6 distinct syndicates** (1991 appears in 2020 and 2018).
- **(b) ICC.** Syndicate random-intercept on $z=S/\hat\sigma$ (89 syndicates with $\ge$3 obs, 649 observations):
  **ICC = 0.282** ($\tau_\alpha^2=0.53$, $\sigma_\varepsilon^2=1.35$) — **non-trivial** (threshold 0.1).
- **(c) Syndicate-block bootstrap** (B=4000, whole syndicates resampled): distinct syndicates
  supplying the VaR99.5 exceedances **median 2 [1, 4]**; VaR99 **median 4 [2, 6]**;
  VaR99.5 = 0.311 [0.220, 0.376].

**Decision.** ICC is non-trivial, and under syndicate resampling the effective tail support is
**~2 syndicates [1–4]**, not four independent draws. → **Recast the tail-support sentence in
syndicate units**.

Vignette 2 is *not* the stronger evidence to promote in its place. Its Δ is a
within-transition contrast whose direction follows from the constrained monotonicity
of the operator in the target's size and concentration: with $\gamma\ge0$ and a fixed
old-to-new target the sign is fixed before any data are seen, so it carries no
evidential weight of its own. Its magnitude is informative; its sign is structural.

---

## 2. Currency / year-effect entanglement (`check_currency_entanglement.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_currency_entanglement_results.json` at each manifest run.

**Concern.** USD share trends 6%→44% and conversion uses the year-end rate, so the sterling
adjustment is time-correlated and could alias the reserve cycle $m_t$.

**Result** (directional-shock model = systemic M1; $\tau_m$ is the standard deviation of the
reporting-year location shock in that model, not the adopted model's floor).

| | $\tau_m$ | $k$ |
|---|---|---|
| Sterling (converted) | 0.0187 | 0.562 |
| Nominal (as-reported) | 0.0188 | 0.564 |
| Sterling + USD-share year covariate | 0.0180 | 0.563 |

- $m_t^{\text{sterling}}-m_t^{\text{nominal}}$ correlates **-0.03** with USD-share$_t$ and
  **+0.22** with the year-end rate.
- USD-share covariate coefficient $\beta=+0.064$ **[-0.046, 0.172]** — the interval includes 0;
  adding it moves $\tau_m$ from 0.0187 to 0.0180.

**Decision.** Three currency treatments were compared on the same sample: sterling converted at the reporting-date H.10 rate, nominal as-reported, and sterling with the year's USD share as a covariate. $\tau_m$ and the shape of $m_t$ are stable across all three, and the covariate's coefficient is unresolved — its interval includes zero. → **Report the systemic component as stable under these three treatments.** An unresolved coefficient is not a demonstration that currency treatment and the reserve cycle are unentangled: stability across three related fits and an interval that spans zero are both consistent with an FX trend this design cannot separate from the cycle, and the year-end conversion date is common to two of the three. Do not state the absence of entanglement as a finding.

---

## 3. Pooling comparison under by-syndicate CV (`check_pooling_cv.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_pooling_cv_results.json` and `results/check_cv_clustered_se_results.json` at each manifest run.

**Concern.** Appendix 3.1 adjudicated M1 (free $k$) vs M2 ($\sqrt N$+floor, $k$=0.5) on
observation-level PSIS-LOO (optimistic under clustering), whereas the headline comparison uses
5-fold by-syndicate CV.

**Result** (5 by-syndicate folds; 691 syndicate-years from 120 syndicates; held-out ELPD):

- ΔELPD(M1 − M2) = **-1.20, SE 1.54**; M1 has the higher held-out density on **38%** of
  syndicate-years.
- The Bayesian bootstrap over syndicate totals, the criterion the manuscript rests on: ΔELPD
  (free $k$ − $k=\tfrac12$+floor) = -1.20, 95% credible interval **[-4.5, 1.9]**,
  $P(\text{free }k\text{ predicts better}) = 0.23$.

**Decision.** Under the by-syndicate criterion the difference is within two standard errors, and
M2 is ahead on the point estimate: the pooling **distinction is not adjudicated by predictive CV**.
→ State this. **Superseded recommendation:** the original advice here was to rest the claim on
$P(k>0.5)=1.00$. That probability is one by construction: theory bounds $k$ to $[\tfrac12,1]$ and the
prior keeps it there. The manuscript rests the claim on $k<1$, which the by-syndicate comparison with
fixed $k=1$ establishes; it does not claim $k>\tfrac12$, and it reports what fixing $k=\tfrac12$ does
to the transferred stresses.

---

## 4. Size–maturity partial confound (`check_size_maturity.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_size_maturity_results.json` at each manifest run.

**Concern.** Larger books may be more mature/vintage-diversified, so part of the size effect is
maturity.

**Result** (two weak proxies; $k$ to 3 dp, with 95% HDI; $n=691$):

| Model | $k$ | proxy coef on log-dispersion |
|---|---|---|
| Base (two-regime) | 0.565 [0.505, 0.636] | — |
| + age-in-window ($t-$ first observed year) | 0.550 [0.503, 0.609] | $\delta=+0.114$ [0.028, 0.207] |
| + log(reserve/GWP) | 0.559 [0.503, 0.628] | $\delta=+0.024$ [-0.049, 0.098] |

Control regression $|z|\sim\log R+$ proxy: age coef +0.134 (t=3.31); log(R/GWP) coef +0.025 (t=0.58).

**Decision.** Both proxies move $k$ down, by at most 0.015 (0.550 and 0.559 against 0.565), so neither proxy explains the
size effect away. The age term's coefficient is resolved (its interval excludes zero); the duration term's is unresolved (its interval spans zero).
→ Write "**$k$ was stable to the available (weak) maturity proxies**" — not that maturity is ruled out.
*(The decision first recorded here, that the age proxy was negligible and that the duration control moved
$k$ up, was written for an earlier fit and is withdrawn.)*

---

## 5. Size-only ($\gamma=0$) operator vignette VaRs (`check_gamma0_vignette.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_gamma0_vignette_results.json` at each manifest run.

**Purpose.** If concentration is reframed as an optional overlay with $\gamma=0$ default, the
size-plus-floor operator's tail numbers are needed.

**Result** (centres at the posterior-mean operator; 95% cluster×posterior intervals in brackets):

| | Full ($\gamma\approx0.30$) | Size-only ($\gamma=0$) |
|---|---|---|
| V1 VaR99 | 0.254 [0.184, 0.362] | 0.273 [0.202, 0.394] |
| V1 VaR99.5 | 0.314 [0.220, 0.424] | 0.337 [0.237, 0.460] |
| V2 Δ99.5 | 0.022 [0.014, 0.031] | 0.019 [0.013, 0.026] |

**Decision.** The $\gamma=0$ vignette figures are **close** to the full-operator ones (V1 99.5
0.314 vs 0.337, +7%; V2 Δ +0.022 vs +0.019), consistent with the small Shapley concentration
effect. → This **quantitatively backs "a size-only operator is a defensible alternative"** and
supports presenting $\gamma=0$ as the default with concentration as an overlay.

---

## 6. Mean-zero boundary for persistent adverse development (`check_mean_zero_boundary.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_mean_zero_boundary_results.json` at each manifest run.

**Purpose.** Bound how much fixing $\mu=0$ could understate stress where development is
persistently adverse.

**Result.**

- **(a)** Pooled within-syndicate AR(1) of $S$ = **-0.03** (median per-syndicate +0.02, interquartile
  range [-0.19, +0.25]; 78 syndicates with at least 4 observations) — persistence is **weak**.
- **(b)** Syndicate random-intercept: **7/89 (7.9%)** of syndicates have a credibly positive
  (adverse) mean; 1/89 credibly negative.
- **(c)** Most-persistent decile (7 syndicates): mean $S=+0.002$, mean $\sigma=0.065$ →
  implied one-year mean contribution **≈0.03σ**.

**Decision.** Persistence is weak and the credibly-adverse share is small, so **one sentence
conceding the boundary suffices** — but note the small subset (≈8%) with a persistently
positive mean; in the most persistent decile the $\mu=0$ stress understates the one-year mean by
about 0.03σ.

---

## 7. Heteroscedastic (size-loaded) scale shock — the last unfitted specification (`calibrate_dispersion_hetscale.py`)

> Generated block: written by `src/build_current_results.py` from
> `model/dispersion_calibration_hetscale.json` and `results/check_bayes_model_compare_results.json` at each
> manifest run.

**Concern.** $k$-robustness had been shown against a size-loaded *mean* shock (M3) but not
against a size-loaded *scale* shock — where large syndicates' scale amplitudes co-move more.
That is where the pooling finding lives and the form shared-slip volatility dependence would
take, so it bears most directly on $k$.

**Result** (M4: $\log\sigma_{it}=(1+\psi_s\,\widetilde{\log R_{\text{eff}}})\,s_t+\ldots$;
$\psi_s=0$ = uniform-scale headline H0; $n=691$):

| | $k$ | $\gamma$ | $\sigma_{\text{undiv}}$ | $\psi_s$ | ΔELPD vs H0 |
|---|---|---|---|---|---|
| H0 (uniform scale) | 0.565 | 0.300 | 0.031 | ≡0 | — |
| M4 (size-loaded scale) | **0.566** [0.504, 0.637] | 0.307 | 0.032 | **-0.04 [-0.55, 0.51]** | -1.78 [-2.79, -0.79] |

- $k$ moves by 0.001 (0.565 under H0, 0.566 under M4). *(Both probabilities quoted in the original —
  $P(k>0.5)=1.00$ and $P(k<1)=1.00$ — are one by construction: theory bounds $k$ to $[\tfrac12,1]$
  and the prior keeps it there.)*
- $\psi_s$ is **weakly identified** (HDI spans 0, $P(\psi_s>0)=0.43$), and M4 predicts **worse** than the uniform-scale model (ΔELPD -1.78, Bayesian bootstrap over syndicates 95% interval [-2.79, -0.79]; better in 3 of the 20,000 bootstrap draws): no evidence that
  large syndicates' scales co-move more.
- The matching diagnostic (within-year mean $|z|$ in the large tercile) is already well fit by
  the uniform model (observed 1.01 in band [0.88, 1.18], $p_{\text{PPC}}=0.49$) — no scale
  co-movement excess exists to capture. What drives any remaining co-movement is not identified:
  pair-specific overlap or residual covariance would have to be fitted directly, and is not fitted here.

**Decision.** $k$ is stable under the heteroscedastic scale shock. All the co-movement models
fitted load a *common* reporting-year factor; pair-specific shared-slip or residual-noise
dependence is not fitted anywhere, so this bounds the common-factor channel only. → Rest the
load-bearing case on **sub-linearity: $k<1$**. *(The original wording here rested it on $P(k<1)=1.00$
"plus the positive floor". Both were withdrawn: the probability is tautological on the bracketed
support, and the floor is not predictively separable from a floorless law, so the manuscript retains
it as a structural choice about extrapolation, not as evidence.)* Treat "above $\sqrt N$" as
non-load-bearing: the $\sqrt N$+floor model (M2) is not distinguished from M1 by by-syndicate CV
(§3 above).
*(When first run, this check read M4 as LOO-neutral; at the current fit the size-loaded scale predicts worse, so that reading is withdrawn.)*

---

## 8. Size vs concentration: association, redundancy, separability (`check_size_concentration_assoc.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_size_concentration_assoc_results.json` and `model/dispersion_posterior_draws_ritc.npz` at
> each manifest run.

**Why.** The operator's effective size is $\log R_{\text{eff}}=\log R-\gamma\log H$, so $k$ (on
size) and $\gamma$ (on concentration) are separately identified only if $\log R$ and $\log H$
are not collinear. If size and concentration were redundant, the two exponents could not be
told apart. Unit: syndicate-year ($n=691$).

**Result.**

- **(a) Association** — modest and negative (bigger books slightly less concentrated):
  $\log R$ vs HHI Pearson **-0.29** ($p\approx10^{-14}$), Spearman -0.29; within reporting year
  Spearman -0.33; $\log R$ vs $\log(1/H)$ (effective line count) Pearson +0.30.
- **(b) Redundancy** — essentially none: **VIF($\log R$)=1.17, VIF($\log(1/H)$)=1.14**
  (with year fixed effects), **condition number of [$\log R,\log H$] = 1.37**, and size explains
  only **$R^2=0.081$** of HHI. All below the usual collinearity thresholds (VIF<2.5, cond<~10).
- **(c) Separability** — concentration varies at fixed size: **median within-size-decile HHI IQR
  width = 0.217** (between 0.07 and 0.29 across the 10 size deciles). The size×concentration tercile
  grid is weakly non-independent ($\chi^2=66.7$ on 4 degrees of freedom, $p\approx10^{-13}$, **Cramér's V = 0.220**).

- **(d) Posterior identification** (from the 6,000 headline draws, `dispersion_posterior_draws_ritc.npz`).
  The data-design checks above concern the *covariates*; the direct question is whether the
  *posterior* of $k$ and $\gamma$ is entangled. They are weakly and mildly positively correlated:
  $\text{corr}(k,\gamma)=\mathbf{+0.12}$ (Pearson; +0.09 Spearman). $k$'s real posterior trade-off
  is with the floor, $\text{corr}(k,\sigma_{\text{undiv}})=\mathbf{-0.57}$, and the diversifiable
  scale, $\text{corr}(k,\sigma_{\text{div}})=+0.41$; $\gamma$ in turn trades off with
  $\sigma_{\text{div}}$ (+0.54) and is only weakly correlated with the floor (+0.16). So $k$ and
  $\gamma$ are close to posterior-separable, and the residual identification tension for $k$ is
  against the size-invariant floor, not concentration.

**Decision.** Size and concentration are **weakly associated but not redundant**; $k$ and
$\gamma$ are separately identified — data-side (VIF≈1.2, condition number 1.4) *and*
posterior-side ($\text{corr}(k,\gamma)=+0.12$). State the posterior correlation at its value, and note
that $k$'s main posterior trade-off is with the floor (-0.57), not $\gamma$. The modest negative
covariate association (-0.29) is worth one sentence but does not compromise separability.

---

## 9. Temporal correlation of PYD severity across consecutive years (`check_pyd_temporal_correlation.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_pyd_temporal_correlation_results.json` (with `results/check_mean_zero_boundary_results.json`
> and `results/check_syndicate_random_effect_results.json` for the cross-references) at each manifest run.

**Why.** The pooling likelihood treats a syndicate's yearly severities as conditionally
independent given size/HHI (with $\mu=0$). Strong within-syndicate serial correlation in
$S=\text{PYD}/\text{reserves}$ would violate that and shrink the effective sample. Unit:
consecutive-year pairs within syndicate (89 syndicates ≥3 obs, 515 lag-1 pairs).

**Result.**

- **Lag-1, de-meaned within syndicate** (the *dynamic* component): Pearson **-0.071**
  [-0.15, +0.04] (syndicate block bootstrap), Spearman +0.075, within-syndicate permutation
  **p = 0.99** — indistinguishable from zero. Implied variance-inflation
  $(1+\rho)/(1-\rho)=0.87$ — a point diagnostic under the fitted lag-1 structure, not an established
  absence of effective-sample loss.
- **Lag-1, raw level** (not de-meaned): Pearson +0.34, Spearman **+0.49** — moderate, but this is
  the *persistent per-syndicate level* (sign), not dynamics.
- **Direction persistence**: **72.0%** of consecutive pairs share the sign of PYD (514 pairs,
  binomial $p<0.001$) — releasers keep releasing.
- **Lag-2 de-meaned**: Pearson -0.26, Spearman -0.05 (no positive persistence at two years).

**Decision.** The within-syndicate temporal structure is a **persistent level (sign) effect,
not serial dependence detectable in the fluctuations**: once each syndicate's mean is
removed, **no positive residual lag-1 association is detected** (Pearson $-0.071$
$[-0.15,+0.04]$, permutation $p=0.99$). That is a non-detection, not a demonstration of
conditional independence. So the pooling likelihood's conditional-independence assumption is
**not contradicted** for the *dispersion* process — a failure to detect, not a demonstration that
it holds — and the persistent syndicate intercept is material when tested directly
($\tau_\alpha=0.041$); the only serial feature is the persistent per-syndicate mean, which is exactly
the $\mu=0$ boundary already bounded in §6 (8% credibly-positive means, about 0.03σ a year in the
most-persistent decile). Report the raw Spearman 0.49 and its decomposition so the persistence is not
mistaken for a dynamic AR effect the model omits.

---

## Bookkeeping (labels, not re-runs)

> Generated block: written by `src/build_current_results.py` from `model/exposure_results.json`,
> `data/pyd_basis_register.json`, `model/dispersion_calibration_ritc.json` and
> `results/ritc_tail_shape_results.json` at each manifest run.

- **Donor pool = fit sample.** The $n=691$ dispersion-fit sample and the transfer pool
  coincide: the one syndicate-year the donor-pool filter's `eligible_for_capital` (N4) guard
  used to drop (**syndicate 2015, year 2014**, the earlier 789-vs-790 gap) is a net-basis
  record and leaves at the basis step (`data/pyd_basis_register.json`), so the guard excludes
  nothing.
- **Three $\nu_{\text{RITC}}$ figures.** Different estimators on different populations:
  **6.61** = headline two-regime Bayesian model, the posterior mean of $\nu_{\text{clean}}\!\cdot\!e^{-\lambda}$, full
  $n=691$ (`calibrate_dispersion_ritc`); **6.66** = direct Student-t MLE on the 34 flagged residuals
  of the same $n=691$ CALIB population (`ritc_tail_shape`, "CALIB"); **1.32** = direct MLE on the
  15 flagged residuals of the strict rescaling population $n=362$ (`ritc_tail_shape`, "N5").
  Label each population in the text (the round-54 record gave 2.54 / 1.23 / 1.10 on $n=678$ and
  $n=347$; the round before, 2.32 / 2.16 / 1.99 on $n=679$ / $n=388$).
