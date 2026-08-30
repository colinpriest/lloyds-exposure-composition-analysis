# Systemic vs Non-Systemic Risk — Size-Dependent PYD Correlation Analysis

> **Status: superseded.**
> This document describes the earlier sequential / least-squares line-of-business
> projection, which was replaced by the robust Bayesian pooling operator
> (size and concentration, Student-t, two-regime RITC tail). It is retained as a record
> of that stage and is **not** a description of the current method. See
> `scaling_analysis_writeup.md` and the manuscript.


## Specification

**Question.** How much of the non-diversifiable component of prior-year development (PYD)
severity is *systemic* (a common, directional reporting-year shock hitting all syndicates at
once) versus merely *scale-free idiosyncratic* (syndicate-specific risk that does not shrink
with size)?

**Identification idea.** If severity decomposes as a common reporting-year location shock
plus size-diversifiable noise, the within-year correlation between two syndicates'
severities rises with the size of both syndicates, because the common
signal-to-idiosyncratic-noise ratio improves. The *shape* of the correlation-vs-size
profile is over-identified given the already-fitted pooling law `(k, gamma)`, so it serves
both as the estimation target (Stage 1) and as a posterior predictive check (Stage 2).

**Why the current model cannot answer this.** The headline model
(`calibrate_dispersion_ritc.py`) has a reporting-year shock `s_t` that multiplies the
*scale* `sigma_it`. A scale shock induces co-movement in magnitudes but zero linear
correlation in signed severities, and it leaves `sd_undiv` doing double duty: the floor
could be (a) perfectly correlated across syndicates (systemic) or (b) syndicate-specific
but non-diversifiable-by-size. These are observationally identical in the marginal variance
but have opposite capital implications. Cross-syndicate correlation among *large*
syndicates — where the diversifiable term has decayed — is the statistic that separates
them.

---

## 1  Notation and baseline model (M0)

For syndicate *i* in reporting year *t*, severity `S_it = PYD / opening_reserves`
(`s_raw_a` in `exposure_results.json`). The fitted baseline (M0, already produced by
`calibrate_dispersion_ritc.py`) is:

```
S_it ~ StudentT( nu_it , mu = 0 , sigma_it )
nu_it        = nu_clean                      (clean)
             = nu_clean * exp(-lambda_ritc)  (RITC)
sigma_it     = exp(s_t + beta_ritc*1[RITC]) * sqrt( sd_undiv^2
               + sd_div^2 * exp( 2(k-1) * log_reff_it ) )
log_reff_it  = log(R_it / 500) - gamma * log(HHI_it)
s_t ~ Normal(0, tau_s)                       (scale shock, log-scale)
```

Throughout this spec, **effective size** means `Reff_it = exp(log_reff_it)` evaluated at
the posterior-mean `gamma` from `dispersion_calibration_ritc.json`.

---

## 2  Data inputs

| Input | Source | Fields used |
|-------|--------|-------------|
| Observations | `exposure_results.json` → `observations[]` | `s_raw_a`, `opening_reserves_gbp_m`, `hhi`, `year`, `syndicate` (same filter as `calibrate_dispersion_ritc.load_sample()`: all three of `s_raw_a`, `opening_reserves_gbp_m`, `hhi` present) |
| RITC flags | `pdf_extraction/ritc_scan.json` | `ritc_occurred` per `syndicate_year` key |
| M0 posterior | `dispersion_posterior_draws_ritc.npz` + `dispersion_calibration_ritc.json` | posterior means of `k`, `gamma`, `sd_undiv`, `sd_div`, `beta_ritc`; per-year `s_t` means are **not** stored — recompute residual scale without `exp(s_t)` (see §3.1, note) |
| LoB weights (M2 only) | `exposure_results.json` → per-observation 13-element LoB weight vector (as computed by `run_analysis.py` §A.3.1) | verify field name at implementation time; if absent, M2 is descoped |

Constants shared with the baseline: `REFERENCE_SIZE = 500.0`, `HHI_FLOOR = 0.01`,
`HHI_CEIL = 1.0`, `SEED = 42`.

---

## 3  Stage 0 — Descriptive gate (`systemic_correlation_check.py`)

Cheap, rank-based, no MCMC. Purpose: decide whether the model extension is worth the
sampling time, and produce the raw correlation-vs-size profile later reused as the PPC
statistic.

### 3.1  Standardised residuals

```
z_it = S_it / sigma_hat_it
sigma_hat_it = exp(beta_ritc_hat * 1[RITC]) * sqrt( sd_undiv_hat^2
               + sd_div_hat^2 * exp( 2(k_hat - 1) * log_reff_it ) )
```

using posterior means from `dispersion_calibration_ritc.json`.

**Note on `s_t`.** The per-year scale shocks are not persisted in the M0 outputs. Omitting
`exp(s_t)` from `sigma_hat` leaves a common *scale* factor per year in `z`. This does not
bias the *signed* rank correlations under the null (a shared positive scale multiplier is
rank-preserving within each syndicate's series and induces no directional co-movement),
but record it as a known approximation. Do **not** refit M0 for Stage 0.

### 3.2  Exclusions

Drop RITC-flagged observations from Stage 0 entirely (RITC transfers move assumed
portfolios between syndicates and can fabricate pair correlation). Report `n_dropped_ritc`.

### 3.3  Pairwise correlation by size bin (the user-facing test)

1. **Pairs.** All unordered syndicate pairs `(i, j)` with at least `T_MIN = 6` common
   reporting years after exclusions.
2. **Pair statistic.** Spearman rank correlation `rho_ij` of `z` over the common years.
3. **Pair size.** Geometric mean of the two syndicates' median `Reff` over their common
   years.
4. **Bins.** Terciles of pair size (equal pair counts). Report per-bin: `n_pairs`,
   mean `rho`, median `rho`, and the mean common-year count.
5. **Trend statistics.**
   - `D = mean_rho(top tercile) − mean_rho(bottom tercile)`
   - `tau_trend` = Kendall's tau of `(log pair size, rho_ij)` across all pairs.

### 3.4  Year-median co-movement (secondary, more powerful per-year view)

For each year `t` and size tercile `g` (terciles of `Reff_it` **within year**), compute the
median residual `m_gt = median(z_it : i in g, t)`. Under no location factor each `m_gt` is
noise of order `1/sqrt(n_gt)`. Report the 3×11 matrix `m_gt`, the cross-tercile Spearman
correlations of the three 11-year series, and `sd(m_gt)` per tercile.

### 3.5  Permutation inference

Null: no common location factor; each syndicate's residual series is exchangeable across
its own observed years. Build the null by independently permuting, within each syndicate,
the assignment of its `z` values to its observed years (`B = 2000` permutations, seed 42).
Recompute `D`, `tau_trend`, and the §3.4 cross-tercile correlations per permutation.
Report one-sided permutation p-values (observed ≥ null).

This scheme preserves each syndicate's marginal distribution and the panel's missingness
pattern while destroying within-year alignment — the correct null for "no directional
common shock". Pairs share years and syndicates, so no analytic SE is valid here;
permutation is mandatory, not optional.

### 3.6  Gate criterion

Proceed to Stage 1 iff **either**:

- `p_perm(D) < 0.20`, **or**
- `p_perm(tau_trend) < 0.20`.

The threshold is deliberately lenient: Stage 0 has low power (11 years, rank statistics),
so it gates only against a clearly flat/inverted profile. If the gate fails, write the
results JSON, record `"gate_passed": false`, and stop — a flat profile *is* a finding
(evidence that the floor is idiosyncratic-but-scale-free, subject to the power caveat).

### 3.7  Output — `systemic_correlation_check_results.json`

```json
{
  "n_obs": 0, "n_dropped_ritc": 0, "n_pairs": 0, "t_min": 6, "seed": 42,
  "m0_source": "dispersion_calibration_ritc.json",
  "pair_bins": [
    { "bin": "small", "n_pairs": 0, "mean_rho": 0.0, "median_rho": 0.0,
      "mean_common_years": 0.0, "reff_range": [0.0, 0.0] }
  ],
  "trend": { "D": 0.0, "p_perm_D": 0.0, "tau_trend": 0.0, "p_perm_tau": 0.0 },
  "year_median_matrix": { "years": [], "terciles": ["small","mid","large"],
                          "m_gt": [[0.0]], "cross_tercile_spearman": {},
                          "sd_by_tercile": {} },
  "gate_passed": true
}
```

---

## 4  Stage 1 — Model extension (`calibrate_dispersion_systemic.py`)

### 4.1  Model M1: location year effect

Identical to M0 in every respect (data filter, priors, constraints, seed, sampler
settings) **except** the location:

```
S_it ~ StudentT( nu_it , mu = m_t , sigma_it )
m_t  = tau_m * z_m,t          z_m,t ~ Normal(0, 1)   (non-centred)
tau_m ~ HalfNormal(0.05)
```

Everything else — `k`, `gamma`, `sd_undiv`, `sd_div`, `f`, `tau_s`, `s_t`, RITC tail
regime (`nu_clean`, `lambda_ritc`), `beta_ritc` — is carried over unchanged so that
posteriors are directly comparable with `dispersion_calibration_ritc.json`.

Prior rationale: `tau_m` is on the severity scale, where total dispersion has prior centre
0.05 (`log_tot ~ N(log 0.05, 1)`); `HalfNormal(0.05)` is weakly informative and does not
force the systemic component to zero or dominance. Prior sensitivity: §5.3.

**Refit M0 in the same script** (same code path, `tau_m` fixed to 0) with
`idata_kwargs={"log_likelihood": True}` on both fits, so that LOO comparison uses
identical data and likelihood bookkeeping. Do not reuse the archived M0 fit for LOO.

### 4.2  Sampler

`pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98, random_seed=42)`,
NUMBA mode — identical to the baseline script. Non-centred parameterisation for both
`s_t` and `m_t`.

### 4.3  Derived quantities (computed per posterior draw, reported as posteriors)

Let `c = ( nu_clean / (nu_clean − 2) ) * exp(2 * tau_s^2)` — the factor converting the
Student-t scale² to a variance and marginalising the lognormal scale shock. Where a draw
has `nu_clean ≤ 2.05`, set `c = NaN` for that draw and report the fraction of such draws
(variance-undefined mass) alongside every `c`-dependent quantity.

1. **Systemic share of the floor** (headline number):

   ```
   phi_floor = tau_m^2 / ( tau_m^2 + c * sd_undiv^2 )
   ```

   This is the large-size limit of the within-year correlation between two syndicates —
   the direct answer to "is the undiversifiable floor systemic or idiosyncratic?"

2. **Implied pairwise correlation profile.** For effective sizes `Reff in
   {50, 100, 250, 500, 1000, 2500} £m` (equal-size pairs):

   ```
   V(Reff)   = c * ( sd_undiv^2 + sd_div^2 * (Reff/500)^{2(k-1)} )
   rho(Reff) = tau_m^2 / ( tau_m^2 + V(Reff) )
   ```

3. **Systemic variance share at reference** — `tau_m^2 / (tau_m^2 + V(500))`.

Report posterior mean, sd, and 95% HDI for each; store raw draws of `tau_m`, `m_t`,
`phi_floor` in the `.npz`.

### 4.4  Model comparison

- `az.compare({M0, M1}, ic="loo")` — report `elpd_diff`, `dse`, and Pareto-k diagnostics
  (flag any k > 0.7).
- `P(tau_m > 0.005)` — posterior probability the systemic component is economically
  non-negligible (0.5% of reserves ≈ 10% of the prior-centre total dispersion).
- Posterior of `sd_undiv` in M1 vs M0 — quantify how much of the M0 floor migrates into
  `tau_m` (this migration, not the LOO score, is the substantive result; with 11 years
  expect LOO to be weakly discriminating).

### 4.5  Optional Model M2: composition-loaded factor (confound probe)

Only if per-observation LoB weight vectors are available (§2). Replace `mu = m_t` with:

```
mu_it = c_it * m_t
c_it  = cosine_similarity( w_it , wbar_t )
```

where `wbar_t` is the premium-weighted market-mean LoB vector in year `t`. M2 asks whether
apparent systemic co-movement is really *composition similarity* (large syndicates all
converging to the market portfolio). Compare M1 vs M2 by LOO. If M2 clearly dominates,
the "systemic" factor is substantially a line-mix loading effect and `phi_floor` from M1
overstates macro-systemic risk; report both. Descope silently to a documented TODO if the
weight data is not in the results bundle.

### 4.6  Output — `dispersion_calibration_systemic.json` + `dispersion_posterior_draws_systemic.npz`

JSON mirrors `dispersion_calibration_ritc.json` structure (model string, spec string,
`params` rows with mean/sd/HDI, `posterior_prob`, `diagnostics`) plus:

```json
{
  "tau_m": {}, "m_t_by_year": {"2014": {}, "...": {}},
  "phi_floor": {}, "rho_profile": {"Reff_50": {}, "Reff_100": {}, "...": {}},
  "frac_draws_nu_le_2": 0.0,
  "loo_compare": { "elpd_diff_m1_minus_m0": 0.0, "dse": 0.0,
                   "pareto_k_gt_0.7": {"m0": 0, "m1": 0} },
  "sd_undiv_migration": { "m0_mean": 0.0, "m1_mean": 0.0 },
  "posterior_prob": { "tau_m_gt_0.005": 0.0, "phi_floor_gt_0.5": 0.0 }
}
```

---

## 5  Stage 2 — Posterior predictive check and sensitivities

### 5.1  PPC of the correlation-vs-size profile (`systemic_ppc.py`)

For 500 posterior draws of M1, simulate a replicated dataset `S_rep` on the **observed**
panel design (same syndicates, years, sizes, HHI, RITC flags, missingness). For each
replicate, run the exact Stage-0 pipeline (§3.1–§3.4, using the same plug-in `sigma_hat`
and the same pair set) and record `D`, `tau_trend`, and per-bin mean `rho`. Report:

- PPC p-values: `P(stat_rep ≥ stat_obs)` for `D` and `tau_trend`;
- per-bin observed mean `rho` against the replicate 5–95% band.

Pass criterion: observed per-bin means inside the 5–95% bands and both PPC p-values in
[0.05, 0.95]. Failure modes to call out explicitly: observed top-tercile correlation
*above* the band (model missing size-dependent loading or subscription-overlap
clustering); *below* the band (factor overfit to one year).

### 5.2  Leave-one-year-out

Refit M1 eleven times, dropping each reporting year. Report the posterior mean of `tau_m`
and `phi_floor` per fit. Flag if dropping any single year (2017 and 2022 are the prior
suspects) moves the `tau_m` posterior mean by more than 50% — that indicates the
"systemic" signal is one event, not a process, and the writeup must say so.

### 5.3  Prior sensitivity

Refit M1 with `tau_m ~ HalfNormal(0.10)` and `HalfNormal(0.025)`. Report `phi_floor`
posterior means across the three priors. With 11 systemic draws the prior will matter;
the deliverable is the sensitivity table, not a single number.

### 5.4  RITC treatment sensitivity

Refit M1 excluding RITC observations entirely (vs the default regime treatment). `tau_m`
should be stable; instability implies RITC co-movement is leaking into the factor.

### 5.5  Output — `systemic_ppc_results.json`

Per-check blocks with observed statistic, replicate band, PPC p-value; LOYO table;
prior-sensitivity table; RITC-exclusion comparison. One figure
(`systemic_correlation_profile.png`): observed per-bin mean `rho` with PPC bands and the
M1 posterior-mean implied `rho(Reff)` curve overlaid.

---

## 6  Interpretation matrix

| `phi_floor` posterior | LOYO stable? | Reading |
|---|---|---|
| concentrated high (≳0.5) | yes | Floor is substantially systemic: a common reporting-year shock, not diversifiable by size *or* by pooling syndicates. Vignette/capital aggregation across syndicates must correlate the floor. |
| concentrated high | no (one year drives it) | One shared event (e.g. 2017 cat recognition), not an ongoing systemic process. Report as event risk; do not hard-wire a correlated floor. |
| concentrated low (≲0.2) | — | Floor is scale-free idiosyncratic; cross-syndicate aggregation may treat floors as independent. |
| wide (spans 0.1–0.8) | — | 11 years cannot resolve the split. Report the posterior honestly; the sensitivity tables (§5.3) become the headline. |

**Standing caveats (must appear in any write-up of results):**

1. **T = 11.** The systemic factor has eleven draws; thousands of pairs do not add
   information about `tau_m` beyond that. All conclusions are estimation-with-uncertainty,
   not sharp tests.
2. **Subscription-market overlap.** Lloyd's syndicates co-subscribe the same slips; larger
   syndicates share more contracts. Contract-level overlap is observationally similar to a
   systemic factor in this data and cannot be separated without slip-level data. For
   market-wide capital purposes both are non-diversifiable, so `phi_floor` is still the
   decision-relevant quantity, but the *label* "systemic" is not identified against
   "shared-slip".
3. **Composition similarity** is partially probed by M2 only; if M2 is descoped, say so.
4. **Heavy tails.** All descriptive statistics are rank-based by design; Pearson
   correlations must not appear anywhere in this analysis (`nu_clean ≈ 2.4`).

---

## 7  Acceptance criteria

1. Stage 0 runs in under a minute, no MCMC, and is fully reproducible from
   `exposure_results.json` + `dispersion_calibration_ritc.json` + seed 42.
2. All MCMC fits: `max_rhat < 1.01`, `min_ess_bulk > 400`, zero divergences. Any
   violation blocks downstream stages until resolved (raise `target_accept`, then
   reparameterise).
3. M0 refit inside Stage 1 reproduces the archived `dispersion_calibration_ritc.json`
   posteriors for `k`, `gamma`, `sd_undiv` within 0.5 posterior sd (sanity gate — same
   data, same seed).
4. Every headline quantity (`phi_floor`, `tau_m`, `rho_profile`) is reported with 95% HDI
   and, where `c` is involved, the `frac_draws_nu_le_2` alongside.
5. All results JSONs include `seed`, `n`, `n_years`, source-file references, and the spec
   string of the fitted model.

## 8  Deliverables

| File | Stage |
|------|-------|
| `systemic_correlation_check.py` → `systemic_correlation_check_results.json` | 0 |
| `calibrate_dispersion_systemic.py` → `dispersion_calibration_systemic.json`, `dispersion_posterior_draws_systemic.npz` | 1 |
| `systemic_ppc.py` → `systemic_ppc_results.json`, `systemic_correlation_profile.png` | 2 |
| New section in `scaling_analysis_writeup.md` (after the RITC regime section): question, method, `phi_floor` headline, interpretation-matrix verdict, standing caveats §6 | write-up |
