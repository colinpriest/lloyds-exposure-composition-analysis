# Dispersion Scaling of Prior-Year Development: A Robust Bayesian Pooling Model

*Working documentation for incorporation into the paper. Covers methodology, the logic
and justification for each modelling choice, the estimation results, and — importantly —
the alternatives that were tested and rejected. Notation is self-contained; adapt to the
paper's conventions as needed.*

---

## 1. Motivation and what the previous specification got wrong

The earlier analysis modelled the per-observation variance proxy $s^2$ (squared severity,
where severity $S=\text{PYD}/R$ is prior-year development scaled by opening reserves $R$)
through a **two-stage least-squares pipeline**: a size power law
$V_{\text{size}}(R)=A_R+B_R R^{C_R}$ fitted first, followed by a concentration power law
$V_{\text{hhi}}(H)=A_H+B_H H^{C_H}$ fitted on size-adjusted residuals, then composed
multiplicatively as $s^2(R,H)=V_{\text{size}}(R)\,V_{\text{hhi}}(H)/V_{\text{hhi}}(H_{\text{ref}})$.

Auditing that pipeline surfaced four problems that motivated a redesign:

1. **Calibration-basis mismatch.** The size stage was in fact fitted on *raw* $s^2$
   (`single_r`, label "Size diversification"), not on mix-adjusted residuals as the prose
   claimed. Because small syndicates are also the concentrated ones, the raw size slope
   ($B_R=0.505$) absorbs part of the concentration effect; a genuinely composition-removed
   size fit gives $B_R\approx0.27$ — roughly half. The published $V_{\text{size}}$ is
   therefore the *total* size–variance gradient, not an orthogonalised "pure size" effect.

2. **Circularity between stages.** One cannot simultaneously fit size on
   composition-removed residuals *and* concentration on size-removed residuals with two
   sequential univariate fits — each stage would be pre-cleaned by the other. Whichever
   stage runs first claims the shared $R$–$H$ covariance. Consistency requires a *single
   joint* estimation.

3. **Two floors for one quantity.** The sequential composition carried two independently
   calibrated intercepts, $A_R$ and $A_H$, nominally both representing irreducible
   ("undiversifiable") variance. Under the multiplicative-ratio composition only $A_R$ is
   an absolute floor; $A_H$ enters as a bounded concentration multiplier. The structure was
   nonetheless conceptually muddled — there should be *one* undiversifiable asymptote.

4. **Apparent joint-fit failure was an artefact.** The joint least-squares fit looked
   degenerate (intercept $\approx0$, both slopes insignificant, $R^2\approx0.015$). We
   traced this **not** to collinearity but to an inconsistency: the univariate fits
   winsorised $s^2$ at the 95th percentile while the joint fit did not, leaving it hostage
   to ~16 extreme observations. Diagnostics confirm collinearity is mild —
   $\mathrm{corr}(R,H)=-0.22$, $\mathrm{corr}(\log R,H)=-0.30$; after the power transforms
   the design columns correlate 0.32 with **VIF = 1.11** and condition number ≈ 600. With
   consistent winsorisation both joint slopes are significant ($p=0.01$, $p<0.001$).

The redesign therefore aims for: a single joint law (no ordering, one floor), robustness to
the genuinely heavy-tailed data, an interpretable size exponent, and honest uncertainty
that respects the panel structure.

---

## 2. Methodology

### 2.1 Reparametrisation to a pooling exponent

We work in **standard-deviation / pooling** terms rather than on an abstract variance
power. Consider aggregate development $L=\text{PYD}$ built from many exposure blocks. Classical
risk pooling gives $\mathrm{SD}(L)\propto R^{\,k}$ with

$$
k=\tfrac12 \;\Rightarrow\; \sqrt{N}\text{ pooling (full independence, maximal diversification)},
\qquad
k=1 \;\Rightarrow\; \text{linear (full dependence / comonotonic, no diversification).}
$$

The severity ratio $S=L/R$ then has $\mathrm{SD}(S)\propto R^{\,k-1}$ (exponent in
$[-\tfrac12,0]$), and variance $\propto R^{2(k-1)}$. This maps onto the old variance
exponent as $C=2(k-1)$, i.e. $k=1+C/2$. The published $C=-0.8127$ corresponds to
$k\approx0.59$ — already inside the admissible pooling range, so **constraining $k\in[0.5,1]$
costs almost nothing but turns the fitted number into an interpretable dependence
coefficient**. We enforce the constraint smoothly via $k=\tfrac12+\tfrac12\,\sigma(\theta)$
with $\theta$ unconstrained.

### 2.2 Folding concentration into the pooling mechanism (one law)

Rather than a second stage, concentration enters through the *same* mechanism. The
Herfindahl index's reciprocal $1/H$ is the **effective number of independent lines of
business** $n_{\text{eff}}$ (inverse-Simpson / participation ratio). We therefore define an
**effective diversified size** directly in terms of the effective line count

$$
R^{\text{eff}} = R\,(1/H)^{\gamma} = R\,n_{\text{eff}}^{\gamma}, \qquad \gamma\ge 0,\ \ n_{\text{eff}}=1/H,
$$

and apply a single pooling law $\mathrm{SD}(S)\propto (R^{\text{eff}})^{k-1}$. Concentration
(larger $H$, fewer effective lines) shrinks the effective size $\Rightarrow$ less pooling, so
its dispersion effect is $(k-1)\gamma$ on the log scale. This **eliminates the stage-ordering
bias and the two-floor problem by construction**: one law, one exponent, one floor.

This $n_{\text{eff}}$ form is also well-defined across the *entire* concentration range,
including **single-line reporters**: at $H=1$, $n_{\text{eff}}=1\Rightarrow R^{\text{eff}}=R$
(no diversification credit — exactly right), avoiding the degeneracy of an equivalent
$(1-H)^{\gamma}$ form, which sends $R^{\text{eff}}\to0$ and $\log R^{\text{eff}}\to-\infty$ at
$H=1$ and would force single-line observations to be dropped.

### 2.3 Bayesian hierarchical robust specification

For syndicate $i$ in reporting year $t$:

$$
\begin{aligned}
S_{it} &\sim \text{Student-}t\!\left(\nu,\; \mu,\; \sigma_{it}\right) \\
\sigma_{it} &= \sqrt{\sigma_{\text{undiv}}^2 + \sigma_{\text{div}}^2\,\big[(R_{it}/R_{\text{ref}})(1/H_{it})^{\gamma}\big]^{2(k-1)}}\;\,e^{s_t}, &&
   R_{\text{ref}}=\pounds500\text{m} \\
s_t &\sim \mathcal N(0,\tau_s) &&\text{(reporting-year shared shock, log-scale)}
\end{aligned}
$$

with $\sigma_{\text{undiv}}$ the **undiversifiable floor** (dispersion as effective size
$\to\infty$) and $\sigma_{\text{div}}$ the **diversifiable SD at the reference** ($R=\pounds500$m,
single-line, where the power term equals 1); the diversifiable term decays with the pooling
exponent $k$ and shrinks the effective size via the effective line count $n_{\text{eff}}=1/H$.
The three design decisions, each addressing a requirement:

- **Robust likelihood (not Gaussian LS/MLE).** The Student-$t$ with estimated degrees of
  freedom $\nu$ accommodates the heavy tails that destroyed the LS joint fit. Robustness is
  therefore *built into the likelihood* rather than imposed by ad-hoc winsorisation.
- **Constrained pooling exponent.** $k\in[0.5,1]$ via the logistic transform (§2.1).
- **Reporting-year shared shock.** A bad reporting/calendar year (e.g. the recognition of
  2017 catastrophe development) hits all syndicates at once, inducing within-year
  cross-sectional correlation. The effect is indexed by the year in which development is
  *recognised* (reporting year $t$), not the underwriting year, since that is when the shared
  shock lands. We model it as a year random effect. With only ~11 years, frequentist
  cluster-robust standard errors are unreliable (too few clusters); **Bayesian partial
  pooling degrades gracefully** and is the appropriate choice.

**Priors** (weakly informative): $\theta\sim\mathcal N(0,1.5)$ (implying $k$ spread over
$[0.5,1]$); $\gamma\sim\text{HalfNormal}(1)$; $b_0\sim\mathcal N(\log 0.05,1)$;
$\tau_s\sim\text{HalfNormal}(0.5)$; $\nu\sim\text{Gamma}(2,0.1)$ (prior mean 20, allowing but
not forcing heavy tails). Year effects use a non-centred parameterisation for sampling
efficiency.

### 2.4 Validity of the pooling exponent under heavy tails

The single-tail posterior for $\nu$ (no RITC regime) concentrates near 2.1 with non-trivial
mass on $\nu<2$, the **infinite-variance** regime, where the standard deviation does not exist
and the literal "$\mathrm{SD}\propto R^{k}$" statement is undefined. Once RITC is split into its
own tail regime (§2.7) the clean tail is credibly finite-variance —
$\nu_{\text{clean}}=2.40$ [1.92, 2.95] with only $P(\nu_{\text{clean}}<2)=0.05$ — while the
infinite-variance mass is concentrated in the RITC regime ($\nu_{\text{RITC}}=1.54$,
$P(\nu_{\text{RITC}}<2)=0.95$). Either way we interpret $k$ as an **aggregation-scaling
exponent** rather than a standard-deviation exponent, with the finite-variance $\sqrt N$ / CLT
argument as a special case.

Let $\alpha=\min(\nu,2)$ be the tail index. By the generalized central limit theorem, the
**scale** of a sum of $n$ i.i.d. contributions in the domain of attraction of an
$\alpha$-stable law grows as $n^{1/\alpha}$; the per-unit (ratio) scale therefore grows as
$n^{1/\alpha-1}$, and under full dependence as $n^0$. Hence

$$
k = \tfrac1\alpha \ \text{(independence)} \ \longrightarrow\ 1 \ \text{(comonotonic)},
$$

which reduces to $k\in[0.5,1]$ exactly when $\alpha=2$ (the finite-variance case). Two points
make this robust rather than a caveat: (i) the Student-$t$ **scale parameter** $\sigma$ is
well-defined for every $\nu$, so the fitted scale law holds throughout — only the verbal
"standard deviation" gloss needs care when $\nu<2$; and (ii) the estimate $\hat k\approx0.61$
sits comfortably interior under either regime (even at $\nu=1.9$ the independence floor
$1/\alpha\approx0.53$ lies below it), so the conclusion is not pinned to a boundary that shifts
with the tail index.

*Empirical check.* Tail-index estimates on the model innovations agree the tail is heavy: the
clean-regime Bayesian $\nu_{\text{clean}}=2.40$ [1.92, 2.95] and a whole-sample Student-$t$ MLE
df $\approx2.1$, while the RITC regime and a Hill estimator on the extreme tail (top 8–20%) sit
lower ($\nu_{\text{RITC}}\approx1.5$, Hill $\alpha\approx1.6$–$1.8$) — i.e. the *extreme* tail is
in the infinite-variance regime, and much of it is RITC (§2.7). Mapping to the aggregation
exponent, the independence value $1/\alpha$ is 0.50 (at $\alpha=2$) to $\approx0.59$ (at
$\alpha=1.7$); the fitted $k\approx0.61$ exceeds it. Two conclusions:
the size-scaling result is invariant to whether variance is finite (the $\sqrt N$ reading) or
infinite (the $\alpha$-stable reading), since $k$ is interior under both; and $k>1/\alpha$
means the portfolios diversify *less* than independent aggregation predicts even after heavy
tails are accounted for — direct evidence of a shared/systematic component, consistent with
the headline interpretation.

### 2.5 Estimation

Fitted by NUTS (PyMC), 4 chains × 1000 post-warmup draws. Convergence was clean throughout
(all $\hat R = 1.00$, ESS in the thousands, zero divergences). Inference and effect sizes
are read directly from the posterior; model comparison uses leave-one-out cross-validation
(PSIS-LOO). This single framework delivers robustness, the shared-shock structure, and
significance-plus-effect-size in one object.

### 2.6 Data

The corpus is **907 syndicate-year observations** across reporting years 2014–2024, built from
the current dual-LLM extraction (1,065 filings; see [data-provenance.md](docs/data-provenance.md)
and the data-audit appendix). An earlier design restricted dispersion calibration to a "dense"
subset (2014–2019), holding out 2020–2024. Having moved to the holistic pooling model, **we drop
the holdout and use all available years**, giving 11 year clusters and materially improving
identification of the shared-shock variance $\tau_s$. Of the 907 corpus observations, **790**
have complete severity, reserves and HHI; the working sample is therefore $n=790$ across 11
years. Because the $n_{\text{eff}}=1/H$ form is well-defined at $H=1$ (§2.2), **single-line
reporters are retained** — 21 such observations, which fit without issue, so no
concentration-based exclusion is applied.

### 2.7 RITC as a tail-shape regime

External **reinsurance-to-close (RITC)** — a syndicate assuming another syndicate's run-off
account — injects a lumpy, non-recurring step change into prior-year development that is *not*
a function of portfolio composition $(R,H)$. The dual-LLM extraction flags it per
syndicate-year (`ritc_scan.json`: `ritc_occurred` with strong/weak confidence); 140 of the
$n=790$ sample-years are RITC-affected (68 strong, 72 weak).

We asked whether RITC breaks the operator's load-bearing assumption — that the standardised
severity $z_{it}=S_{it}/\sigma_{it}$ is a **scale family with one invariant shape**. It does,
in the tail only:

- **Scale is invariant.** After the operator's $\sigma(R,H)$, RITC and clean years have the
  same body spread — bootstrap IQR$(z)$ and MAD$(z)$ ratios $\approx0.95/0.90$ ($p\approx0.5$–0.8);
  Fligner–Killeen $p=0.48$. So RITC is **not** an $(R,H)$ mis-scaling.
- **The tail shape is not.** Fitting the Student-$t$ degrees of freedom to $z$ *separately* by
  regime, the RITC tail is roughly twice as heavy: $\nu=2.43$ (clean) vs $1.50$ (RITC) at
  $n=790$ (contrast $p=0.07$), and $2.17$ vs $1.08$ in the stricter rescaling population
  ($p=0.035$). All six tail estimators (regime $t$-$\nu$, GPD $\xi$, Hill, $q_{95}/q_{99}$
  ratios) agree directionally. Robust *central* shape statistics (Bowley, Moors, tail-skew)
  and the body-dominated KS test see nothing ($p=0.95$) — because they are built from
  quantiles at or inside the 10th–90th percentiles and are **blind to the tail**. The tail is
  part of the shape, so shape-invariance is genuinely violated there.

Because RITC is a syndicate-specific injection rather than a composition property, we do not
exclude it (that would discard 140 observations and cannot answer "what does RITC do to the
tail"). Instead we **model it as a one-parameter tail regime** — the scale is shared, only
$\nu$ shifts:

$$
S_{it}\sim\text{Student-}t\!\left(\nu_{it},\,0,\,\sigma_{it}\right),\qquad
\nu_{it}=\begin{cases}\nu_{\text{clean}} & \text{clean}\\[2pt]
\nu_{\text{clean}}\,e^{-\lambda_{\text{RITC}}} & \text{RITC}\end{cases}
$$

with $\lambda_{\text{RITC}}\sim\mathcal N(0,0.7)$ (so $\lambda>0\Leftrightarrow$ RITC heavier).
A **falsification term** $\beta_{\text{RITC}}\cdot\mathbf 1[\text{RITC}]$ is added to $\log\sigma$
to test the "tail-only" claim: if RITC also moved the scale, $\beta_{\text{RITC}}$ would be
non-zero.

**Fit** ($n=790$, 0 divergences, $\hat R=1.00$): $\nu_{\text{clean}}=2.40$ [1.92, 2.95],
$\nu_{\text{RITC}}=1.54$ [1.06, 2.08], $\lambda_{\text{RITC}}=+0.45$ [0.08, 0.86] with
$P(\nu_{\text{RITC}}<\nu_{\text{clean}})=0.99$ — decisive evidence for the heavier RITC tail.
The falsification term $\beta_{\text{RITC}}=-0.15$ [$-0.41$, $+0.10$] straddles zero, confirming
RITC leaves the scale alone (tail-only holds). Crucially the composition operator is
**unchanged**: $k=0.611$ [0.53, 0.69], $\gamma=0.264$, $\sigma_{\text{undiv}}=0.022$ — identical
to the no-regime fit, so RITC is not confounding the pooling/concentration/floor structure.

The consequence for the operator and the headline VaRs is in §6.1.

**Four-treatment robustness.** Running the transfer under (T1) preferred de-RITC, (T2) pure
rescale with RITC carried, (T3) clean-only exclusion, and (T4) strong-only exclusion, the
**structural parameters are invariant** ($k$ 0.598–0.611, $\gamma$ 0.26–0.31, floor 0.022–0.025)
— RITC does not create the pooling result. And the **de-RITC Vignette-1 VaR$_{99.5}$ (0.427)
closely matches the clean-only exclusion (0.410)**, both far below pure-rescale (0.676): the
preferred operator *approximates* excluding RITC for the far tail while retaining all 790
observations to fit the pooling law. (`ritc_treatments.py`.)

---

## 3. Results

**Headline posterior (full sample, $n=790$, 11 reporting years; RITC tail regime §2.7):**

| Parameter | Meaning | Mean | 95% HDI |
|---|---|---|---|
| $k$ | diversifiable-term pooling exponent | **0.61** | [0.53, 0.69] |
| $\gamma$ | concentration ($n_{\text{eff}}$ effective-size) | 0.26 | [0.00, 0.65] |
| $\sigma_{\text{undiv}}$ | undiversifiable floor | **0.022** | [0.005, 0.036] |
| $\sigma_{\text{div}}$ | diversifiable SD at reference | 0.059 | [0.046, 0.073] |
| $\nu_{\text{clean}}$ | Student-$t$ df, clean regime | **2.40** | [1.92, 2.95] |
| $\nu_{\text{RITC}}$ | Student-$t$ df, RITC regime | **1.54** | [1.06, 2.08] |
| $\lambda_{\text{RITC}}$ | log tail-weight shift (RITC) | 0.45 | [0.08, 0.86] |
| $\beta_{\text{RITC}}$ | RITC scale falsification (≈0) | −0.15 | [−0.41, 0.10] |
| $\tau_s$ | year shared-shock SD (log-scale) | 0.090 | [0.00, 0.20] |

Posterior probabilities: $P(k<1)=1.00$ (diversification is certain — the portfolio is not
comonotonic); $P(\gamma>0.05)=0.89$; $P(\sigma_{\text{undiv}}>0.005)=0.98$ (a positive
undiversifiable floor is well-supported); $P(\nu_{\text{RITC}}<\nu_{\text{clean}})=0.99$ (the
RITC tail is credibly heavier). Diagnostics clean (0 divergences, $\hat R=1.00$).

**Interpretation of $k$.** $k\approx0.61$ governs the *diversifiable* component of dispersion,
which decays as (effective size)$^{k-1}$ — meaningfully sub-linear (real diversification) but
above the $R^{0.5}$ independence benchmark, i.e. a substantial *shared* component remains.
Diversification does not run to zero, though: it decays toward the undiversifiable floor
$\sigma_{\text{undiv}}$.

**Effect sizes (in standard-deviation terms):**

- **Size dominates, but the floor caps it.** A $\pounds100$m portfolio carries **≈2.7×** the
  dispersion of a $\pounds2{,}000$m portfolio of equal composition — less than the 3.2× a
  no-floor power law implied, because the floor compresses the gap at large sizes.
- **Concentration is second-order and weakly identified.** Moving from diversified ($H=0.1$)
  to concentrated ($H=0.9$) at fixed size raises dispersion by **≈1.2×** — directionally
  plausible but modest, and $\gamma$'s posterior is wide ($P(\gamma>0.05)=0.89$, HDI reaching to
  $\approx0.65$). It should be read as a **cautious observable business-mix adjustment**, not a
  precisely identified reserve-mix effect (see §3.3 — the concentration input is *premium* HHI,
  a proxy for the unobserved reserve HHI).
- **Undiversifiable floor.** A very large, diversified book's dispersion bottoms out at
  $\sigma_{\text{undiv}}\approx0.022$ (≈2.2% of reserves): $\sigma\approx0.028$ at $\pounds10$bn,
  $\approx0.023$ at $\pounds100$bn — it does not decay to zero.

**Heavy tails confirmed.** The clean-regime $\nu_{\text{clean}}$ concentrates near **2.4**
(prior mean 20) and the RITC regime near **1.5**, so the data pull decisively toward heavy
tails: the robust likelihood is doing real work, and a Gaussian model would have been
outlier-dominated exactly as the LS joint fit was.

### 3.1 Goodness of fit and shape adequacy

Standardised residuals $z_{it}=(S_{it}-\hat\mu)/\hat\sigma_{it}$ should be trend-free and
$t$-distributed if the pooling law and effective-size shape are correct:

- **Size scale shape correct.** Mean $|z|$ shows no trend against $\log R$ (Spearman
  $r=+0.02$, $p=0.70$): the exponent $(k-1)$ absorbs the size heteroscedasticity across the
  full range.
- **Concentration scale shape adequate.** Mean $|z|$ shows no trend against $H$
  ($r=-0.02$, $p=0.65$): the $n_{\text{eff}}=1/H$ effective-size form leaves no residual
  concentration heteroscedasticity, and the single-line ($H=1$) observation fits within the
  bulk.
- **Tails calibrated.** Every observed $|S|$ quantile from the median to the **99th** lies
  inside the 95% posterior-predictive band (observed $q_{99}=0.649$ vs predicted
  $[0.37,1.02]$); the residual QQ-plot tracks Student-$t(2.2)$ to $\pm3$–$4\sigma$.

Diagnostics are reproduced in Figure X (six panels: posterior-predictive density; tail
calibration; residuals vs size; residuals vs HHI; scale check; $t$ QQ-plot).

### 3.2 The mean (location) effect

Although we model dispersion, we also examined a **location** channel $\mu = m_0 + m_1 H$.
On the earlier $n=492$ sample this HHI–mean slope was clearly negative ($m_1=-0.061$
[−0.105, −0.018]); **on the full $n=790$ sample it weakens to non-significance:**

| Quantity | $n=790$ estimate | |
|---|---|---|
| $m_1$ (HHI slope on mean $S$) | **−0.014 [−0.081, +0.052]** (SE 0.034) | CI spans 0 |
| $m_1$ with $\ln R$ control | −0.005 | negligible |
| HHI direction test $\hat\beta$ | −0.043, $p=0.47$ | not significant |

So the earlier "concentrated portfolios run off less adversely" signal **does not survive the
larger sample** — the point effect over $H:0.1\to0.9$ is ≈ −0.19 dispersion-scale units but
indistinguishable from zero. We therefore no longer report a concentration–mean effect;
$\mu=0$ is retained for the volatility model as before.

### 3.3 Premium-HHI is a proxy, and the results do not depend on it being exact

The ideal concentration measure is reserve-weighted HHI $H^{\text{res}}=\sum_\ell(w^{\text{res}}_\ell)^2$,
but public syndicate accounts do not consistently disclose line-level opening reserves, so we
use **premium-weighted HHI** $H^{\text{prem}}$ as a transparent, auditable proxy. Rather than
invent unobserved reserve-duration multipliers, we stress the proxy directly:

- **Rank-correlation stress (A3).** Perturbing HHI (Gaussian-copula rank noise onto the
  *empirical* HHI marginal) down to Spearman correlations of 0.9, 0.7, 0.5, 0.3 with the observed
  premium HHI, and refitting ($B=250$ each): $k$ (0.62), the floor (0.019), $\nu_{\text{clean}}$
  (2.29) and the vignette VaRs (V1 VaR$_{99.5}\approx0.44$, V2 change $\approx0.030$) are **all
  stable**; only $\gamma$ stays wide and weakly identified. The transfer result does not rely on
  premium HHI being a perfect reserve-HHI measure.
- **Adversarial concentration (A4).** Forcing reserve concentration progressively *above*
  premium concentration, $w^{(\alpha)}=(1-\alpha)w^{\text{prem}}+\alpha\,e_{\max}$ for
  $\alpha\in\{0.25,0.5,0.75\}$: size, floor and heavy-tail conclusions are unchanged; only
  $\gamma$ and the concentration-driven VaR move — as they must, because the concentration
  variable itself has been deliberately distorted.

The reading is: concentration is a **cautious observable-mix adjustment**, directionally
plausible and auditable but second-order and weakly identified — not a precisely identified
reserve-mix effect. (`proxy_stress.py`, `proxy_stress_results.json`.)

---

## 4. Model comparison: what we tested and discarded

All comparisons use PSIS-LOO on the full sample; $\Delta\text{elpd}$ is relative to the best
model and $\Delta\text{SE}$ is the standard error of the difference.

### 4.1 Concentration shape — no shape preferred; HHI barely earns its place

Comparing three dispersion shapes (effective-size $(1-H)^{\gamma}$; a separate power
$H^{\delta}$; and size-only):

| Model | $\Delta$elpd | $\Delta$SE |
|---|---|---|
| Effective-size $(1-H)^{\gamma}$ | 0.00 | — |
| Separate power $H^{\delta}$ | 0.28 | 0.91 |
| **Size-only (no HHI)** | 0.34 | 1.28 |

(This shape screen was run with the $(1-H)^{\gamma}$ variant; the conclusion is form-agnostic
and unchanged under the adopted $n_{\text{eff}}=1/H$ form, which was chosen for its behaviour
at the $H=1$ boundary, §2.2.) All three are statistically indistinguishable. **Discarded:**
any claim that the HHI *shape* matters, and — more strongly — the notion that concentration
is a first-order dispersion driver. Adding HHI to the *dispersion* does not improve out-of-sample prediction over
size-only; $k\approx0.70$ regardless. Concentration's dispersion effect is real in-sample
($P(\gamma>0)=0.98$) but predictively marginal.

### 4.2 The undiversifiable floor (asymptote) — retained, and positive

We extend the scale to
$\sigma(R,H)=\sqrt{\sigma_{\text{undiv}}^2 + \sigma_{\text{div}}^2\,[(R/R_{\text{ref}})(1/H)^{\gamma}]^{2(k-1)}}$
(times the reporting-year shock), so that $\sigma\to\sigma_{\text{undiv}}$ as size grows.
$\sigma_{\text{undiv}}$ is the **undiversifiable floor** — the dispersion an arbitrarily large,
diversified book cannot shed.

*Prior matters here.* A boundary parameter like a variance floor is sensitive to its prior.
A HalfNormal$(0.1)$ prior on $\sigma_{\text{undiv}}$ piles probability mass at zero and, combined
with LOO's insensitivity to a small weakly-identified floor, will suggest "zero" spuriously.
We therefore place a **uniform (Beta$(1,1)$) prior on the undiversifiable variance *share*** at
the reference, letting the data — not the prior — decide the floor.

Under that honest prior (full sample, $n=790$):

- $\sigma_{\text{undiv}} = 0.022$ [0.006, 0.036] — the **95% lower bound clears zero**;
  $P(\sigma_{\text{undiv}} > 0.005) = 0.99$.
- Undiversifiable variance share $f = 0.20$ [0.01, 0.48], $P(f>0.05) = 0.89$.
- For comparison, the HalfNormal$(0.1)$ prior gives a similar *point* estimate (0.021) but a
  lower bound grazing zero — the "set to zero" reading was a prior artefact.

**Retained.** The data support a **positive undiversifiable floor** of $\approx 0.022$ (about
2.2% of reserves), consistent with the actuarial expectation that some reserve risk is never
diversifiable. Including the floor steepens the diversifiable exponent to $k\approx0.61$ (from
$0.71$ without a floor): with the floor catching the large-size behaviour, the diversifiable
term is free to decay faster. **Practical consequence:** a very large diversified book's
dispersion bottoms out at $\sigma_{\text{undiv}}\approx0.022$ rather than decaying to zero — and
a pure power-law (no-floor) extrapolation would understate it (e.g. it implies $\sigma\approx0.020$
at $R=\pounds10$bn, *below* the floor). This corrects the earlier draft, which set the floor to
zero on the strength of a zero-piling prior and a null LOO.

#### 4.2.1 Floor vs no-floor: a predictive tie, resolved by extrapolation safety

We compared the two candidate scale laws head-to-head on the full sample ($n=790$). **Both
freely estimate the pooling exponent $k$** (and $\gamma$, $\sigma_{\text{div}}$, $\nu$,
$\tau_s$); they are identical in every respect **except that Model B adds one parameter, the
undiversifiable floor $\sigma_{\text{undiv}}$**:

- **Model A (no floor):** $\sigma = \sigma_{\text{div}}\big[(R/R_{\text{ref}})(1/H)^{\gamma}\big]^{k-1}$ — a single power term with a free exponent $k$.
- **Model B (floor + power, $\sqrt{\cdot}$ form):** $\sigma = \sqrt{\sigma_{\text{undiv}}^2 + \sigma_{\text{div}}^2\big[(R/R_{\text{ref}})(1/H)^{\gamma}\big]^{2(k-1)}}$ — the same free exponent, plus the floor.

| Model | elpd$_{\text{LOO}}$ | $\Delta$elpd | $\Delta$SE | $p_{\text{LOO}}$ |
|---|---|---|---|---|
| A — no floor | 451.05 | 0.00 | — | 4.74 |
| B — floor + power | 450.98 | 0.08 | 1.00 | 4.98 |

WAIC agrees to two decimals ($\Delta=0.08$, $\Delta$SE $=1.00$). **The models are a predictive
dead heat:** the difference (0.08) is two orders of magnitude below its own standard error
(1.0), and Model A is nominally ahead only by a whisker and by ~0.24 fewer effective
parameters (a faint parsimony edge).

The tie is not a failure to find signal — it is *structural*. The two laws are nearly
identical everywhere there is data (≈£1m–£6bn of reserves) and diverge **only in
extrapolation** to very large books, where Model A sends dispersion to zero and Model B to the
floor $\sigma_{\text{undiv}}\approx0.022$. Because the sample contains no books beyond ~£6bn,
LOO — which scores fit *within* the observed data — is blind to precisely the region where the
models differ. Predictive fit therefore *cannot* adjudicate this choice.

**We select Model B.** The decision rests not on fit but on the two things fit is blind to:
(i) the floor parameter is **credibly positive** under an honest (uniform variance-share) prior
($\sigma_{\text{undiv}}=0.022$ [0.006, 0.036], $P(\sigma_{\text{undiv}}>0.005)=0.98$); and
(ii) the model's purpose is *extrapolative* — transferring scenarios onto portfolios that
include very large books — where Model A's implicit claim that a big-enough syndicate carries
*no* undiversifiable reserve risk is untenable, both actuarially and against the reviewer's
prior. We therefore accept **one extra parameter** (the floor) — giving up Model A's marginal
parsimony — in exchange for the **extrapolation safety** of an explicit undiversifiable floor.
The floor earns its place on parameter evidence and out-of-range safety, not on in-sample
predictive gain — which is the honest basis to state in the paper.

#### 4.2.2 Blended exponent vs independent-plus-systematic pooling

§2.1 frames diversification between two limits: **independent ($\sqrt N$) pooling** (exponent
$k=\tfrac12$, dispersion decays fastest) and **comonotonic** risk ($k=1$, undiversifiable). A
partially-pooled portfolio can be modelled two ways, and — holding the undiversifiable floor
in both — we tested which the data prefer:

- **Model 1 — single blended exponent:** the diversifiable part pools at a *freely estimated*
  effective exponent, $\sigma^2 = \sigma_{\text{undiv}}^2 + \sigma_{\text{div}}^2\,E^{2(k-1)}$,
  $k\in[0.5,1]$. One number captures where the portfolio sits between independence and
  comonotonicity.
- **Model 2 — independent + systematic:** the diversifiable part is *fixed* at the textbook
  $\sqrt N$/CLT rate ($k=\tfrac12$), $\sigma^2 = \sigma_{\text{undiv}}^2 + \sigma_{\text{div}}^2\,E^{-1}$;
  all non-independent behaviour is carried by the systematic floor. ($E=R\,(1/H)^{\gamma}$ in both.)

| Model | elpd$_{\text{LOO}}$ | $\Delta$elpd | $\Delta$SE | LOO weight | $\sigma_{\text{undiv}}$ |
|---|---|---|---|---|---|
| **M1 — blended exponent ($k$ free)** | 604.14 | 0.00 | — | **0.94** | 0.022 |
| M2 — independent $\sqrt N$ + floor ($k=0.5$) | 602.42 | 1.72 | 2.00 | 0.06 | 0.033 |

*(Refitted on $n=790$; single-$t$ baseline, the RITC tail regime of §2.7 is orthogonal and
applies on top of the winner.)* Unlike the floor-vs-no-floor comparison (§4.2.1), the two models
differ **within the observed data**, because the exponent shapes the whole dispersion curve —
so LOO *can* discriminate, and it favours the blended exponent (stacking weight 0.94 vs 0.06;
$\Delta$elpd 1.72, though $\Delta$SE $=2.00$ keeps it short of a knockout on the strict
$\Delta$SE rule).

**The supporting evidence is the exponent posterior:** in Model 1, $k=0.613$ [0.531, 0.688]
with $P(k>0.5)=1.00$ — the posterior places the diversifiable pooling exponent **above the
independence value $\tfrac12$**, indicating systematic co-movement beyond pure independence.
Model 2 cannot express this (its exponent is pinned at $\tfrac12$), so it absorbs the residual
dependence into the floor — inflating $\sigma_{\text{undiv}}$ from 0.022 to 0.033. Two
qualifications keep this honest: (i) the **predictive** gap is modest — the blended model wins
on LOO but only by $\Delta$elpd $1.72$ against $\Delta$SE $2.00$ (stacking weight 0.94 vs 0.06),
i.e. **within one standard error**, so a floor-plus-$\sqrt N$ model is close in out-of-sample
performance and we do not claim independence is *decisively rejected*; and (ii) the evidence for
$k>\tfrac12$ is a posterior statement, not a knockout predictive one. **We therefore adopt
Model 1 as the preferred (not uniquely mandated) form:** the free effective-dependence exponent
is supported by the parameter posterior and marginally preferred out-of-sample, and it avoids
mislabelling dependence as an inflated floor.

### 4.3 The mean — the strongest effect, retained (or reported separately)

| Model | $\Delta$elpd | $\Delta$SE |
|---|---|---|
| **$\mu=m_0+m_1 H$** | 0.00 | — |
| $\mu=0$ (no floor) | 19.2 | 6.8 |
| $\mu=0$ (with floor) | 19.5 | 6.8 |

Including the concentration-dependent mean improves elpd by **~19 (≈2.8 SE)** — the single
largest predictive gain in the model, far exceeding either the concentration-on-dispersion
term or the floor.

**Modelling decision — $\mu=0$ fixed, on principle.** The model's purpose is *scenario
transfer across portfolio characteristics*. The mean development level is a syndicate-specific
reserving bias (management conservatism/optimism), **not a transferable portfolio
characteristic** — carrying a donor syndicate's reserving bias onto a target portfolio would
be a category error. We therefore fix $\mu=0$ by design and treat mean development as out of
scope. The concentration-lowers-mean relationship ($m_1=-0.059$, 99.8% credibly negative,
≈4.9% of reserves across the HHI range) is reported as a distinct empirical finding, not
folded into the transfer model.

**This is not a confound risk.** One might worry that fixing $\mu=0$ forces the negative mean
of concentrated books to be absorbed as *scale*, mechanically inflating the concentration
dispersion effect $\gamma$. We checked directly (on the adopted $n_{\text{eff}}=1/H$ form,
$n=790$): re-estimating $\gamma$ with the mean modelled ($\mu=m_0+m_1H$) leaves it
statistically unchanged — $\gamma=0.54$ [0.03, 1.35] with the mean vs $0.44$ [0.02, 1.18] at
$\mu=0$ (fully overlapping; concentration SD multiplier 1.45× vs 1.33×), and $k$ is unchanged
(0.70 vs 0.71). If anything $\gamma$ is *smaller* under $\mu=0$ — the opposite of the feared
inflation — so the $\mu=0$ headline is, if biased at all, conservative on concentration. The
heavy-tailed symmetric scale absorbs essentially none of the location shift, so the headline
$\gamma$ is robust to the mean specification, not an artefact of it.

### 4.4 Line-of-business composition — dominant line and long-tail share (both not significant)

Two further compositional predictors were tested as additions to the *dispersion* scale
(the volatility model, $\mu=0$), alongside size and the year shared shock:

1. **Dominant line of business** (categorical): the LoB carrying the largest portfolio
   weight in each syndicate-year, entered as a hierarchical (partial-pooling) effect
   $\delta_{L}\sim\mathcal N(0,\tau_L)$ on $\log\sigma$. Levels grouped as {Aggregate,
   Property, Casualty, Aviation, Other}.
2. **Long-tail proportion** (continuous): the summed weight of long-tail lines
   (Casualty, Motor, Reinsurance–Casualty, Professional Lines), entered as a linear term
   $\beta_{\text{LT}}$ on $\log\sigma$.

Refitted on $n=790$ (single-$t$ floor baseline; PSIS-LOO):

| Model | elpd$_{\text{LOO}}$ | $\Delta$elpd vs base | $\Delta$SE |
|---|---|---|---|
| **base (size + year, $\mu=0$)** | 604.14 | 0.00 | — |
| + dominant LoB | 604.81 | +0.67 | 1.71 |
| + long-tail proportion | 603.16 | −0.98 | 1.63 |

Neither improves out-of-sample fit (the dominant-LoB gain is a fraction of its SE; long-tail
share is *worse* than base). The qualitative null is unchanged from the earlier $n=492$ fit.

- **Dominant LoB:** the between-LoB dispersion SD is small and pressed toward zero
  ($\tau_L=0.169$ [0.011, 0.497]); *every* category's dispersion multiplier includes 1.0
  (Aggregate 0.92 [0.71, 1.14], Property 0.98 [0.76, 1.23], Casualty 1.09 [0.86, 1.43],
  Aviation 1.15 [0.90, 1.67], Other 0.95 [0.67, 1.21]). No line credibly deviates.
- **Long-tail proportion:** $\beta_{\text{LT}}=+0.036$ [−0.30, +0.37], $P(\beta_{\text{LT}}>0)=0.58$;
  the implied dispersion multiplier across the full observed range is 1.04× — squarely
  including one.

**Discarded:** both. Neither the identity of the dominant line nor the long-tail share is a
credible driver of development dispersion once size and year effects are accounted for.

*Caveats.* The dominant-LoB test is coarse because 61% of syndicate-years have their largest
weight in an unclassified *Aggregate* bucket, so much compositional detail is unresolved; and
the long-tail proportion is summed over resolved lines only, understating true long-tail
content where the Aggregate share is large. These null results therefore concern *resolved*
composition. (Whether these variables affect the *mean* development, as HHI does, was not
tested — the model is deliberately a $\mu=0$ volatility model.)

### 4.5 Summary of rejected alternatives

| Rejected | Reason (after testing) |
|---|---|
| Two-stage sequential LS pipeline | Ordering bias; circular if both stages pre-adjusted; outlier-driven |
| "Size fitted on mix-adjusted residuals" (as previously written) | Code fits raw $s^2$; slope halves under true mix-adjustment |
| Two-floor structure ($A_R$, $A_H$) | Only $A_R$ is an absolute floor; conceptually replaced by one law/one floor |
| "Joint fit fails due to collinearity" | Disproved: VIF 1.11, cond ≈ 600; failure was un-winsorised outliers |
| Gaussian / least-squares estimation | Data are heavy-tailed ($\nu\approx2$); non-robust |
| Holdout split (2020–2024) | Dropped under holistic model; all 11 years now used |
| ~~Nonzero variance floor / asymptote~~ (retracted §4.2) | Earlier "zero" was a zero-piling prior artefact; honest uniform-share prior gives a positive floor $\sigma_{\text{undiv}}\approx0.022$ — **retained** |
| HHI as a first-order dispersion driver | LOO indifferent vs size-only; second-order at best |
| Dominant line of business (categorical) on dispersion | LOO no improvement; every category multiplier includes 1.0; $\tau_L\to0$ |
| Long-tail proportion on dispersion | LOO no improvement; $\beta_{\text{LT}}$ CI straddles zero |
| Excluding RITC syndicate-years | Discards 140 obs and cannot transfer RITC; replaced by a one-parameter **tail regime** (§2.7) — RITC fattens the tail only ($\nu_{\text{RITC}}\approx1.5$ vs $\nu_{\text{clean}}\approx2.4$, $P=0.99$), scale invariant ($\beta_{\text{RITC}}\approx0$), operator $k/\gamma/\text{floor}$ unchanged — **retained as a regime** |

---

## 5. Recommended final specification

$$
S_{it}\sim\text{Student-}t\!\left(\nu_{it},\,0,\,\sigma_{it}\right),\qquad
\sigma_{it}=\sqrt{\sigma_{\text{undiv}}^2+\sigma_{\text{div}}^2\,\big[(R_{it}/R_{\text{ref}})(1/H_{it})^{\gamma}\big]^{2(k-1)}}\;\,e^{s_t},\qquad
s_t\sim\mathcal N(0,\tau_s),
$$

with **$\mu=0$ fixed**, $k\in[0.5,1]$, $\gamma\ge0$, a **positive undiversifiable floor**
$\sigma_{\text{undiv}}\approx0.022$ (uniform variance-share prior), the effective-line
$n_{\text{eff}}=1/H$ concentration form (well-defined at $H=1$), heavy-tailed errors, and an
**RITC tail regime** $\nu_{it}=\nu_{\text{clean}}$ (clean) or $\nu_{\text{clean}}e^{-\lambda_{\text{RITC}}}$
(RITC) — fitted by Bayesian NUTS on all 11 reporting years ($n=790$). Headline: a diversifiable
**pooling law with $k\approx0.61$** (certain diversification, real shared component) over an
**undiversifiable floor of $\approx2.2\%$ of reserves**, heavy tails
($\nu_{\text{clean}}\approx2.4$), and concentration as a weak, second-order and weakly-identified
observable-mix adjustment (premium-HHI proxy; robust to proxy error, §3.3).
The transfer operator is the fitted law applied (§6), generalised to a **shape-aware**
quantile transform (§6.1) that de-RITCs donor tails ($\nu_{\text{RITC}}\approx1.5\to\nu_{\text{clean}}$);
this leaves the size/concentration/floor transfer untouched but lightens the transferred tail
VaR by ~35%. The concentration-lowers-mean-development result is the strongest single signal
in the data and is reported as a **separate empirical finding**, deliberately kept outside the
volatility model.

---

## 6. The transfer operator is the fitted model

The scenario-transfer operator **is** the dispersion model, applied. To transfer a donor
severity $S_{\text{source}}$ observed at $(R_s,H_s)$ to a target profile $(R_t,H_t)$, we
rescale by the ratio of model dispersions:

$$
S_{\text{adj}} = S_{\text{source}}\cdot\frac{\sigma(R_t,H_t)}{\sigma(R_s,H_s)},\qquad
\sigma(R,H)=\sqrt{\sigma_{\text{undiv}}^2+\sigma_{\text{div}}^2\big[(R/R_{\text{ref}})(1/H)^{\gamma}\big]^{2(k-1)}}.
$$

The size exponent $k$, the concentration exponent $\gamma$, **and** the undiversifiable floor
$\sigma_{\text{undiv}}$ all enter: the operator uses the whole fitted law and discards nothing.
(When $\sigma_{\text{undiv}}=0$ this collapses to the pure power ratio
$(R_t/R_s)^{k-1}(H_s/H_t)^{\gamma(k-1)}$.) The idiosyncratic reporting-year shock $s_t$
and the (fixed-zero) mean are *not* transferred — neither is a portfolio characteristic
(§4.3). Single-line portfolios raise no difficulty: $\sigma(R,1)$ is finite under the
$n_{\text{eff}}=1/H$ form (§2.2), so $H=1$ donors and targets transfer directly.

*Why not a projection-plus-size hybrid?* An alternative operator would reproject the donor's
per-line severities onto the target weights, $S_{\text{mix}}=\sum_l w^q_l s^{\text{donor}}_l$,
and then apply only a size multiplier $[R_t/R_s]^{k-1}$. This is rejected: it estimates a
concentration effect $\gamma$ and then ignores it, substituting a structural
concentration→dispersion channel (the projected variance $w_q'\Sigma w_q=\sigma^2[\rho+(1-\rho)H_q]$
rises in target HHI) for the one the model actually fit. Consistency requires that the
operator be the model. The "double-counting" caution — that one must not apply $\gamma$ *on
top of* a projection — is a reason not to build the hybrid, not a reason to strip $\gamma$
from the model-based operator: with no projection there is nothing to double-count. This
matches the operator as specified in §9.

### 6.1 Shape-aware transfer across RITC status

The pure rescale above is valid only when source and target share the standardised shape.
§2.7 shows they do not when RITC status differs: an RITC donor carries a heavier tail
($\nu_{\text{RITC}}\approx1.5$ vs $\nu_{\text{clean}}\approx2.4$). Transferring it by scale
alone would import RITC's tail into a composition it does not belong to. We therefore generalise
the operator to also transform the **shape**, by rank-matching (the probability-integral
transform) through the two $t$-laws:

$$
S_{\text{adj}} = \sigma(R_t,H_t)\cdot
F^{-1}_{\nu_t}\!\Big(F_{\nu_s}\big(S_{\text{source}}/\sigma(R_s,H_s)\big)\Big),
$$

where $F_\nu$ is the standard Student-$t$ CDF. This is monotone, rank- and median-preserving
(so $\mu=0$ survives), and **nests the pure rescale exactly**: when $\nu_s=\nu_t$,
$F^{-1}_{\nu}(F_{\nu}(z))=z$ and it reduces to §6. Nothing about size/concentration transfer
changes; the shape step only fires when RITC status differs. The default for an RITC-flagged
donor transferred to a clean-composition target sets $\nu_s=\nu_{\text{RITC}}$,
$\nu_t=\nu_{\text{clean}}$, which **thins** the donor's heavy tail — "de-RITC-ing" it to what an
equivalent clean-composition syndicate would show. Setting $\nu_t=\nu_{\text{RITC}}$ instead
gives a free stress lever: inject RITC tail risk into any composition.

**Headline impact.** De-RITC-ing the donor pool (140 of 789 donors) materially lightens the
transferred tail — RITC contamination was inflating the vignette tail VaRs by about a third:

| Vignette VaR$_{99.5\%}$ | pure rescale (RITC in) | shape-aware (de-RITC) |
|---|---|---|
| V1 adjusted | 0.670 | **0.427** |
| V2 new profile | 0.642 | **0.407** |

The fitted EVT tail shape lightens correspondingly (GPD $\hat\xi$ $0.50\to0.36$), and the
empirical, frequentist-POT and Bayesian-POT VaRs remain mutually consistent on the de-RITC pool
(V1: 0.427 / 0.483 / 0.491; V2: 0.407 / 0.460 / 0.468; each point inside the others' 95%
intervals). This is the sense in which the RITC treatment *moves the headline*: the operator
(size/concentration/floor) is untouched, but the tail VaR it transfers drops by ~35% once the
donor tail is cleaned rather than carried.
