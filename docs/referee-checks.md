# Referee checks — tail support, currency entanglement, pooling CV, maturity, size-only operator, mean-zero boundary

Six checks requested in review, each with a pre-agreed decision rule. All run on the
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
predictive CV**. → State this, and rest the sub-linear-pooling claim on the **posterior
$P(k>0.5)=1.00$** (a statement about the fitted exponent, not out-of-sample prediction). This
makes the criterion consistent with the rest of the paper.

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
