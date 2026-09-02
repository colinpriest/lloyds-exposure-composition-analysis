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
  (d) the implied variance-inflation / effective-sample factor (1+rho)/(1-rho) for rho=lag1.

Writes check_pyd_temporal_correlation_results.json.
Usage:  python src/check_pyd_temporal_correlation.py [B]
"""
import io, json, sys
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
                             "note": "not de-meaned; reflects persistent per-syndicate level "
                                     "(sign), i.e. the mu=0 boundary (check 6), not dynamics"},
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
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print("(a) lag-1 DEMEANED: Pearson %.3f [%.3f, %.3f], Spearman %.3f, permutation p=%.3f"
          % (r1_p, ci[0], ci[1], r1_s, p_perm))
    print("    lag-1 RAW level: Pearson %.3f, Spearman %.3f" % (r1_raw_p, r1_raw_s))
    print("(b) lag-2 demeaned: Pearson %.3f, Spearman %.3f" % (r2_p, r2_s))
    print("(c) direction persistence: %.1f%% same-sign (%d pairs), binomial p vs 50pct=%.3f"
          % (100 * share_same, len(same_sign), binom_p))
    print("(d) lag-1 demeaned rho=%.3f -> variance-inflation factor %.3f (~1 = temporally indep)"
          % (rho, vif_factor))


if __name__ == "__main__":
    sys.exit(main())
