# Exposure Diversification Analysis — Application Specification

> **Status: superseded.**
> This document describes the earlier sequential / least-squares line-of-business
> projection, which was replaced by the robust Bayesian pooling operator
> (size and concentration, Student-t, two-regime RITC tail). It is retained as a record
> of that stage and is **not** a description of the current method. See
> [`docs/current-results.md`](../docs/current-results.md) (generated) and the manuscript.
> `scaling_analysis_writeup.md` is an archived development record, not a current source.


This specification defines two components:

- **Part A — Analysis Script** (`run_analysis.py`): reads raw syndicate JSONs, performs all statistical estimation, and emits a single versioned `exposure_results.json` bundle.
- **Part B — Dashboard Viewer** (`exposure_analysis.html`): a static HTML file that loads the results bundle and renders tables, charts, and drill-through detail.  It performs **no** regression, bootstrap, posterior sampling, or raw-file parsing.

---

# PART A — ANALYSIS SCRIPT

## A.1  Purpose

`run_analysis.py` is a Python script that:

1. Reads all `syndicate_*_*.json` files from the `pdf_extraction/` folder.
2. Filters, resolves, and transforms them into an analysis dataset.
3. Runs all statistical models (frequentist, bootstrap).
4. Emits `exposure_results.json` — the single input for the viewer.

---

## A.2  Data Ingestion

### A.2.1  Source files

Read all files matching `pdf_extraction/syndicate_*_*.json`.

### A.2.2  Model resolution

Each JSON file contains a `models` object with one or more model keys (e.g. `gemini-2.5-flash`, `gpt-5-mini`).  Resolve to a single canonical record per syndicate-year:

1. If `validation.passed === true`, use the **first model** key (alphabetical).
2. If validation failed, use the model whose `prior_year_development_pct` is not null; if both are non-null, use the one with higher `prior_year_movement_confidence`.
3. If neither model has a non-null `prior_year_development_pct`, mark as INCOMPLETE.

### A.2.3  Data quality classification

Apply these rules to every file (mutually exclusive, evaluated in order):

```
1. EXCLUDED:  file.excluded === true  OR  file.manual_override_status === 'excluded'
2. SKIPPED:   file.models is absent/empty  AND  (file.first_year_syndicate OR file.reason OR file.no_triangle_data)
3. NO_RESERVES: opening_reserves_gbp_m is null or ≤ 0.1 £m  (after resolving the canonical model)
4. Otherwise, resolve the canonical model record:
   a. hasReliablePyd    = (prior_year_development_pct is not None)
   b. hasReliablePremium = (len(gross_premium_mix) > 0 AND gross_premiums_written_gbp_m > 0)
   c. isRunoff = (hasReliablePyd AND NOT hasReliablePremium AND gross_premiums_written_gbp_m == 0)
   d. isReliable = (hasReliablePyd AND (hasReliablePremium OR isRunoff))
   Result:
     - isRunoff    → IN RUNOFF
     - isReliable  → RELIABLE
     - else        → INCOMPLETE
```

### A.2.4  Filtering

**Discard** records tagged IN RUNOFF, SKIPPED, EXCLUDED, or NO_RESERVES.  Keep RELIABLE and INCOMPLETE (flagged).

### A.2.5  Parsed record fields

For each kept syndicate-year, extract from the canonical model record:

| Field | Source |
|-------|--------|
| `syndicate` | `model.syndicate` |
| `year` | `model.year` |
| `opening_reserves_gbp_m` | `model.opening_reserves_gbp_m` |
| `pyd_gbp_m` | `model.prior_year_development_gbp_m` |
| `pyd_pct` | `model.prior_year_development_pct` |
| `direction` | `model.direction` |
| `gpw_gbp_m` | `model.gross_premiums_written_gbp_m` |
| `gross_premium_mix` | `model.gross_premium_mix` |
| `lob_movements` | `model.lob_movements` |
| `primary_causes` | `model.primary_causes` |
| `standardized_narrative` | `model.standardized_narrative` |
| `named_events` | `model.named_events` |
| `confidence` | `model.prior_year_movement_confidence` |
| `data_quality_tag` | computed per §A.2.3 |

---

## A.3  Derived Computations

### A.3.1  LoB weight extraction

Compute a 13-element LoB weight vector `w_s[]` from `gross_premium_mix` for each syndicate-year.

#### Standard LoB categories

The 13 standard Lloyd's LoB categories.  **Matching order matters** — more-specific patterns are tested before broad ones:

| Priority | # | Standard LoB | Keywords / patterns (case-insensitive) |
|:---:|---|-------------|---------------------------------------|
| 1 | 6 | Reinsurance — Property | reinsurance property, property treaty, property reinsurance |
| 2 | 7 | Reinsurance — Casualty | reinsurance casualty, casualty treaty, casualty reinsurance |
| 3 | 8 | Reinsurance — Specialty | reinsurance specialty, specialty treaty, specialty reinsurance |
| 4 | 9 | Professional Lines | professional, D&O, directors, E&O, PI, financial lines |
| 5 | 10 | Accident & Health | accident, health, A&H, personal accident |
| 6 | 5 | Aviation | aviation |
| 7 | 11 | Cyber | cyber |
| 8 | 0 | Property | property, fire, damage to property |
| 9 | 1 | Casualty | casualty, third party liability, liability |
| 10 | 2 | Marine | marine, hull, cargo, transit |
| 11 | 3 | Energy | energy |
| 12 | 4 | Motor | motor |
| 13 | 12 | Aggregate | aggregate, miscellaneous, other, whole account, reinsurance (bare) |

When `"reinsurance"` appears alone (without further qualifier), map to **Aggregate** (catch-all).

#### Weight normalisation

1. Sum all `amount_gbp_m` values mapped to each standard LoB.
2. Normalise so weights sum to 1.0.
3. If no premium mix is available, fall back to equal weights across LoBs with observed `lob_movements`; if none, set `weight_source = "none"`.

#### Weight floor

Floor all LoB weights at 0.01 (1%) before computing severities, then re-normalise.

### A.3.2  Severity computation

#### Aggregate severity (Raw-A)

$$S_{\text{raw-A}} = \frac{\text{pyd\_gbp\_m}}{\text{opening\_reserves\_gbp\_m}}$$

If `opening_reserves_gbp_m` is null or ≤ 0, set to null.

**Sign correction:** If the sign of `pyd_pct` disagrees with `direction`, trust `direction` and flip the sign of `pyd_gbp_m`.  **Count and log every sign flip** for the diagnostics block.

**No winsorisation is applied.**  The ±5.0 LoB severity cap (below) is the only truncation.  Rationale: winsorising at the 1st/99th percentile while reporting VaR 99.5% and TVaR 99.5% is a direct conflict — it clips the very tail the analysis aims to characterise.

#### LoB-level severity

For each standard LoB ℓ:

1. Compute LoB reserves: $R^{(s)}_\ell = R^{(s)} \times \max(w^{(s)}_\ell, 0.01)$
2. Find movements for LoB ℓ from `lob_movements`.  If multiple entries map to the same standard LoB, sum their `amount_gbp_m`.  If `amount_gbp_m` is null for all entries, allocate the aggregate movement proportionally: $M^{(s)}_\ell = M_{\text{total}} \times w^{(s)}_\ell$.
3. Compute: $s_\ell = M^{(s)}_\ell / R^{(s)}_\ell$
4. **Cap** at ±5.0.
5. Unobserved LoBs (no movement data and no allocation): $s_\ell = 0$.

#### Reconstructed severity (Raw-B)

$$S_{\text{raw-B}} = \sum_\ell w^{(s)}_\ell \cdot s_\ell$$

### A.3.2.1  Decile statistical tests

For each decile grouping (reserves, HHI, complexity), compute:

- **One-way ANOVA F-test** for whether PYD means differ across deciles.
- **Bartlett's test** (chi-squared) for whether PYD variances differ across deciles.
- **Variance ratio** (max decile variance / min decile variance).

These are emitted in `distribution.boxplots.decile_tests`:

```json
{
  "by_reserves_decile": { "anova_f": F, "anova_p": p, "variance_ratio": R, "bartlett_chi2": chi2, "bartlett_p": p },
  "by_hhi_decile": { ... },
  "by_complexity_decile": { ... }
}
```

### A.3.3  Concentration and complexity

| Metric | Formula |
|--------|---------|
| HHI | $\sum_\ell (w^{(s)}_\ell)^2$ |
| Diversification score | $1 - \text{HHI}$ |
| Complexity | $R^{(s)} \times (1 - \text{HHI})$ |

### A.3.4  Cause classification and event grouping

Classify each syndicate-year into a **display cause category** using keyword matching against the concatenation of `primary_causes` and `standardized_narrative` (case-insensitive).  Apply rules in **priority order**; first match wins:

| Priority | Category | Keywords |
|:---:|----------|----------|
| 1 | `covid` | covid, pandemic |
| 2 | `ogden` | ogden |
| 3 | `natural_cat` | catastrophe, cat, hurricane, flood, earthquake, wildfire, storm, typhoon |
| 4 | `man_made` | man-made, explosion, fire (standalone word), collision |
| 5 | `social_inflation` | social inflation, litigation, nuclear verdict |
| 6 | `economic_inflation` | economic inflation, claims cost, cost inflation |
| 7 | `large_loss` | large loss, large claim |
| 8 | `court_rulings` | court, ruling, legal |
| 9 | `ibnr` | ibnr, incurred but not reported |
| 10 | `regulatory` | regulatory, regulation, solvency |
| 11 | `methodology` | methodology, reserving approach, assumption |
| 12 | `geopolitical` | geopolitical, sanctions, war |
| 13 | `reinsurance` | reinsurance, recoveries |
| 14 | `adverse_dev` | adverse, deterioration, prior year, strengthening |
| 15 | `uncategorised` | (default) |

**Separate fixed-effects grouping:** Create `event_group_id = "{year}_{cause_category}"`.  Events with < 3 syndicates are pooled into `"{year}_pooled"`.  Emit an **event group audit table** listing each `event_group_id`, its constituent syndicates, and whether it was pooled.

### A.3.5  Subset definitions

| Subset | Filter |
|--------|--------|
| DENSE | Years 2014–2019 |
| MID | Years 2020–2023 |
| FULL | Years 2014–2023 |
| BALANCED_K8 | 2014–2023, syndicates in ≥ 8 years |
| BALANCED_K6 | 2014–2023, syndicates in ≥ 6 years |
| BALANCED_ALL | 2014–2023, syndicates in all 10 years |
| YEAR_2024 | Year 2024 only |

For each subset, record: `n_observations`, `n_syndicates`, `year_range`, `syndicates_per_year` (min, median, max).

### A.3.6  Per-module eligibility masks

Each analysis module operates on a different eligible subset.  The analysis script computes and records these masks:

| Mask | Rule | Used by |
|------|------|---------|
| `eligible_for_distribution` | `pyd_pct` is not null | Tab 2 |
| `eligible_for_boxplot_reserves` | `pyd_pct` not null AND `opening_reserves_gbp_m` > 0 | Box plot: reserves decile |
| `eligible_for_n1` | `pyd_pct` not null, DENSE subset | Tab 3 |
| `eligible_for_n3` | `opening_reserves_gbp_m` > 5, `pyd_pct` not null, DENSE subset | Tab 5 |
| `eligible_for_capital` | `pyd_pct` not null, all LoB severity vectors computed | Tab 6 |
| `eligible_for_persona` | FULL subset, `opening_reserves_gbp_m` > 0, LoB weights available | Tabs 8–10 |

Every chart and table in the viewer must display the `N` actually used, sourced from these eligibility counts.

---

## A.4  Exposure Adjustment Engine

### A.4.1  Mix standardisation

Given a target portfolio weight vector $\mathbf{w}^{(q)}$ (13-element, summing to 1):

$$S^{(q)}_{\text{std},i} = \sum_{\ell \in \mathcal{L}} w^{(q)}_\ell \cdot s_{i\ell}$$

### A.4.2  Size adjustment

#### LoB-specific coefficients

LoB-specific size-severity elasticities $\tilde{\beta}_\ell$ are estimated from the project data via James-Stein shrinkage (§A.5.4).  The grand mean $\bar{\beta}$ is the observation-weighted mean of the estimated LoB betas — no external prior is used.

Reference size: $R_{\text{ref}} = 500$ £m.

#### Composite exponent

$$\beta_{\text{weighted}} = \sum_\ell w^{(q)}_\ell \cdot \beta_\ell$$

#### Size adjustment factor

$$A = \left(\frac{R^{(q)}}{R_{\text{ref}}}\right)^{\beta_{\text{weighted}}}$$

Guard rails: if $R^{(q)} \le 0$ or $R_{\text{ref}} \le 0$, $A = 1.0$.

#### Fully adjusted severity

$$S^{(q)}_{\text{adj},i} = S^{(q)}_{\text{std},i} \times A$$

### A.4.3  Four severity distributions for capital analysis

For each target portfolio, compute four parallel severity vectors:

| Distribution | Symbol | Formula |
|-------------|--------|---------|
| Naive | $S_{\text{naive}}$ | $S_{\text{raw-A},i}$ |
| Mix-only | $S_{\text{mix}}$ | $\sum_\ell w^{(q)}_\ell \cdot s_{i\ell}$ |
| Size-only | $S_{\text{size}}$ | $S_{\text{raw-A},i} \times (R^{(q)} / R_{\text{ref}})^{\beta_w}$ |
| Full (mix+size) | $S_{\text{full}}$ | $(\sum_\ell w^{(q)}_\ell \cdot s_{i\ell}) \times (R^{(q)} / R_{\text{ref}})^{\beta_w}$ |

**Note:** The size-only distribution uses the same portfolio-weighted $\beta_w = \sum_\ell w^{(q)}_\ell \beta_\ell$ as the full distribution (not the overall $\bar{\beta}$), so that the Shapley decomposition (§A.5.5) is internally consistent.

---

## A.5  Statistical Analyses

### A.5.1  N0 — Sampling Robustness

DENSE subset.  200 iterations of 10% syndicate-level leave-out resampling.

For each leave-out sample, compute:
- `p95_slope`: OLS slope of annual p95 severity on year
- `beta`: Size-severity elasticity from RE-GLS (§A.5.4)
- `var995`: 99.5th empirical percentile of `S_raw_a`

Report: point estimate, leave-out CV(%), bootstrap CV(%), stability flag.

### A.5.2  N1 — Tail Trend Analysis

**Visual:** For each year, compute 95th percentile of `S_raw_a` and of `S_fully_std` (standardised for both **LoB mix** and **portfolio size**).  Plot both series.

**Standardisation method (mean-preserving):**  Each observation's severity is adjusted to a common reference, then re-centred to preserve the market mean:

1. **Reference mean test:** Test whether the market mean PYD% differs significantly from zero (t-test, two-sided, α = 0.05).  If significant, the reference mean $\mu$ is the sample mean; otherwise $\mu = 0$.
2. **Mix adjustment:** Reweight to the equal-weighted average of all LoB weight vectors in the DENSE subset (one observation = one vote).
3. **Size adjustment:** Scale to the median reserve size of the DENSE subset: $S_{\text{raw-std},i} = (\mathbf{w}_{\text{ref}} \cdot \mathbf{s}_{i}) \times (R_{\text{ref}} / R_i)^{\beta_w}$
4. **Re-centring:** Shift the standardised distribution so its mean equals $\mu$: $S_{\text{std},i} = S_{\text{raw-std},i} - \bar{S}_{\text{raw-std}} + \mu$

**Rationale:** ANOVA tests (§A.3.2.1) show that PYD means do not vary significantly by reserve-size decile or complexity decile.  Therefore standardisation should affect only dispersion (tail behaviour), not the central tendency.  The raw mix+size adjustment introduces a spurious mean shift due to Jensen's inequality (the nonlinear power-law size factor does not average to 1.0).  Re-centring removes this artifact while preserving the dispersion changes that are the purpose of standardisation.

The `reference_mean_test` results are emitted in the `distribution` block for transparency.

**Inference:** Run a **full-panel quantile-like regression** on the observation-level data (not on the 6 annual p95 points).  Specifically, use the RE-GLS model (§A.5.4) with a year trend term added:

$$s_{it} = \alpha + \beta \ln(R_{it}) + \delta \cdot t + u_i + \gamma_{e(it)} + \varepsilon_{it}$$

Report the slope $\delta$ with cluster-robust SE and bootstrap CI.  The viewer labels the chart: "Annual p95 shown for intuition; inference based on full-panel model."

**P95 regression slopes:** Additionally, compute OLS slopes and 500-replicate bootstrap CIs on the per-year P95 series for both raw and standardised severity.  Report slope, SE, p-value, R², and bootstrap 95% CI.  Calculate slope reduction percentage: $(1 - \text{slope}_{\text{std}} / \text{slope}_{\text{raw}}) \times 100$.

### A.5.3  N2 — Tail Stability (Mean Excess Function)

For positive severity values only, compute the mean excess function at thresholds from the 5th to 85th percentile with ≥ 5 exceedances per threshold.  Compute for both raw and fully-standardised severity (mix + size adjusted with mean-preserving re-centring, same method as §A.5.2).

### A.5.4  N3 — Size-Severity Elasticity Estimation

#### Primary estimator: Random-Effects GLS

The primary size-elasticity estimate uses a **random-effects GLS** (RE-GLS) model that accounts for repeated syndicate measures:

$$s_{it} = \alpha + \beta \ln(R_{it}) + u_i + \gamma_{e(it)} + \varepsilon_{it}$$

where $u_i \sim N(0, \sigma^2_u)$ and $\varepsilon_{it} \sim N(0, \sigma^2_\varepsilon)$.

**Estimation procedure:**

1. Estimate $\sigma^2_u$ and $\sigma^2_\varepsilon$ from a preliminary OLS with event dummies via the between-within decomposition.
2. Compute the GLS weight $\theta_i = 1 - \sqrt{\sigma^2_\varepsilon / (\sigma^2_\varepsilon + n_i \sigma^2_u)}$ where $n_i$ is the number of years for syndicate $i$.
3. Quasi-demean: $\tilde{s}_{it} = s_{it} - \theta_i \bar{s}_i$, $\tilde{X}_{it} = X_{it} - \theta_i \bar{X}_i$ (after absorbing event means).
4. Run OLS on the quasi-demeaned data.
5. Report $\hat{\beta}$ with **cluster-robust SEs** (clustered at syndicate level).

DENSE subset, observations with `opening_reserves_gbp_m` > 5.

#### Frequentist comparison specifications

| Model | Dependent | Fixed effects | Notes |
|-------|-----------|---------------|-------|
| M0 | $S_{\text{raw-A}}$ | None | Baseline OLS |
| M1 | $S_{\text{raw-A}}$ | `event_group_id` | OLS + event FE |
| M2 | $\ln(\lvert S_{\text{raw-A}} \rvert)$ | `event_group_id` | Log-scale |
| M3 | $\ln(S_{\text{raw-A}}^2)$ | `event_group_id` | Variance-scale |
| M1-balanced | $S_{\text{raw-A}}$ | `event_group_id` | BALANCED_K8 subset |

All use cluster-robust SEs (clustered at syndicate level).

For each model, also compute and report:

- **AIC** = $n \ln(\text{RSS}/n) + 2k$
- **BIC** = $n \ln(\text{RSS}/n) + k \ln(n)$
- **Significance marker**: `***` (p < 0.001), `**` (p < 0.01), `*` (p < 0.05), `†` (p < 0.10)

#### LoB-level elasticities with James-Stein shrinkage

For each standard LoB ℓ with ≥ 10 observations:

1. Run OLS: $s_{i\ell} = \alpha_\ell + \beta_\ell \ln(R_i) + \varepsilon_{i\ell}$
2. Record $\hat{\beta}_\ell$ and its SE $\sigma_\ell$.

Shrinkage (grand mean derived from data — no external prior):
1. $\tau^2 = \text{Var}(\{\hat{\beta}_\ell\})$
2. $\bar{\beta} = \sum_\ell n_\ell \hat{\beta}_\ell \,/\, \sum_\ell n_\ell$ (observation-weighted mean of estimated LoB betas)
3. $\lambda_\ell = \tau^2 / (\tau^2 + \sigma^2_\ell)$
4. $\tilde{\beta}_\ell = \lambda_\ell \hat{\beta}_\ell + (1 - \lambda_\ell) \bar{\beta}$
5. For LoBs with < 10 observations: inflate $\sigma_\ell$ to $2\times$ median SE, ensuring strong shrinkage.

### A.5.5  N5 — Dispersion Scaling

> **Superseded.** The delivered dispersion model is the **robust Bayesian pooling model**
> (single joint law: pooling exponent $k\in[0.5,1]$, effective-line concentration $1/H$, a
> positive undiversifiable floor, heavy Student-$t$ tails split into a clean and an RITC tail
> regime), documented in [scaling_analysis_writeup.md](../scaling_analysis_writeup.md). The
> two-stage power-law / sequential framing below (N5/N6) is retained only as design history;
> it does not describe the current operator.

#### Motivation

The Bartlett test (§A.5.4) and decile analysis confirm that PYD volatility decreases with both portfolio size and LoB diversification (heteroskedasticity).  Linear models (OLS of |severity| on diversification) fail to capture this because the relationship is nonlinear — variance falls steeply initially then flattens toward an irreducible floor.

This analysis fits constrained power-law models to quantify the rate at which diversification reduces variance, separating contributions from LoB mix and portfolio size.

#### Model specification

**Target variable:**  $Y_i = s_{i}^2$ (squared PYD severity for observation $i$), an unbiased estimator of the per-observation second moment.

**Single-factor models:**

$$Y_i = A + B \cdot x_i^C + \varepsilon_i$$

where:
- $x = H = \max(1 - \text{HHI}, 0.01)$ for the mix model, or $x = R$ (opening reserves in £m) for the size model
- $A \geq 0$ is the **undiversifiable variance floor** (systematic risk that cannot be eliminated)
- $B > 0$ is the **diversifiable variance scale**
- $C \in (-1, 0)$ is the **power of diversification** — negative ensures monotonically decreasing dispersion

The floor on $H$ at 0.01 prevents the singularity $H^C \to \infty$ as $H \to 0$.

**Joint model:**

$$Y_i = A + B_1 \cdot H_i^{C_1} + B_2 \cdot R_i^{C_2} + \varepsilon_i$$

with $A \geq 0$, $B_1 > 0$, $B_2 > 0$, $C_1 \in (-1, 0)$, $C_2 \in (-1, 0)$.

This decomposes the variance reduction into **mix diversification** ($B_1 \cdot H^{C_1}$) and **size diversification** ($B_2 \cdot R^{C_2}$) contributions.

#### Estimation

Profile likelihood over the power parameters:

1. For each candidate $C$ (or pair $(C_1, C_2)$) on a grid of 200 (or $80 \times 80$) values in $(-0.99, -0.01)$:
   - Compute $x_i^C$ (and $R_i^{C_2}$ for the joint model)
   - The model is linear in $(A, B)$ (or $(A, B_1, B_2)$), so solve by OLS
   - Reject solutions where $B \leq 0$ (or $B_k \leq 0$) or $A < 0$ (enforcing monotonicity and non-negative floor)
   - Record RSS
2. Select the $C$ (or $(C_1, C_2)$) that minimises RSS.
3. At the optimal power(s), compute OLS standard errors for $A$ and $B$ (conditional on $C$).
4. Report $R^2 = 1 - \text{RSS}/\text{SS}_{\text{tot}}$.

#### Interpretation

| Parameter | Meaning |
|-----------|---------|
| $A$ | Irreducible variance — the volatility floor even for infinitely large, perfectly diversified portfolios |
| $B$ | Scale of the diversifiable component |
| $C$ | Strength of diversification: $C = -0.5$ implies $\sqrt{n}$-type (CLT) diversification; $C = -1$ implies $1/x$ |
| $R^2$ | Proportion of cross-sectional variance in $s^2$ explained by the model |

**Stability diagnostic:** The single-factor models are fit first to establish marginal parameters.  If $C_1$ or $C_2$ in the joint model diverge from the corresponding single-factor $C$ by more than 0.3, a stability warning is raised.

> **Empirical note** ([docs/model-simplification-tests.md](../docs/model-simplification-tests.md) §6).  On the current data both flags fire ($C_1$ shifts 0.58, $C_2$ shifts 0.36), but this is **not** classical collinearity: the size/HHI association is weak (|Pearson| ≈ 0.21, VIF ≈ 1.04, design condition number 1.23).  The joint fit is unstable because size and concentration are **near-redundant** for dispersion — each single factor explains ~24–27 % of the variance in $s^2$ and the other then adds only ~0.2 % — so the five-parameter nonlinear form is under-identified on a weak signal (observation-level $R^2 ≈ 0.05$).  Every joint parameter is individually insignificant ($p_A = 0.99$, $p_{B_1} = 0.17$, $p_{B_2} = 0.22$).  The wording "collinearity" was retained in the flag string for backward compatibility but the mechanism is redundancy, not correlation.

#### Output

```json
{
  "dispersion_models": {
    "single_h": { "A": ..., "B": ..., "C": ..., "r_squared": ..., "fitted_curve": [...] },
    "single_r": { "A": ..., "B": ..., "C": ..., "r_squared": ..., "fitted_curve": [...] },
    "joint": { "A": ..., "B1": ..., "C1": ..., "B2": ..., "C2": ..., "r_squared": ... },
    "stability_flags": [...]
  }
}
```

### A.5.6  N6 — Sequential Adjustment Pipeline (Joint Composition)

#### Motivation

Size and LoB diversification both reduce PYD volatility.  Fitting them simultaneously (the joint model in §A.5.5) is unstable in practice: every parameter of the joint power-law is individually insignificant and its exponents swing relative to the single-factor fits.  The instability is **not** classical collinearity — the size/HHI association is weak (VIF ≈ 1.04) — but **near-redundancy**: the two factors are close substitutes for explaining dispersion, so the joint nonlinear fit is under-identified.  See [docs/model-simplification-tests.md](../docs/model-simplification-tests.md) §6.

The sequential pipeline removes size first (the effect that is more robust out-of-sample — HHI alone does not generalise, with negative held-out $R^2$), then estimates the *incremental* HHI diversification benefit on the residuals.  LoB-specific elasticities are applied as a final refinement layer.

> **Ordering.**  Because the two effects are near-redundant, the removal order is nearly immaterial: `ordering_comparison` reports size-first vs HHI-first explaining 23.7 % vs 27.0 % of dispersion variance (a 3.3 pp gap, within bootstrap noise).  The pipeline ships **size-first** for out-of-sample robustness and interpretability even though the in-sample variance-maximising comparator marginally prefers HHI-first.  Given S1 (specific LoB mix adds nothing to dispersion beyond HHI) and S4 (HHI adds nothing beyond size out-of-sample), dropping the HHI factor from the operational scaling entirely — as the distortion tool already does — is a defensible simplification.

#### Pipeline

**Step 1: Size adjustment**

Using the single-factor size model from §A.5.5:

$$V(R) = A_R + B_R \cdot R^{C_R}$$

Each observation's squared severity is scaled to a reference size $R_{\text{ref}}$:

$$s^2_{\text{adj},i} = s_i^2 \times \frac{V(R_{\text{ref}})}{V(R_i)}$$

This removes the size-driven heteroskedasticity while preserving the mean structure.

**Step 2: HHI dispersion on residuals**

Fit the mix power-law on the size-adjusted squared severity:

$$s^2_{\text{adj},i} = A_H + B_H \cdot H_i^{C_H} + \varepsilon_i$$

where $H_i = \max(1 - \text{HHI}_i, 0.01)$.  Same estimation as §A.5.5 (profile likelihood over $C_H$, with $A_H \geq 0$, $B_H > 0$, $C_H \in (-1, 0)$).

This isolates the *incremental* HHI diversification benefit — the variance reduction from mix diversification after size has been accounted for.

**Step 3: LoB-specific refinement**

The LoB shrinkage elasticities (§A.5.4, James-Stein) capture per-LoB deviations from the aggregate size power-law.  They are applied as a final adjustment layer:

$$\beta_{\text{weighted}} = \sum_\ell w^{(q)}_\ell \cdot \tilde{\beta}_\ell$$

These elasticities refine the aggregate size adjustment by accounting for the fact that, e.g., Property reserves diversify faster than Professional Lines reserves.

#### Variance attribution

At each pipeline stage, the cross-sectional variance of $s^2$ is reported:

| Stage | Metric |
|-------|--------|
| Raw | $\text{Var}(s_i^2)$ |
| After size adjustment | $\text{Var}(s^2_{\text{adj},i})$ |
| After HHI fit | $\text{Var}(s^2_{\text{adj},i} - \hat{Y}_i)$ where $\hat{Y}_i = A_H + B_H H_i^{C_H}$ |

The percentage explained at each stage quantifies the relative contribution of size vs mix diversification to the overall dispersion reduction.

#### Output

```json
{
  "joint_composition": {
    "size_model_used": { "A": ..., "B": ..., "C": ... },
    "reference_size": 500,
    "disp_h_adjusted": { "A": ..., "B": ..., "C": ..., "r_squared": ..., "fitted_curve": [...] },
    "variance_attribution": {
      "var_raw_sq": ...,
      "var_after_size_adj": ...,
      "pct_explained_by_size": ...,
      "var_after_hhi_adj": ...,
      "pct_explained_by_hhi": ...
    },
    "lob_elasticities": [...],
    "lob_diagnostics": [...]
  }
}
```

### A.5.7  N4 — Capital Distortion (Shapley Attribution)

For each of the 6 test portfolios (§A.5.7) plus 5 persona portfolios (§A.6):

1. Compute the four severity distributions (§A.4.3).
2. Compute empirical VaR at 99% and 99.5% (linear interpolation).
3. Compute TVaR at 99% and 99.5%.

**Shapley attribution** (symmetric, order-independent):

The two adjustments are "mix" and "size".  The Shapley value averages both orderings:

$$\text{Mix effect} = \frac{1}{2}\bigl[(\text{VaR}_{\text{mix}} - \text{VaR}_{\text{naive}}) + (\text{VaR}_{\text{full}} - \text{VaR}_{\text{size}})\bigr]$$

$$\text{Size effect} = \frac{1}{2}\bigl[(\text{VaR}_{\text{size}} - \text{VaR}_{\text{naive}}) + (\text{VaR}_{\text{full}} - \text{VaR}_{\text{mix}})\bigr]$$

This ensures: $\text{Mix effect} + \text{Size effect} = \text{VaR}_{\text{full}} - \text{VaR}_{\text{naive}}$.

### A.5.6  Bootstrap Confidence Intervals

Cluster bootstrap at the **syndicate level**: sample syndicates with replacement, keeping all years for each selected syndicate.  B = 500 replicates, seed = 42.

For each replicate, recompute:
- All four severity distributions and VaR/TVaR
- RE-GLS $\hat{\beta}$
- Shapley attribution effects

Report 2.5th and 97.5th percentiles as 95% CIs.

### A.5.7  Test portfolios

| Name | Property | Casualty | Marine | Prof Lines | Reins-Cas | Size (£m) |
|------|:--------:|:--------:|:------:|:----------:|:---------:|:---------:|
| Prop-heavy £200m | 0.60 | 0.20 | 0.10 | 0.10 | 0 | 200 |
| Prop-heavy £500m | 0.60 | 0.20 | 0.10 | 0.10 | 0 | 500 |
| Prop-heavy £2bn | 0.60 | 0.20 | 0.10 | 0.10 | 0 | 2000 |
| Cas-heavy £200m | 0.15 | 0.50 | 0 | 0.20 | 0.15 | 200 |
| Cas-heavy £500m | 0.15 | 0.50 | 0 | 0.20 | 0.15 | 500 |
| Cas-heavy £2bn | 0.15 | 0.50 | 0 | 0.20 | 0.15 | 2000 |

Unspecified LoBs receive weight 0.  All weight vectors sum to 1.0.

**Market reference mix:** Equal-weighted average of all LoB weight vectors in the DENSE subset (one observation = one vote, not reserve-weighted).  This is the mix used for standardisation in N1.

### A.5.8  Local-Donor Sensitivity Analysis

Hellinger distance: $H(\mathbf{w}^{(s)}, \mathbf{w}^{(q)}) = \frac{1}{\sqrt{2}} \| \sqrt{\mathbf{w}^{(s)}} - \sqrt{\mathbf{w}^{(q)}} \|_2$

For each test portfolio at £500m, at thresholds $H_{\max} \in \{0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80, 0.90, 1.0\}$:
- Retain only observations with $H \le H_{\max}$
- Compute VaR 99.5% for raw and fully-adjusted severity
- Record donor count

---

## A.6  Persona Syndicates

All persona definitions use the **FULL subset** (2014–2023, excluding 2024).

### A.6.1  Persona definitions

| Persona | Size ($R$) | HHI / Diversification |
|---------|-----------|----------------------|
| **Typical** | Median opening reserves | Median HHI |
| **Small** | 5th percentile of opening reserves | Median HHI of 10 nearest neighbours by reserve size |
| **Large** | 95th percentile of opening reserves | Median HHI of 10 nearest neighbours by reserve size |
| **Diversified** | Median opening reserves | 5th percentile of HHI (= 95th percentile diversification) |
| **Undiversified** | Median opening reserves | 95th percentile of HHI (= 5th percentile diversification) |

The Small and Large personas derive their HHI targets from the 10 syndicate-years closest in reserve size (absolute distance), rather than from quartile medians.  This avoids sensitivity to quartile boundaries and ensures the persona reflects the concentration typical of similarly-sized syndicates.

### A.6.2  LoB weight vector construction

All five personas use a common two-step pipeline: **prune**, then **adjust HHI**.

#### Step 1 — Raw weight averaging

Each persona averages LoB weight vectors from a reference group of syndicate-years:

- **Typical:** Equal-weighted average of all LoB weight vectors in the FULL subset (one observation = one vote).  Median active LoB count computed across all observations.
- **Small:** 10 nearest neighbours by absolute reserve-size distance to the 5th percentile.  Average their LoB weight vectors; median active LoB count from those 10 neighbours.
- **Large:** 10 nearest neighbours by absolute reserve-size distance to the 95th percentile.  Average their LoB weight vectors; median active LoB count from those 10 neighbours.
- **Diversified:** 10 nearest neighbours by absolute HHI distance to the 5th percentile HHI.  Average their LoB weight vectors; median active LoB count from those 10 neighbours.
- **Undiversified:** 10 nearest neighbours by absolute HHI distance to the 95th percentile HHI.  Average their LoB weight vectors; median active LoB count from those 10 neighbours.

An "active" LoB has weight > 1%.

#### Step 2 — Prune to target LoB count

Zero out the smallest-weight LoBs to keep only $n$ active LoBs (where $n$ is the median active LoB count from the reference group), then renormalise.

#### Step 3 — Adjust to target HHI

Blend the pruned weights toward or away from uniform to hit the persona's target HHI:

$$\mathbf{w}_{\text{adj}} = \alpha \mathbf{w}_{\text{pruned}} + (1-\alpha) \mathbf{u}$$

where $\mathbf{u} = 1/13$.  The analytical solution uses:

$$\text{HHI}(\mathbf{w}_{\text{adj}}) = \alpha^2 (\text{HHI}(\mathbf{w}) - 1/N) + 1/N$$

Solving for $\alpha$:

$$\alpha = \sqrt{\frac{\text{HHI}_{\text{target}} - 1/N}{\text{HHI}(\mathbf{w}) - 1/N}}$$

If the denominator is near zero (weights already uniform), the weights are returned as-is.  $\alpha^2$ is clamped to $[0, 4]$ to prevent extreme concentration.  The result is renormalised.

This preserves relative LoB proportions while achieving the desired concentration level.

### A.6.3  Nearest syndicates

Composite distance based on **percentile ranks** of the empirical CDFs for reserve size and HHI:

$$d(i, \text{persona}) = 0.4 \cdot | F_R(R_i) - F_R(R_{\text{persona}}) | + 0.6 \cdot | F_H(\text{HHI}_i) - F_H(\text{HHI}_{\text{persona}}) |$$

where $F_R$ and $F_H$ are the empirical CDF (percentile rank) functions computed over the FULL subset.  This ensures reserves and HHI contribute to distance on the same [0, 1] scale regardless of their different units.

Select the 3 syndicate-years with smallest $d$.  If the same syndicate appears multiple times, keep only its closest year.  These identify 3 **syndicate numbers**.

### A.6.4  Persona standardisation (dispersion adjustment)

For each persona, the market PYD% distribution is rescaled to the persona's target reserve size and HHI using the combined dispersion model (§A.5.5–A.5.6).

#### Dispersion adjustment multiplier

The combined variance model is:

$$V(R, \text{HHI}) = V_{\text{size}}(R) \times V_{\text{HHI}}(\text{HHI}) \,/\, V_{\text{HHI,ref}}$$

where $V_{\text{size}}(R) = A_R + B_R R^{C_R}$ and $V_{\text{HHI}}(H) = A_H + B_H H^{C_H}$ with $H = \max(\text{HHI}, 0.01)$, and $V_{\text{HHI,ref}}$ is a normalising constant.

For each observation $i$ with observed $(R_i, \text{HHI}_i)$ and persona target $(R_q, \text{HHI}_q)$:

$$m_i = \sqrt{\frac{V(R_q, \text{HHI}_q)}{V(R_i, \text{HHI}_i)}}$$

#### Residual rescaling

1. Compute the market reference mean $\mu$ (per §A.5.2 reference mean test).
2. For each observation: $\text{residual}_i = \text{PYD\%}_i - \mu$
3. Rescale: $\text{persona\_residual}_i = \text{residual}_i \times m_i$
4. Reconstruct: $\text{persona\_PYD\%}_i = \max(\mu + \text{persona\_residual}_i,\; -100\%)$

The $-100\%$ floor prevents nonsensical results (cannot lose more than all reserves).

This approach preserves the market mean while adjusting the dispersion to match the persona's risk profile.  It is equivalent to mean-preserving re-centring (§A.5.2) but uses the fitted variance model rather than direct LoB-reweighting and power-law size scaling.

### A.6.4a  Persona histograms

**Histogram (b):** The "3 nearest syndicates" histogram uses all years for those 3 syndicate numbers (not just the matched year), restricted to the FULL subset.  This is explicitly labelled as "Historical record of 3 nearest syndicate numbers."

**Histogram (c):** Raw market PYD% (FULL subset) overlaid with persona-standardised PYD% (dispersion-adjusted per §A.6.4).

**Histogram (multipliers):** Distribution of the dispersion adjustment multipliers $m_i$ across all observations, with 0.1 bin width.

All PYD% histograms use 2pp bin width.  Histogram values are in **percentage form** (e.g. bins at −10%, −8%, …, not −0.10, −0.08).  The analysis script emits pre-binned histogram arrays.

### A.6.5  Market PYD% summary statistics

For each persona, compute summary statistics for both the raw market PYD% distribution and the persona-standardised distribution (dispersion-adjusted per §A.6.4):

| Statistic | Description |
|-----------|-------------|
| `n` | Observation count |
| `min` | Minimum |
| `max` | Maximum |
| `mean` | Mean (should be equal for raw and standardised due to mean-preserving rescaling) |
| `median` | Median |
| `std` | Standard deviation |
| `p10` | 10th percentile |
| `p75` | 75th percentile |
| `p90` | 90th percentile |
| `p99` | 99th percentile |
| `p995` | 99.5th percentile |

Emitted in `personas.{name}.market_pyd_stats` with `raw` and `standardised` sub-keys.

### A.6.5a  Multiplier statistics

Distribution statistics for the dispersion adjustment multipliers $m_i$ (§A.6.4), using the same statistic template as §A.6.5 (`n`, `min`, `max`, `mean`, `median`, `std`, `p10`, `p75`, `p90`, `p99`, `p995`).

Emitted in `personas.{name}.multiplier_stats`.

### A.6.5b  Tail diagnostics

For each persona, diagnostics assessing the quality and composition of the rescaled tail:

| Metric | Description |
|--------|-------------|
| `kish_n_eff` | Kish's effective sample size: $(\sum m_i)^2 / \sum m_i^2$.  Measures how much the dispersion rescaling reduces the effective number of independent observations. |
| `raw_excess_kurtosis` | Excess kurtosis of raw (unrescaled) residuals. |
| `rescaled_excess_kurtosis` | Excess kurtosis of persona-rescaled residuals. |
| `lognormal_excess_kurtosis` | Reference excess kurtosis from a lognormal fit to positive raw residuals: $e^{4\sigma^2} + 2e^{3\sigma^2} + 3e^{2\sigma^2} - 6$ where $\sigma$ is the standard deviation of $\ln(\text{positive residuals})$. |
| `t_dist_df` | Implied Student-t degrees of freedom if the raw kurtosis were t-distributed: $\text{df} = 4 + 6/\kappa$ where $\kappa$ is the raw excess kurtosis (only computed when $\kappa > 0$). |
| `n_top10_pct` | Count of observations in the top 10% of the rescaled distribution. |
| `nn_in_top10_pct` | Count of the 3 nearest-syndicate observations that fall in the top 10%. |
| `pct_top10_from_nn` | Percentage of top-10% observations that come from the 3 nearest syndicates. |
| `manufactured_in_top10` | Count of top-10% observations with multiplier > 1.5 ("manufactured" tail). |
| `pct_top10_manufactured` | Percentage of top-10% observations with multiplier > 1.5. |
| `tail_histogram_raw` | Histogram of the raw PYD% values in the top 10% of the raw distribution (2pp bins). |
| `tail_histogram_rescaled` | Histogram of the rescaled PYD% values in the top 10% of the rescaled distribution (2pp bins). |

These diagnostics help assess whether the persona's tail is driven by genuine market observations or artefacts of the dispersion rescaling.  High `pct_top10_manufactured` or low `kish_n_eff` relative to $n$ indicate that the rescaling is generating rather than revealing tail risk.

Emitted in `personas.{name}.tail_diagnostics`.

### A.6.6  Persona capital metrics

VaR 99%, VaR 99.5%, TVaR 99.5% for each of the five personas under all four distributions (§A.4.3), with Shapley attribution (§A.5.7) and bootstrap CIs (§A.5.6).

**Note:** The four distributions use the persona's target HHI (from §A.6.1), not the HHI implied by the constructed weight vector.  This ensures consistency between the capital metrics and the dispersion adjustment.

---

## A.7  Diagnostic Counters

The analysis script emits the following counters in the results bundle:

| Counter | Description |
|---------|-------------|
| `sign_flips` | Count of observations where `pyd_pct` sign disagreed with `direction` and was corrected |
| `sign_flip_pct` | As percentage of total observations |
| `cap_binding_pos` | Count of LoB-level severities hitting +5.0 |
| `cap_binding_neg` | Count of LoB-level severities hitting −5.0 |
| `cap_binding_pct` | Combined as % of all LoB-observation cells |
| `lob_floor_count` | Count of LoB weights floored at 1% |
| `lob_floor_pct` | As % of all LoB-observation cells |
| `reserve_source_dist` | Dict: counts by reserve source used |
| `weight_source_dist` | Dict: counts by weight source used |
| `cap_binding_by_year` | Per-year breakdown |
| `lob_floor_by_year` | Per-year breakdown |
| `proportional_allocation_count` | Count of observations where LoB movements were allocated proportionally |
| `no_reserves_filtered` | Count of records filtered due to null or negligible (≤ £0.1m) opening reserves |
| `yearly_observation_counts` | Dict: year → observation count for all kept records |
| `near_zero_pyd` | List of syndicate-year records with \|PYD %\| < 0.05% (syndicate, year, pyd_pct, pyd_gbp_m, opening_reserves, direction, quality tag) |
| `near_zero_pyd_count` | Count of near-zero PYD records |

**Sign flip warning:** If `sign_flip_pct` > 5%, emit a warning flag.

The `cap_binding` and `lob_floor` counters are emitted as nested objects:
```json
{
  "cap_binding": { "pos": N, "neg": N, "pct": N, "by_year": {...} },
  "lob_floor": { "count": N, "pct": N, "by_year": {...} }
}
```

---

## A.8  Analysis Configuration (Assumptions Block)

The results bundle includes an `analysis_config` block documenting all modelling assumptions:

```json
{
  "lob_weight_floor": 0.01,
  "lob_severity_cap": 5.0,
  "reserve_min_for_n3": 5.0,
  "min_events_for_fe": 3,
  "min_obs_per_lob": 10,
  "reference_size_m": 500.0,
  "market_reference_mix": "equal_weighted",
  "sign_correction_rule": "trust_direction_field",
  "movement_allocation_fallback": "proportional_to_lob_weights",
  "bootstrap_replicates": 500,
  "bootstrap_seed": 42,
  "leave_out_iterations": 200,
  "leave_out_fraction": 0.10,
  "primary_estimator": "RE-GLS with syndicate random intercepts",
  "winsorisation": "none",
  "lob_coefficients": { ... },
  "overall_beta_default": -0.24
}
```

---

## A.9  Results Bundle Schema

The output file is `exposure_results.json`.  Top-level structure:

```json
{
  "spec_version": "2.0",
  "analysis_run_id": "uuid",
  "analysis_timestamp": "ISO8601",
  "source_data_hash": "sha256 of concatenated input filenames+sizes",
  "analysis_code_hash": "sha256 of run_analysis.py",
  "analysis_config": { ... },

  "meta": {
    "total_files_scanned": 622,
    "kept": 435,
    "discarded": { "in_runoff": 12, "skipped": 80, "excluded": 95, "no_reserves": 3 },
    "incomplete_flagged": 15
  },

  "eligibility": {
    "eligible_for_distribution": { "n": 420, "mask_indices": [...] },
    "eligible_for_boxplot_reserves": { "n": 415 },
    "eligible_for_n1": { "n": 177 },
    "eligible_for_n3": { "n": 165 },
    "eligible_for_capital": { "n": 410 },
    "eligible_for_persona": { "n": 390 }
  },

  "subsets": {
    "DENSE": { "n_observations": 177, "n_syndicates": 52, ... },
    ...
  },

  "observations": [
    {
      "syndicate": 1084, "year": 2017,
      "opening_reserves_gbp_m": 1830.6,
      "pyd_pct": -2.12, "direction": "release",
      "S_raw_a": -0.0212,
      "w_s": [0.035, 0.101, ...],
      "s_lob": [0.0, -0.15, ...],
      "HHI": 0.18, "complexity": 1501.1,
      "cause_category": "natural_cat",
      "event_group_id": "2017_natural_cat",
      "data_quality_tag": "RELIABLE",
      "confidence": 1.0,
      "narrative_excerpt": "The Syndicate released GBP 39.4 million..."
    },
    ...
  ],

  "overview": { ... },
  "distribution": {
    "pyd_histogram": { "bins": [...], "counts": [...], "overflow_count": 0 },
    "stats": { "mean": -2.1, "std": 8.5, "min": -15.2, "max": 55.5, "q995": 32.9 },
    "boxplots": {
      "by_reserves_decile": [...],
      "by_hhi_decile": [...],
      "by_complexity_decile": [...],
      "by_year": [...]
    }
  },

  "tail_trends": {
    "annual_p95": { "raw": [...], "standardised": [...] },
    "regression": {
      "raw": { "slope": 0.163, "se": 0.079, "p_value": 0.04, "ci_95": [...], "boot_ci_95": [...] },
      "standardised": { "slope": 0.023, "se": 0.022, "p_value": 0.31, "ci_95": [...], "boot_ci_95": [...] },
      "slope_reduction_pct": 86
    },
    "panel_trend": {
      "delta": 0.005, "se": 0.003, "p_value": 0.08, "boot_ci_95": [...]
    },
    "inference_note": "Annual p95 shown for intuition; inference based on full-panel RE-GLS model."
  },

  "tail_diagnostics": {
    "mean_excess": {
      "raw": { "thresholds": [...], "values": [...] },
      "standardised": { "thresholds": [...], "values": [...] }
    }
  },

  "size_scaling": {
    "primary": {
      "model": "RE-GLS (syndicate RE + event FE)",
      "beta": -0.605, "se": 0.284, "p_value": 0.033,
      "ci_95": [-1.16, -0.05], "boot_ci_95": [-1.10, -0.08],
      "sigma_u": 0.45, "sigma_eps": 1.2,
      "n": 165, "n_syndicates": 48, "n_events": 12
    },
    "frequentist_comparison": [
      { "spec": "M0", "beta": -0.642, "se": 0.276, "p_value": 0.020, ... },
      { "spec": "M1", ... },
      ...
    ],
    "lob_elasticities": [
      { "lob": "Property", "beta_raw": -0.18, "se": 0.12, "beta_shrunk": -0.14, "lambda": 0.59, "ci_95": [...] },
      ...
    ],
    "scatter_data": {
      "points": [ { "x": 3.2, "y": -1.5, "syndicate": 1084, "year": 2017, ... }, ... ],
      "binned_means": [ { "x_mid": 2.5, "y_mean": 0.8, "y_q1": 0.2, "y_q3": 1.5, "n": 12 }, ... ],
      "regression_line": { "slope": -0.605, "intercept": 2.1 }
    },
    "event_group_audit": [
      { "event_group_id": "2017_natural_cat", "n_syndicates": 30, "pooled": false },
      ...
    ]
  },

  "capital_impact": {
    "portfolios": [
      {
        "name": "Prop-heavy £200m",
        "var_99": { "naive": 25.1, "mix": 3.8, "size": 26.2, "full": 4.8 },
        "var_995": { "naive": 32.9, "mix": 4.0, "size": 34.1, "full": 5.6 },
        "tvar_99": { ... },
        "tvar_995": { ... },
        "shapley": {
          "mix_effect_var995": -28.5, "size_effect_var995": 1.2,
          "mix_effect_var99": -21.0, "size_effect_var99": 0.9
        },
        "boot_ci": {
          "var_995_full": [3.2, 8.1],
          "mix_effect_var995": [-32.1, -24.9],
          "size_effect_var995": [-0.5, 2.9]
        }
      },
      ...
    ]
  },

  "robustness": {
    "sampling": {
      "p95_slope": { "estimate": 0.163, "leave_out_cv": 13.3, "boot_cv": 14.1, "stability": "Stable" },
      "beta": { "estimate": -0.605, "leave_out_cv": 17.8, "boot_cv": 16.2, "stability": "Stable" },
      "var995": { "estimate": 32.9, "leave_out_cv": 4.1, "boot_cv": 5.2, "stability": "Stable" }
    },
    "local_donor": {
      "prop_heavy_500m": [
        { "h_max": 0.30, "donor_count": 15, "var995_raw": 28.1, "var995_adj": 4.2 },
        ...
      ],
      "cas_heavy_500m": [ ... ]
    }
  },

  "personas": {
    "typical": {
      "definition": { "reserves": 58.5, "hhi": 0.22, "diversification": 0.78 },
      "weights": [0.12, 0.09, ...],
      "lob_weights": { "Property": 0.12, "Casualty": 0.09, ... },
      "hhi": 0.22,
      "nearest_syndicates": [
        { "syndicate": 1234, "year": 2018, "reserves_m": 62.1, "hhi": 0.21, "diversification": 0.79, "distance": 0.05, "lob_weights": { ... } },
        ...
      ],
      "histogram_nearest": { "bins": [...], "counts": [...], "bin_width": 2.0 },
      "histogram_b": { "bins": [...], "counts": [...], "bin_width": 2.0 },
      "histogram_market_raw": { "bins": [...], "counts": [...], "bin_width": 2.0 },
      "histogram_market_standardised": { "bins": [...], "counts": [...], "bin_width": 2.0 },
      "histogram_c": {
        "raw": { "bins": [...], "counts": [...], "bin_width": 2.0 },
        "standardised": { "bins": [...], "counts": [...], "bin_width": 2.0 }
      },
      "histogram_multipliers": { "bins": [...], "counts": [...], "bin_width": 0.1 },
      "multiplier_stats": { "n": 390, "min": 0.3, "max": 3.1, "mean": 1.1, ... },
      "tail_diagnostics": {
        "kish_n_eff": 340.2,
        "raw_excess_kurtosis": 5.1,
        "rescaled_excess_kurtosis": 7.3,
        "lognormal_excess_kurtosis": 12.5,
        "t_dist_df": 5.2,
        "n_top10_pct": 39,
        "nn_in_top10_pct": 2,
        "pct_top10_from_nn": 5.1,
        "manufactured_in_top10": 8,
        "pct_top10_manufactured": 20.5,
        "tail_histogram_raw": { "bins": [...], "counts": [...], "bin_width": 2.0 },
        "tail_histogram_rescaled": { "bins": [...], "counts": [...], "bin_width": 2.0 }
      },
      "market_pyd_stats": {
        "raw": { "n": 390, "min": -15.2, "max": 55.5, "mean": -2.1, "median": -1.8, "std": 8.5, "p10": -8.2, "p75": 1.5, "p90": 5.3, "p99": 28.1, "p995": 32.9 },
        "standardised": { ... }
      },
      "capital": { ... }
    },
    "small": { ... },
    "large": { ... },
    "diversified": { ... },
    "undiversified": { ... }
  },

  "worked_example": {
    "syndicate_a": { "syndicate": 1414, "year": 2017, "reserves_m": 19.3, "lob_weights": [...], "s_lob": [...] },
    "syndicate_b": { "syndicate": 4444, "year": 2017, "reserves_m": 389.8, "lob_weights": [...], "s_lob": [...] },
    "lob_coefficients": { ... },
    "reference_size_m": 500
  },

  "data_quality": {
    "sign_flips": 8, "sign_flip_pct": 1.8,
    "cap_binding": { "pos": 45, "neg": 12, "pct": 2.8, "by_year": {...} },
    "lob_floor": { "count": 180, "pct": 8.1, "by_year": {...} },
    "reserve_source_dist": { "opening_reserves": 380, "technical_provisions": 30, ... },
    "weight_source_dist": { "premium_mix": 400, "movement_based": 20, "none": 15 },
    "confidence_histogram": { "bins": [...], "counts": [...] },
    "proportional_allocation_count": 120,
    "missing_reserves": 20, "missing_reserves_pct": 4.6
  }
}
```

The schema shown above is illustrative.  All numeric values are placeholders.  The actual structure must match exactly, with real computed values.

---

# PART B — DASHBOARD VIEWER

## B.1  Purpose

`exposure_analysis.html` is a **static viewer** for the precomputed `exposure_results.json` bundle.  It validates the results file, applies display filters, and renders tables, charts, and drill-through detail.

**It does not:**
- Estimate regressions or run bootstraps
- Sample posteriors or run MCMC
- Parse raw syndicate JSON files
- Perform any LoB mapping, severity computation, or statistical inference

**The only browser-side arithmetic** is in Tab 11 (Worked Example): dot products, weighted-beta combinations, and power-law size adjustment.

## B.2  Technology Stack

| Layer | Choice | CDN |
|-------|--------|-----|
| Charts | Chart.js 4.x | `https://cdn.jsdelivr.net/npm/chart.js` |
| Layout / styling | Vanilla CSS (no framework) | — |

No other dependencies.  No jStat, no KaTeX, no Hammer.js, no chartjs-plugin-zoom.

## B.3  Data Loading

The user clicks a **"Load Results"** button.  Two loading mechanisms:

1. **File picker:** `<input type="file" accept=".json">` — user selects `exposure_results.json`.
2. **Drag and drop:** User drops the JSON file onto the page.

On load:
1. Parse JSON.
2. Validate `spec_version === "2.0"`.
3. Validate required top-level keys exist: `meta`, `analysis_config`, `eligibility`, `observations`, `distribution`, `tail_trends`, `tail_diagnostics`, `size_scaling`, `capital_impact`, `robustness`, `personas`, `worked_example`, `data_quality`.
4. Show provenance: `analysis_run_id`, `analysis_timestamp`, `source_data_hash`, subset counts.

## B.4  Tab Structure

| Tab # | Tab name | Data source block |
|-------|----------|-------------------|
| 1 | **Data Summary** | `meta`, `subsets`, `eligibility`, `analysis_config` |
| 2 | **Distribution** | `distribution` |
| 3 | **Tail Trends** | `tail_trends` |
| 4 | **Tail Diagnostics** | `tail_diagnostics` |
| 5 | **Size Scaling** | `size_scaling` |
| 6 | **Capital Impact** | `capital_impact` |
| 7 | **Robustness** | `robustness` |
| 8 | **Persona: Typical** | `personas.typical` |
| 9 | **Persona: Small** | `personas.small` |
| 10 | **Persona: Large** | `personas.large` |
| 11 | **Persona: Diversified** | `personas.diversified` |
| 12 | **Worked Example** | `worked_example` + browser arithmetic |
| 13 | **Data Quality** | `data_quality`, `analysis_config` |

Each tab reads **only its own precomputed block** from the results bundle.

### Tab switching

- Horizontal tab bar below the header.
- Clicking a tab shows its content; hides all others.
- Active tab: coloured underline.
- All tabs render immediately from precomputed data (no lazy computation needed).

---

## B.5  Detailed Tab Specifications

### B.5.1  Tab 1: Data Summary

#### Corpus summary table (Table 1)

| Metric | Value source |
|--------|-------------|
| Years covered | `subsets.FULL.year_range` |
| Total observations | `meta.kept` |
| Unique syndicates | `subsets.FULL.n_syndicates` |
| Syndicates per year (DENSE) | `subsets.DENSE.syndicates_per_year` |
| Syndicates per year (MID) | `subsets.MID.syndicates_per_year` |
| Balanced-panel syndicates (K≥8) | `subsets.BALANCED_K8.n_syndicates` |
| Median reserves (£m) | `distribution.stats.median_reserves` |
| LoB categories observed | `meta.lob_categories_observed` |
| Partial-year observations (2024) | `subsets.YEAR_2024.n_observations` |

#### Data quality breakdown

Horizontal stacked bar from `meta.discarded` + `meta.kept`.

#### Yearly observation count

Vertical bar chart from `subsets` per-year counts.

#### Assumptions card

Render `analysis_config` as a readable table of all modelling assumptions (LoB floor, severity cap, reference size, estimator name, etc.).

### B.5.2  Tab 2: Distribution

#### PYD % histogram

Render from `distribution.pyd_histogram`.  5pp bin width.  Red (≥0%) / green (<0%).  Overflow bin purple.  Horizontal orientation.

#### PYD statistics cards

From `distribution.stats`: mean, std (with min–max), 99.5% quantile.

#### Box plots (2×2 grid)

Render from `distribution.boxplots`.  Each box plot entry provides: Q1, median, Q3, whisker_lo, whisker_hi, outliers[], n, label.

Styling: blue boxes, white median, red/green outlier dots, dashed zero line, n= annotation.  Observations with null reserves excluded from reserves-decile plot (show excluded-N label).

#### Decile statistical tests

Table showing ANOVA F-statistic and Bartlett chi-squared for each decile grouping (reserves, HHI, complexity).  Each p-value cell displays a **Sig** (≤ 0.05, red) or **Insig** (> 0.05, green) badge.

### B.5.3  Tab 3: Tail Trends

#### Figure 2

From `tail_trends.annual_p95`.  Two series (raw blue, standardised red).  Solid markers for DENSE years, hollow for 2020+.  Regression lines from `tail_trends.regression`.

Annotation: slope reduction %, raw slope ± boot CI, std slope ± boot CI.

Note below chart: text from `tail_trends.inference_note`.

#### Regression summary table

| Metric | Raw | Standardised |
|--------|-----|-------------|
| Slope (per year) | value [boot CI] | value [boot CI] |
| p-value | value | value |
| Slope reduction | — | XX% |

### B.5.4  Tab 4: Tail Diagnostics

Mean excess plot from `tail_diagnostics.mean_excess`.  Two series, connected scatter.

**Interpretive guidance** (displayed below the chart): "The Mean Excess Function (MEF) plots the expected excess above a threshold, conditional on exceeding it. Look for linearity: a straight line suggests an exponential tail; an upward slope suggests a heavier-than-exponential (e.g. Pareto) tail. If the standardised (mix-adjusted) MEF is flatter or lower than the raw MEF, composition adjustment is reducing tail risk. Instability at high thresholds reflects small sample sizes."

**Standardisation note:** "The Standardised line adjusts each observation for LoB mix and portfolio size, then re-centres to preserve the market mean.  Since ANOVA shows means do not vary significantly by size or complexity, standardisation isolates the effect on dispersion (tail behaviour) without introducing a spurious mean shift from Jensen's inequality."

### B.5.5  Tab 5: Size Scaling

#### Figure 4: Log-log scatter

From `size_scaling.scatter_data`.  Grey dots (alpha 0.3), blue binned means with IQR bars, red regression line.  Annotation: β value, p-value from primary estimator.

#### Table 3: Size-severity elasticity

**Panel A: Primary estimator (RE-GLS)**

From `size_scaling.primary`.  Single row: β, SE, p-value, 95% CI, boot 95% CI.

**Panel B: Frequentist comparisons**

From `size_scaling.frequentist_comparison`.  Rows M0–M3, M1-balanced.  Each: β, cluster SE, p-value, AIC, BIC, significance marker.

Significance markers: *** p < 0.001, ** p < 0.01, * p < 0.05, † p < 0.10.  AIC and BIC are computed as $n \ln(\text{RSS}/n) + 2k$ and $n \ln(\text{RSS}/n) + k \ln(n)$ respectively.

#### Figure C.6: LoB shrinkage

From `size_scaling.lob_elasticities`.  Horizontal dot plot: raw β with CI (blue), shrunk β (red diamond), arrow, λ annotation, grand mean dashed line.

#### Event group audit table

From `size_scaling.event_group_audit`.  Collapsible table showing event groups, syndicate counts, and pooling status.

### B.5.6  Tab 6: Capital Impact

#### Test portfolio definitions card

Before the VaR tables, display a card listing each test portfolio's target LoB weight vector and reserve size.  Sourced from `capital_impact.portfolios[].target_weights` and `.size`.

#### Table 4: Capital distortion

From `capital_impact.portfolios`.  Columns: portfolio name, raw VaR, mix-adj VaR, full-adj VaR, mix effect (Shapley), size effect (Shapley).

Uncertainty displayed as plain text bootstrap intervals below point estimates:
```
4.02
  [3.2, 5.1] (B=500)
```

Separate panels for VaR 99% and VaR 99.5%.

#### Figure 5: Capital decomposition waterfall

Horizontal waterfall chart for each portfolio.  Shows Naive VaR as base, then floating bar segments for mix effect (green if negative/favourable, red if adverse) and size effect (orange if positive/penalty, green if credit).  A thin marker indicates the full-adjusted VaR.  This replaces the previous stacked bar chart for clarity.

#### TVaR table

Same structure for TVaR 99% and 99.5%.

### B.5.7  Tab 7: Robustness

#### Table 2: Sampling robustness

From `robustness.sampling`.

| Metric | Estimate | Leave-out CV (%) | Bootstrap CV (%) | Stability |
|--------|----------|:---:|:---:|-----------|

Stability badge: green if both CVs < 20%, red if either > 20%.

#### Table 5: Local-donor sensitivity

From `robustness.local_donor`.

#### Figure 6: Local-donor convergence

Two panels.  X-axis: H_max (decreasing).  Blue = raw VaR, red = adjusted VaR.  Donor count annotations.

### B.5.8  Tabs 8–11: Persona Syndicates

Each reads from `personas.{typical|small|large|diversified}`:

1. **Attributes card:** Reserves, HHI, diversification, complexity from `definition`.  **LoB mix** displayed as horizontal stacked bar from `lob_weights` (dict of LoB name → weight) with colour-coded legend.
2. **Nearest syndicates table:** 3 rows showing syndicate number, year, reserves (£m), HHI, diversification score, composite distance, and a mini LoB weight stacked bar per row.  Each nearest syndicate entry includes `reserves_m`, `hhi`, `diversification`, and `lob_weights` (dict).
3. **Histogram (b):** "Historical record of 3 nearest syndicate numbers" — bar chart from pre-binned `histogram_b` data ({bins, counts}, 2pp bin width).
4. **Histogram (c):** "All market raw vs standardised to persona" — overlaid bar chart from `histogram_c` with `raw` and `standardised` sub-keys ({bins, counts} each).  Both series are plotted on a common bin grid covering the union of both ranges so the x-axis aligns correctly.
5. **Market PYD% summary statistics table:** From `market_pyd_stats.raw` and `market_pyd_stats.standardised`.  Columns: Metric, Raw, Standardised-to-Persona.  Metrics: minimum, maximum, mean, median, standard deviation, 75th/90th/99th/99.5th percentiles, N.  This quantifies the dispersion change from standardisation — means should be equal (due to re-centring) while tail quantiles show the capital impact.
6. **Capital metrics card:** VaR/TVaR under four distributions, Shapley attribution, boot CIs.

### B.5.9  Tab 11: Worked Example

The **only tab with browser-side arithmetic**.  Loads precomputed LoB severity vectors and coefficients from `worked_example`.

1. **Syndicate selector:** Two dropdowns populated from `observations[]`.
2. **Query portfolio editor:** 13 sliders (summing to 1.0) and a reserve size input (£m).
3. **Step-by-step computation (live):**
   - Step 1: Display LoB severity vectors for both syndicates (from `observations[].s_lob`).
   - Step 2: $S_{\text{std}} = \mathbf{w}^{(q)} \cdot \mathbf{s}$ — dot product computed in browser.
   - Step 3: $\beta_w = \sum w^{(q)}_\ell \beta_\ell$ — using coefficients from `worked_example.lob_coefficients`.
   - Step 4: $A = (R^{(q)} / R_{\text{ref}})^{\beta_w}$, $S_{\text{adj}} = S_{\text{std}} \times A$.

**Event fixed effects are set to zero** in the worked example, because it is a hypothetical portfolio projection, not a historical event-tagged observation.  This is stated explicitly in the UI.

### B.5.10  Tab 12: Data Quality

#### Diagnostics cards

From `data_quality`:
- Sign flip count and percentage (warning badge if > 5%)
- Cap binding rates (+5.0, −5.0) with per-year bar chart
- LoB floor rates with per-year bar chart
- Proportional allocation count
- No-reserves filtered count

#### Near-zero PYD records table

Table listing all syndicate-year records where |PYD %| < 0.05%, showing syndicate, year, PYD %, PYD £m, opening reserves, direction, and data quality tag.  These may indicate flat/unchanged reserves or data extraction issues.

#### Reserve source distribution

Pie chart from `data_quality.reserve_source_dist`.

#### Weight source distribution

Bar chart from `data_quality.weight_source_dist`.

#### Confidence distribution

Histogram from `data_quality.confidence_histogram`.

#### Observations by report year

Bar chart from `data_quality.yearly_observation_counts` showing the count of kept records per report year.

#### Assumptions table

Render `analysis_config` in full — all parameters that define the analytical specification.

---

## B.6  Chart Interactivity

### B.6.1  Hover tooltips

Every chart shows contextual tooltips on hover:

| Chart type | Tooltip content |
|------------|----------------|
| Scatter (Figure 4) | Syndicate, year, reserves, severity, cause |
| Line/time-series (Figures 2, 3) | Year, value, series name |
| Bar charts (Figure 5, histograms) | Bin range or portfolio name, value, % of total |
| Box plots | Q1, median, Q3, whisker bounds, n |
| Dot plots (Figure C.6) | LoB, raw β, shrunk β, λ, CI |

Tooltip styling: dark background (#333), white text, 12px, rounded, max-width 300px.

### B.6.2  Click-to-select

Clicking a data point or chart element populates a fixed **"Selected observation"** card below the chart (no animated slide-down, no drill-down panel framework).

| Chart | Card content on click |
|-------|-----------------------|
| Scatter | Syndicate, year, reserves, severity, cause, narrative excerpt |
| Histogram bin | Count and list of observation IDs in the bin |
| Box plot group | Count and summary stats for the group |
| Time-series point | Year and list of top-5 observations by severity |
| Capital bar | Full VaR decomposition for that portfolio |
| LoB dot | LoB name, raw β, SE, p-value, shrunk β, λ |

The card has a "Clear" button.  Only one card visible at a time.

---

## B.7  Colour Palette and Styling

### B.7.1  Core colours

| Use | Hex | Name |
|-----|-----|------|
| Raw / unadjusted | #2166ac | Blue |
| Standardised / adjusted | #b2182b | Red |
| Favourable / release | #27ae60 | Green |
| Adverse / strengthening | #e74c3c | Red-orange |
| Size credit | #4daf4a | Mid-green |
| Size penalty | #ff7f0e | Orange |
| Mix effect | #ffd700 | Gold |
| Neutral / background | #6c757d | Grey |

### B.7.2  Colour-blind alternate palette

A toggle in the header switches to a colour-blind-safe palette:

| Use | Default | CB-safe |
|-----|---------|---------|
| Raw | #2166ac | #0072B2 |
| Standardised | #b2182b | #D55E00 |
| Favourable | #27ae60 | #009E73 |
| Adverse | #e74c3c | #CC79A7 |
| Size credit | #4daf4a | #009E73 |
| Size penalty | #ff7f0e | #E69F00 |
| Mix effect | #ffd700 | #F0E442 |

### B.7.3  Typography

- Body: `system-ui, -apple-system, sans-serif`, 14px
- Headings: same family, bold
- Tables: 13px, alternating row shading (#f8f9fa / white)
- Monospace (values): `"Fira Code", "Consolas", monospace`

### B.7.4  Layout

- Max content width: 1200px, centred
- Tab content: 24px padding
- Charts: responsive, max height 500px
- Tables: horizontally scrollable on small screens

---

## B.8  Error Handling

| Scenario | Behaviour |
|----------|-----------|
| No file loaded | Show landing page with instructions |
| JSON parse error | Show "Invalid JSON file" error |
| `spec_version` mismatch | Show "Results file version X.X not supported; expected 2.0" |
| Missing required top-level key | Show "Results file is missing block: {key}" |
| A tab's data block is empty or null | Show "No data available for this analysis" in the tab body |
| Chart has < 2 data points | Show "Insufficient data" placeholder |

---

## B.9  File Output

Single file: `pdf_extraction/exposure_analysis.html`.  All CSS in `<style>`, all JS in `<script>`.  Only CDN dependency: Chart.js.

---

## B.10  Acceptance Criteria

1. **Schema validation:** Results bundle validates against required top-level keys; viewer rejects files with wrong `spec_version` or missing blocks.
2. **Eligibility consistency:** Every displayed `N` matches the eligibility count from the corresponding mask in the bundle.
3. **Tab rendering:** All 12 tabs render from the results bundle without JavaScript errors.
4. **No statistical computation:** The viewer performs no regression, bootstrap, or posterior sampling.  Only Tab 11 performs arithmetic (dot products, power-law).
5. **Chart rendering:** All charts render from precomputed payload arrays.  Hover tooltips work on all charts.
6. **Click-to-select:** Clicking a chart element populates the selection card.
7. **Colour-blind toggle:** Switching the palette updates all visible charts immediately.
8. **Worked example:** Sliders and inputs update Steps 2–4 live; event FE explicitly zeroed and labelled.
9. **Provenance:** Tab 1 shows `analysis_run_id`, timestamp, source hash, code hash.
10. **No dependencies** beyond Chart.js CDN.
