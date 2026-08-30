# Referee checks — tail support, currency entanglement, pooling CV, maturity, size-only operator, mean-zero boundary

> **Status: dated review record.** This logs the checks requested across successive
> review rounds, each with its pre-agreed decision rule and the decision taken at the
> time. It is **not** a current-results document: several intervals quoted below are
> from the fits as they stood when the check was run and have since moved by a few
> thousandths. For current fitted values use the generated
> `docs/current-results.md` in the analysis repository; the manuscript governs wherever the two
> differ. The manuscript does not cite this file.

9 checks, each with a pre-agreed decision rule. All run on the
single-currency (GBP) dataset. Scripts: `check_*.py`; results: `check_*_results.json`.

---

## 1. Effective independent support in the Vignette-1 tail (`check_tail_support_syndicate.py`)

**Concern.** Top transferred severities repeat syndicates, so "about four donors" may be
fewer than four independent syndicates.

**Result** (de-RITC transferred pool, posterior-mean operator; 789 donors, 118 syndicates):

- **(a) Exceedance sets.** VaR99.5: **4 syndicate-years = 4 distinct syndicates** (2003_2017,
  1183_2016, 1969_2014, 2008_2019 — no repeats at the point estimate on the converted data).
  VaR99: 8 syndicate-years = **7 distinct syndicates** (one repeat, 1183).
- **(b) ICC.** Syndicate random-intercept on $z=S/\hat\sigma$ (95 syndicates ≥3 obs):
  **ICC = 0.164** ($\tau_\alpha^2=0.90$, $\sigma_\varepsilon^2=4.61$) — **non-trivial** (> 0.1).
- **(c) Syndicate-block bootstrap** (B=4000, whole syndicates resampled): distinct syndicates
  supplying the VaR99.5 exceedances **median 3 [2, 4]**; VaR99 **median 5 [3, 7]**;
  VaR99.5 = 0.385 [0.308, 1.002].

**Decision.** ICC is non-trivial, and under syndicate resampling the effective tail support is
**~3 syndicates [2–4]**, not four independent draws. → **Recast the tail-support sentence in
syndicate units** ("the 99.5% exceedances rest on ~3–4 distinct syndicates") and **promote
Vignette 2 as the stronger evidence** (its Δ is a within-transition contrast, not a
count-of-donors tail).

---

## 2. Currency / year-effect entanglement (`check_currency_entanglement.py`)

**Concern.** USD share trends 4%→46% and conversion uses the year-end rate, so the sterling
adjustment is time-correlated and could alias the reserve cycle $m_t$.

**Result** (directional-shock model = systemic M1).

| | $\tau_m$ | $k$ |
|---|---|---|
| Sterling (converted) | 0.0220 | 0.601 |
| Nominal (as-reported) | 0.0219 | 0.606 |
| Sterling + USD-share year covariate | 0.0212 | — |

- $m_t^{\text{sterling}}-m_t^{\text{nominal}}$ correlates only **+0.24** with USD-share$_t$ and
  **−0.11** with the year-end rate — weak.
- USD-share covariate coefficient $\beta=+0.051$ **[−0.059, 0.157]** — credibly **includes 0**;
  adding it barely moves $\tau_m$ (0.0220 → 0.0212).

**Decision.** $\tau_m$ and the $m_t$ shape are stable across nominal, sterling, and
covariate-adjusted fits. → **State explicitly that the currency treatment and the reserve
cycle are not entangled**; the systemic component is not an FX-trend artefact.

---

## 3. Pooling comparison under by-syndicate CV (`check_pooling_cv.py`)

**Concern.** Appendix 3.1 adjudicated M1 (free $k$) vs M2 ($\sqrt N$+floor, $k$=0.5) on
observation-level PSIS-LOO (optimistic under clustering), whereas the headline comparison uses
5-fold by-syndicate CV.

**Result** (identical 5 by-syndicate folds as Section 4.6, held-out ELPD):

- ΔELPD(M1 − M2) = **+2.05, SE 2.09 (z = 0.98)**; M1 has higher density on **47%** of held-out
  syndicate-years.

**Decision.** Under the conservative by-syndicate criterion the difference is **~1 SE and M1
wins on fewer than half** the held-out points — the pooling **distinction is not adjudicated by
predictive CV**. → State this. **Superseded recommendation:** the original advice here was to rest the claim on $P(k>0.5)=1.00$. That probability is tautological, because $k$ is sampled on the bracketed support $[\tfrac12,1]$. The manuscript instead rests the claim on $k<1$, and quotes $P(k>\tfrac12)=0.977$ from the unconstrained refit (against a prior of $0.5$) where the comparison with independence is discussed at all.

---

## 4. Size–maturity partial confound (`check_size_maturity.py`)

**Concern.** Larger books may be more mature/vintage-diversified, so part of the size effect is
maturity.

**Result** (two weak proxies; $k$ to 3 dp, with 95% HDI):

| Model | $k$ | proxy coef on log-dispersion |
|---|---|---|
| Base (two-regime) | **0.606** [0.527, 0.679] | — |
| + age-in-window ($t-$ first observed year) | 0.579 [0.517, 0.649] | $\delta=+0.132$ [0.045, 0.225] |
| + log(reserve/GWP) | 0.658 [0.560, 0.741] | $\delta=-0.112$ [−0.214, −0.015] |

Control regression $|z|\sim\log R+$ proxy: age coef +0.046 (t=0.60, ns); log(R/GWP) coef
−0.175 (**t=−2.05**).

**Decision.** $k$ stays firmly in the pooling regime under both proxies (0.58–0.66, always
credibly $\in(0.5,1)$); the age proxy is negligible. The R/GWP proxy nudges $k$ **up** (more
pooling, not less) with a modest negative dispersion coefficient — i.e. controlling for a crude
duration proxy, if anything, **strengthens** sub-linear pooling. → Write "**$k$ was stable to
the available (weak) maturity proxies**, staying credibly sub-linear and, if anything, more
pooled under a duration control" — not that maturity is ruled out.

---

## 5. Size-only ($\gamma=0$) operator vignette VaRs (`check_gamma0_vignette.py`)

**Purpose.** If concentration is reframed as an optional overlay with $\gamma=0$ default, the
size-plus-floor operator's tail numbers are needed.

**Result** (posterior-mean centres; cluster×posterior intervals):

| | Full ($\gamma\approx0.24$) | Size-only ($\gamma=0$) |
|---|---|---|
| V1 VaR99 | 0.341 | 0.379 |
| V1 VaR99.5 | 0.393 [0.287, 1.001] | 0.415 [0.324, 1.096] |
| V2 Δ99.5 | +0.030 | +0.026 |

**Decision.** The $\gamma=0$ vignette figures are **close** to the full-operator ones (V1 99.5
0.393 vs 0.415, ~6%; V2 Δ +0.030 vs +0.026), consistent with the small Shapley concentration
effect. → This **quantitatively backs "a size-only operator is a defensible alternative"** and
supports presenting $\gamma=0$ as the default with concentration as an overlay.

---

## 6. Mean-zero boundary for persistent adverse development (`check_mean_zero_boundary.py`)

**Purpose.** Bound how much fixing $\mu=0$ could understate stress where development is
persistently adverse.

**Result.**

- **(a)** Pooled within-syndicate AR(1) of $S$ = **−0.06** (median per-syndicate −0.09; 87
  syndicates ≥4 obs) — persistence is **weak and slightly mean-reverting**, not positive.
- **(b)** Syndicate random-intercept: **8/95 (8.4%)** of syndicates credibly positive (adverse)
  mean; 2/95 credibly negative.
- **(c)** Most-persistent decile (8 syndicates): mean $S=+0.015$, mean $\sigma=0.075$ →
  implied one-year mean contribution **≈0.20σ**.

**Decision.** Persistence is weak and the credibly-adverse share is small, so **one sentence
conceding the boundary suffices** — but note the small non-trivial subset (≈8%) with a
persistently positive mean, for which the $\mu=0$ stress understates by up to ~0.2σ in a year.

---

## 7. Heteroscedastic (size-loaded) scale shock — the last unfitted specification (`calibrate_dispersion_hetscale.py`)

**Concern.** $k$-robustness had been shown against a size-loaded *mean* shock (M3, §2.8 Stage
2b) but not against a size-loaded *scale* shock — where large syndicates' scale amplitudes
co-move more. That is exactly where the pooling finding lives and the form shared-slip
volatility dependence would take, so it bears most directly on $k$.

**Result** (M4: $\log\sigma_{it}=(1+\psi_s\,\widetilde{\log R_{\text{eff}}})\,s_t+\ldots$;
$\psi_s=0$ = uniform-scale headline H0):

| | $k$ | $\gamma$ | $\sigma_{\text{undiv}}$ | $\psi_s$ | LOO vs H0 |
|---|---|---|---|---|---|
| M0 / H0 (uniform scale) | 0.606 | 0.243 | 0.021 | ≡0 | — |
| M4 (size-loaded scale) | **0.606** [0.529, 0.682] | 0.235 | 0.021 | **+0.11 [−0.72, 0.93]** | −0.01 ± 0.42 |

- $k$ **unchanged to three decimals** (0.606). *(Both probabilities quoted in the original — $P(k>0.5)=1.00$ and $P(k<1)=1.00$ — are tautological on the bracketed support $[\tfrac12,1]$ and are not evidence. The unconstrained refit gives $P(k>\tfrac12)=0.977$ against a prior of $0.5$.)*
- $\psi_s$ **unidentified** (HDI spans 0, $P(\psi_s>0)=0.63$) and LOO-neutral (−0.01 ± 0.42):
  no evidence large syndicates' scales co-move more.
- The matching diagnostic (within-year mean $|z|$ in the large tercile) is already well fit by
  the uniform model (observed 1.26 in band [1.05, 1.58], $p_{\text{PPC}}=0.48$) — no scale
  co-movement excess exists to capture. Contrast §2.8 Stage 2b: the *signed* large-tercile
  excess is real but the *magnitude* co-movement is not, so the excess is **not**
  heteroscedastic scale. What it *is* remains unidentified: directional/noise dependence
  (shared slips) is one possible explanation, but M3 failing to explain the excess through
  the mean channel does not identify the channel that does. Fitting pair-specific overlap
  or residual covariance directly would be required for that, and is not done here.

**Decision.** $k$ survives the heteroscedastic scale shock — the strongest of the
co-movement models fitted. All of them load a *common* reporting-year factor;
pair-specific shared-slip or residual-noise dependence is not fitted anywhere, so
this bounds the common-factor channel only. → Rest the load-bearing case on **sub-linearity: $k<1$**. *(The original
wording here rested it on $P(k<1)=1.00$ "plus the positive floor". Both were withdrawn: the
probability is tautological on the bracketed support, and the floor is not predictively
separable from a floorless law, so the manuscript retains it as a structural choice about
extrapolation rather than as evidence.)* Treat "above $\sqrt N$" as
non-load-bearing since the $\sqrt N$+floor model (M2) gives the same operator conclusions
(§3 above) and is not distinguished from M1 by by-syndicate CV.

## 8. Size vs concentration: association, redundancy, separability (`check_size_concentration_assoc.py`)

**Why.** The operator's effective size is $\log R_{\text{eff}}=\log R-\gamma\log H$, so $k$ (on
size) and $\gamma$ (on concentration) are separately identified only if $\log R$ and $\log H$
are not collinear. If size and concentration were redundant, the two exponents could not be
told apart. Unit: syndicate-year ($n=790$).

**Result.**

- **(a) Association** — modest and negative (bigger books slightly less concentrated):
  $\log R$ vs HHI Pearson **−0.27** ($p\approx10^{-14}$), Spearman −0.23; within reporting year
  Spearman −0.245; $\log R$ vs $\log(1/H)$ (effective line count) Pearson +0.26.
- **(b) Redundancy** — essentially none: **VIF($\log R$)=1.14, VIF($\log(1/H)$)=1.09**
  (with year fixed effects), **condition number of [$\log R,\log H$] = 1.31**, and size explains
  only **$R^2=0.073$** of HHI. All far below any collinearity threshold (VIF<2.5, cond<~10).
- **(c) Separability** — concentration varies freely at fixed size: **median within-size-decile
  HHI IQR width = 0.196** (about a fifth of the [0,1] range at every size level). The
  size×concentration tercile grid is weakly-but-significantly non-independent ($\chi^2=35.9$,
  $p=3\times10^{-7}$, **Cramér's V = 0.151**).

- **(d) Posterior identification** (from the 6,000 headline draws, `dispersion_posterior_draws_ritc.npz`).
  The data-design checks above concern the *covariates*; the direct question is whether the
  *posterior* of $k$ and $\gamma$ is entangled. It is **not, but the correlation is modest, not
  near-zero**: $\text{corr}(k,\gamma)=\mathbf{+0.18}$ (Pearson; +0.16 Spearman). $k$'s real
  posterior trade-off is **not with $\gamma$ at all** — it is with the floor,
  $\text{corr}(k,\sigma_{\text{undiv}})=\mathbf{-0.60}$, and the diversifiable scale,
  $\text{corr}(k,\sigma_{\text{div}})=+0.53$; $\gamma$ in turn trades off with $\sigma_{\text{div}}$
  (+0.59) and is essentially uncorrelated with the floor (0.00). So $k$ and $\gamma$ are close to
  posterior-separable, and the residual identification tension for $k$ is against the
  size-invariant floor, not concentration.

**Decision.** Size and concentration are **weakly associated but not redundant**; $k$ and
$\gamma$ are separately identified — data-side (VIF≈1.1, condition number 1.3) *and*
posterior-side ($\text{corr}(k,\gamma)=+0.18$). State the posterior correlation as **+0.18, not
"near-zero,"** and note that $k$'s main posterior trade-off is with the floor ($-0.60$), not
$\gamma$. The modest negative covariate association ($-0.27$) is worth one sentence but does not
compromise separability — concentration carries independent information at every size level.

## 9. Temporal correlation of PYD severity across consecutive years (`check_pyd_temporal_correlation.py`)

**Why.** The pooling likelihood treats a syndicate's yearly severities as conditionally
independent given size/HHI (with $\mu=0$). Strong within-syndicate serial correlation in
$S=\text{PYD}/\text{reserves}$ would violate that and shrink the effective sample. Unit:
consecutive-year pairs within syndicate (95 syndicates ≥3 obs, 620 lag-1 pairs).

**Result.**

- **Lag-1, de-meaned within syndicate** (the *dynamic* component): Pearson **−0.068**
  [−0.22, +0.11], Spearman +0.099, within-syndicate permutation **p = 0.93** — indistinguishable
  from zero. Implied variance-inflation $(1+\rho)/(1-\rho)=0.87\approx1$ — a point
  diagnostic under the fitted lag-1 structure, not an established absence of
  effective-sample loss.
- **Lag-1, raw level** (not de-meaned): Pearson +0.18, Spearman **+0.40** — moderate, but this is
  the *persistent per-syndicate level* (sign), not dynamics.
- **Direction persistence**: **68.8%** of consecutive pairs share the sign of PYD (618 pairs,
  binomial $p<0.001$) — releasers keep releasing.
- **Lag-2 de-meaned**: Pearson −0.17, Spearman −0.07 (no positive persistence at two years).

**Decision.** The within-syndicate temporal structure is a **persistent level (sign) effect,
not serial dependence detectable in the fluctuations**: once each syndicate's mean is
removed, **no positive residual lag-1 association is detected** (Pearson $-0.068$
$[-0.22,+0.11]$, permutation $p=0.93$). That is a non-detection, not a demonstration of
conditional independence. So the pooling likelihood's
conditional-independence assumption is **not contradicted** for the *dispersion* process -- a failure to detect, not a demonstration that it holds, and the persistent syndicate intercept is material when tested directly ($\tau_\alpha=0.041$); the only serial feature
is the persistent per-syndicate mean, which is exactly the $\mu=0$ boundary already bounded in
§6 (8.4% credibly-positive means, ~0.2σ/yr in the most-persistent decile). Report the raw
Spearman 0.40 and its decomposition so the persistence is not mistaken for a dynamic AR effect
the model omits.

## Bookkeeping (labels, not re-runs)

- **789 vs 790.** The single syndicate-year in the $n=790$ dispersion-fit sample but absent from
  the 789-donor transfer pool is **syndicate 2015, year 2014**. It is dropped by the donor-pool
  filter's additional `eligible_for_capital` (N4) guard — a target/eligibility exclusion, not a
  missing transfer input.
- **Three $\nu_{\text{RITC}}$ figures.** Different estimators on different populations:
  **1.55** = headline two-regime Bayesian model, $\nu_{\text{clean}}\!\cdot\!e^{-\lambda}$, full
  $n=790$ (`calibrate_dispersion_ritc`); **1.52** = direct Student-t MLE on the RITC subset, same
  $n=790$ CALIB population (`ritc_tail_shape`, "CALIB"); **1.08** = direct MLE on the strict
  rescaling population $n=421$ (`ritc_tail_shape`, "N5"). Label each population in the text.
