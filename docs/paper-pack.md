# Paper Pack Documentation

> **Status: superseded.**
> This document describes the earlier sequential / least-squares line-of-business
> projection, which was replaced by the robust Bayesian pooling operator
> (size and concentration, Student-t, two-regime RITC tail). It is retained as a record
> of that stage and is **not** a description of the current method. See
> `scaling_analysis_writeup.md` and the manuscript.


## 1. Overview

The paper pack is the collection of LaTeX tables (`.tex`) and PNG figures (`.png`) produced by the analysis pipeline. Together, these artefacts constitute the empirical evidence base for an academic paper investigating how **exposure composition** -- specifically, line-of-business (LoB) mix and portfolio size -- affects the severity of prior-year reserve development (PYD) in the Lloyd's of London market.

The central thesis is that naive pooling of PYD observations across syndicates with heterogeneous LoB mixes and reserve sizes introduces composition bias into tail-risk estimates. The paper pack demonstrates a sequential standardisation procedure that removes this bias and quantifies its capital impact.

All outputs reside in the `paper_pack/` directory and are regenerated deterministically by the analysis pipeline (see [Reproduction](#5-reproduction)).

---

## 2. Tables

Each table is emitted as a standalone LaTeX fragment suitable for inclusion in a journal article via `\input{}`.

### Table 1: Corpus Coverage Summary

| Aspect | Detail |
|---|---|
| **Content** | High-level dataset dimensions: calendar years covered (2014--2024), total syndicate-year observations, count of unique syndicates, syndicates per year in the dense and mid-density periods, balanced-panel membership count, median opening reserves ($R$), and the number of LoB categories used in the analysis. |
| **Interpretation** | Establishes that the corpus is broad enough for credible tail estimation. The dense-period count indicates how many syndicates report in every year of the core window, while the balanced-panel count shows the subset available for longitudinal analysis. Median reserves contextualise the market's size distribution. |
| **Key metrics** | Total observations $N$; unique syndicates; dense-period syndicates per year; balanced-panel $K$; median $R$ (GBP millions); LoB category count. |
| **Pipeline stage** | Corpus construction (`corpus_summary`). |

### Table 2: Sampling Sensitivity

| Aspect | Detail |
|---|---|
| **Content** | Leave-one-out cross-validation (LOOCV) resampling results for three key quantities: the slope of the annual p95 trend, the size-severity elasticity $\hat\beta$, and VaR$_{99.5\%}$. Each row reports the point estimate, coefficient of variation (CV), and a qualitative stability assessment. |
| **Interpretation** | A low CV (typically $< 0.10$) indicates that no single syndicate drives the result. If the stability column reads "stable", the finding is robust to arbitrary single-syndicate exclusion. |
| **Key metrics** | CV of each estimator under LOOCV; stability flag. |
| **Pipeline stage** | Sensitivity analysis (`sampling_sensitivity`). |

### Table 3: Size Effects Under Alternative Reserve-Movement Estimands

| Aspect | Detail |
|---|---|
| **Content** | $\hat\beta$ estimates organised into two panels. **Panel A (Mean-shift estimand)** regresses signed severity $S$ on $\log R$: RE-GLS (primary), pooled OLS (no controls), OLS with event FE, and the balanced-panel variant. **Panel B (Dispersion estimand)** uses absolute or squared severity as the dependent variable: $\log\lvert S\rvert$ on $\log R$ and $\lvert S\rvert$ on $\log R$. Each row shows $\hat\beta$, its standard error, and $p$-value. |
| **Interpretation** | Panel A tests whether portfolio size shifts the **mean** of PYD -- an insignificant $\hat\beta$ supports a pure-dispersion model. Panel B tests whether size reduces PYD **volatility** -- a significant negative $\hat\beta$ confirms the diversification benefit. The panel structure makes the distinction between location and scale effects explicit. |
| **Key metrics** | $\hat\beta$, SE($\hat\beta$), $p$-value per specification. |
| **Pipeline stage** | Size-severity regression (`size_severity_elasticity`). |

### Table 4: VaR 99.5% Decomposition

| Aspect | Detail |
|---|---|
| **Content** | For six hypothetical test portfolios (property-heavy and casualty-heavy variants at reserve sizes of GBP 200m, 500m, and 2bn), the table decomposes VaR$_{99.5\%}$ into three layers: **raw** (naive empirical), **mix-adjusted** (after LoB composition standardisation), and **fully adjusted** (after both mix and size standardisation). Two additional columns isolate the **mix effect** and **size effect** via Shapley-value attribution. |
| **Interpretation** | The mix effect is the change in VaR attributable solely to re-weighting the LoB composition to match the query portfolio. The size effect is the residual change from scaling dispersion to the query portfolio's reserve size. A large mix effect relative to the size effect indicates that composition, not scale, is the dominant source of distortion. |
| **Key metrics** | VaR$_{99.5\%}$ (raw, mix-adjusted, fully adjusted); Shapley mix effect; Shapley size effect. |
| **Pipeline stage** | Capital impact assessment (`var_decomposition`). |

### Table 5: Worked Example -- Event Detail

| Aspect | Detail |
|---|---|
| **Content** | A three-panel table illustrating the full adjustment pipeline on a concrete historical event. **Panel A** identifies the event year and the number of syndicates observed. **Panel B** presents two contrasting source syndicates from that event -- one small, one large -- with their reserve bases, HHI, LoB weight vectors (non-zero lines only), LoB-level severities, raw aggregate severity, PYD%, and direction. **Panel C** defines the target portfolio (name, size, HHI, and LoB weights) to which both syndicates' observations will be projected. |
| **Interpretation** | Answers the practitioner question: "What would this historical event have meant for my portfolio?" The reader can trace the mechanics of the mapping: both syndicates contribute to the same event, but their differing LoB mixes produce very different raw severities. The target portfolio definition sets up the projection that Table 6 completes. |
| **Key metrics** | Event year; $n$ syndicates; $R_i$ (reserves); HHI; $w_{i,\ell}$ (LoB weights); $s_{i,\ell}$ (LoB severities); $S_i^{\text{raw}}$; target portfolio weights $w_\ell^q$. |
| **Pipeline stage** | Worked example (`worked_example_detail`). |

### Table 6: Worked Example -- Adjustment Summary

| Aspect | Detail |
|---|---|
| **Content** | Side-by-side comparison of raw severity ($S^{\text{raw}}$), mix-standardised severity ($S^{\text{mix}}$), the size-adjustment factor ($\lambda$), and the fully-adjusted severity ($S^{\text{adj}}$) for both syndicates from Table 5. Mix-standardised severity is computed by projecting each syndicate's LoB-level severities onto the target portfolio's weight vector: $S^{\text{mix}}_i = \sum_\ell w_\ell^q \cdot s_{i,\ell}$. The size-adjustment factor rescales dispersion to the target portfolio's reserve size and HHI: $\lambda_i = \sqrt{V(R_q, \text{HHI}_q) / V(R_i, \text{HHI}_i)}$. The fully-adjusted severity is $S^{\text{adj}}_i = S^{\text{mix}}_i \times \lambda_i$. |
| **Interpretation** | Demonstrates convergence: the two syndicates' raw severities may differ substantially due to composition, but their mix-standardised severities are closer (both projected to the same LoB mix). The size-adjustment factor then rescales for the reserve-size difference -- a small syndicate with $\lambda < 1$ has its dispersion compressed (it was over-volatile relative to the target), while a large syndicate with $\lambda > 1$ has its dispersion expanded. The final adjusted severities represent what each syndicate's event would have looked like in the target portfolio's risk profile. |
| **Key metrics** | $S^{\text{raw}}$; $S^{\text{mix}}$; $\lambda$ (size-adjustment factor); $S^{\text{adj}}$ for each syndicate. |
| **Pipeline stage** | Worked example (`worked_example_summary`). |

### Table 7: Persona PYD% Statistics

| Aspect | Detail |
|---|---|
| **Content** | For each of five market personas -- **typical**, **small**, **large**, **diversified**, **undiversified** -- the table reports distributional statistics (mean, standard deviation, skewness, kurtosis, selected quantiles) of PYD% under both the raw and standardised-to-persona distributions. |
| **Interpretation** | Shows how standardisation reshapes the PYD distribution for different market archetypes. For example, the "small" persona may see its raw distribution compressed after size adjustment removes the excess volatility attributable to its low reserve base. |
| **Key metrics** | Mean, SD, skewness, kurtosis, p5, p25, p50, p75, p95 of PYD% (raw and standardised). |
| **Pipeline stage** | Persona analysis (`persona_pyd_stats`). |

### Table 8: Persona Tail Diagnostics

| Aspect | Detail |
|---|---|
| **Content** | Tail-quality metrics for each persona's standardised distribution: Hill estimator of the tail index, Anderson-Darling statistic, and possibly a GPD goodness-of-fit $p$-value. |
| **Interpretation** | Confirms that the standardisation procedure does not produce pathological tails. A finite Hill estimate and non-rejected GPD fit indicate that the adjusted distribution remains amenable to EVT-based capital modelling. |
| **Key metrics** | Hill tail index $\hat\xi$; AD statistic; GPD fit $p$-value. |
| **Pipeline stage** | Persona analysis (`persona_tail_diagnostics`). |

### Table 9: Corpus Summary (Subset Definitions)

| Aspect | Detail |
|---|---|
| **Content** | Enumerates the data subsets used throughout the analysis -- **DENSE**, **FULL**, **BALANCED_K8**, etc. -- with observation counts and year ranges. |
| **Interpretation** | Documents the data-partitioning strategy. "DENSE" is the high-participation window where most syndicates report; "BALANCED_K8" is the maximal balanced panel of $K = 8$ years. The reader can trace any result back to its specific subset. |
| **Key metrics** | Subset label; $N$; year range. |
| **Pipeline stage** | Corpus construction (`corpus_summary_subsets`). |

### Table 10: Data Quality Breakdown

| Aspect | Detail |
|---|---|
| **Content** | Tabulates the percentage of potential observations that are kept versus discarded, broken down by exclusion reason: **excluded** (manual blacklist), **skipped** (insufficient LoB detail), **in_runoff** (syndicate in run-off), **no_reserves** (zero or missing opening reserves). |
| **Interpretation** | Provides transparency about data filtering. A high kept percentage (e.g., $> 80\%$) supports the claim that results are not an artefact of selective inclusion. |
| **Key metrics** | Kept %; discarded % by reason. |
| **Pipeline stage** | Data ingestion (`data_quality`). |

### Table 11: Opening Reserves Distribution

| Aspect | Detail |
|---|---|
| **Content** | Descriptive statistics of the opening-reserves distribution across all syndicate-year observations: minimum, maximum, mean, median, standard deviation, skewness, and selected percentiles (p10, p25, p75, p90). |
| **Interpretation** | Characterises the population of syndicates by size. Heavy right skew is expected (a few very large syndicates dominate market capacity). The gap between mean and median quantifies this skew. |
| **Key metrics** | Min, max, mean, median, SD, skewness, percentiles of $R$. |
| **Pipeline stage** | Descriptive statistics (`reserves_distribution`). |

### Table 12: Decile Statistical Tests

| Aspect | Detail |
|---|---|
| **Content** | One-way ANOVA $F$-statistics and Bartlett test statistics for PYD grouped by deciles of (a) opening reserves, (b) HHI, and (c) LoB complexity. |
| **Interpretation** | ANOVA tests whether the **mean** PYD differs across deciles; Bartlett tests whether the **variance** is homogeneous. A significant ANOVA suggests that the grouping variable shifts the central tendency of PYD; a significant Bartlett statistic (more relevant for this analysis) indicates that dispersion varies across deciles -- the key motivation for dispersion modelling. |
| **Key metrics** | $F$-statistic and $p$-value (ANOVA); Bartlett $\chi^2$ and $p$-value. |
| **Pipeline stage** | Exploratory heterogeneity tests (`decile_tests`). |

### Table 13: Primary RE-GLS Estimator

| Aspect | Detail |
|---|---|
| **Content** | Random-effects generalised least squares (RE-GLS) regression of PYD severity on portfolio size, with syndicate-level random intercepts and event (year) fixed effects. Reports $\hat\beta$, SE, $z$-statistic, $p$-value, and variance components ($\sigma^2_u$, $\sigma^2_e$). |
| **Interpretation** | Tests whether the **mean** of PYD severity shifts with portfolio size. An insignificant $\hat\beta$ implies that size does not bias the direction of reserve development -- it affects only the dispersion. This justifies modelling size as a volatility (not location) parameter. |
| **Key metrics** | $\hat\beta$; $p$-value; $\sigma^2_u / (\sigma^2_u + \sigma^2_e)$ (intra-class correlation). |
| **Pipeline stage** | Mean-shift tests (`re_gls`). |

### Table 14: Dispersion Models

| Aspect | Detail |
|---|---|
| **Content** | Two dispersion-regression specifications: (i) $\log\lvert S\rvert$ on $\log R$ (log-scale absolute severity) and (ii) $\lvert S\rvert$ on $\log R$ (level-scale). Both include event fixed effects. Reports $\hat\beta$, SE, $p$-value. |
| **Interpretation** | A negative $\hat\beta$ confirms a diversification benefit in the second moment: larger syndicates have lower PYD volatility. The semi-log specification (severity on $\log R$) means $\hat\beta$ measures the change in severity dispersion per unit increase in log reserves. |
| **Key metrics** | $\hat\beta$ (dispersion elasticity); $p$-value. |
| **Pipeline stage** | Dispersion modelling (`dispersion_models`). |

### Table 15: Direction Test (HHI on Mean Severity)

| Aspect | Detail |
|---|---|
| **Content** | Regression of signed PYD severity on HHI (Herfindahl-Hirschman Index of LoB concentration), with event fixed effects. Reports $\hat\beta$, SE, $p$-value. |
| **Interpretation** | Tests whether LoB concentration shifts the **mean direction** of PYD. A non-significant result supports the assumption that mix affects only the variance of PYD, not its expected value -- enabling a pure-dispersion adjustment. **Caveat:** this tests HHI (concentration), not LoB *identity*. The identity of the largest line **does** significantly shift the mean (casualty- and aviation-dominant books run ~5 pp more adverse, joint Wald $p<0.001$ even after size and HHI controls; [model-simplification-tests.md](model-simplification-tests.md) §3b). So the pure-dispersion / market-mean re-centring holds on the concentration axis but **not** the line-identity axis -- re-centring a casualty-heavy target to the market mean understates its central PYD. |
| **Key metrics** | $\hat\beta$ (HHI direction effect); $p$-value. |
| **Pipeline stage** | Direction tests (`hhi_direction`). |

### Table 16: Power-Law HHI Dispersion

| Aspect | Detail |
|---|---|
| **Content** | Non-linear least squares fit of $s^2 = A + B \cdot \text{HHI}^C$, where $s^2$ is the squared severity. Reports parameter estimates $\hat{A}$ (variance floor), $\hat{B}$ (concentration scale), $\hat{C}$ (power exponent), and $R^2$ computed both on decile-binned means and on individual observations. |
| **Interpretation** | $\hat{A}$ represents the irreducible baseline variance; $\hat{B} \cdot \text{HHI}^{\hat{C}}$ captures the excess variance attributable to LoB concentration. A positive $\hat{B}$ with $\hat{C} > 0$ indicates that more concentrated syndicates exhibit higher PYD dispersion. The decile $R^2$ is typically much higher than the observation-level $R^2$ because averaging within deciles removes idiosyncratic noise. |
| **Key metrics** | $\hat{A}$, $\hat{B}$, $\hat{C}$; $R^2_{\text{decile}}$; $R^2_{\text{obs}}$. |
| **Pipeline stage** | Dispersion modelling (`power_law_hhi`). |

### Table 17: Diversification vs Reserve Size Correlation

| Aspect | Detail |
|---|---|
| **Content** | Pearson and Spearman correlation coefficients between $(1 - \text{HHI})$ (diversification index) and opening reserves $R$, with $p$-values. |
| **Interpretation** | Larger syndicates tend to be more diversified, but on the current data the association is **weak** (\|Pearson\| ≈ 0.21, VIF ≈ 1.04) — not enough collinearity to break a joint fit. The sequential pipeline is used not because of this correlation but because size and concentration are **near-redundant** for dispersion, which under-identifies the joint nonlinear model; and because the two are near-substitutes, the ordering is nearly immaterial (size-first vs HHI-first differ by 3.3 pp). See [model-simplification-tests.md](model-simplification-tests.md) §6. |
| **Key metrics** | $\rho_{\text{Pearson}}$, $\rho_{\text{Spearman}}$; $p$-values. |
| **Pipeline stage** | Confounding diagnostics (`div_size_correlation`). |

### Table 18: Variance Attribution

| Aspect | Detail |
|---|---|
| **Content** | Proportion of cross-sectional variance in $s^2$ explained at each stage of the pipeline: raw $\to$ after size adjustment $\to$ after HHI adjustment. |
| **Interpretation** | Quantifies the explanatory contribution of each adjustment. For example, if size adjustment explains 40% and HHI adjustment a further 15%, the combined model accounts for 55% of inter-syndicate dispersion heterogeneity. |
| **Key metrics** | $R^2$ increments at each stage; cumulative $R^2$. |
| **Pipeline stage** | Variance decomposition (`variance_attribution`). |

### Table 19: HHI Dispersion After Size Adjustment

| Aspect | Detail |
|---|---|
| **Content** | Power-law fit ($s^2_{\text{resid}} = A + B \cdot \text{HHI}^C$) on the residuals from the size-dispersion model. Reports $\hat{A}$, $\hat{B}$, $\hat{C}$, and $R^2$. |
| **Interpretation** | Shows the **residual** diversification effect after the size effect has been partialled out. A significant $\hat{B}$ indicates that HHI carries independent information about PYD dispersion beyond what size already captures. |
| **Key metrics** | $\hat{A}$, $\hat{B}$, $\hat{C}$; $R^2$ on size-adjusted residuals. |
| **Pipeline stage** | Sequential dispersion modelling (`hhi_after_size`). |

### Table 20: Combined Dispersion Scaling Model

| Aspect | Detail |
|---|---|
| **Content** | The final multiplicative model: $s^2(R, \text{HHI}) = V_{\text{size}}(R) \times V_{\text{hhi}}(\text{HHI}) \;/\; V_{\text{hhi}}(\text{HHI}_{\text{ref}})$. Reports model parameters and includes worked examples showing predicted PYD standard deviation ($\hat\sigma$) for representative portfolio profiles (e.g., small-concentrated, large-diversified). |
| **Interpretation** | This is the operational model. To obtain a bespoke severity distribution for a query portfolio with reserves $R_q$ and concentration $\text{HHI}_q$, one computes the scaling factor $s^2(R_q, \text{HHI}_q) / s^2(R_{\text{ref}}, \text{HHI}_{\text{ref}})$ and applies it to the standardised base distribution. The worked examples allow the reader to verify the arithmetic. |
| **Key metrics** | Model parameters; predicted $\hat\sigma$ for each profile. |
| **Pipeline stage** | Combined model assembly (`combined_dispersion_model`). |

### Table 21: Test Portfolio Definitions and Capital Impact

| Aspect | Detail |
|---|---|
| **Content** | Defines the six hypothetical test portfolios (LoB weight vectors and reserve sizes) and reports capital metrics -- VaR$_{99.5\%}$ and VaR$_{99\%}$ -- under three regimes: **naive** (raw empirical distribution), **mix-adjusted**, and **fully adjusted**. Includes Shapley decomposition of the adjustment into mix and size components, with bootstrap 95% confidence intervals. |
| **Interpretation** | The central policy-relevant table. It answers: "By how much does a syndicate's capital requirement change when we account for its specific LoB mix and size?" A positive mix effect for a property-heavy portfolio means the naive estimate under-states that portfolio's tail risk. Bootstrap CIs indicate estimation uncertainty. |
| **Key metrics** | VaR$_{99.5\%}$, VaR$_{99\%}$ (naive, mix-adjusted, fully adjusted); Shapley mix/size effects; 95% bootstrap CIs. |
| **Pipeline stage** | Capital impact assessment (`test_portfolio_capital`). |

### Table 4b: VaR 99.5% Decomposition by Persona Portfolio

| Aspect | Detail |
|---|---|
| **Content** | The same VaR$_{99.5\%}$ decomposition as Table 4, but applied to the five market personas -- **typical**, **small**, **large**, **diversified**, **undiversified** -- rather than the hypothetical property-heavy/casualty-heavy test portfolios. Each row reports the persona's reserve size (£m), HHI, raw (naive) VaR$_{99.5\%}$, mix-adjusted VaR, fully-adjusted VaR, mix effect (mix-adj $-$ raw), and size effect (full-adj $-$ mix-adj). |
| **Interpretation** | Shows how the capital correction varies across realistic market archetypes. The **small** persona typically shows a large positive size effect (naive under-states tail risk because the market pool is dominated by larger, less volatile syndicates). The **undiversified** persona may show a positive size effect offset by a smaller mix effect. Comparing Table 4b with Table 4 reveals whether the pattern of mix/size dominance holds across both stylised and empirically-grounded portfolios. |
| **Key metrics** | VaR$_{99.5\%}$ (raw, mix-adjusted, fully adjusted); mix effect; size effect; reserve size and HHI for each persona. |
| **Pipeline stage** | Persona capital impact (`persona_var_decomposition`). |

### Table 22: Univariate Model Comparison (Size vs HHI)

| Aspect | Detail |
|---|---|
| **Content** | Side-by-side comparison of two univariate power-law models fitted independently on raw $s^2$: the size model ($s^2 = A + B \cdot R^C$) and the HHI model ($s^2 = A + B \cdot \text{HHI}^C$). Reports $R^2$ at both observation and vigintile-mean levels, AIC, and likelihood-ratio test $p$-values for each model. |
| **Interpretation** | Identifies which single factor -- reserve size or LoB concentration -- explains more cross-sectional variance in PYD dispersion before any sequential conditioning. The model with higher $R^2$ (and lower AIC) is the stronger univariate predictor. This informs the sequential ordering: if size dominates, removing it first yields cleaner residuals for estimating the HHI effect (and vice versa). |
| **Key metrics** | $R^2_{\text{obs}}$, $R^2_{\text{binned}}$, AIC, $p$-value for each univariate model; $\Delta R^2$. |
| **Pipeline stage** | Univariate diagnostics (`univariate_comparison`). |

### Table 23: Variance Attribution (HHI-First Pipeline)

| Aspect | Detail |
|---|---|
| **Content** | Variance-attribution table for the alternative sequential pipeline that removes the HHI effect first and then fits the size power-law on the residuals. Reports raw $\sigma^2$, $\sigma^2$ after HHI adjustment, percentage explained by HHI, $\sigma^2$ after subsequent size adjustment, and percentage explained by size. |
| **Interpretation** | Mirrors Table 18 (which reports the size-first ordering) but reverses the conditioning order. Comparing the two tables reveals how much each factor's explanatory power depends on whether it is fitted first or on the residuals of the other. A factor that explains similar variance regardless of ordering has a robust, independent effect. |
| **Key metrics** | Variance at each stage; $\%$ explained by HHI (first step); $\%$ explained by size (second step); cumulative $\%$. |
| **Pipeline stage** | Sequential dispersion modelling, HHI-first variant (`hhi_first_variance_attribution`). |

### Table 24: Pipeline Ordering Comparison

| Aspect | Detail |
|---|---|
| **Content** | Head-to-head comparison of total variance explained by the two sequential pipelines: (A) size $\to$ HHI and (B) HHI $\to$ size. Each row shows the first-step explanatory percentage, second-step incremental percentage, and cumulative total. The table concludes with the absolute difference (in percentage points) and a recommendation of which ordering to prefer. |
| **Interpretation** | If the two factors were truly independent, total explained variance would be identical regardless of ordering. A difference indicates confounding -- the factor removed first "absorbs" some of the second factor's effect. The recommended ordering is the one that maximises total explained variance, ensuring the dominant effect is cleanly estimated first. A difference below 1 pp indicates practical equivalence. |
| **Key metrics** | Total $\%$ explained (size-first vs HHI-first); difference in pp; recommendation. |
| **Pipeline stage** | Ordering diagnostics (`ordering_comparison`). |

### Table 25: Local-Donor Sensitivity (one `.tex` file per portfolio)

| Aspect | Detail |
|---|---|
| **Content** | For each £500m test portfolio (property-heavy and casualty-heavy), a table showing how VaR$_{99.5\%}$ changes as the donor pool is progressively restricted to syndicates whose LoB composition is close to the target. Closeness is measured by Hellinger distance $h$; thresholds range from $h_{\max} = 0.30$ (very local) to $h_{\max} = 1.0$ (full market). Each row reports $h_{\max}$, the number of qualifying donors $n$, the raw (unweighted) VaR$_{99.5\%}$, and the fully-adjusted VaR$_{99.5\%}$ (mix-projected and size/HHI-scaled). |
| **Interpretation** | Tests the robustness of the mix-standardisation procedure. The full-market estimate ($h_{\max} = 1.0$) uses all syndicates regardless of LoB similarity. If the adjusted VaR is stable as $h_{\max}$ decreases (and $n$ shrinks), the projection is robust -- distant donors are not distorting the result. A sharp shift at small $h_{\max}$ would suggest that composition-distant syndicates introduce bias, motivating a tighter donor radius. Entries marked $<5$ indicate too few donors for a reliable quantile estimate. |
| **Key metrics** | VaR$_{99.5\%}$ (raw and adjusted) at each Hellinger threshold; donor count $n$. |
| **Pipeline stage** | Local-donor sensitivity (`robustness.local_donor`). |
| **Output files** | `table25_local_donor_prop-heavy_500m.tex`, `table25_local_donor_cas-heavy_500m.tex`. |

### Table 26: Tail Sample Support

| Aspect | Detail |
|---|---|
| **Content** | For each test portfolio, the total number of usable observations in the capital-eligible sample ($n$), the number of adverse observations (PYD $> 0$), and the effective number of observations sitting in the upper tail relevant to the 99th and 99.5th percentiles ($\lceil 0.01n \rceil$ and $\lceil 0.005n \rceil$ respectively). |
| **Interpretation** | Quantifies how many data points actually determine the tail-capital estimate. A VaR$_{99.5\%}$ based on 3 effective tail observations is fundamentally less precise than one based on 30, regardless of point-estimate stability. This table makes the thin-tail problem explicit. |
| **Key metrics** | $n$ (total); $n_{\text{adverse}}$; $n_{\text{tail},99\%}$; $n_{\text{tail},99.5\%}$. |
| **Pipeline stage** | Extended diagnostics (`tail_support`). |

### Table 27: Tail Capital Sensitivity Across Sample Variants

| Aspect | Detail |
|---|---|
| **Content** | VaR$_{99.5\%}$ (naive and fully adjusted) computed separately on the DENSE, FULL, BALANCED\_K8, and BALANCED\_K6 subsets, for each test portfolio. |
| **Interpretation** | Tests whether the headline capital estimates are sensitive to the choice of sample window. If VaR estimates are stable across subsets with different year coverage and syndicate composition, the result is robust. A large shift between DENSE and FULL may indicate that post-2020 thinning materially affects the tail. |
| **Key metrics** | VaR$_{99.5\%}$ (naive, adjusted) per subset per portfolio; sample size $n$. |
| **Pipeline stage** | Extended diagnostics (`tail_capital_sensitivity`). |

### Table 28: Bootstrap VaR Estimates with Uncertainty Bands

| Aspect | Detail |
|---|---|
| **Content** | For each test portfolio, the point estimate of VaR$_{99\%}$ and VaR$_{99.5\%}$ (fully adjusted) together with the 95\% bootstrap confidence interval (2.5th and 97.5th percentiles of 500 syndicate-resampled replicates). |
| **Interpretation** | Shows the sampling uncertainty around the tail-capital claim. Wide confidence intervals indicate that the VaR estimate is sensitive to the specific syndicate composition of the sample and should not be quoted as a precise number. |
| **Key metrics** | VaR point estimate; 95\% CI lower; 95\% CI upper; for both 99\% and 99.5\% levels. |
| **Pipeline stage** | Capital impact bootstrap (`capital_impact.portfolios[].boot_ci`). |

### Table 29: Reserve-Base Source Audit

| Aspect | Detail |
|---|---|
| **Content** | Counts and percentages of observations by reserve-base source type: opening reserves extracted from annual reports. |
| **Interpretation** | Documents that the denominator used to compute PYD severity ($S = \text{PYD} / R$) is consistently sourced from prior-year net claims reserves disclosed in syndicate annual reports. |
| **Key metrics** | Count and percentage by source type. |
| **Pipeline stage** | Data quality diagnostics (`data_quality.reserve_source_dist`). |

### Table 30: LoB Weight Source Audit

| Aspect | Detail |
|---|---|
| **Content** | Counts and percentages by LoB weight source: direct premium-mix disclosure versus unavailable (proportional allocation). |
| **Interpretation** | Quantifies the fraction of observations for which the LoB composition was directly extracted from gross premium mix disclosures versus those where the pipeline fell back to proportional allocation (which assumes severity is uniform across lines). |
| **Key metrics** | Count and percentage by source type. |
| **Pipeline stage** | Data quality diagnostics (`data_quality.weight_source_dist`). |

### Table 31: PYD Severity Source Audit

| Aspect | Detail |
|---|---|
| **Content** | Counts and percentages by PYD severity derivation method: structured LoB-level amounts extracted from tables, versus triangle/proportional allocation. |
| **Interpretation** | Shows how LoB-level severity was constructed. Records with structured table data have directly observed LoB-level reserve movements; the remainder rely on proportional allocation of the aggregate PYD across LoB weights. |
| **Key metrics** | Count and percentage by derivation method. |
| **Pipeline stage** | Extended diagnostics (`pyd_source_dist`). |

### Table 32: Dual-Model Disagreement Workflow

| Aspect | Detail |
|---|---|
| **Content** | A compact summary table and narrative paragraph describing the dual-model extraction workflow. Reports: total files processed, number with dual-model extractions, number with single-model extraction, and material disagreements (defined as $> 0.5$\,pp difference in PYD\%). |
| **Interpretation** | Documents the quality-assurance process for data extraction. The disagreement count quantifies how often the two LLM extraction models produced materially different PYD\% values, and the narrative explains how conflicts were resolved. |
| **Key metrics** | Total files; dual-model count; material disagreement count; resolution rule. |
| **Pipeline stage** | Extended diagnostics (`dual_model_stats`). |

### Table 33: Exclusions by Reason and Year

| Aspect | Detail |
|---|---|
| **Content** | Cross-tabulation of excluded observations by exclusion reason (EXCLUDED, SKIPPED, IN RUNOFF, NO\_RESERVES) and calendar year. Includes row and column totals. |
| **Interpretation** | Makes the sample-selection process transparent. Readers can verify that exclusions are not concentrated in particular years (which would introduce survivorship bias) and understand the magnitude of each exclusion reason. |
| **Key metrics** | Count per reason per year; row totals; column totals. |
| **Pipeline stage** | Extended diagnostics (`classification_summary`). |

### Table 34: Subset Comparison

| Aspect | Detail |
|---|---|
| **Content** | Side-by-side comparison of the DENSE, FULL, BALANCED\_K8, and BALANCED\_K6 subsets showing: observation count, unique syndicates, year range, median opening reserves, median HHI, and shares of the two dominant event-group categories (natural catastrophe and COVID). |
| **Interpretation** | Allows the reader to assess compositional differences across the subsets used in the analysis. If median reserves or HHI differ substantially between DENSE and BALANCED panels, results may not be directly comparable without noting the selection effect. |
| **Key metrics** | $n$; syndicates; year range; median $R$; median HHI; event-group shares. |
| **Pipeline stage** | Extended diagnostics (`subset_profiles`). |

### Table 35: Size--Dispersion Robustness

| Aspect | Detail |
|---|---|
| **Content** | The dispersion regression ($\log|S|$ on $\log R$) estimated on three samples: (i) the primary DENSE specification, (ii) pre-2020 observations only, and (iii) persistent reporters only (syndicates with $\geq 6$ years of data). Each row shows $n$, $\hat\beta$, standard error, and $p$-value. |
| **Interpretation** | Tests whether the size--dispersion finding is an artefact of (a) post-2020 sample thinning or (b) intermittent reporters who may have systematically different characteristics. If $\hat\beta$ and significance are broadly preserved across all three samples, the finding is robust. |
| **Key metrics** | $\hat\beta$; SE; $p$-value per specification. |
| **Pipeline stage** | Extended diagnostics (`dispersion_robustness`). |

### Table 36: Event-Group Categories and Counts

| Aspect | Detail |
|---|---|
| **Content** | Lists every event-group ID used in the RE-GLS model, decomposed into year and cause category, with the number of syndicate-year observations assigned to each group and whether the group was pooled (fewer than 3 original observations merged into the year-level pooled group). |
| **Interpretation** | Provides transparency on the event fixed-effect structure. Large groups (e.g., ``2019\_natural\_cat'' with 66 observations) dominate the within-event variation; pooled groups collect thin causes that individually lack sufficient mass. |
| **Key metrics** | Event-group ID; year; cause; $n$; pooled flag. |
| **Pipeline stage** | Size-severity analysis (`size_scaling.event_group_audit`). |

### Table 37: Event-Group Operational Definitions

| Aspect | Detail |
|---|---|
| **Content** | A reference table documenting the operational rules for event-group assignment: which fields feed the assignment (year, cause\_category derived from primary\_causes and narrative keywords), the pooling rule ($n_{\min} = 3$), and the minimum count that triggers pooling. |
| **Interpretation** | Ensures the event-group construction is fully reproducible. The pooling rule prevents singleton event groups from absorbing all degrees of freedom in the RE-GLS model. |
| **Key metrics** | Assignment fields; pooling threshold; minimum group size. |
| **Pipeline stage** | Event-group assignment (`assign_event_groups`). |

### Table 38: Power-Law Dispersion Calibration

| Aspect | Detail |
|---|---|
| **Content** | Full NLS calibration output for the two power-law variance functions that underpin the transfer operator: **Panel A** reports the size model $V_{\text{size}}(R) = A + B \cdot R^C$ and **Panel B** reports the HHI model $V_{\text{hhi}}(\text{HHI}) = A + B \cdot \text{HHI}^C$ (fitted on size-adjusted $s^2$). Each panel shows the point estimates for $A$, $B$, and $C$, standard errors (OLS conditional on $\hat{C}$ for $A$ and $B$; profile CI for $C$), $p$-values, 95\% confidence intervals, $R^2$, and sample size. **Panel C** documents the estimation method: profile NLS with grid search over $C$, winsorisation, and the profile-likelihood CI construction. |
| **Interpretation** | Addresses the replicability gap identified in Section 4.4. A reviewer can verify: (i) the floor $A > 0$ (undiversifiable variance exists); (ii) $B > 0$ (diversifiable component is material); (iii) $C < 0$ for size (variance decreases with reserves) and $C > 0$ for HHI (variance increases with concentration); (iv) the profile CI for $C$ does not include zero. The constraint note on the HHI model's $C$ (upper bound at grid edge, $A \geq 0$ binding) flags that the true curvature may be higher than estimated. |
| **Key metrics** | $\hat{A}$, $\hat{B}$, $\hat{C}$; SE($A$), SE($B$); profile CI($C$); $p$-values; $R^2$; $n$. |
| **Pipeline stage** | Dispersion modelling (`fit_power_dispersion`, `analysis_n6`). |

---

## 3. Figures

All figures are output as PNG files at 300 dpi, sized for single- or double-column journal layout.

### Figure 1: Yearly Observation Count

| Aspect | Detail |
|---|---|
| **Visual** | Bar chart with calendar year on the $x$-axis and the number of syndicate-year observations on the $y$-axis. Each bar is labelled with its count. |
| **How to read** | Shows the data density available in each year. A drop in count indicates fewer syndicates reported in that year (e.g., due to the switch from SFCRs to newer reporting formats, or syndicates entering run-off). |
| **Key patterns** | (i) The dense period (typically 2015--2019) with $\sim$60--68 observations per year; (ii) the step-down from 2020 onwards ($\sim$33--38 per year), reflecting the transition in reporting availability; (iii) whether any single year is thin enough to warrant caution in year-specific analyses. |
| **Pipeline stage** | Corpus construction (`meta.yearly_observations`). |

### Figure 2: Annual p95 Trends

| Aspect | Detail |
|---|---|
| **Visual** | Line chart with calendar year on the $x$-axis and the 95th percentile of PYD severity on the $y$-axis. Two series are plotted: **raw** (pre-standardisation) and **mix-standardised** (post-LoB-composition projection). OLS regression lines are overlaid on both series. |
| **How to read** | Compare the slopes of the two regression lines. A steep raw trend that flattens after standardisation implies the apparent trend was driven by shifting market composition over time, not by genuinely worsening reserve development. |
| **Key patterns** | Look for (i) divergence between the two series in recent years, (ii) a near-zero slope on the standardised series, and (iii) the magnitude of the gap between raw and standardised p95 at the endpoints of the time window. |
| **Pipeline stage** | Trend analysis (`annual_p95_trends`). |

### Figure 3: Mean Excess Function

| Aspect | Detail |
|---|---|
| **Visual** | Mean excess plot (also called the mean residual life plot) for both raw and standardised severity. The $x$-axis is the threshold $u$; the $y$-axis is $E[X - u \mid X > u]$. |
| **How to read** | A linear and upward-sloping mean excess function is consistent with a **generalised Pareto distribution** (GPD) tail. Curvature or a sudden change in slope suggests the tail behaviour shifts at that threshold. |
| **Key patterns** | (i) Linearity in the upper tail region; (ii) whether the standardised series exhibits a cleaner linear region (indicating better-behaved tails after adjustment); (iii) the threshold at which the plot stabilises, which informs the choice of GPD fitting threshold. |
| **Pipeline stage** | Tail diagnostics (`mean_excess_function`). |

### Figure 4: Size--Severity Relationship

| Aspect | Detail |
|---|---|
| **Visual** | Scatter plot with $\log(R)$ (log opening reserves) on the $x$-axis and PYD severity on the $y$-axis. A fitted regression line is overlaid. |
| **How to read** | The slope of the fitted line is the empirical size-severity elasticity $\hat\beta$. A negative slope confirms the diversification benefit: larger syndicates exhibit lower severity dispersion. |
| **Key patterns** | (i) The downward slope confirming the diversification benefit; (ii) the scatter around the line (wider scatter = more noise in the relationship); (iii) potential non-linearity at the extremes (very small or very large syndicates). |
| **Pipeline stage** | Size-severity regression (`size_severity_scatter`). |

### Figure 4a: Reserve Size vs Absolute PYD Severity

| Aspect | Detail |
|---|---|
| **Visual** | Scatter plot with $\log(R)$ on the $x$-axis and $\lvert\text{PYD \%}\rvert$ on the $y$-axis. A Gaussian-kernel smoothed trend line is overlaid. |
| **How to read** | A downward-sloping trend confirms that larger syndicates exhibit smaller absolute PYD movements. Unlike Figure 4 (which plots signed severity), this figure isolates the **magnitude** of reserve development regardless of direction. |
| **Key patterns** | (i) Whether the trend is monotonically decreasing or flattens at extreme sizes; (ii) the density of the scatter — wide dispersion at small sizes narrowing at large sizes is consistent with a volatility-reduction mechanism. |
| **Pipeline stage** | Size-severity regression (`size_severity_scatter`). |

### Figure 4b: Diversification vs Absolute PYD Severity

| Aspect | Detail |
|---|---|
| **Visual** | Scatter plot with diversification $(1 - \text{HHI})$ on the $x$-axis and $\lvert\text{PYD \%}\rvert$ on the $y$-axis. A Gaussian-kernel smoothed trend line is overlaid. |
| **How to read** | A downward-sloping trend indicates that more diversified syndicates (higher $1 - \text{HHI}$) experience smaller absolute PYD movements. This complements the size plot by isolating the **composition channel** of the diversification benefit. |
| **Key patterns** | (i) Whether the trend is monotonically decreasing; (ii) whether the relationship is weaker or stronger than the size relationship (Figure 4a), informing the relative importance of mix vs size adjustments. |
| **Pipeline stage** | Joint composition analysis (`hhi_scatter`). |

### Figure 5: VaR Decomposition (Shapley Bar Chart)

| Aspect | Detail |
|---|---|
| **Visual** | Grouped bar chart with one group per test portfolio. Within each group, two bars represent the **mix effect** and **size effect** (Shapley values), showing their respective contributions to the difference between naive and fully-adjusted VaR$_{99.5\%}$. |
| **How to read** | Taller bars indicate a larger adjustment. If the mix bar consistently exceeds the size bar, composition standardisation is the primary driver of capital correction. |
| **Key patterns** | (i) Mix effect dominance across portfolios; (ii) sign differences (positive = naive under-states risk; negative = naive over-states); (iii) variation across portfolio sizes for the same LoB mix. |
| **Pipeline stage** | Capital impact assessment (`var_decomposition_chart`). |

### Figure C.6: LoB-Level Elasticities (Appendix)

| Aspect | Detail |
|---|---|
| **Visual** | Dot plot (forest plot) with one row per LoB category. Each row shows the **raw** size-severity elasticity estimate (open circle) and the **empirical-Bayes shrinkage** estimate (filled circle), with horizontal error bars for the shrinkage estimate's posterior interval. |
| **How to read** | Shrinkage pulls extreme raw estimates toward the grand mean. LoBs with few observations will shrink more. The ordering reveals which lines of business exhibit the strongest (or weakest) diversification benefit. |
| **Key patterns** | (i) Which LoBs have elasticities significantly different from zero; (ii) the degree of shrinkage (large gaps between raw and shrinkage estimates indicate sparse data for that LoB); (iii) whether all LoBs share the same sign (all negative = universal diversification benefit). |
| **Pipeline stage** | LoB-level analysis (`lob_elasticities`). |

### Persona Overlay Figures

| Aspect | Detail |
|---|---|
| **Visual** | One figure per market persona (typical, small, large, diversified, undiversified). Each figure is a histogram overlay: the **raw PYD%** distribution in one colour and the **standardised-to-persona PYD%** distribution in another, with kernel density estimates superimposed. |
| **How to read** | Compare the spread, skewness, and tail weight of the two distributions. The standardised distribution is what the persona "should" look like after removing composition distortions from the broader market data. |
| **Key patterns** | (i) Whether standardisation narrows or widens the distribution (narrowing for small/concentrated personas; widening for large/diversified); (ii) shifts in skewness or kurtosis; (iii) changes in the tail (p95/p99 region). |
| **Pipeline stage** | Persona analysis (`persona_overlays`). |

### PYD% Distribution

| Aspect | Detail |
|---|---|
| **Visual** | Single histogram of PYD% across all syndicate-year observations, with a kernel density overlay. |
| **How to read** | Provides the baseline view of how PYD is distributed in the raw data before any adjustments. |
| **Key patterns** | (i) Central tendency (most syndicates cluster near zero PYD%); (ii) skewness (typically a longer right tail representing reserve deterioration); (iii) heavy tails motivating EVT methods. |
| **Pipeline stage** | Descriptive statistics (`pyd_distribution`). |

### Boxplots by Decile (Reserves, HHI, Year)

| Aspect | Detail |
|---|---|
| **Visual** | Three separate box-plot panels. Each has decile bins on the $x$-axis and PYD on the $y$-axis. The panels are grouped by (a) reserves decile, (b) HHI decile, and (c) calendar year. |
| **How to read** | Compare the box widths (IQR), median positions, and whisker extents across deciles. Increasing box width from left to right indicates rising dispersion. |
| **Key patterns** | (i) **Reserves deciles**: dispersion should decrease from the smallest to largest decile (diversification benefit). (ii) **HHI deciles**: dispersion should increase with concentration. (iii) **Year**: look for temporal trends or one-off spikes (e.g., catastrophe years). |
| **Pipeline stage** | Exploratory analysis (`decile_boxplots`). |

### Size vs PYD Severity (Log-Log)

| Aspect | Detail |
|---|---|
| **Visual** | Log-log scatter (same underlying data as Figure 4, alternative axis labels or annotation). |
| **How to read** | Identical interpretation to Figure 4. |
| **Pipeline stage** | Dispersion modelling (`size_vs_severity`). |

### Power-Law Size Dispersion Curve

| Aspect | Detail |
|---|---|
| **Visual** | Curve plot of the fitted power law $s^2 = A + B \cdot R^C$ overlaid on either raw observation points or decile-binned means with error bars. |
| **How to read** | The curve should pass through the binned means. Residuals around the curve indicate the fit quality. The asymptotic floor $A$ is visible as the curve's horizontal asymptote for large $R$. |
| **Key patterns** | (i) Rapid decline in $s^2$ for small $R$, flattening for large $R$; (ii) goodness of fit in the tails of the $R$ distribution. |
| **Pipeline stage** | Dispersion modelling (`power_law_size`). |

### Diversification vs PYD Severity

| Aspect | Detail |
|---|---|
| **Visual** | Scatter of $(1 - \text{HHI})$ (diversification index) on the $x$-axis versus PYD severity on the $y$-axis. |
| **How to read** | A downward trend indicates that more diversified syndicates have lower severity dispersion. |
| **Key patterns** | (i) Overall trend direction; (ii) heteroscedasticity (the scatter may be wider at low diversification); (iii) potential non-linearity. |
| **Pipeline stage** | Exploratory analysis (`div_vs_severity`). |

### Power-Law HHI Dispersion Curve

| Aspect | Detail |
|---|---|
| **Visual** | Curve plot of $s^2 = A + B \cdot \text{HHI}^C$ with decile-binned data overlay. |
| **How to read** | Analogous to the power-law size curve, but with HHI on the $x$-axis. Rising curve confirms that concentration increases dispersion. |
| **Key patterns** | (i) Monotonic increase; (ii) the power $C$ controls the curvature -- $C = 1$ is linear, $C > 1$ is convex, $C < 1$ is concave. |
| **Pipeline stage** | Dispersion modelling (`power_law_hhi_chart`). |

### Diversification vs Reserve Size

| Aspect | Detail |
|---|---|
| **Visual** | Scatter of $(1 - \text{HHI})$ vs $R$ (or $\log R$). |
| **How to read** | A positive trend confirms the confounding: larger syndicates tend to be more diversified. This motivates the sequential adjustment strategy. |
| **Key patterns** | (i) Strength and direction of correlation; (ii) whether the relationship is roughly monotonic or exhibits clusters. |
| **Pipeline stage** | Confounding diagnostics (`div_vs_size`). |

### Size-Adjusted $s^2$ vs Diversification

| Aspect | Detail |
|---|---|
| **Visual** | Scatter of size-adjusted residual variance ($s^2_{\text{resid}}$) vs $(1 - \text{HHI})$ or HHI. |
| **How to read** | After removing the size effect, any remaining trend with diversification is the independent HHI contribution. The fitted power-law curve from Table 19 may be overlaid. |
| **Key patterns** | (i) A residual trend confirms HHI adds explanatory power beyond size; (ii) the scatter should be tighter than the unadjusted version if size was a significant confounder. |
| **Pipeline stage** | Sequential dispersion modelling (`size_adjusted_vs_div`). |

### HHI-Adjusted $s^2$ vs Reserve Size

| Aspect | Detail |
|---|---|
| **Visual** | Scatter of HHI-adjusted residual variance ($s^2_{\text{resid}}$) vs opening reserves $R$, with the fitted power-law size curve overlaid and vigintile bin means marked. This is the counterpart to the size-adjusted HHI scatter, but with the conditioning order reversed. |
| **How to read** | After removing the HHI effect, any remaining trend with reserve size is the independent size contribution. The fitted curve from the HHI-first pipeline's second stage is overlaid. Compare the strength of this residual trend with the HHI residual trend in the size-first scatter. |
| **Key patterns** | (i) A clear downward trend confirms that size carries independent information beyond HHI; (ii) the scatter tightness relative to the size-first pipeline indicates how much overlap exists between the two factors; (iii) the fitted curve should pass through the bin means. |
| **Pipeline stage** | Sequential dispersion modelling, HHI-first variant (`hhi_adjusted_vs_size`). |

### Capital Decomposition Bar Chart

| Aspect | Detail |
|---|---|
| **Visual** | Bar chart showing three bars per test portfolio: **naive VaR**, **mix-adjusted VaR**, and **fully-adjusted VaR** (at the 99.5% level). Bars may be stacked or grouped. |
| **How to read** | The difference between the naive bar and the fully-adjusted bar is the total capital correction. The intermediate mix-adjusted bar shows how much of the correction comes from composition alone. |
| **Key patterns** | (i) Direction of correction (naive over- or under-states relative to adjusted); (ii) whether the mix step or the size step contributes more; (iii) variation across portfolios. |
| **Pipeline stage** | Capital impact assessment (`capital_decomposition_chart`). |

---

## 4. Interpretation Guide

### 4.1 The Adjustment Pipeline

The analysis applies a sequential standardisation to transform a heterogeneous pool of syndicate-level PYD observations into a distribution that is representative of a specific query portfolio. The stages are:

1. **Raw observations.** Each syndicate $i$ in event $t$ contributes a severity observation $S_{i,t}^{\text{raw}}$. These are pooled across all syndicates and events.

2. **Mix standardisation.** Each raw severity is re-weighted to reflect a common (or query-specific) LoB composition. The standardised severity for syndicate $i$ in event $t$ is:

   $$S_{i,t}^{\text{mix}} = \sum_\ell w_\ell^{\text{query}} \cdot s_{i,t,\ell}$$

   where $w_\ell^{\text{query}}$ is the query portfolio's weight in LoB $\ell$ and $s_{i,t,\ell}$ is the LoB-level severity. This removes the distortion caused by syndicates having different LoB mixes.

3. **Size adjustment.** The mix-standardised severity is rescaled to reflect the dispersion appropriate for the query portfolio's reserve size $R_q$:

   $$S_{i,t}^{\text{adj}} = S_{i,t}^{\text{mix}} \times \sqrt{\frac{V_{\text{size}}(R_q)}{V_{\text{size}}(R_i)}}$$

   where $V_{\text{size}}(R) = A + B \cdot R^C$ is the power-law size-dispersion function.

4. **Fully adjusted.** Optionally, HHI-based dispersion scaling is applied on top of the size adjustment:

   $$S_{i,t}^{\text{full}} = S_{i,t}^{\text{adj}} \times \sqrt{\frac{V_{\text{hhi}}(\text{HHI}_q)}{V_{\text{hhi}}(\text{HHI}_i)}} \times \sqrt{\frac{V_{\text{hhi}}(\text{HHI}_{\text{ref}})}{V_{\text{hhi}}(\text{HHI}_{\text{ref}})}}$$

   In practice, the combined model from Table 20 handles both adjustments in a single multiplicative step.

### 4.2 Shapley Decomposition of Mix and Size Effects

When decomposing the difference between the naive VaR and the fully-adjusted VaR, the analysis uses **Shapley values** to attribute the change to the mix effect and the size effect. The Shapley approach is order-independent: it averages over both possible orderings (mix-first then size, and size-first then mix) to produce a fair attribution that sums exactly to the total difference.

- **Mix effect**: the average marginal impact of switching from the market-average LoB composition to the query portfolio's composition, computed across both orderings.
- **Size effect**: the average marginal impact of switching from the market-average reserve size to the query portfolio's reserve size, computed across both orderings.

The sum of the two Shapley values equals exactly:

$$\text{VaR}^{\text{fully adjusted}} - \text{VaR}^{\text{naive}}$$

### 4.3 Using the Combined Dispersion Model for Capital Assessment

To derive a bespoke PYD severity distribution for a portfolio with reserves $R_q$ and LoB concentration $\text{HHI}_q$:

1. Start with the standardised base distribution (mix-projected to the query portfolio's LoB weights).
2. Compute the dispersion scaling factor:

   $$\lambda = \sqrt{\frac{V_{\text{size}}(R_q) \times V_{\text{hhi}}(\text{HHI}_q)}{V_{\text{size}}(R_{\text{ref}}) \times V_{\text{hhi}}(\text{HHI}_{\text{ref}})}}$$

3. Multiply each observation in the base distribution by $\lambda$.
4. Read off quantiles (e.g., VaR$_{99.5\%}$) from the rescaled distribution.

The reference values $R_{\text{ref}}$ and $\text{HHI}_{\text{ref}}$ are the median reserves and median HHI in the corpus, respectively.

### 4.4 Caveats and Limitations

- **LoB granularity.** The adjustment operates at the level of Lloyd's reporting categories. Intra-LoB heterogeneity (e.g., different sub-classes within "Property") is not captured.
- **One-year, no development structure.** Each syndicate-year is reduced to a single one-year PYD ratio; the maturity of the reserve base (the claims-development triangle) is discarded. This aligns with the Solvency II one-year reserve-risk view. Empirically the omission is defensible: a triangle-derived reserve maturity is insignificant for |PYD| once size is controlled ([model-simplification-tests.md](model-simplification-tests.md) §4, $p = 0.57$).
- **Premium mix as reserve mix.** The current-year gross premium mix is used as the LoB composition of the reserves, which were actually written across several prior underwriting-year vintages. For the median syndicate this proxy is close to the vintage-blended reserve mix (Hellinger ≈ 0.07), but for mix-shifters it is materially wrong — ~1 in 5 reconstructed line-level severities move > 25 % and the projected tail shifts ~6 % at VaR95 ([model-simplification-tests.md](model-simplification-tests.md) §5). Prefer segmental technical-provision splits where disclosed.
- **Stationarity assumption.** The pipeline assumes that the relationship between LoB mix and PYD severity is stable over the observation window. Structural market changes (e.g., post-COVID liability shifts) could invalidate this.
- **Power-law functional form.** The $s^2 = A + B \cdot X^C$ specification is empirically motivated but not derived from first principles. Alternative functional forms (e.g., log-linear, piecewise) may fit comparably.
- **Independence of LoB severities.** Mix standardisation implicitly assumes that LoB-level severities are exchangeable across syndicates. In practice, syndicates with different underwriting strategies within the same LoB may exhibit different severity distributions.
- **Tail estimation uncertainty.** VaR$_{99.5\%}$ is estimated from a finite sample. Bootstrap confidence intervals (reported in Table 21) should be consulted before drawing capital conclusions.
- **Survivorship.** Syndicates that close or enter run-off are excluded, potentially introducing survivorship bias. The balanced-panel robustness check (Table 3, M1 balanced) partially addresses this.

---

## 5. Reproduction

To regenerate the entire paper pack from source data:

```bash
python run_analysis.py
```

This executes the full analysis pipeline and writes all LaTeX table fragments and PNG figures to the `paper_pack/` directory. The pipeline is deterministic given the same input data: re-running produces identical outputs.

### Prerequisites

- Python environment with dependencies installed (see project `requirements.txt` or conda environment).
- Source data files in the expected location (see project data configuration).

### Output Structure

```
paper_pack/
    table_01_corpus_coverage.tex
    table_02_sampling_sensitivity.tex
    table_03_size_severity_elasticity.tex
    ...
    table_21_test_portfolio_capital.tex
    table_4b_var_decomposition_personas.tex
    table_22_univariate_comparison.tex
    table_23_variance_attribution_hhi_first.tex
    table_24_ordering_comparison.tex
    table26_tail_sample_support.tex
    table27_tail_capital_sensitivity.tex
    table28_bootstrap_var.tex
    table29_reserve_source_audit.tex
    table30_lob_weight_source_audit.tex
    table31_pyd_source_audit.tex
    table32_dual_model_workflow.tex
    table33_exclusions_by_year.tex
    table34_subset_comparison.tex
    table35_dispersion_robustness.tex
    table36_event_groups.tex
    table37_event_group_definitions.tex
    fig_02_annual_p95_trends.png
    fig_03_mean_excess.png
    fig_04_size_severity.png
    fig_size_abs_pyd.png
    fig_diversification_abs_pyd.png
    fig_05_var_decomposition.png
    fig_c6_lob_elasticities.png
    ...
```

Individual pipeline stages can be run selectively; consult `run_analysis.py --help` for stage-specific options.
