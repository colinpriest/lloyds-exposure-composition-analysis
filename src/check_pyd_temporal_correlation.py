"""Temporal correlation of the PYD-severity ratio across consecutive years, within
syndicate (syndicate-year unit).

Why it matters: the pooling likelihood treats a syndicate's yearly severities as
conditionally independent given size/HHI (mu=0, no within-syndicate serial term). If
S = PYD/reserves is strongly autocorrelated year-to-year within a syndicate, that
independence is violated and the effective sample is smaller than n. This tests it.

Reports, on consecutive-year pairs (t, t+1) within each syndicate, de-meaned per syndicate:
  (a) pooled lag-1 autocorrelation of S (Pearson and Spearman), with a syndicate-block
      bootstrap 95% CI and a within-syndicate year-permutation one-sided p-value;
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
      level: it bounds the serial component instead. It records the lag-1 correlation that would
      read the observed (a), the largest that would still fall inside its interval, what the
      observed raw lag-1 would read, and a simulation of the same statistic on the real year sets
      that checks the closed form (frozen review of 24 September 2026, D02).

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


def demeaned_lag1_under_ar1(series, rho):
    """The pooled lag-1 correlation these syndicates would show, in the population, under a stationary AR(1) in
    CALENDAR time with lag-1 correlation `rho` and no persistent per-syndicate level, after the same demeaning (a).

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
        cov = float(rho) ** np.abs(y[:, None] - y[None, :])
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


def ar1_rho_reading(series, target, hi=0.99):
    """The lag-1 correlation of a level-free AR(1) whose demeaned statistic equals `target` on these series, or None
    when no rho in (0, hi] reads it. Bisection on a function that increases in rho; no solver dependency."""
    lo, f_lo, f_hi = 0.0, demeaned_lag1_under_ar1(series, 0.0), demeaned_lag1_under_ar1(series, hi)
    if not f_lo <= target <= f_hi:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if demeaned_lag1_under_ar1(series, mid) < target:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


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
    # raw (NOT de-meaned) lag-1: captures persistent per-syndicate level, not dynamics
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

    # within-syndicate year-permutation null (destroys serial order, keeps marginals)
    ge = 0
    for _ in range(B):
        perm = {}
        for s, (yy, ss) in series.items():
            p = rng.permutation(len(ss))
            perm[s] = (yy, ss[p])
        px, py = lag_pairs(perm, 1)
        rp = stats.pearsonr(px, py)[0] if len(px) >= 3 else 0.0
        ge += abs(rp) >= abs(r1_p)
    p_perm = (1 + ge) / (B + 1)

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

    out = {
        "unit": "syndicate-year, consecutive years within syndicate",
        "n_syndicates_ge3obs": n_syn, "n_lag1_pairs": int(len(x1)),
        "n_lag2_pairs": int(len(x2)), "B": B, "seed": SEED,
        "a_lag1_demeaned": {"pearson": float(r1_p), "spearman": float(r1_s),
                            "block_bootstrap_ci95": ci, "permutation_p_two_sided": float(p_perm)},
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
                               "interpretation": "≈1 means this diagnostic detects no "
                                                 "residual within-syndicate temporal "
                                                 "dependence. That is a failure to detect, "
                                                 "not a demonstration that the pooling "
                                                 "likelihood's conditional-independence "
                                                 "assumption holds; the persistent "
                                                 "syndicate intercept is tested directly in "
                                                 "check_syndicate_random_effect.py, where "
                                                 "tau_alpha = 0.041."},
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
            "note": "What (a) would read, in the population, under a stationary AR(1) in calendar time with that "
                    "lag-1 correlation and no persistent per-syndicate level, after the same demeaning, grouped "
                    "as (a) groups: over a syndicate's whole series, keeping the consecutive-year pairs. "
                    "Demeaning biases the demeaned lag-1 correlation downward, so the raw-against-demeaned "
                    "contrast does not identify the level on its own: it bounds the serial component instead "
                    "(frozen review of 24 September 2026, D02). monte_carlo_check draws AR(1) paths on the real "
                    "year sets and pools them through lag_pairs, so the closed form is measured and not asserted."},
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print("(a) lag-1 DEMEANED: Pearson %.3f [%.3f, %.3f], Spearman %.3f, permutation p=%.3f"
          % (r1_p, ci[0], ci[1], r1_s, p_perm))
    print("    lag-1 RAW level: Pearson %.3f, Spearman %.3f" % (r1_raw_p, r1_raw_s))
    print("(b) lag-2 demeaned: Pearson %.3f, Spearman %.3f" % (r2_p, r2_s))
    print("(c) direction persistence: %.1f%% same-sign (%d pairs), binomial p vs 50pct=%.3f"
          % (100 * share_same, len(same_sign), binom_p))
    print("(d) lag-1 demeaned rho=%.3f -> variance-inflation factor %.3f (~1: no residual temporal dependence detected by this diagnostic)"
          % (rho, vif_factor))


if __name__ == "__main__":
    sys.exit(main())
