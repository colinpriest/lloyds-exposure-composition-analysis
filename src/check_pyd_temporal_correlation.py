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
      severities were a stationary AR(1) with a given lag-1 correlation and NO persistent
      level, after the same within-panel demeaning. Demeaning a short panel removes part of a
      serial process and leaves a bias of its own, so (a) against the raw statistic does not
      identify the level on its own. It records the lag-1 correlation that would read the
      observed (a), the largest that would still fall inside its interval, and what the
      observed raw lag-1 would read (frozen review of 24 September 2026, D02).

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
B = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
SEED = 42
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


def consecutive_runs(series):
    """Lengths of the maximal runs of consecutive years the lag-1 pairs are drawn from."""
    lengths = []
    for _s, (yy, _ss) in series.items():
        run = 1
        for i in range(1, len(yy)):
            if yy[i] == yy[i - 1] + 1:
                run += 1
            else:
                lengths.append(run)
                run = 1
        lengths.append(run)
    return [int(L) for L in lengths if L >= 2]


def demeaned_lag1_under_ar1(lengths, rho):
    """The pooled lag-1 correlation these panels would show, in the population, under a stationary AR(1) with
    lag-1 correlation `rho` and no persistent per-syndicate level, after the same within-panel demeaning.

    Exact covariance algebra, not simulation: for a run of length L the demeaned vector has covariance
    M @ Sigma @ M with Sigma_ij = rho^|i-j| and M = I - J/L, and the pooled statistic is the sum of the
    super-diagonal over the square root of the two shifted diagonal sums, runs weighted by how many there are.
    At L = 4 and rho = 0.6 it is -0.064: on short panels a process that is all dynamics and no level reads as no
    dynamics. These runs are longer, so the bias is milder and the statistic keeps some power.
    """
    num = den_a = den_b = 0.0
    for L, n in sorted(Counter(lengths).items()):
        if L < 2:
            continue
        ix = np.arange(L)
        cov = float(rho) ** np.abs(ix[:, None] - ix[None, :])
        m = np.eye(L) - np.ones((L, L)) / L
        c = m @ cov @ m
        num += n * float(np.diag(c, 1).sum())
        den_a += n * float(np.diag(c)[:-1].sum())
        den_b += n * float(np.diag(c)[1:].sum())
    if den_a <= 0 or den_b <= 0:
        raise ValueError("no run of two or more consecutive years")
    return float(num / np.sqrt(den_a * den_b))


def ar1_rho_reading(lengths, target, hi=0.99):
    """The lag-1 correlation of a level-free AR(1) whose demeaned statistic equals `target` on these runs, or None
    when no rho in (0, hi] reads it. Bisection on a function that increases in rho; no solver dependency."""
    lo, f_lo, f_hi = 0.0, demeaned_lag1_under_ar1(lengths, 0.0), demeaned_lag1_under_ar1(lengths, hi)
    if not f_lo <= target <= f_hi:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if demeaned_lag1_under_ar1(lengths, mid) < target:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


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

    # (e) what the demeaned statistic would read under dynamics alone, on these runs
    runs = consecutive_runs(series)

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
            "n_runs": len(runs), "run_lengths": {str(k): v for k, v in sorted(Counter(runs).items())},
            "observed_raw_lag1": float(r1_raw_p),
            "at_observed_raw_lag1": demeaned_lag1_under_ar1(runs, r1_raw_p),
            "rho_reading_the_observed_demeaned": ar1_rho_reading(runs, float(r1_p)),
            "rho_reading_the_interval_upper": ar1_rho_reading(runs, float(ci[1])),
            "by_rho": [{"rho": r, "pooled_demeaned_lag1": demeaned_lag1_under_ar1(runs, r)}
                       for r in (0.2, 0.4, 0.6, 0.8)],
            "note": "What (a) would read, in the population, under a stationary AR(1) with that lag-1 "
                    "correlation and no persistent per-syndicate level, after the same within-panel "
                    "demeaning. Demeaning biases the demeaned lag-1 correlation downward, so the "
                    "raw-against-demeaned contrast does not identify the level on its own: it bounds the "
                    "serial component instead (frozen review of 24 September 2026, D02)."},
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
