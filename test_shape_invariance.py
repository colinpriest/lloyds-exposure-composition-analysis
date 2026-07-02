"""Shape-invariance tests for the donor->target severity rescaling.

The donor->target rescaling (vignettes / distortion tool) assumes the PYD
severity  s = signed_pyd / opening_reserves  behaves as a *scale family with
location 0*:  s | (size R, mix HHI) has

    location  = 0                (mean-zero: tested elsewhere, holds)
    scale     = sqrt(V(R,HHI))   (power-law dispersion model, N5)
    SHAPE     = invariant        <-- what this script tests

If shape is invariant then, after removing location and scale, the *shape* of
the distribution (skewness, kurtosis, tail asymmetry) must not depend on where
in the (R, HHI) space an observation sits.  If it does, transporting a donor's
shape to a target at different coordinates is not justified by mere linear
scaling.

We test this model-free: robust shape statistics that are invariant to any
linear rescale (Bowley skewness, Moors kurtosis, tail-spread ratio) are
computed within groups along each axis (size R, mix HHI) and tested for
constancy.  Being scale/location invariant, these sidestep any mis-
specification of the variance model itself -- a cleaner test of the shape
assumption alone.  A k-sample Anderson-Darling test on group-standardised
values provides a full-distribution complement.

All p-values / CIs use a CLUSTER bootstrap that resamples *syndicates*, since
a syndicate contributes multiple correlated syndicate-years.

Run:  python test_shape_invariance.py
"""

import sys
import warnings
import numpy as np
from scipy import stats

import run_analysis as ra

SEED = 12345
N_BOOT = 4000


# ── robust, scale/location-invariant shape statistics ────────────────────────
def _q(a, p):
    return float(np.percentile(a, p, method="linear"))


def bowley_skew(a):
    """(Q3 + Q1 - 2 Q2) / (Q3 - Q1).  Symmetric -> 0."""
    q1, q2, q3 = _q(a, 25), _q(a, 50), _q(a, 75)
    d = q3 - q1
    return (q3 + q1 - 2 * q2) / d if d > 0 else np.nan


def tail_skew_ratio(a):
    """(Q90 - Q50) / (Q50 - Q10).  Symmetric -> 1; >1 = heavier right tail."""
    q10, q50, q90 = _q(a, 10), _q(a, 50), _q(a, 90)
    lo = q50 - q10
    return (q90 - q50) / lo if lo > 0 else np.nan


def moors_kurt(a):
    """Octile-based kurtosis ((E7-E5)+(E3-E1))/(E6-E2).  Normal ~ 1.233."""
    e = {i: _q(a, 100.0 * i / 8.0) for i in range(1, 8)}
    d = e[6] - e[2]
    return ((e[7] - e[5]) + (e[3] - e[1])) / d if d > 0 else np.nan


def robust_scale(a):
    """IQR (used to standardise a group to unit spread for the AD test)."""
    return _q(a, 75) - _q(a, 25)


SHAPE_STATS = {
    "Bowley skew": bowley_skew,
    "Tail skew ratio": tail_skew_ratio,
    "Moors kurtosis": moors_kurt,
}


# ── cluster bootstrap ────────────────────────────────────────────────────────
def cluster_bootstrap_diff(s, cluster, group, stat_fn, g_top, g_bot, rng, n=N_BOOT):
    """Bootstrap CI for stat(top group) - stat(bottom group).

    Resamples whole clusters (syndicates).  Group membership is fixed
    (thresholds from the full sample), so a resampled syndicate keeps its
    observations' original group labels.
    """
    clusters = np.unique(cluster)
    idx_by_cluster = {c: np.where(cluster == c)[0] for c in clusters}
    diffs = []
    for _ in range(n):
        pick = rng.choice(clusters, size=len(clusters), replace=True)
        rows = np.concatenate([idx_by_cluster[c] for c in pick])
        sg, gg = s[rows], group[rows]
        top, bot = sg[gg == g_top], sg[gg == g_bot]
        if len(top) < 8 or len(bot) < 8:
            continue
        diffs.append(stat_fn(top) - stat_fn(bot))
    diffs = np.array([d for d in diffs if np.isfinite(d)])
    if len(diffs) < n * 0.5:
        return None
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    # two-sided bootstrap p for H0: diff == 0
    p = 2.0 * min((diffs <= 0).mean(), (diffs >= 0).mean())
    return {"point": float(np.median(diffs)), "ci": (float(lo), float(hi)),
            "p": float(min(p, 1.0)), "n_boot": len(diffs)}


def cluster_bootstrap_slope(s, cluster, axis, stat_fn, rng, n_bins=10, n=N_BOOT):
    """Bootstrap the OLS slope of a per-bin shape stat vs bin index.

    Non-zero slope => shape drifts monotonically along the axis.
    """
    clusters = np.unique(cluster)
    idx_by_cluster = {c: np.where(cluster == c)[0] for c in clusters}

    def slope_for(rows):
        sx, ax = s[rows], axis[rows]
        edges = np.percentile(ax, np.linspace(0, 100, n_bins + 1))
        edges[-1] += 1e-9
        b = np.clip(np.digitize(ax, edges) - 1, 0, n_bins - 1)
        xs, ys = [], []
        for k in range(n_bins):
            vals = sx[b == k]
            if len(vals) >= 12:
                st = stat_fn(vals)
                if np.isfinite(st):
                    xs.append(k)
                    ys.append(st)
        if len(xs) < 4:
            return np.nan
        return float(np.polyfit(xs, ys, 1)[0])

    obs_slope = slope_for(np.arange(len(s)))
    boots = []
    for _ in range(n):
        pick = rng.choice(clusters, size=len(clusters), replace=True)
        rows = np.concatenate([idx_by_cluster[c] for c in pick])
        v = slope_for(rows)
        if np.isfinite(v):
            boots.append(v)
    boots = np.array(boots)
    if len(boots) < n * 0.5:
        return {"slope": obs_slope, "ci": None, "p": None}
    lo, hi = np.percentile(boots, [2.5, 97.5])
    p = 2.0 * min((boots <= 0).mean(), (boots >= 0).mean())
    return {"slope": float(obs_slope), "ci": (float(lo), float(hi)),
            "p": float(min(p, 1.0)), "n_boot": len(boots)}


def anderson_ksample_shape(s, group):
    """k-sample Anderson-Darling on group-standardised values.

    Each group is centred by its median and scaled by its IQR, so location and
    scale are removed and only SHAPE differences remain.  Returns (stat, p).
    """
    samples = []
    for g in np.unique(group):
        a = s[group == g]
        sc = robust_scale(a)
        if sc > 0 and len(a) >= 8:
            samples.append((a - _q(a, 50)) / sc)
    if len(samples) < 2:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = stats.anderson_ksamp(samples)
    p = getattr(res, "pvalue", None)
    if p is None:
        p = res.significance_level
    return {"stat": float(res.statistic), "p": float(p), "k": len(samples)}


def make_groups(axis, n_groups):
    edges = np.percentile(axis, np.linspace(0, 100, n_groups + 1))
    edges[-1] += 1e-9
    return np.clip(np.digitize(axis, edges) - 1, 0, n_groups - 1)


# ── one axis (size or mix) ───────────────────────────────────────────────────
def analyse_axis(name, axis, s, cluster, rng, n_quartiles=4):
    print(f"\n{'='*74}\n  AXIS: {name}\n{'='*74}")
    grp = make_groups(axis, n_quartiles)

    # per-group descriptive shape table
    hdr = f"  {'group':<7}{'n':>5}{'axis med':>12}{'s median':>11}{'IQR':>9}" \
          f"{'Bowley':>9}{'tailR':>8}{'Moors':>8}"
    print(hdr)
    for g in range(n_quartiles):
        a = s[grp == g]
        ax = axis[grp == g]
        print(f"  Q{g+1:<6}{len(a):>5}{np.median(ax):>12.3g}{_q(a,50):>11.4f}"
              f"{robust_scale(a):>9.4f}{bowley_skew(a):>9.3f}"
              f"{tail_skew_ratio(a):>8.2f}{moors_kurt(a):>8.3f}")

    # location check across groups (should be flat if mean-zero holds)
    kw = stats.kruskal(*[s[grp == g] for g in range(n_quartiles)])
    print(f"\n  Location (Kruskal-Wallis, medians equal?):  H={kw.statistic:.2f}  p={kw.pvalue:.3f}")

    # full-distribution SHAPE test
    ad = anderson_ksample_shape(s, grp)
    if ad:
        verdict = "SHAPE DIFFERS" if ad["p"] < 0.05 else "no shape difference"
        print(f"  Shape (Anderson-Darling k-sample, group-standardised):"
              f"  A2k={ad['stat']:.2f}  p={ad['p']:.3f}  -> {verdict}")

    # extreme-group differences with cluster bootstrap CI
    print(f"\n  Extreme-group shape difference (Q{n_quartiles} - Q1), cluster bootstrap:")
    for label, fn in SHAPE_STATS.items():
        res = cluster_bootstrap_diff(s, cluster, grp, fn, n_quartiles - 1, 0, rng)
        if res:
            sig = "  *** " if res["p"] < 0.05 else "      "
            print(f"    {label:<16} diff={res['point']:+.3f}  "
                  f"95% CI [{res['ci'][0]:+.3f}, {res['ci'][1]:+.3f}]  "
                  f"p={res['p']:.3f}{sig}")

    # monotone trend across deciles
    print(f"\n  Monotone trend across deciles (OLS slope of stat vs decile index):")
    for label, fn in SHAPE_STATS.items():
        res = cluster_bootstrap_slope(s, cluster, axis, fn, rng)
        if res.get("ci"):
            sig = "  *** " if res["p"] < 0.05 else "      "
            print(f"    {label:<16} slope={res['slope']:+.4f}/decile  "
                  f"95% CI [{res['ci'][0]:+.4f}, {res['ci'][1]:+.4f}]  "
                  f"p={res['p']:.3f}{sig}")
        else:
            print(f"    {label:<16} slope={res['slope']:+.4f}/decile  (CI unavailable)")


def build_population():
    records, counters, _clog, _files = ra.load_and_classify()
    ra.assign_event_groups(records)
    _subsets, subset_records = ra.build_subsets(records)
    ra.compute_eligibility(records, subset_records)
    return records


def select(records, mode):
    if mode == "N5":
        # exactly the population the dispersion model / rescaling is fit on
        return [r for r in records
                if r.get("eligible_for_n3", False)
                and r["s_raw_a"] is not None
                and r.get("hhi") is not None
                and r.get("hhi", 1.0) < 0.99
                and r.get("weight_source") != "none"
                and r["opening_reserves_gbp_m"] is not None
                and r["opening_reserves_gbp_m"] > 0]
    # broader: any observation with severity, reserves and a mix (more power)
    return [r for r in records
            if r["s_raw_a"] is not None
            and r.get("hhi") is not None
            and r.get("hhi", 1.0) < 0.99
            and r["opening_reserves_gbp_m"] is not None
            and r["opening_reserves_gbp_m"] > 0]


def run_for(records, mode):
    rng = np.random.default_rng(SEED)
    rows = select(records, mode)
    s = np.array([r["s_raw_a"] for r in rows], float)
    R = np.array([r["opening_reserves_gbp_m"] for r in rows], float)
    HHI = np.array([r["hhi"] for r in rows], float)
    cluster = np.array([r["syndicate"] for r in rows])
    n_synd = len(np.unique(cluster))

    print(f"\n\n{'#'*74}\n#  POPULATION: {mode}   (n_obs={len(rows)}, n_syndicates={n_synd})\n{'#'*74}")
    print(f"  severity s: mean={s.mean():+.4f}  median={np.median(s):+.4f}  "
          f"sd={s.std():.4f}  min={s.min():+.3f}  max={s.max():+.3f}")
    if len(rows) < 60:
        print("  (too few observations for a reliable shape test)")
        return
    analyse_axis("SIZE  (opening reserves, GBP m)", R, s, cluster, rng)
    analyse_axis("MIX   (HHI; higher = more concentrated)", HHI, s, cluster, rng)


def main():
    print("Shape-invariance tests for donor->target severity rescaling")
    print(f"(cluster bootstrap: {N_BOOT} resamples of syndicates; seed={SEED})")
    records = build_population()
    run_for(records, "N5")     # primary: matches the fitted rescaling population
    run_for(records, "BROAD")  # sensitivity: wider net for statistical power
    print("\nInterpretation:")
    print("  * A significant Anderson-Darling p, a Q4-Q1 CI excluding 0, or a")
    print("    non-zero decile slope => the standardised shape (skew / kurtosis /")
    print("    tail asymmetry) drifts along that axis => shape is NOT invariant,")
    print("    so pure linear donor->target rescaling under-/over-states the tail.")
    print("  * Bowley skew & Moors kurtosis are invariant to any linear rescale,")
    print("    so these results are independent of the variance-model fit.")


if __name__ == "__main__":
    main()
