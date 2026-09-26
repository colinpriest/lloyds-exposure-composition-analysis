"""Temporal correlation of the PYD-severity ratio across consecutive years, within
syndicate (syndicate-year unit).

Why it matters: the pooling likelihood treats a syndicate's yearly severities as
conditionally independent given size/HHI (mu=0, no within-syndicate serial term). If
S = PYD/reserves is strongly autocorrelated year-to-year within a syndicate, that
independence is violated and the effective sample is smaller than n. This tests it.

The alternative is POSITIVE persistence, so every test here is one-sided in that direction and each
p-value is the rank of the observed statistic in the null the permutation actually draws. Until the
frozen review of 25 September 2026 (M01) (a) instead reported the share of permutations whose
statistic was further from ZERO than the observed one. That is not directed at positive persistence:
demeaning within syndicate biases the lag-1 correlation down by about 1/(T-1), so this null is
centred near -0.195 rather than at zero, and a negative observed value can sit high in it. It did.
The published p = 0.963 was the rank of |-0.089| in |null|; the observed statistic sits in the upper
3.7% of the null itself. Every null's own location is now reported beside its p-value, so the
direction can be checked by eye rather than taken on trust.

Reports, on consecutive-year pairs (t, t+1) within each syndicate, de-meaned per syndicate:
  (a) pooled lag-1 autocorrelation of S (Pearson and Spearman), with a syndicate-block
      bootstrap 95% CI, the within-syndicate permutation null's location and spread, and the
      one-sided p-value for positive persistence (the two-sided rank p-value and the superseded
      distance-from-zero quantity are recorded beside it, the second under a name that says so);
  (b) lag-2 autocorrelation (decay check);
  (c) same on the signed direction: share of consecutive pairs with the SAME sign of PYD
      (direction persistence) vs the 50% chance rate;
  (d) the factor (1+rho)/(1-rho) for rho=lag1: the long-run variance-inflation factor of a
      STATIONARY FINITE-VARIANCE AR(1) process, reported for orientation only.  It is a
      heuristic, not a bound on model uncertainty: a lag-one estimate does not bound
      dependence at other lags, and the fitted Student-t regimes admit nu <= 2.
  (e) the demeaning benchmark: what (a) would read, in the population, if each syndicate's
      severities were a stationary AR(1) in calendar time with a given lag-1 correlation and NO
      persistent level, after the same demeaning (a) applies. Demeaning removes part of a serial
      process and leaves a bias of its own, so (a) against the raw statistic does not identify the
      level or bound the serial component. It records the lag-1 correlation that would
      read the observed (a), the largest that would still fall inside its interval, what the
      observed raw lag-1 would read, and a simulation of the same statistic on the real year sets
      that checks the closed form (frozen review of 24 September 2026, D02). The closed form assumes
      ONE lag-1 correlation and the SAME marginal variance for every syndicate, and the reading is
      an illustration under those assumptions, not a bound: weighting the same algebra by each
      syndicate's own observed variance moves the coefficient that reads the observed (a) from about
      0.075 to about 0.141, so heterogeneity matters to it. Both readings are recorded (frozen
      review of 25 September 2026, D01).
  (f) the same directed test on the residuals of the ADOPTED MODEL rather than on raw severities:
      z_it = S_it / sigma_it with sigma_it from adopted_model.sigma_numeric, which is what the
      likelihood's conditional independence given size, HHI, regime and reporting year actually
      claims. Permuting unstandardised severities does not test that. Two nulls, because the
      reporting-year shock is common to a year's whole cross-section:
        * a calendar-year BLOCK permutation, which relabels the eleven reporting years by one
          permutation so each year's cross-section moves whole and only temporal adjacency is
          destroyed -- the null for serial dependence GIVEN the year;
        * a within-syndicate permutation after the per-year location and scale are taken out of the
          cross-section, which conditions on the year explicitly instead.
      Spearman leads here: the fitted regimes are Student-t with nu about 5, where a rank statistic
      is the better-behaved one (frozen review of 25 September 2026, M01).
  (g) the calibration of those nulls on these year sets, because a p-value is only worth printing if
      its null is the right one. The WITHIN-SYNDICATE permutation, which (a) uses, is not: permuting a
      syndicate's own years destroys its alignment with the calendar, so a common reporting-year
      component contributes to the observed statistic and not to the null, and the test rejects
      whether or not anything is serially dependent. (g) measures that -- the size of both nulls on
      simulated panels carrying a year component and no within-syndicate dynamics, and their power
      when dynamics are added -- and the script refuses to write its output if the per-year-adjusted
      test is not near its nominal size, or has no power, or if the unadjusted one has stopped
      over-rejecting. So the section's reading rests on the test whose behaviour is demonstrated
      here, and (a)'s directed p-value is reported as the correction of an arithmetic error rather
      than as the finding.

Writes check_pyd_temporal_correlation_results.json.
Usage:  python src/check_pyd_temporal_correlation.py [B]
"""
import io, json, sys
from collections import Counter
from pathlib import Path
import numpy as np
from scipy import stats

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_pyd_temporal_correlation_results.json"
# A bootstrap size may be given on the command line; anything else on it (pytest's own arguments, when a
# test imports this module) is not one.
B = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4000
SEED = 42
#: The benchmark's own cross-check: the closed form is the population value of (a) only if it
#: agrees with paths drawn on the real year sets and pooled through lag_pairs (R222 correction).
MC_RHO, MC_DRAWS, MC_SEED, MC_TOL = 0.4, 1500, 20260924, 0.01
HLO, HCE = 0.01, 1.0

#: (g) The nulls' own calibration, on these syndicates' year sets. A p-value is only worth printing
#: if its null is the right one, and the WITHIN-SYNDICATE permutation is not when a reporting-year
#: component is present: permuting a syndicate's own years destroys its alignment with the calendar,
#: so the year component contributes to the observed statistic and not to the null, and the test
#: rejects whether or not anything is serially dependent. Removing each year's location and scale
#: from the cross-section first repairs it. So the script measures the size and the power of both,
#: under a design with a common year component and no within-syndicate dynamics (the null) and one
#: that adds them (the alternative), rather than asserting which null to trust.
CAL_REPS, CAL_PERMS, CAL_SEED, CAL_ALPHA = 20, 200, 20260925, 0.05
CAL_YEAR_RHO, CAL_SYN_RHO = 0.6, 0.3
#: what the measurement has to show for the section's reading to stand: the adjusted test near its
#: nominal size on the null design, the unadjusted one clearly above it, and power on the alternative.
CAL_MAX_SIZE_ADJUSTED, CAL_MIN_SIZE_UNADJUSTED, CAL_MIN_POWER = 0.35, 0.50, 0.50


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    syn = np.array([o["syndicate"] for o in recs])
    yr = np.array([o["year"] for o in recs])
    return S, syn, yr


def series_by_synd(S, syn, yr, min_obs):
    """{syndicate: (years_sorted, S_sorted)} for syndicates with >= min_obs."""
    out = {}
    for s in set(syn):
        m = syn == s
        if m.sum() < min_obs:
            continue
        o = np.argsort(yr[m])
        out[int(s)] = (yr[m][o], S[m][o])
    return out


def lag_pairs(series, lag, demean=True):
    """Collect (x_t, x_{t+lag}) consecutive-in-calendar pairs across syndicates,
    de-meaned within syndicate."""
    xs, ys = [], []
    for s, (yy, ss) in series.items():
        v = ss - ss.mean() if demean else ss
        for i in range(len(yy) - lag):
            if yy[i + lag] == yy[i] + lag:
                xs.append(v[i]); ys.append(v[i + lag])
    return np.array(xs), np.array(ys)


def demeaned_lag1_under_ar1(series, rho, variances=None):
    """The pooled lag-1 correlation these syndicates would show, in the population, under a stationary AR(1) in
    CALENDAR time with lag-1 correlation `rho` and no persistent per-syndicate level, after the same demeaning (a).

    `variances` maps syndicate -> marginal variance. The default, None, gives every syndicate variance 1, which is
    the equal-variance illustration; passing the syndicates' own observed variances weights the pooled statistic the
    way the data do, and the two readings differ materially (frozen review of 25 September 2026, D01). Neither is a
    bound on the serial component: both are what ONE assumed process would read.

    Exact covariance algebra, not simulation, and grouped the way (a) groups: lag_pairs demeans over a syndicate's
    WHOLE series and then keeps the pairs whose years are consecutive, so for a syndicate observed in years y the
    demeaned vector has covariance M @ Sigma @ M with Sigma_ij = rho^|y_i - y_j| and M = I - J/T, and only the
    consecutive-year entries enter the pooled statistic. Thirty-seven of these syndicates have a gap in their years;
    demeaning each maximal run separately, which R222 first did, is a different operator and reads about a third
    lower (0.170 against 0.245 at the observed raw lag-1).

    On four consecutive years and rho = 0.6 it is -0.064: on a short panel a process that is all dynamics and no
    level reads as no dynamics. These series are longer, so the bias is milder and the statistic keeps some power.
    """
    num = den_a = den_b = 0.0
    for _s, (yy, _ss) in series.items():
        y = np.asarray(yy, dtype=float)
        T = y.size
        if T < 2:
            continue
        v = 1.0 if variances is None else float(variances[_s])
        cov = v * float(rho) ** np.abs(y[:, None] - y[None, :])
        m = np.eye(T) - np.ones((T, T)) / T
        c = m @ cov @ m
        for i in range(T - 1):
            if yy[i + 1] == yy[i] + 1:
                num += float(c[i, i + 1])
                den_a += float(c[i, i])
                den_b += float(c[i + 1, i + 1])
    if den_a <= 0 or den_b <= 0:
        raise ValueError("no pair of consecutive years")
    return float(num / np.sqrt(den_a * den_b))


def ar1_rho_reading(series, target, hi=0.99, variances=None):
    """The lag-1 correlation of a level-free AR(1) whose demeaned statistic equals `target` on these series, or None
    when no rho in (0, hi] reads it. Bisection on a function that increases in rho; no solver dependency.

    `variances` is passed straight to demeaned_lag1_under_ar1, so the reading can be taken under the equal-variance
    illustration or under the syndicates' own observed variances."""
    lo = 0.0
    f_lo = demeaned_lag1_under_ar1(series, 0.0, variances)
    f_hi = demeaned_lag1_under_ar1(series, hi, variances)
    if not f_lo <= target <= f_hi:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if demeaned_lag1_under_ar1(series, mid, variances) < target:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def observed_variances(series):
    """Each syndicate's own observed variance of S, for the heterogeneous reading of the illustration.

    The unbiased sample variance (ddof=1): the quantity being estimated is the marginal variance of the
    syndicate's process, and these series are short enough that the divisor matters -- at ddof=0 the reading
    below comes out 0.129 rather than 0.141.
    """
    return {s: max(float(np.var(ss, ddof=1)), 1e-12) for s, (_yy, ss) in series.items()}


def short_history_variance_reading(series, rho, target, max_len=4, hi=1e6):
    """The marginal variance which, given to the syndicates with at most `max_len` years and 1 to the rest, makes a
    LEVEL-FREE AR(1) with lag-1 correlation `rho` read `target` as its demeaned statistic. None if none does.

    This is the counterexample to "the contrast excludes dynamics alone at the raw level" (frozen review of
    25 September 2026, D01). Put `rho` at the observed RAW lag-1 and `target` at the observed demeaned statistic: a
    process with no persistent level at all reads both observed numbers, so the contrast between them excludes
    nothing once the syndicates are allowed different variances. Bisection on a function decreasing in the variance.
    """
    lens = {s: len(yy) for s, (yy, _ss) in series.items()}
    short = [s for s, T in lens.items() if T <= max_len]

    def reading(v):
        return demeaned_lag1_under_ar1(series, rho, {s: (v if lens[s] <= max_len else 1.0) for s in series})

    lo = 1.0
    if not reading(hi) <= target <= reading(lo):
        return None, len(short)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if reading(mid) > target:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi)), len(short)


def upper_tail_p(null, obs):
    """The one-sided p-value for POSITIVE persistence: the rank of `obs` in the null the draws describe.

    The +1s are the observed statistic's own place in the reference set, which keeps the p-value valid (it can
    never be 0) -- the same convention the superseded distance-from-zero quantity used.
    """
    null = np.asarray(null, dtype=float)
    return float((1 + np.sum(null >= obs)) / (null.size + 1))


def two_sided_rank_p(null, obs):
    """Twice the smaller tail, capped at 1: two-sided about the null's own centre, not about zero."""
    null = np.asarray(null, dtype=float)
    lo = float((1 + np.sum(null <= obs)) / (null.size + 1))
    return float(min(1.0, 2 * min(upper_tail_p(null, obs), lo)))


def null_location(null):
    """Where the permutation null sits, so a p-value's direction can be checked against it by eye."""
    null = np.asarray(null, dtype=float)
    q = np.percentile(null, [2.5, 50, 97.5])
    return {"mean": float(null.mean()), "median": float(np.median(null)), "sd": float(null.std()),
            "pct2_5": float(q[0]), "pct97_5": float(q[2]),
            "share_below_zero": float((null < 0).mean()), "draws": int(null.size),
            "note": "demeaning within syndicate biases the pooled lag-1 correlation down by about 1/(T-1), so a "
                    "null centred well below zero is expected here and a p-value measured as distance from zero "
                    "is not a test of positive persistence."}


def within_syndicate_null(series, b, rng, stat):
    """Draws of `stat` under a permutation of each syndicate's own years, independently per syndicate."""
    out = []
    for _ in range(b):
        perm = {s: (yy, ss[rng.permutation(len(ss))]) for s, (yy, ss) in series.items()}
        out.append(stat(perm))
    return np.array([v for v in out if np.isfinite(v)])


def year_block_null(vals, syn, yr, b, rng, stat, min_obs=3):
    """Draws of `stat` under a permutation of the CALENDAR-YEAR LABELS, one permutation for all syndicates.

    Each reporting year's whole cross-section keeps its members and its values and moves to another year's place, so
    the systemic year component -- the exp(s_t) shock the model carries, and any common movement in a year -- is
    left intact and only temporal adjacency is destroyed. This is the null for serial dependence GIVEN the year.
    """
    years = np.array(sorted(set(np.asarray(yr).tolist())))
    out = []
    for _ in range(b):
        relabel = dict(zip(years.tolist(), rng.permutation(years).tolist()))
        yr2 = np.array([relabel[int(t)] for t in yr])
        out.append(stat(series_by_synd(vals, syn, yr2, min_obs=min_obs)))
    return np.array([v for v in out if np.isfinite(v)])


def simulate_panel(series, year_rho, syn_rho, rng):
    """A panel on THESE syndicates' own year sets: a common reporting-year component with lag-1
    correlation `year_rho`, plus a per-syndicate AR(1) with lag-1 correlation `syn_rho`.

    At syn_rho = 0 nothing is serially dependent WITHIN a syndicate, which is the null the pooling
    likelihood's conditional independence asserts; the year component is still there, because it is
    in the data and in the model (as exp(s_t)), and a null that cannot tolerate it is the wrong null.
    """
    years = sorted({int(y) for _s, (yy, _ss) in series.items() for y in yy})
    a = {}
    prev = rng.normal()
    for i, y in enumerate(years):
        prev = prev if i == 0 else year_rho * prev + rng.normal() * np.sqrt(max(1e-12, 1 - year_rho ** 2))
        a[y] = prev
    vals, syn, yr = [], [], []
    for s, (yy, _ss) in series.items():
        e, prev = [], rng.normal()
        for i in range(len(yy)):
            prev = prev if i == 0 else syn_rho * prev + rng.normal() * np.sqrt(max(1e-12, 1 - syn_rho ** 2))
            e.append(prev)
        for i, y in enumerate(yy):
            vals.append(a[int(y)] + 0.5 * e[i])
            syn.append(s)
            yr.append(int(y))
    return np.array(vals), np.array(syn), np.array(yr)


def calibrate_nulls(series, reps=CAL_REPS, perms=CAL_PERMS, seed=CAL_SEED):
    """The size and the power of the two nulls, measured on these year sets, for BOTH statistics.

    Returns {design: {method: {null: rejection share}}} at CAL_ALPHA, one-sided for positive
    persistence, over `reps` simulated panels. `unadjusted` is the within-syndicate permutation the
    published statistic used; `per_year_adjusted` takes each reporting year's location and scale out
    of the cross-section before the same permutation.

    Both Pearson and Spearman, because the section leads with the rank statistic: calibrating one and
    reporting the other would leave the reported p-value's behaviour unmeasured, which is the defect
    this whole check exists to correct.
    """
    rng = np.random.default_rng(seed)
    out = {}
    for design, syn_rho in (("common_year_component_only", 0.0), ("within_syndicate_ar1", CAL_SYN_RHO)):
        hits = {m: {"unadjusted": 0, "per_year_adjusted": 0} for m in ("pearson", "spearman")}
        for _ in range(reps):
            vals, syn, yr = simulate_panel(series, CAL_YEAR_RHO, syn_rho, rng)
            for name, vec in (("unadjusted", vals), ("per_year_adjusted", per_year_adjusted(vals, yr))):
                ser = series_by_synd(vec, syn, yr, min_obs=3)
                for method in ("pearson", "spearman"):
                    obs = pooled_lag1(ser, method)
                    null = within_syndicate_null(ser, perms, rng,
                                                 lambda s, m=method: pooled_lag1(s, m))
                    hits[method][name] += int(upper_tail_p(null, obs) < CAL_ALPHA)
        out[design] = {m: {k: v / float(reps) for k, v in d.items()} for m, d in hits.items()}
    return out


def pooled_lag1(series, method="pearson"):
    """(a)'s statistic on any series dict: demean within syndicate, keep consecutive-year pairs, pool, correlate."""
    x, y = lag_pairs(series, 1)
    return float(corr(x, y, method)) if len(x) >= 3 else np.nan


def per_year_adjusted(z, yr):
    """z with each reporting year's own median and robust scale removed from its cross-section.

    The model's year shock is a multiplicative scale common to a year; a common movement in a year is a location.
    Taking both out conditions on the year explicitly, so what survives is within-syndicate and not systemic.
    """
    out = np.array(z, dtype=float, copy=True)
    for t in sorted(set(np.asarray(yr).tolist())):
        m = np.asarray(yr) == t
        med = float(np.median(out[m]))
        sc = float(1.4826 * np.median(np.abs(out[m] - med)))
        out[m] = (out[m] - med) / (sc if sc > 0 else 1.0)
    return out


def benchmark_monte_carlo(series, rho, draws, seed):
    """The same quantity by simulation, drawn on the real year sets and pooled through lag_pairs itself.

    The closed form is only worth printing if it is the population value of the statistic the section reports, so
    the check measures that rather than asserting it: it draws AR(1) paths over each syndicate's own years,
    demeans and pools exactly as (a) does, and records how far the two are apart.
    """
    rng = np.random.default_rng(seed)
    chol = {}
    for s, (yy, _ss) in series.items():
        y = np.asarray(yy, dtype=float)
        cov = float(rho) ** np.abs(y[:, None] - y[None, :])
        chol[s] = np.linalg.cholesky(cov + 1e-12 * np.eye(y.size))
    xs, ys = [], []
    for _ in range(draws):
        sim = {s: (yy, chol[s] @ rng.standard_normal(len(yy))) for s, (yy, _ss) in series.items()}
        a, b = lag_pairs(sim, 1)
        xs.append(a)
        ys.append(b)
    x, y = np.concatenate(xs), np.concatenate(ys)
    return float(np.corrcoef(x, y)[0, 1])


def corr(x, y, method):
    if len(x) < 3:
        return np.nan
    return (stats.pearsonr(x, y)[0] if method == "pearson"
            else stats.spearmanr(x, y)[0])


def main():
    S, syn, yr = load()
    series = series_by_synd(S, syn, yr, min_obs=3)
    n_syn = len(series)
    x1, y1 = lag_pairs(series, 1)
    x2, y2 = lag_pairs(series, 2)
    print(f"n_syndicates(>=3 obs)={n_syn}  lag-1 pairs={len(x1)}  lag-2 pairs={len(x2)}")

    r1_p = corr(x1, y1, "pearson"); r1_s = corr(x1, y1, "spearman")
    r2_p = corr(x2, y2, "pearson"); r2_s = corr(x2, y2, "spearman")
    # raw (NOT de-meaned) lag-1: carries the persistent per-syndicate level AND any serial component together. It
    # said "not dynamics" until R222; demeaning does not separate the two, it bounds the serial one, which is (e).
    rx1, ry1 = lag_pairs(series, 1, demean=False)
    r1_raw_p = corr(rx1, ry1, "pearson"); r1_raw_s = corr(rx1, ry1, "spearman")

    # (a) syndicate-block bootstrap CI on lag-1 Pearson
    keys = list(series.keys())
    rng = np.random.default_rng(SEED)
    boot = []
    for _ in range(B):
        pick = rng.choice(len(keys), len(keys), replace=True)
        sub = {i: series[keys[p]] for i, p in enumerate(pick)}
        bx, by = lag_pairs(sub, 1)
        if len(bx) >= 3:
            boot.append(stats.pearsonr(bx, by)[0])
    boot = np.array(boot)
    ci = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]

    # within-syndicate year-permutation null (destroys serial order, keeps each syndicate's own values). The rng
    # continues the stream the bootstrap above used, so these draws are the ones the superseded p-value was read
    # from and the two quantities are comparable on the same null.
    null_a = within_syndicate_null(series, B, rng, lambda ser: pooled_lag1(ser, "pearson"))
    p_up = upper_tail_p(null_a, r1_p)
    p_two = two_sided_rank_p(null_a, r1_p)
    p_abs_zero = float((1 + np.sum(np.abs(null_a) >= abs(r1_p))) / (null_a.size + 1))

    # (c) direction persistence
    same_sign = []
    for s, (yy, ss) in series.items():
        for i in range(len(yy) - 1):
            if yy[i + 1] == yy[i] + 1 and ss[i] != 0 and ss[i + 1] != 0:
                same_sign.append(np.sign(ss[i]) == np.sign(ss[i + 1]))
    same_sign = np.array(same_sign)
    share_same = float(same_sign.mean())
    binom_p = float(stats.binomtest(int(same_sign.sum()), len(same_sign), 0.5).pvalue)

    # (e) what the demeaned statistic would read under dynamics alone, with the simulation that checks it
    mc_value = benchmark_monte_carlo(series, MC_RHO, MC_DRAWS, MC_SEED)
    if abs(mc_value - demeaned_lag1_under_ar1(series, MC_RHO)) > MC_TOL:
        raise SystemExit("the demeaning benchmark disagrees with the simulation of the same statistic: %.4f against "
                         "%.4f" % (demeaned_lag1_under_ar1(series, MC_RHO), mc_value))

    # (d) effective-sample factor from lag-1 rho
    rho = r1_p
    vif_factor = float((1 + rho) / (1 - rho)) if abs(rho) < 1 else np.inf

    # (e) the counterexample: is there a level-free process at the observed RAW lag-1 that reads the observed
    # DEMEANED one? If there is, the contrast between them excludes nothing.
    ce_var, n_short = short_history_variance_reading(series, float(r1_raw_p), float(r1_p))

    # (f) the same directed test on the adopted model's own residuals. sigma_it comes from
    # adopted_model.sigma_numeric, so the residual is this model's and not a second scale typed here.
    import adopted_model as AM
    S_m, R_m, H_m, yr_m, syn_m, ritc_m = AM.load_sample()
    if not (len(S_m) == len(S) and np.allclose(S_m, S) and np.array_equal(yr_m, yr)):
        raise SystemExit("adopted_model.load_sample and this script's load() disagree on the sample, so the "
                         "residuals would not belong to the observations (f) pairs")
    z = S_m / AM.sigma_numeric(R_m, H_m, ritc_m)
    z_year = per_year_adjusted(z, yr_m)
    cond = {}
    for tag, vec, note in (
            ("year_block_permutation", z,
             "the calendar-year labels permuted, one permutation for every syndicate, so each reporting year's "
             "cross-section keeps its members and its values. It destroys the temporal ARRANGEMENT of the year "
             "blocks as well as each syndicate's serial order, so it tests whether the reporting years are "
             "exchangeable in time and cannot separate a persistent common year component from within-syndicate "
             "dynamics. Reported because it is the weakest assumption of the three, not because it conditions on "
             "the year."),
            ("per_year_adjusted", z_year,
             "each reporting year's own median and robust scale removed from its cross-section first, then each "
             "syndicate's years permuted. This is the test that conditions on the year, and the one (g) shows to "
             "be correctly sized: what it finds is within-syndicate and not the systemic year component.")):
        ser = series_by_synd(vec, syn_m, yr_m, min_obs=3)
        entry = {"note": note}
        for method in ("pearson", "spearman"):
            obs = pooled_lag1(ser, method)
            rng_f = np.random.default_rng(SEED)
            if tag == "year_block_permutation":
                null = year_block_null(vec, syn_m, yr_m, B, rng_f, lambda s, m=method: pooled_lag1(s, m))
            else:
                null = within_syndicate_null(ser, B, rng_f, lambda s, m=method: pooled_lag1(s, m))
            entry[method] = {"observed": float(obs),
                             "p_upper_positive_persistence": upper_tail_p(null, obs),
                             "p_two_sided_rank": two_sided_rank_p(null, obs),
                             "permutation_null": null_location(null)}
        cond[tag] = entry

    # (g) which of those nulls is the right one, measured rather than asserted, for both statistics.
    # The guards run over BOTH: the section leads with the rank statistic, and a guard that only
    # watched the other one would leave the reported p-value's behaviour unguarded.
    cal = calibrate_nulls(series)
    size_all = cal["common_year_component_only"]
    power_all = cal["within_syndicate_ar1"]
    for method in ("pearson", "spearman"):
        size, power = size_all[method], power_all[method]
        if size["per_year_adjusted"] > CAL_MAX_SIZE_ADJUSTED:
            raise SystemExit("the per-year-adjusted %s test is not correctly sized on these year sets: it "
                             "rejects %.2f of panels that have a common year component and no within-syndicate "
                             "dynamics" % (method, size["per_year_adjusted"]))
        if size["unadjusted"] < CAL_MIN_SIZE_UNADJUSTED:
            raise SystemExit("the unadjusted within-syndicate permutation no longer over-rejects the %s "
                             "statistic under a common year component (%.2f), so the reason this section gives "
                             "for adjusting is not the reason" % (method, size["unadjusted"]))
        if power["per_year_adjusted"] < CAL_MIN_POWER:
            raise SystemExit("the per-year-adjusted %s test has no power against within-syndicate AR(1) on "
                             "these year sets (%.2f), so a non-rejection from it would mean nothing"
                             % (method, power["per_year_adjusted"]))

    out = {
        "unit": "syndicate-year, consecutive years within syndicate",
        "n_syndicates_ge3obs": n_syn, "n_lag1_pairs": int(len(x1)),
        "n_lag2_pairs": int(len(x2)), "B": B, "seed": SEED,
        "a_lag1_demeaned": {
            "pearson": float(r1_p), "spearman": float(r1_s),
            "block_bootstrap_ci95": ci,
            "alternative": "positive persistence (one-sided); the null is the within-syndicate permutation",
            "p_upper_positive_persistence": float(p_up),
            "p_two_sided_rank": float(p_two),
            "permutation_null": null_location(null_a),
            "p_absolute_distance_from_zero_superseded": float(p_abs_zero),
            "superseded_note": "p_absolute_distance_from_zero_superseded is the quantity published until the "
                               "frozen review of 25 September 2026 (M01): the share of permutations further from "
                               "ZERO than the observed statistic. It is not a test of positive persistence, "
                               "because this null is centred near the mean recorded in permutation_null and not "
                               "at zero. It is kept so the change is visible, and it is not to be read as a "
                               "p-value for dependence.",
            "block_bootstrap_note": "the interval is for the demeaned STATISTIC, which is biased down by the "
                                    "demeaning; it is not an interval for an underlying AR coefficient. "
                                    "e_demeaning_benchmark maps the statistic onto one under stated assumptions."},
        "a_lag1_raw_level": {"pearson": float(r1_raw_p), "spearman": float(r1_raw_s),
                             "note": "not de-meaned; carries the persistent per-syndicate level (sign), "
                                     "i.e. the mu=0 boundary (check 6), and any serial component together. "
                                     "The demeaned statistic does not separate them: see "
                                     "e_demeaning_benchmark for how strong a level-free AR(1) could be and "
                                     "still read as (a)."},
        "b_lag2": {"pearson": float(r2_p), "spearman": float(r2_s)},
        "c_direction_persistence": {"share_same_sign": share_same,
                                    "n_pairs": int(len(same_sign)),
                                    "binomial_p_vs_50pct": binom_p},
        "d_effective_sample": {"lag1_rho": float(rho),
                               "variance_inflation_1plusrho_over_1minusrho": vif_factor,
                               "interpretation": "the factor is read off the DEMEANED statistic, which the "
                                                 "demeaning biases down, so a value near 1 says nothing about "
                                                 "whether dependence is present: under the correctly directed "
                                                 "test in (a) and (f) it is. The factor is kept as the arithmetic "
                                                 "of a stationary finite-variance AR(1) at that rho and nothing "
                                                 "more; the consequence for the fit is measured in "
                                                 "check_serial_sensitivity.py, and the persistent syndicate "
                                                 "intercept is tested directly in "
                                                 "check_syndicate_random_effect.py."},
        "f_conditional_on_adopted_model": {
            "residual": "z_it = S_it / sigma_it, sigma_it from adopted_model.sigma_numeric at the published "
                        "posterior means: the conditional scale in size, HHI and regime that the likelihood "
                        "assumes the severities are independent given.",
            "why": "permuting unstandardised severities tests exchangeability of the raw ratios, not the fitted "
                   "model's conditional independence. This does (frozen review of 25 September 2026, M01).",
            "primary": "spearman under per_year_adjusted. The fitted regimes are Student-t with nu about 5, where a "
                       "rank statistic is the better-behaved one, and (g) measures the per-year-adjusted null to be "
                       "the correctly sized one: the unadjusted within-syndicate permutation rejects panels that "
                       "carry only a common reporting-year component, which these data do carry.",
            "tests": cond},
        "g_null_calibration": {
            "question": "which of these permutation nulls is the right one, on these syndicates' year sets?",
            "panels_per_design": CAL_REPS, "permutations_per_panel": CAL_PERMS, "alpha": CAL_ALPHA,
            "year_component_lag1": CAL_YEAR_RHO, "alternative_within_syndicate_lag1": CAL_SYN_RHO,
            "seed": CAL_SEED,
            "design": ("panels simulated on the real year sets: a common reporting-year component with lag-1 "
                       "correlation %.2f, plus a per-syndicate AR(1) with lag-1 correlation %.2f in the "
                       "alternative and none in the null. %d panels each, %d permutations each, one-sided at "
                       "alpha = %.2f." % (CAL_YEAR_RHO, CAL_SYN_RHO, CAL_REPS, CAL_PERMS, CAL_ALPHA)),
            "rejection_shares": cal,
            "statistics": "both, because the section leads with the rank statistic: calibrating one and "
                          "reporting the other would leave the reported p-value's behaviour unmeasured.",
            "reading": ("common_year_component_only is SIZE: nothing is serially dependent within a syndicate "
                        "there, so a correctly sized test rejects about alpha of the time. within_syndicate_ar1 "
                        "is POWER. The unadjusted within-syndicate permutation is the null the published statistic "
                        "used, and its size here is the reason the section's finding rests on the adjusted test "
                        "instead: permuting a syndicate's own years destroys its alignment with the calendar, so a "
                        "common year component lands in the observed statistic and not in the null."),
            "limits": ("%d panels per design fix each share only to about +/-0.1, which is enough to separate a "
                       "test near alpha from one near 1 and not enough to quote as a size. One year-component "
                       "correlation and one AR coefficient are examined, not a grid." % CAL_REPS)},
        "e_demeaning_benchmark": {
            "n_syndicates": len(series),
            "n_with_a_gap_in_their_years": sum(1 for _s, (yy, _ss) in series.items()
                                               if any(yy[i + 1] != yy[i] + 1 for i in range(len(yy) - 1))),
            "observed_raw_lag1": float(r1_raw_p),
            "at_observed_raw_lag1": demeaned_lag1_under_ar1(series, r1_raw_p),
            "rho_reading_the_observed_demeaned": ar1_rho_reading(series, float(r1_p)),
            "rho_reading_the_interval_upper": ar1_rho_reading(series, float(ci[1])),
            "by_rho": [{"rho": r, "pooled_demeaned_lag1": demeaned_lag1_under_ar1(series, r)}
                       for r in (0.2, 0.4, 0.6, 0.8)],
            "monte_carlo_check": {"rho": MC_RHO, "draws": MC_DRAWS, "seed": MC_SEED,
                                  "closed_form": demeaned_lag1_under_ar1(series, MC_RHO),
                                  "simulated": mc_value,
                                  "difference": mc_value - demeaned_lag1_under_ar1(series, MC_RHO)},
            "assumptions": "ONE lag-1 correlation shared by every syndicate, the SAME marginal variance for every "
                           "syndicate, no intercept, stationary in calendar time. All four are assumptions, not "
                           "findings, and the reading is an illustration under them.",
            "heterogeneous_variance_reading": {
                "rho_reading_the_observed_demeaned": ar1_rho_reading(series, float(r1_p),
                                                                    variances=observed_variances(series)),
                "rho_reading_the_interval_upper": ar1_rho_reading(series, float(ci[1]),
                                                                  variances=observed_variances(series)),
                "at_observed_raw_lag1": demeaned_lag1_under_ar1(series, r1_raw_p,
                                                                observed_variances(series)),
                "note": "the same algebra with each syndicate's own observed variance in place of 1. It moves the "
                        "coefficient that reads the observed statistic, which is why the equal-variance figure is "
                        "an illustration and not a bound on the serial component (frozen review of 25 September "
                        "2026, D01)."},
            "counterexample_to_excluding_dynamics": {
                "rho": float(r1_raw_p),
                "short_history_max_years": 4,
                "n_short_histories": n_short,
                "variance_for_short_histories": ce_var,
                "reading": (None if ce_var is None
                            else demeaned_lag1_under_ar1(series, float(r1_raw_p),
                                                         {s: (ce_var if len(yy) <= 4 else 1.0)
                                                          for s, (yy, _ss) in series.items()})),
                "target_observed_demeaned": float(r1_p),
                "note": "a stationary AR(1) with NO persistent level, one lag-1 correlation equal to the observed "
                        "RAW statistic, variance 1 for the longer histories and this variance for the short ones, "
                        "reads the observed DEMEANED statistic. Both observed numbers therefore come out of a "
                        "process that is all dynamics and no level, so the raw-against-demeaned contrast excludes "
                        "dynamics at the raw level only if every syndicate has the same variance. It does not "
                        "exclude them here (frozen review of 25 September 2026, D01)."},
            "note": "What (a) would read, in the population, under a stationary AR(1) in calendar time with that "
                    "lag-1 correlation and no persistent per-syndicate level, after the same demeaning, grouped "
                    "as (a) groups: over a syndicate's whole series, keeping the consecutive-year pairs. "
                    "Demeaning biases the demeaned lag-1 correlation downward, so the raw-against-demeaned "
                    "contrast does not identify the level on its own (frozen review of 24 September 2026, D02). "
                    "monte_carlo_check draws AR(1) paths on the real year sets and pools them through lag_pairs, "
                    "so the closed form is measured and not asserted. What the contrast does NOT do is exclude "
                    "dynamics in general: it compares the data with ONE assumed process, and the same statistic "
                    "is reproduced by a process with no level at all once the variances are allowed to differ "
                    "(frozen review of 25 September 2026, D01)."},
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print("(a) lag-1 DEMEANED: Pearson %.3f [%.3f, %.3f], Spearman %.3f" % (r1_p, ci[0], ci[1], r1_s))
    print("    null mean %+.3f; p(positive persistence)=%.4f, two-sided rank %.4f; superseded distance-from-zero "
          "%.4f" % (null_a.mean(), p_up, p_two, p_abs_zero))
    print("    lag-1 RAW level: Pearson %.3f, Spearman %.3f" % (r1_raw_p, r1_raw_s))
    print("(b) lag-2 demeaned: Pearson %.3f, Spearman %.3f" % (r2_p, r2_s))
    print("(c) direction persistence: %.1f%% same-sign (%d pairs), binomial p vs 50pct=%.3f"
          % (100 * share_same, len(same_sign), binom_p))
    print("(d) lag-1 demeaned rho=%.3f -> AR(1) variance-inflation arithmetic %.3f (read off a downward-biased "
          "statistic; not a detection either way)" % (rho, vif_factor))
    for tag, entry in cond.items():
        print("(f) %-24s Pearson obs %+.4f p=%.4f (null %+.3f) | Spearman obs %+.4f p=%.4f (null %+.3f)"
              % (tag, entry["pearson"]["observed"], entry["pearson"]["p_upper_positive_persistence"],
                 entry["pearson"]["permutation_null"]["mean"], entry["spearman"]["observed"],
                 entry["spearman"]["p_upper_positive_persistence"],
                 entry["spearman"]["permutation_null"]["mean"]))
    print("(g) null calibration on these year sets, %d panels at alpha=%.2f:" % (CAL_REPS, CAL_ALPHA))
    for design, by_method in cal.items():
        for method, shares in by_method.items():
            print("    %-28s %-9s unadjusted %.2f   per-year-adjusted %.2f"
                  % (design, method, shares["unadjusted"], shares["per_year_adjusted"]))


if __name__ == "__main__":
    sys.exit(main())
