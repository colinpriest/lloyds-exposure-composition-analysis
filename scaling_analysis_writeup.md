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

The posterior for $\nu$ concentrates near 2.2 but assigns ~13% mass to $\nu<2$, the
**infinite-variance** regime, where the standard deviation does not exist and the literal
"$\mathrm{SD}\propto R^{k}$" statement is undefined. We therefore interpret $k$ as an
**aggregation-scaling exponent** rather than a standard-deviation exponent, with the
finite-variance $\sqrt N$ / CLT argument as a special case.

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
"standard deviation" gloss needs care when $\nu<2$; and (ii) the estimate $\hat k\approx0.64$
sits comfortably interior under either regime (even at $\nu=1.9$ the independence floor
$1/\alpha\approx0.53$ lies below it), so the conclusion is not pinned to a boundary that shifts
with the tail index.

*Empirical check.* Three tail-index estimates on the model innovations agree the tail is
heavy: Bayesian $\nu=2.33$ [1.84, 2.90] and a Student-$t$ MLE df $=2.26$ [1.82, 2.89] (both
$P(\alpha<2)\approx0.11$–$0.15$), while a Hill estimator on the extreme tail (top 8–20%) gives
$\alpha\approx1.6$–$1.8$ — i.e. the *extreme* tail is in the infinite-variance regime. Mapping
to the aggregation exponent, the independence value $1/\alpha$ is 0.50 (at $\alpha=2$) to
$\approx0.59$ (at $\alpha=1.7$); the fitted $k\approx0.64$ exceeds it. Two conclusions:
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

544 syndicate-year observations span reporting years 2014–2024. An earlier design
restricted dispersion calibration to a "dense" subset (2014–2019, $n=327$), holding out
2020–2024. Having moved to the holistic pooling model, **we drop the holdout and use all
available years**; this also raises the number of year clusters from 6 to 11, materially
improving identification of the shared-shock variance $\tau_s$. Of the 544 observations, 492
have complete severity, reserves and HHI (the remaining 52 lack one of these); the working
sample is therefore $n=492$ across 11 years. Because the $n_{\text{eff}}=1/H$ form is
well-defined at $H=1$ (§2.2), **single-line reporters are retained** — there is only one such
observation, and it fits without issue (its standardised residual is $+0.7$), so no
concentration-based exclusion is applied.

---

## 3. Results

**Headline posterior (full sample, $n=492$, 11 reporting years):**

| Parameter | Meaning | Mean | 95% HDI |
|---|---|---|---|
| $k$ | diversifiable-term pooling exponent | **0.64** | [0.52, 0.75] |
| $\gamma$ | concentration ($n_{\text{eff}}$ effective-size) | 0.42 | [0.00, 1.04] |
| $\sigma_{\text{undiv}}$ | undiversifiable floor | **0.026** | [0.008, 0.042] |
| $\sigma_{\text{div}}$ | diversifiable SD at reference | 0.055 | [0.039, 0.071] |
| $\nu$ | Student-$t$ degrees of freedom | **2.3** | [1.8, 2.9] |
| $\tau_s$ | year shared-shock SD (log-scale) | 0.058 | [0.00, 0.15] |

Posterior probabilities: $P(k<1)=1.00$ (diversification is certain — the portfolio is not
comonotonic); $P(\gamma>0.05)=0.93$; $P(\sigma_{\text{undiv}}>0.005)=0.99$ (a positive
undiversifiable floor is well-supported). Diagnostics clean (0 divergences, $\hat R=1.00$).

**Interpretation of $k$.** $k\approx0.64$ governs the *diversifiable* component of dispersion,
which decays as (effective size)$^{k-1}$ — meaningfully sub-linear (real diversification) but
above the $R^{0.5}$ independence benchmark, i.e. a substantial *shared* component remains.
Diversification does not run to zero, though: it decays toward the undiversifiable floor
$\sigma_{\text{undiv}}$.

**Effect sizes (in standard-deviation terms):**

- **Size dominates, but the floor caps it.** A $\pounds100$m portfolio carries **≈2.1×** the
  dispersion of a $\pounds2{,}000$m portfolio of equal composition — less than the 2.4× a
  no-floor power law implied, because the floor compresses the gap at large sizes.
- **Concentration is second-order.** Moving from diversified ($H=0.1$) to concentrated
  ($H=0.9$) at fixed size raises dispersion by **≈1.3×** — credibly above one, but modest.
- **Undiversifiable floor.** A very large, diversified book's dispersion bottoms out at
  $\sigma_{\text{undiv}}\approx0.026$ (≈2.6% of reserves): $\sigma\approx0.029$ at $\pounds10$bn,
  $\approx0.027$ at $\pounds100$bn — it does not decay to zero.

**Heavy tails confirmed.** The posterior for $\nu$ concentrates near **2** (prior mean 20),
so the data pull decisively toward heavy tails: the robust likelihood is doing real work,
and a Gaussian model would have been outlier-dominated exactly as the LS joint fit was.

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

Although we model dispersion, the data reveal a strong **location** signal. Adding
$\mu = m_0 + m_1 H$ (HHI centred):

| Quantity | Posterior | |
|---|---|---|
| $m_0$ (mean $S$ at average $H$) | +0.011 [−0.001, +0.024] | level ≈ 0 |
| $m_1$ (HHI slope) | **−0.061 [−0.105, −0.018]** | $P(m_1<0)=0.998$ |
| Mean shift, $H:0.1\to0.9$ | **−0.049 [−0.084, −0.015]** | ≈ 4.9% of reserves ≈ 1.0 σ |

Concentrated portfolios run off **less adversely** on average — a shift of about one full
dispersion-scale unit across the observed concentration range, 99.8% credibly negative.
LOO strongly favours including it (Section 4). This is an *economically interesting* finding
in its own right, independent of the dispersion scaling.

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

Under that honest prior (full sample, $n=492$):

- $\sigma_{\text{undiv}} = 0.026$ [0.007, 0.041] — the **95% lower bound clears zero**;
  $P(\sigma_{\text{undiv}} > 0.005) = 0.99$.
- Undiversifiable variance share $f = 0.20$ [0.01, 0.48], $P(f>0.05) = 0.89$.
- For comparison, the HalfNormal$(0.1)$ prior gives a similar *point* estimate (0.021) but a
  lower bound grazing zero — the "set to zero" reading was a prior artefact.

**Retained.** The data support a **positive undiversifiable floor** of $\approx 0.026$ (about
2.6% of reserves), consistent with the actuarial expectation that some reserve risk is never
diversifiable. Including the floor steepens the diversifiable exponent to $k\approx0.64$ (from
$0.71$ without a floor): with the floor catching the large-size behaviour, the diversifiable
term is free to decay faster. **Practical consequence:** a very large diversified book's
dispersion bottoms out at $\sigma_{\text{undiv}}\approx0.026$ rather than decaying to zero — and
a pure power-law (no-floor) extrapolation would understate it (e.g. it implies $\sigma\approx0.020$
at $R=\pounds10$bn, *below* the floor). This corrects the earlier draft, which set the floor to
zero on the strength of a zero-piling prior and a null LOO.

#### 4.2.1 Floor vs no-floor: a predictive tie, resolved by extrapolation safety

We compared the two candidate scale laws head-to-head on the full sample ($n=492$). **Both
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
floor $\sigma_{\text{undiv}}\approx0.026$. Because the sample contains no books beyond ~£6bn,
LOO — which scores fit *within* the observed data — is blind to precisely the region where the
models differ. Predictive fit therefore *cannot* adjudicate this choice.

**We select Model B.** The decision rests not on fit but on the two things fit is blind to:
(i) the floor parameter is **credibly positive** under an honest (uniform variance-share) prior
($\sigma_{\text{undiv}}=0.026$ [0.008, 0.042], $P(\sigma_{\text{undiv}}>0.005)=0.99$); and
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
| **M1 — blended exponent ($k$ free)** | 450.87 | 0.00 | — | **0.97** | 0.026 |
| M2 — independent $\sqrt N$ + floor ($k=0.5$) | 449.93 | 0.94 | 1.46 | 0.03 | 0.036 |

WAIC agrees ($\Delta=0.94$). Unlike the floor-vs-no-floor comparison (§4.2.1), the two models
differ **within the observed data**, because the exponent shapes the whole dispersion curve —
so LOO *can* discriminate, and it favours the blended exponent (stacking weight 0.97 vs 0.03;
$\Delta$elpd 0.94, though $\Delta$SE $=1.46$ keeps it short of a knockout on the strict
$\Delta$SE rule).

**The decisive evidence is the exponent itself:** in Model 1, $k=0.638$ [0.526, 0.751] with
$P(k>0.5)=1.00$. The data are *certain* the diversifiable part pools **more slowly than
independent $\sqrt N$** — there is systematic co-movement beyond pure independence. Model 2
cannot express this (its exponent is pinned at $\tfrac12$), so it **mislabels the residual
dependence as floor** — inflating $\sigma_{\text{undiv}}$ from 0.026 to 0.036 — and still fits
worse. **We adopt Model 1 (the blended-exponent form, already the shipped specification):**
independent $\sqrt N$ pooling is rejected, and a freely-estimated effective-dependence exponent
between the independence and comonotonic limits is required.

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
$n=492$): re-estimating $\gamma$ with the mean modelled ($\mu=m_0+m_1H$) leaves it
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
   $\delta_{L}\sim\mathcal N(0,\tau_L)$ on $\log\sigma$. Levels were grouped as
   {Aggregate (301), Property (90), Casualty (62), Aviation (26), Other (12)}.
2. **Long-tail proportion** (continuous): the summed weight of long-tail lines
   (Casualty, Motor, Reinsurance–Casualty, Professional Lines, Cyber; mean 0.21, range
   0–0.97), entered as a linear term $\beta_{\text{LT}}$ on $\log\sigma$.

| Model | $\Delta$elpd | $\Delta$SE |
|---|---|---|
| **base (size + year, $\mu=0$)** | 0.00 | — |
| + dominant LoB | 0.33 | 0.95 |
| + long-tail proportion | 0.62 | 1.13 |

Neither improves out-of-sample fit ($\Delta$elpd below its standard error in both cases).

- **Dominant LoB:** the between-LoB dispersion SD is small and pressed toward zero
  ($\tau_L=0.148$ [0.005, 0.470]); *every* category's dispersion multiplier includes 1.0
  (Aggregate 0.96 [0.74, 1.16], Property 0.97 [0.75, 1.21], Casualty 1.09 [0.88, 1.47],
  Aviation 1.09 [0.87, 1.55], Other 0.95 [0.64, 1.22]). No line credibly deviates.
- **Long-tail proportion:** $\beta_{\text{LT}}=-0.26$ [−0.81, +0.30], $P(\beta_{\text{LT}}>0)=0.18$;
  the implied dispersion multiplier across the full observed range (0→0.97) is 0.81×
  [0.45, 1.34] — squarely including one.

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
| ~~Nonzero variance floor / asymptote~~ (retracted §4.2) | Earlier "zero" was a zero-piling prior artefact; honest uniform-share prior gives a positive floor $\sigma_{\text{undiv}}\approx0.026$ — **retained** |
| HHI as a first-order dispersion driver | LOO indifferent vs size-only; second-order at best |
| Dominant line of business (categorical) on dispersion | LOO no improvement; every category multiplier includes 1.0; $\tau_L\to0$ |
| Long-tail proportion on dispersion | LOO no improvement; $\beta_{\text{LT}}$ CI straddles zero |

---

## 5. Recommended final specification

$$
S_{it}\sim\text{Student-}t\!\left(\nu,\,0,\,\sigma_{it}\right),\qquad
\sigma_{it}=\sqrt{\sigma_{\text{undiv}}^2+\sigma_{\text{div}}^2\,\big[(R_{it}/R_{\text{ref}})(1/H_{it})^{\gamma}\big]^{2(k-1)}}\;\,e^{s_t},\qquad
s_t\sim\mathcal N(0,\tau_s),
$$

with **$\mu=0$ fixed**, $k\in[0.5,1]$, $\gamma\ge0$, a **positive undiversifiable floor**
$\sigma_{\text{undiv}}\approx0.026$ (uniform variance-share prior), the effective-line
$n_{\text{eff}}=1/H$ concentration form (well-defined at $H=1$), and heavy-tailed errors —
fitted by Bayesian NUTS on all 11 reporting years ($n=492$). Headline: a diversifiable
**pooling law with $k\approx0.64$** (certain diversification, real shared component) over an
**undiversifiable floor of $\approx2.6\%$ of reserves**, heavy tails, and concentration as a
weak second-order dispersion effect. The concentration-lowers-mean-development result is the
strongest single signal in the data and is reported as a **separate empirical finding**,
deliberately kept outside the volatility model.

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
