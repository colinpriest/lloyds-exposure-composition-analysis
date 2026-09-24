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

**Result** (de-RITC shape-aware, posterior-mean parameters; 685 donors, 118 syndicates):

- **(a) Exceedance sets.** VaR99.5: **4 syndicate-years = 3 distinct syndicates** (1991_2020, 1991_2018, 3010_2024, 2468_2016; 1991 appears in 2020 and 2018).
  VaR99: 7 syndicate-years = **5 distinct syndicates** (1991 appears in 2020 and 2018; 3010 appears in 2024 and 2023).
- **(b) ICC.** Syndicate random-intercept on $z=S/\hat\sigma$ (88 syndicates with $\ge$3 obs, 644 observations):
  **ICC = 0.329** ($\tau_\alpha^2=0.56$, $\sigma_\varepsilon^2=1.15$) — **non-trivial** (threshold 0.1).
- **(c) Syndicate-block bootstrap** (B=4000, whole syndicates resampled): distinct syndicates
  supplying the VaR99.5 exceedances **median 2 [1, 4]**; VaR99 **median 4 [1, 6]**;
  VaR99.5 = 0.278 [0.209, 0.347].

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

**Concern.** USD share trends 6%→45% and conversion uses the year-end rate, so the sterling
adjustment is time-correlated and could alias the reserve cycle $m_t$.

**Result** (directional-shock model = systemic M1; $\tau_m$ is the standard deviation of the
reporting-year location shock in that model, not the adopted model's floor).

| | $\tau_m$ | $k$ |
|---|---|---|
| Sterling (converted) | 0.0207 | 0.563 |
| Nominal (as-reported) | 0.0207 | 0.566 |
| Sterling + USD-share year covariate | 0.0201 | 0.562 |

- $m_t^{\text{sterling}}-m_t^{\text{nominal}}$ correlates **-0.03** with USD-share$_t$ and
  **+0.04** with the year-end rate.
- USD-share covariate coefficient $\beta=+0.062$ **[-0.060, 0.176]** — the interval includes 0;
  adding it moves $\tau_m$ from 0.0207 to 0.0201.

**Decision.** Three currency treatments were compared on the same sample: sterling converted at the reporting-date H.10 rate, nominal as-reported, and sterling with the year's USD share as a covariate. $\tau_m$ and the shape of $m_t$ are stable across all three, and the covariate's coefficient is unresolved — its interval includes zero. → **Report the systemic component as stable under these three treatments.** An unresolved coefficient is not a demonstration that currency treatment and the reserve cycle are unentangled: stability across three related fits and an interval that spans zero are both consistent with an FX trend this design cannot separate from the cycle, and the year-end conversion date is common to two of the three. Do not state the absence of entanglement as a finding.

---

## 3. Pooling comparison under by-syndicate CV (`check_pooling_cv.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_pooling_cv_results.json` and `results/check_cv_clustered_se_results.json` at each manifest run.

**Concern.** Appendix 3.1 adjudicated M1 (free $k$) vs M2 ($\sqrt N$+floor, $k$=0.5) on
observation-level PSIS-LOO (optimistic under clustering), whereas the headline comparison uses
5-fold by-syndicate CV.

**Result** (5 by-syndicate folds; 685 syndicate-years from 118 syndicates; held-out ELPD):

- ΔELPD(M1 − M2) = **-0.51, SE 1.47**; M1 has the higher held-out density on **41%** of
  syndicate-years.
- The Bayesian bootstrap over syndicate totals, the criterion the manuscript rests on: ΔELPD
  (free $k$ − $k=\tfrac12$+floor) = -0.51, 95% credible interval **[-3.7, 2.6]**,
  $P(\text{free }k\text{ predicts better}) = 0.37$.

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

**Result** (two weak proxies; $k$ to 3 dp, with 95% HDI; $n=685$):

| Model | $k$ | proxy coef on log-dispersion |
|---|---|---|
| Base (two-regime) | 0.568 [0.505, 0.639] | — |
| + age-in-window ($t-$ first observed year) | 0.552 [0.502, 0.613] | $\delta=+0.125$ [0.037, 0.214] |
| + log(reserve/GWP) | 0.571 [0.505, 0.649] | $\delta=-0.011$ [-0.078, 0.057] |

Control regression $|z|\sim\log R+$ proxy: age coef +0.140 (t=3.66); log(R/GWP) coef -0.024 (t=-0.64).

**Decision.** The two proxies move $k$ in opposite directions, by at most 0.016 (0.552 and 0.571 against 0.568), so neither proxy explains the
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

| | Full ($\gamma\approx0.50$) | Size-only ($\gamma=0$) |
|---|---|---|
| V1 VaR99 | 0.231 [0.169, 0.331] | 0.266 [0.194, 0.347] |
| V1 VaR99.5 | 0.278 [0.197, 0.407] | 0.296 [0.223, 0.444] |
| V2 Δ99.5 | 0.020 [0.012, 0.030] | 0.017 [0.011, 0.025] |

**Decision.** The $\gamma=0$ vignette figures are **close** to the full-operator ones (V1 99.5
0.278 vs 0.296, +7%; V2 Δ +0.020 vs +0.017), consistent with the small Shapley concentration
effect. → This **quantitatively backs "a size-only operator is a defensible alternative"** and
supports presenting $\gamma=0$ as the default with concentration as an overlay.

---

## 6. Mean-zero boundary for persistent adverse development (`check_mean_zero_boundary.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_mean_zero_boundary_results.json` at each manifest run.

**Purpose.** Bound how much fixing $\mu=0$ could understate stress where development is
persistently adverse.

**Result.**

- **(a)** Pooled within-syndicate AR(1) of $S$ = **-0.09** (median per-syndicate +0.02, interquartile
  range [-0.26, +0.25]; 80 syndicates with at least 4 observations) — persistence is **weak**.
- **(b)** Syndicate random-intercept: **12/88 (13.6%)** of syndicates have a credibly positive
  (adverse) mean; 3/88 credibly negative.
- **(c)** Most-persistent decile (8 syndicates): mean $S=+0.000$, mean $\sigma=0.070$ →
  implied one-year mean contribution **≈0.00σ**.

**Decision.** Persistence is weak and the credibly-adverse share is small, so **one sentence
conceding the boundary suffices** — but note the small subset (≈14%) with a persistently
positive mean; in the most persistent decile the $\mu=0$ stress understates the one-year mean by
about 0.00σ.

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
$\psi_s=0$ = uniform-scale headline H0; $n=685$):

| | $k$ | $\gamma$ | $\sigma_{\text{undiv}}$ | $\psi_s$ | ΔELPD vs H0 |
|---|---|---|---|---|---|
| H0 (uniform scale) | 0.568 | 0.499 | 0.034 | ≡0 | — |
| M4 (size-loaded scale) | **0.568** [0.503, 0.641] | 0.493 | 0.034 | **+0.02 [-0.45, 0.51]** | -1.43 [-2.17, -0.71] |

- $k$ moves by 0.000 (0.568 under H0, 0.568 under M4). *(Both probabilities quoted in the original —
  $P(k>0.5)=1.00$ and $P(k<1)=1.00$ — are one by construction: theory bounds $k$ to $[\tfrac12,1]$
  and the prior keeps it there.)*
- $\psi_s$ is **weakly identified** (HDI spans 0, $P(\psi_s>0)=0.53$), and M4 predicts **worse** than the uniform-scale model (ΔELPD -1.43, Bayesian bootstrap over syndicates 95% interval [-2.17, -0.71]; better in 0 of the 20,000 bootstrap draws): no evidence that
  large syndicates' scales co-move more.
- The matching diagnostic (within-year mean $|z|$ in the large tercile) is already well fit by
  the uniform model (observed 0.98 in band [0.86, 1.15], $p_{\text{PPC}}=0.48$), so this check
  detects no excess scale co-movement for the model to capture. That is one test's non-detection,
  not a demonstration that none exists. What drives any remaining co-movement is not identified:
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
told apart. Unit: syndicate-year ($n=685$).

**Result.**

- **(a) Association** — modest and negative (bigger books slightly less concentrated):
  $\log R$ vs HHI Pearson **-0.30** ($p\approx10^{-15}$), Spearman -0.29; within reporting year
  Spearman -0.32; $\log R$ vs $\log(1/H)$ (effective line count) Pearson +0.31.
- **(b) Redundancy** — essentially none: **VIF($\log R$)=1.17, VIF($\log(1/H)$)=1.13**
  (with year fixed effects), **condition number of [$\log R,\log H$] = 1.37**, and size explains
  only **$R^2=0.088$** of HHI. All below the usual collinearity thresholds (VIF<2.5, cond<~10).
- **(c) Separability** — concentration varies at fixed size: **median within-size-decile HHI IQR
  width = 0.188** (between 0.08 and 0.23 across the 10 size deciles). The size×concentration tercile
  grid is weakly non-independent ($\chi^2=61.9$ on 4 degrees of freedom, $p\approx10^{-12}$, **Cramér's V = 0.212**).

- **(d) Posterior identification** (from the 6,000 headline draws, `dispersion_posterior_draws_ritc.npz`).
  The data-design checks above concern the *covariates*; the direct question is whether the
  *posterior* of $k$ and $\gamma$ is entangled. They are weakly and mildly positively correlated:
  $\text{corr}(k,\gamma)=\mathbf{+0.05}$ (Pearson; +0.04 Spearman). $k$'s real posterior trade-off
  is with the floor, $\text{corr}(k,\sigma_{\text{undiv}})=\mathbf{-0.56}$, and the diversifiable
  scale, $\text{corr}(k,\sigma_{\text{div}})=+0.34$; $\gamma$ in turn trades off with
  $\sigma_{\text{div}}$ (+0.65) and is only weakly correlated with the floor (+0.25). So $k$ and
  $\gamma$ are close to posterior-separable, and the residual identification tension for $k$ is
  against the size-invariant floor, not concentration.

**Decision.** Size and concentration are **weakly associated but not redundant**; $k$ and
$\gamma$ are separately identified — data-side (VIF≈1.2, condition number 1.4) *and*
posterior-side ($\text{corr}(k,\gamma)=+0.05$). State the posterior correlation at its value, and note
that $k$'s main posterior trade-off is with the floor (-0.56), not $\gamma$. The modest negative
covariate association (-0.30) is worth one sentence but does not compromise separability.

---

## 9. Temporal correlation of PYD severity across consecutive years (`check_pyd_temporal_correlation.py`)

> Generated block: written by `src/build_current_results.py` from
> `results/check_pyd_temporal_correlation_results.json` (with `results/check_mean_zero_boundary_results.json`
> and `results/check_syndicate_random_effect_results.json` for the cross-references) at each manifest run.

**Why.** The pooling likelihood treats a syndicate's yearly severities as conditionally
independent given size/HHI (with $\mu=0$). Strong within-syndicate serial correlation in
$S=\text{PYD}/\text{reserves}$ would violate that and shrink the effective sample. Unit:
consecutive-year pairs within syndicate (88 syndicates ≥3 obs, 508 lag-1 pairs).

**Result.**

- **Lag-1, de-meaned within syndicate** (the *dynamic* component): Pearson **-0.089**
  [-0.19, +0.02] (syndicate block bootstrap), Spearman +0.058, within-syndicate permutation
  **p = 0.96** — indistinguishable from zero. Implied variance-inflation
  $(1+\rho)/(1-\rho)=0.84$ — a point diagnostic under the fitted lag-1 structure, not an established
  absence of effective-sample loss.
- **Lag-1, raw level** (not de-meaned): Pearson +0.48, Spearman **+0.51** — moderate. It carries the
  *persistent per-syndicate level* (sign) and any serial component together, which the demeaned
  statistic separates only as far as check (e) bounds them.
- **Direction persistence**: **72.6%** of consecutive pairs share the sign of PYD (507 pairs,
  binomial $p<0.001$) — releasers keep releasing.
- **Lag-2 de-meaned**: Pearson -0.24, Spearman -0.07 (no positive persistence at two years).

**Decision.** The within-syndicate temporal structure is **consistent with a persistent level
(sign) effect**: once each syndicate's mean is removed, **no positive residual lag-1 association is
detected** (Pearson $-0.089$ $[-0.19,+0.02]$, permutation $p=0.96$). That is a non-detection, not a
demonstration of conditional independence, and demeaning does not identify the level on its own: it
pulls the demeaned statistic down. Over these syndicates' own year sets, a process with **no persistent
level at all** whose own lag-1 correlation is 0.07 would read the observed $-0.089$ here, and one as
strong as 0.21 would still read inside the interval (check (e), which a simulation of the same statistic
on those year sets confirms).
What the contrast does exclude is dynamics alone at the raw level: a process whose own lag-1 correlation
is the observed raw +0.48 would read $+0.24$ here, which is not observed. So the raw Spearman 0.51 is not
a dynamic AR effect of that size, a serial component up to about 0.21 is not excluded, and below that
bound these diagnostics do not split level from dynamics. The pooling likelihood's conditional-independence
assumption is **not contradicted** for the *dispersion* process — a failure to detect, not a
demonstration that it holds — and the persistent syndicate intercept is material when tested directly
($\tau_\alpha=0.042$); the persistent per-syndicate mean is the $\mu=0$ boundary already bounded
in §6 (14% credibly-positive means, about 0.00σ a year in the most-persistent decile), and
dependence of a form a lag-1 statistic cannot see is not tested.

---

## Bookkeeping (labels, not re-runs)

> Generated block: written by `src/build_current_results.py` from `model/exposure_results.json`,
> `data/pyd_basis_register.json`, `model/dispersion_calibration_ritc.json` and
> `results/ritc_tail_shape_results.json` at each manifest run.

- **Donor pool = fit sample.** The $n=685$ dispersion-fit sample and the transfer pool
  coincide: the one syndicate-year the donor-pool filter's `eligible_for_capital` (N4) guard
  used to drop (**syndicate 2015, year 2014**, the earlier 789-vs-790 gap) is a net-basis
  record and leaves at the basis step (`data/pyd_basis_register.json`), so the guard excludes
  nothing.
- **Three $\nu_{\text{RITC}}$ figures.** Different estimators on different populations:
  **6.25** = headline two-regime Bayesian model, the posterior mean of $\nu_{\text{clean}}\!\cdot\!e^{-\lambda}$, full
  $n=685$ (`calibrate_dispersion_ritc`); **4.18** = direct Student-t MLE on the 36 flagged residuals
  of the same $n=685$ CALIB population (`ritc_tail_shape`, "CALIB"); **1.00** = direct MLE on the
  16 flagged residuals of the strict rescaling population $n=360$ (`ritc_tail_shape`, "N5").
  Label each population in the text (the round-54 record gave 2.54 / 1.23 / 1.10 on $n=678$ and
  $n=347$; the round before, 2.32 / 2.16 / 1.99 on $n=679$ / $n=388$).
