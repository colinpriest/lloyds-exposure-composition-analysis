"""How shallow is the size-dispersion slope among large books, with an interval?

The referee's point is exact: a non-significant rank correlation above 1bn
(Spearman -0.06, p=0.42) establishes "no DETECTABLE further decline", not that
dispersion has stopped falling. Absence of evidence is not evidence of absence.

The stronger and more useful question is not "is the local slope zero?" but "is it
materially shallower than the global power law predicts?".  The two candidate scale laws
make different predictions for the conditional derivative over the large-book range:

  no-floor law   d log sigma / d log R = k - 1, CONSTANT at every size
  floor law      d log sigma / d log R = (k-1) * sd^2 x^{2(k-1)} / (su^2 + sd^2 x^{2(k-1)})
                 which tends to 0 as R grows, because the floor comes to dominate

WHAT THIS SCRIPT ESTIMATES, AND WHAT IT DOES NOT.  A regression of log|S| on log R with
nothing else held fixed is a MARGINAL association.  It is not the conditional derivative
d log sigma / d log R that those two laws are statements about, and the slopes below are
not to be read as that derivative (frozen review of 25 September 2026, D03).  The two
differ whenever size moves with the other covariates, and here it does: even a floorless
law gives

    log sigma = const + (k-1) log R - gamma (k-1) log H,

so a concentration term correlated with size contributes to an unadjusted size slope, and
reporting year and the RITC regime do the same.  The controlled estimate, which holds
concentration, year and regime, is check_large_book_slope_conditional.py: read that one
for the derivative, together with its own caveat that its comparison against the floorless
law pairs draws from two separately specified likelihoods and is a product-of-marginals
diagnostic rather than a joint posterior probability.

What remains here is a descriptive marginal diagnostic of the large-book range, with an
interval, and it is worth reporting as that.  On its own it does not demonstrate
flattening, and nothing in it is an equivalence statement.  The model reference slopes it
records are computed from the fitted calibrations, never typed, so they move with the fit.

Slopes are Theil-Sen (robust to the heavy lower tail of log|S|) with an OLS check,
and intervals come from a bootstrap that resamples whole syndicates.

Writes check_large_book_slope_results.json.
Usage:  python src/check_large_book_slope.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats

from oos_validation import load, REF, HLO, HCE

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_large_book_slope_results.json"
CV = SD / "results" / "check_pooling_cv_extended_results.json"
B = 4000
SEED = 42
ZERO = 1e-6            # exact-zero severities cannot be logged


def model_local_slope(R, H, k, gamma, su, sd):
    """d log sigma / d log R at each observation, for sigma^2 = su^2 + sd^2 x^{2(k-1)}."""
    x = (np.asarray(R, float) / REF) * (1.0 / np.clip(H, HLO, HCE)) ** gamma
    div = sd ** 2 * x ** (2.0 * (k - 1.0))
    return (k - 1.0) * div / (su ** 2 + div)


def slopes(lr, ls):
    ts = stats.theilslopes(ls, lr)[0]
    ols = np.polyfit(lr, ls, 1)[0]
    return float(ts), float(ols)


def main():
    S, R, H, syn = load()
    cv = json.load(io.open(CV, encoding="utf-8"))["full_sample_params"]
    f, nf = cv["M1_free_k_floor"], cv["M7_free_k_nofloor"]
    kf, gf, suf, sdf = f["k"][0], f["gamma"][0], f["sd_undiv"][0], f["sd_div"][0]
    kn, gn, sun, sdn = nf["k"][0], nf["gamma"][0], nf["sd_undiv"][0], nf["sd_div"][0]
    print(f"floor model k={kf:.3f} floor={suf:.4f}; no-floor k={kn:.3f} "
          f"(constant local slope {kn-1:+.3f})")

    rng = np.random.default_rng(SEED)
    uniq = np.array(sorted(set(syn)))
    res = {"seed": SEED, "bootstrap": B,
           "definition": ("MARGINAL slope of log|S| on log R among large books, nothing else held fixed. It is "
                          "not the conditional derivative d log sigma / d log R: size moves with concentration, "
                          "reporting year and the RITC regime, and even a floorless law puts a "
                          "-gamma(k-1) log H term in the scale, so an unadjusted size slope carries part of it. "
                          "The controlled estimate is check_large_book_slope_conditional.py "
                          "(results/check_large_book_slope_conditional_results.json), whose own comparison "
                          "against the floorless law is a product-of-marginals diagnostic. Read this entry as a "
                          "descriptive diagnostic of the large-book range and not as an equivalence statement "
                          "(frozen review of 25 September 2026, D03)."),
           "model_local_slopes_are": ("the two candidate scale laws' CONDITIONAL derivatives at the fitted "
                                      "calibrations, computed by model_local_slope; they are the quantity the "
                                      "conditional diagnostic estimates, not this one."),
           "model_local_slopes": {
               "no_floor_constant": kn - 1.0,
               "floor_k_minus_1": kf - 1.0},
           "thresholds": {}}

    for name, T in [("above_500m", 500.0), ("above_1bn", 1000.0), ("above_2bn", 2000.0)]:
        m = (R >= T) & (np.abs(S) > ZERO)
        ndrop = int(((R >= T) & (np.abs(S) <= ZERO)).sum())
        lr, ls, sy = np.log(R[m]), np.log(np.abs(S[m])), syn[m]
        ts, ols = slopes(lr, ls)

        # model-implied local slopes over the same observations
        mf = float(np.median(model_local_slope(R[m], H[m], kf, gf, suf, sdf)))
        mn = kn - 1.0

        # syndicate-cluster bootstrap
        by = {s: np.where(sy == s)[0] for s in np.unique(sy)}
        keys = list(by)
        bs = []
        for _ in range(B):
            pick = rng.choice(len(keys), size=len(keys), replace=True)
            idx = np.concatenate([by[keys[i]] for i in pick])
            if len(np.unique(lr[idx])) < 3:
                continue
            try:
                bs.append(stats.theilslopes(ls[idx], lr[idx])[0])
            except Exception:
                pass
        bs = np.array(bs, float)
        lo, hi = np.percentile(bs, [2.5, 97.5])

        rec = {"threshold_m": T, "n": int(m.sum()),
               "n_syndicates": int(len(np.unique(sy))),
               "n_zero_severity_dropped": ndrop,
               "theil_sen_slope": ts, "ols_slope": ols,
               "ci95": [float(lo), float(hi)],
               "model_slope_floor_median": mf,
               "model_slope_nofloor": mn,
               "excludes_nofloor_slope": bool(mn < lo or mn > hi),
               "contains_floor_slope": bool(lo <= mf <= hi),
               "p_boot_slope_below_nofloor": float((bs < mn).mean())}
        res["thresholds"][name] = rec
        print(f"\n{name}: n={rec['n']} ({rec['n_syndicates']} syndicates), "
              f"{ndrop} zero-severity dropped")
        print(f"   Theil-Sen slope {ts:+.3f}  (OLS {ols:+.3f})   95% CI "
              f"[{lo:+.3f}, {hi:+.3f}]")
        print(f"   no-floor predicts {mn:+.3f}  -> {'EXCLUDED' if rec['excludes_nofloor_slope'] else 'inside CI'}")
        print(f"   floor model predicts {mf:+.3f} (median) -> "
              f"{'inside CI' if rec['contains_floor_slope'] else 'OUTSIDE CI'}")

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
