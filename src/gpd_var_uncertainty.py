"""GPD-derived VaR99.5 uncertainty: 95% interval for the POT return level.

Reverse-direction check to the empirical intervals: for each tail distribution, fit a
generalised-Pareto (peaks-over-threshold) tail on every bootstrap replicate and report the
95% band for the GPD VaR99.5 return level, then state whether the empirical point falls
inside the GPD's own band.

Piggybacks on the same scheme as vignette_uncertainty.py: cluster (by-syndicate) bootstrap
of the donor pool x posterior draws of theta, B replicates, same seed.

Return level (POT), N = sample size, Nu = # exceedances above threshold u:
    VaR_0.995 = u + (sigma/xi) * [ ( (N/Nu)*(1-0.995) )^(-xi) - 1 ]
with the xi->0 continuity limit  u - sigma*ln( (N/Nu)*(1-0.995) ).

Run: python gpd_var_uncertainty.py [B] [seed] [threshold_pctile]
"""
import json, sys
from pathlib import Path
import numpy as np
from scipy import stats

from vignette_uncertainty import load_pool, load_draws, load_targets, transfer, build_resampler, load_ritc

SCRIPT_DIR = Path(__file__).resolve().parent.parent
B = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20240704
U_Q = float(sys.argv[3]) if len(sys.argv) > 3 else 90.0   # threshold = U_Q-th pctile of the sample
ALPHA = 0.995
# The empirical VaR99.5 comparator is COMPUTED from the same transferred sample
# the GPD is fitted to. It used to be a pair of literals from an earlier fit
# (0.427 / 0.407), which then travelled into the committed JSON and left the
# results directory reporting one vintage against another.


def gpd_var995(sample, uq):
    """POT GPD return level at 0.995 for a signed transferred-severity sample."""
    u = float(np.percentile(sample, uq, method="linear"))
    exc = sample[sample > u] - u
    Nu, N = len(exc), len(sample)
    if Nu < 10:
        return np.nan, np.nan, np.nan, Nu, u
    try:
        xi, _, sc = stats.genpareto.fit(exc, floc=0.0)
    except Exception:
        return np.nan, np.nan, np.nan, Nu, u
    if sc <= 0 or not np.isfinite(xi):
        return np.nan, np.nan, np.nan, Nu, u
    a = (N / Nu) * (1.0 - ALPHA)
    v = (u - sc * np.log(a)) if abs(xi) < 1e-6 else (u + (sc / xi) * (a ** (-xi) - 1.0))
    return float(v), float(xi), float(sc), Nu, u


def analyse(name, tgt, S, R, H, drawcl, draws, thbar, cfg, ndraw, rng, ritc):
    # point: full pool at posterior mean
    samp0 = transfer(S, R, H, tgt, thbar, cfg, ritc)
    pv, pxi, psc, pNu, pu = gpd_var995(samp0, U_Q)
    vs, xis, scs, nus = [], [], [], []
    for _ in range(B):
        idx = drawcl(rng)
        th = {p: draws[p][rng.integers(0, ndraw)] for p in draws}
        samp = transfer(S[idx], R[idx], H[idx], tgt, th, cfg, ritc[idx])
        v, xi, sc, nu, _ = gpd_var995(samp, U_Q)
        if np.isfinite(v):
            vs.append(v); xis.append(xi); scs.append(sc); nus.append(nu)
    vs = np.array(vs); xis = np.array(xis); scs = np.array(scs)
    lo, med, hi = (float(np.percentile(vs, q)) for q in (2.5, 50, 97.5))
    # point empirical VaR99.5 of the transferred sample, at the same alpha
    emp = float(np.percentile(samp0, 100.0 * ALPHA, method="linear"))
    return {
        "point_var995": pv, "point_threshold_u": pu, "point_Nu": pNu, "point_xi": pxi, "point_sigma": psc,
        "band_lo_2.5": lo, "band_median": med, "band_hi_97.5": hi,
        "median_Nu": float(np.median(nus)), "n_valid_reps": int(len(vs)),
        "xi_median": float(np.median(xis)), "xi_2.5": float(np.percentile(xis, 2.5)), "xi_97.5": float(np.percentile(xis, 97.5)),
        "sigma_median": float(np.median(scs)), "sigma_2.5": float(np.percentile(scs, 2.5)), "sigma_97.5": float(np.percentile(scs, 97.5)),
        "empirical": emp, "empirical_inside_band": bool(lo <= emp <= hi),
        "tail_shape": "heavy (xi>0, unbounded)" if np.median(xis) > 0 else "bounded (xi<0)",
    }


def main():
    S, R, H, synd, year = load_pool()
    draws, ref, hlo, hce = load_draws(); cfg = (ref, hlo, hce)
    ritc = load_ritc(synd, year)
    v1, v2_old, v2_new = load_targets()
    thbar = {p: float(draws[p].mean()) for p in draws}
    ndraw = len(draws["k"]); rng = np.random.default_rng(SEED)
    drawcl = build_resampler(synd, year, "cluster")

    res = {name: analyse(name, tgt, S, R, H, drawcl, draws, thbar, cfg, ndraw, rng, ritc)
           for name, tgt in [("V1_adjusted", v1), ("V2_new", v2_new)]}
    out = {"meta": {"seed": SEED, "B": B, "n_donors": len(S), "n_syndicates": int(len(set(synd))),
                    "threshold_rule": f"{U_Q:.0f}th percentile of the signed transferred-severity sample (fixed, same on every replicate)",
                    "clustering": "cluster (by syndicate) bootstrap x posterior draws of theta",
                    "return_level_formula": "u + (sigma/xi)[((N/Nu)(1-0.995))^(-xi) - 1]",
                    "quantile_method": "numpy type-7 (linear)"},
           "distributions": res}
    (SCRIPT_DIR / "results" / "gpd_var_uncertainty_results.json").write_text(json.dumps(out, indent=2))

    print(f"threshold rule: {out['meta']['threshold_rule']}  |  B={B} seed={SEED}\n")
    for name, r in res.items():
        print(f"=== {name} ===")
        print(f"  point VaR99.5 (GPD, full pool @ mean): {r['point_var995']:.3f}   (threshold u={r['point_threshold_u']:.3f}, Nu={r['point_Nu']})")
        print(f"  95% band [2.5, 50, 97.5]: [{r['band_lo_2.5']:.3f}, {r['band_median']:.3f}, {r['band_hi_97.5']:.3f}]")
        print(f"  median Nu across reps: {r['median_Nu']:.0f}   (valid reps {r['n_valid_reps']}/{B})")
        print(f"  xi_hat: {r['xi_median']:+.3f} [{r['xi_2.5']:+.3f}, {r['xi_97.5']:+.3f}]  -> {r['tail_shape']}")
        print(f"  sigma_hat: {r['sigma_median']:.4f} [{r['sigma_2.5']:.4f}, {r['sigma_97.5']:.4f}]")
        print(f"  empirical point {r['empirical']:.3f} inside GPD band? {'YES' if r['empirical_inside_band'] else 'NO'}")
        print()
    print("Wrote gpd_var_uncertainty_results.json")


if __name__ == "__main__":
    main()
