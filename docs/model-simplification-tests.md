# Model Simplification Audit and Tests

This note audits four deliberate simplifications in the exposure-composition
**end model** (the distortion tool / vignette transfer and the persona
dispersion model). For each it (a) states precisely what is collapsed, (b)
classifies whether the choice is *documented* elsewhere in the repo, and (c)
where it is undocumented — or documented on questionable grounds — defines an
empirical test and records the result.

All tests are reproduced deterministically (seed 42) by:

```bash
python simplification_tests/run_tests.py     # writes simplification_tests/results.json
```

They read only committed artefacts: `exposure_results.json` (observations and
fitted dispersion models) and `pdf_extraction/syndicate_*.json` (raw claims
triangles).

---

## 1  What the end model collapses

For each historical donor syndicate-year the transfer does exactly two things
([docs/exposure-adjustment.md](exposure-adjustment.md), [specifications/vignettes.md](../specifications/vignettes.md)):

1. **Location / first moment** — re-project the donor's LoB-level severities
   onto the target weights: `S_mix = Σ_ℓ w^q_ℓ · s_iℓ`. *This uses the full,
   specific LoB mix.*
2. **Scale / second moment** — rescale dispersion for size:
   `S_adj = S_mix · √(V_size(R_q)/V_size(R_i))`, with
   `V_size(R) = A + B·R^C` (`A=0.0056, B=0.505, C=-0.81`). The paper / persona
   path multiplies in a second factor `V_HHI(HHI)`.

So the *specific LoB mix is not ignored* — it drives the central projection.
What is collapsed is everything feeding the **second moment and the tail**:

| Collapsed dimension | Replaced by |
|---|---|
| Which specific lines carry the variance | a scalar concentration index (HHI), or nothing (size only, in the tool) |
| Development / maturity structure of the reserve | a single one-year PYD ratio `PYD/opening_reserves` |
| The historical LoB mix of each underwriting-year vintage in the reserve | the current-year gross premium mix |
| Correlated (size × concentration) estimation | two power-laws applied **sequentially** |

Questions 1–4 below are exactly these four rows.

---

## 2  Simplification inventory & documentation status

| # | Simplification | Documentation status | Where |
|---|---|---|---|
| S1 | Dispersion uses LoB-agnostic concentration (HHI), not specific mix | **Partial → tested ✓** | [hhi-vs-entropy.md](hhi-vs-entropy.md); pure-dispersion Tables 13/15; stability §A.5.5; independence caveat §4.4 |
| S2 | Age / development structure discarded (one-year PYD ratio) | **None** | absent from caveats [paper-pack.md](paper-pack.md) §4.4; triangles exist but are unused |
| S3 | Current premium mix used as the reserve-vintage mix | **None (as justification)** | data cascade §3.2; Table 30 labels it a "proxy"; not in §4.4 |
| S4 | Size and concentration scaled sequentially, not jointly | **Yes** | spec §A.5.5–§A.5.6; Tables 17, 22–24; implemented in `run_analysis.py` |

---

## 3  S1 — LoB-agnostic dispersion  *(partial documentation → tested)*

**What / why the concern.** HHI treats a 60 %-Property book and a 60 %-Casualty
book as identical for volatility, yet long-tail casualty reserves plausibly
carry heavier PYD tails than short-tail property.

**Documented rationale (partial).** [hhi-vs-entropy.md](hhi-vs-entropy.md) §3
argues reserve risk is dominated by the largest 1–2 lines and HHI's collision
probability maps to correlated deterioration; the pure-dispersion finding
(Tables 13 & 15 — mean PYD does not move with size or HHI) justifies modelling
only the scale; §4.4 lists "independence of LoB severities" as a known caveat.
None of this shows that *line identity carries no tail information beyond HHI.*

**Test S1 (run).** Two functions of the *same* weight vector that HHI compresses
to a scalar: (a) `long_tail_share` = weight in Casualty + Professional Lines +
Reinsurance-Casualty + Motor (slow-developing lines); (b) dominant-LoB fixed
effects (the argmax line). Regress winsorised `s²` on `log R + HHI (+ these)`,
cluster-robust by syndicate; regress signed PYD on `long_tail_share` as a
mean-channel (pure-dispersion) check; and compare 5-fold syndicate-clustered OOS.

**Result** (`n = 790`, 133 syndicates; dominant lines with ≥15 obs: Property,
Casualty, Aviation, Aggregate):

| Channel | Finding |
|---|---|
| Mean: signed PYD ~ `long_tail_share` | coef **p = 0.069** — not significant at 5 % (pure-dispersion broadly holds) |
| Dispersion: `long_tail_share` coefficient | **p = 0.66**, ΔR² **+0.001** (negligible) |
| Dispersion: dominant-LoB fixed effects | in-sample ΔR² **+0.010** |
| OOS CV R²: base (size+HHI) → +long_tail / +dominant FE | 0.053 → 0.034 / 0.030 (**−1.9 pp / −2.4 pp — both worse**) |

**Verdict.** The specific LoB composition adds **no robust dispersion
information beyond (size, HHI)**: the long-tail-share slope is insignificant, and
both LoB-augmented models are *worse* out-of-sample (they overfit). The
LoB-agnostic collapse of the dispersion channel is justified, and now documented.

**Caveat.** This tests weight-vector-derived axes (long-tail share, dominant
line), not a full per-LoB severity-*distribution* model. Combined with S4 (even
HHI adds nothing beyond size out-of-sample, §6), the evidence strongly favours
the simplification. Note the mix still drives the *first moment* (`S_mix`) — S1
concerns only the dispersion scaling.

### 3b  Follow-up: largest-LoB identity and long-tail proportion (run)

Two sharper variants: (A) is the *identity* of the largest LoB predictive, and
its *top-share weight*? (B) is the *long-tail proportion* predictive? Each is
tested on **both** the direction (signed PYD) and dispersion (`s²`) channels,
cluster-robust by syndicate, with a joint Wald test for the categorical.

All dispersion tests condition on size + HHI; the direction test is reported
both raw and conditioned on size + HHI.

| Feature | Channel (controls) | Finding |
|---|---|---|
| Largest-LoB **identity** | Direction — raw | joint Wald **p < 0.001** |
| Largest-LoB **identity** | Direction — **after size + HHI** | joint Wald **p < 0.001** (effect survives) |
| Largest-LoB **identity** | Dispersion — after size + HHI | joint Wald p = 0.52, ΔR² +0.010, **OOS −2.4 pp** — n.s. |
| Largest-LoB **top share** | Dispersion — after size + HHI | p = 0.015 but **r = 0.96 with HHI** → restates concentration, not identity |
| Long-tail **proportion** | Direction — raw / after size + HHI | p = 0.069 / 0.117 — marginal |
| Long-tail **proportion** | Dispersion — after size + HHI | p = 0.66, **OOS −1.9 pp** — n.s. |

Mean signed PYD by dominant line (**raw** group means): **Casualty +6.7 %**,
**Aviation +6.3 %**, Property +2.0 %, Aggregate +1.0 %. The direction effect is
**not** a size/HHI artefact — it is p < 0.001 with or without those controls,
as expected since size and HHI carry no mean effect (Tables 13/15).

**Reading — a clean split by channel:**
- **Dispersion:** every LoB-specificity axis (identity, top-share-beyond-HHI,
  long-tail share) is insignificant or worse out-of-sample. Confirms S1 — the
  HHI collapse of the *variance* is justified. (Top-share is significant
  in-sample but 96 % collinear with HHI, so it is concentration re-labelled,
  not line identity.)
- **Direction:** the *identity* of the largest LoB **does** shift the mean —
  casualty/aviation-dominant books run ~5 pp more adverse than property/aggregate.
  The linear long-tail *proportion* only picks this up weakly (p = 0.07) because
  the effect is concentrated in specific lines, which the categorical captures
  and the linear share smooths away.

**Consequence (new — previously undocumented).**
- The composition-transfer tool handles this correctly: `S_mix = Σ w^q · s_iℓ`
  carries the casualty-adverse signal in the line-level severity `s_i,Casualty`.
- But the persona / paper dispersion path re-centres every target to the
  **market mean** (mean-preserving, §A.6.4), justified by the Table 15 direction
  test — which tested **HHI**, not **LoB identity**. Because LoB identity *does*
  shift the mean, re-centring a casualty- or aviation-heavy target to the market
  mean **understates its central PYD by ~5 pp**. Table 15's "mix does not move
  the mean" holds on the concentration axis but **not** the line-identity axis.

**Recommendation.** Keep HHI-only *dispersion* (justified). For the persona /
dispersion path, re-centre to the **mix-projected mean** (the mean of `S_mix`
under the target weights) rather than the market mean, so casualty / long-tail-
heavy targets are not handed the market-average direction.

---

## 4  S2 — age / maturity structure  *(undocumented → tested)*

**What.** Each syndicate-year is reduced to one calendar-year signed ratio
`PYD / opening_reserves`. The maturity of the reserve base (a young, immature
book is far more uncertain than a runoff book) is dropped.

**Documentation status: none.** The caveats list ([paper-pack.md](paper-pack.md)
§4.4) covers LoB granularity, stationarity, functional form, LoB-severity
independence, tail uncertainty and survivorship — but *not* the discarding of
development structure. And the structure exists: **559 of 622** raw files carry
an aggregate claims-development triangle (`_claims_triangle`), collapsed to a
scalar. The one-year-view alignment with Solvency II reserve risk would justify
it, but is nowhere stated.

**Test S2 (run).** From each triangle derive a reserve-weighted average
development age (`maturity`, orientation-robust: latest non-null incurred per
underwriting-year column, weighting `age = report_year − uw_year`). Regress
`|PYD ratio|` on `maturity + log R + HHI`, cluster-robust by syndicate.

**Result** (`n = 469` syndicate-years, 80 syndicates; maturity median 3.0y,
p10–p90 1.6–4.6y):

| Quantity | Value |
|---|---|
| corr(\|PYD\|, maturity), raw | **−0.105** (older → slightly less volatile, as expected) |
| maturity coefficient after size+HHI controls | −0.003, **p = 0.57 (n.s.)** |
| log R coefficient (same model) | −0.018, p = 0.013 (significant) |
| model R² | 0.049 |

**Verdict.** The raw signal is in the expected direction but weak, and it is
**absorbed by size** — once reserves are controlled, maturity adds nothing
(p = 0.57). At the aggregate level the one-year collapse is *empirically
defensible*, and now documented as such.

**Caveats / stronger test remaining.** The triangle is aggregate, so this tests
portfolio-average maturity, not per-LoB or per-cohort age. A sharper test —
one-step-ahead cohort development from the panel (does UW-year age predict the
magnitude of the *next* year's development?) — could still find signal for
immature-heavy books and should be run before treating S2 as settled.

**Recommendation.** Add the SII one-year-view justification to §4.4; keep the
one-year ratio; add a maturity flag only if the cohort test overturns this.

---

## 5  S3 — vintage LoB mix vs current-premium proxy  *(undocumented → tested)*

**What.** The reserves developing in year *t* were written across many prior
underwriting years, each with its own LoB mix. The pipeline uses the
**current-year** gross premium mix as the reserve mix (it sets the donor's HHI
and the LoB reserve split `R_iℓ = R_i·w_iℓ`).

**Documentation status: none as a justification.** It is a data cascade (§3.2);
Table 30 calls premium mix a "volume-based proxy"; it is absent from the §4.4
caveats. Vignette 2 is literally a mix-shifter but treats the phenomenon as a
use-case, not a model correction.

**Test S3 (run).** Using the panel of per-syndicate premium mixes:
- (a) pattern-free within-syndicate mix drift: Hellinger between mix in year *t*
  and year *t − k*;
- (b) proxy error: Hellinger between the current mix and a vintage-blended
  reserve mix (past mixes weighted by a generic decaying reserve-age pattern),
  and the resulting shift in HHI and in the `V_HHI` dispersion multiplier.

**Result:**

| Quantity | Value |
|---|---|
| Mix drift (median Hellinger) at lag 1 / 3 / 5 | 0.08 / 0.14 / 0.17 |
| Proxy error, median Hellinger (premium vs reserve-blend) | **0.07** (benign) |
| Proxy error, **p90** Hellinger | **0.225** |
| Median \|ΔHHI\| / p90 \|ΔHHI\| | 0.025 / 0.115 |
| Share of obs with dispersion-multiplier shift > 10 % | **8.4 %** |
| Top shifter (syn 457, 2024) | Hellinger 0.61, ΔHHI −0.68, dispersion ×0.58 |

**Verdict.** For the **median** syndicate the current-mix proxy is close to the
reserve-relevant mix (Hellinger 0.07, HHI shift 0.025, <1 % dispersion effect) —
the simplification is fine. But it is **materially wrong for a minority**: p90
Hellinger 0.225 is comparable to the *tightest* local-donor threshold (0.30),
and ~8 % of syndicate-years shift their dispersion scale by >10 %. The worst
cases (syndicates 457, 386, 2791, 780, 2010 — mostly recent years) are exactly
the vignette-2 mix-shifter population.

**Caveat.** The metrics above cover the HHI / mix-distance channels. The larger
channel — the LoB reserve split `R_iℓ` that feeds the LoB-level severities and
hence `S_mix` — is quantified in the fuller re-run below (§5b).

### 5b  Fuller materiality (run) — LoB-severity split and projected tail

For the **123** syndicate-years with observed LoB-level movement *amounts*
(**87** of which have enough panel history to form a reserve-blend), the pipeline's
own reconstruction (`classify_lob`, sign logic, ±5 cap) recomputes the
LoB-level severities `s_iℓ = M_iℓ / (R_i · max(w_iℓ, 0.01))` under the current
premium mix vs the reserve-blend mix, then projects onto target weights.

| Metric | Value |
|---|---|
| Line-severity distortion (297 donor×line cells): median rel. change | **9 %** |
| … p90 rel. change | **37 %** |
| … share of line cells moving > 25 % | **21 %** |
| Market-average projection: VaR95 premix → reserveblend | 0.097 → 0.103 (**+5.8 %**) |
| … VaR99 (≤1 tail obs — noisy) | 0.299 → 0.377 (+26 %) |
| … median \|ΔS_mix / S_mix\| | **12 %** |

The six narrow test portfolios project to zero for these donors (`n_nonzero = 0`
— their observed lines rarely overlap a Property/Casualty target), so the
market-average projection and the projection-free line-level distortion are the
reliable signals. Both confirm §5: swapping current premium mix for the
reserve-relevant mix leaves the *median* donor almost unchanged but moves ~1 in 5
line-level severities by >25 % and shifts the projected tail by ~6 % (VaR95).

**Recommendation.** Keep the proxy as default (median error is small), but:
(i) add the premium-vs-reserve-mix mismatch to §4.4; (ii) flag / down-weight
donors whose year-on-year mix drift is large; (iii) warn in the tool when the
*target's* premium mix and reserve-implied mix diverge (the vignette-2 case);
(iv) where segmental technical-provisions-by-class exist, prefer them over
premium mix.

---

## 6  S4 — sequential vs simultaneous scaling  *(documented → results verified, rationale corrected)*

**Documentation status: yes.** The sequential (size → HHI) pipeline is motivated
in spec §A.5.6 ("size and diversification are correlated … fitting them
simultaneously … is unstable in practice"), a stability/collinearity diagnostic
is defined in §A.5.5, and Tables 17 and 22–24 report the correlation, univariate
comparison and ordering. It is implemented in
[run_analysis.py](../run_analysis.py) (`fit_joint_power_dispersion`, the
`hhi_first` variant, `ordering_comparison`, and `stability_flags`).

**But the documented *mechanism* is only half right.** The recalled reason —
"size and concentration are strongly associated, so separability breaks" — is
not what the data show.

**Result:**

| Evidence | Value | Reading |
|---|---|---|
| Pearson(log R, HHI) / Spearman | **−0.21 / −0.14** | *weak* association, not strong |
| VIF, design condition number | **1.04, 1.23** | negligible collinearity |
| Joint power-law (delivered): p(A), p(B1), p(B2) | 0.99, 0.17, 0.22 | every parameter insignificant |
| Joint stability flags | C1 shift 0.58, C2 shift 0.36 | power exponents swing vs single-factor |
| In-sample joint linear: p(HHI \| size) | **0.19** | HHI adds nothing once size is in |
| Variance added by 2nd factor (size-first / hhi-first) | **0.19 % / 0.20 %** | near-total redundancy |
| Out-of-sample CV R²: size / hhi / joint | 0.057 / **−0.007** / 0.053 | joint is *worse* than size-only; HHI alone doesn't generalise |
| Joint HHI slope: bootstrap sign-stability / CV | 91.5 % / **79 %** | HHI slope flips sign in 8.5 % of resamples (size CV only 31 %) |
| Ordering recommendation vs shipped default | code says **hhi_first** (27 % vs 23.7 %); pipeline ships **size_first** | recommendation is fragile / mismatched |

**Corrected conclusion.** Sequential scaling *is* the right call, but **not
because of strong collinearity** (there is none — VIF ≈ 1.04). The joint fit is
unstable because size and concentration are **near-redundant for dispersion**
(each explains ~24–27 % of the variance in `s²`; the other then adds ~0.2 %),
and the 5-parameter nonlinear joint form is over-parameterised on a weak,
noisy signal (observation-level R² ≈ 0.05–0.07). The ordering is not robustly
identified: HHI "wins" on binned nonlinear fit but size wins on
observation-level and out-of-sample linear fit — a symptom of two
near-substitutes rather than two separable effects.

**Recommendations.**
1. **Correct the documented rationale** in §A.5.5–§A.5.6 and Table 17: replace
   "correlated → unstable" with "near-redundant + weak-signal → the joint
   nonlinear fit is unidentified (VIF ≈ 1.04, so it is *not* classical
   collinearity)."
2. **Reconcile** the `hhi_first` recommendation with the shipped `size_first`
   default, or state explicitly that the ordering is immaterial (difference
   3.3 pp, within noise).
3. **Consider dropping HHI from the operational dispersion scaling** entirely.
   The distortion tool already scales on size only ([vignettes.md](../specifications/vignettes.md):
   "HHI is a concentration descriptor and diagnostic, not a separate primary
   adjustment operator"); the OOS result (joint no better than size-only)
   is direct evidence that this is the honest choice.

---

## 7  Summary

| # | Simplification | Documented? | Test result | Action |
|---|---|---|---|---|
| S1 | HHI not specific mix (dispersion) | Partial | **justified** — LoB terms n.s. (p=0.66), worse OOS (−1.9/−2.4 pp) | keep HHI-only dispersion; record the test |
| S1b | LoB identity for *direction* | New | **largest LoB shifts the mean** (Wald p<0.001; Casualty +6.7 % vs Property +2 %) — mean only, not dispersion | re-centre personas to the mix-projected mean, not the market mean |
| S2 | one-year PYD, no age structure | No | **defensible** — maturity n.s. after size (p=0.57) | document SII one-year rationale; run cohort test to confirm |
| S3 | current premium mix as reserve mix | No | **mostly fine, tail matters** — median Hellinger 0.07 / line distortion 9 %, but p90 0.225 / 21 % of lines >25 % / VaR95 +6 % | document; flag mix-shifters; prefer segmental reserves |
| S4 | sequential not joint scaling | Yes | **right call, wrong reason** — no collinearity (VIF 1.04), it is redundancy | correct rationale; reconcile ordering; consider size-only |

**Common thread.** The end model is a one-period, aggregate, current-mix
cross-sectional transfer applied to a multi-vintage, per-LoB, development-
structured process. The size-only *first-moment* projection and the sequential
scaling are empirically sound; the *undocumented* discards (age structure, and
the premium-as-reserve-mix proxy) are defensible in the median but each has a
minority tail where they bite — precisely the mix-shifter / immature-book
populations the personas and vignettes are meant to represent.

---

## 8  Reproduction

- `simplification_tests/run_tests.py` — runs S1, S2, S3, S3b and S4 and writes
  `simplification_tests/results.json`. It imports `run_analysis.py` to reuse the
  pipeline's own `classify_lob`, `mix_standardise`, weight vectors and test
  portfolios, so all reconstructions are faithful to the delivered model.
- S1 and S3b use donors with observed LoB-level movement amounts (123) and the
  panel of premium mixes; S2 reads the raw claims triangles directly.
