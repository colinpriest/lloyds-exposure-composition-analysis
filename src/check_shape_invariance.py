"""Shape invariance along the size and concentration axes, on the working sample (the review of 2 October 2026, P-17).

The paper says the rescale-invariant shape tests (a k-sample Anderson-Darling test on group-standardised values,
with Bowley-skewness, tail-skew and Moors-kurtosis comparisons) find no drift along either axis. Those tests lived in
src/test_shape_invariance.py, which only printed, wrote no file, sat outside the manifest and ran on a legacy
348-record population. This manifest step runs the same statistics, imported from that script so the method is
identical, on the working sample the calibration is fitted on (adopted_model.load_sample), and writes them.

For each axis (opening reserves R; the concentration index H), the sample is cut into quartiles and deciles:
  * location: Kruskal-Wallis across the quartiles (are the medians equal?);
  * shape: the k-sample Anderson-Darling test on quartiles each centred by its median and scaled by its IQR;
  * the top-less-bottom quartile difference of each robust shape statistic, with a 95% interval from a cluster
    bootstrap over syndicates;
  * the slope of each statistic across deciles, with the same bootstrap interval.
The verdict "no drift" needs every interval to cover zero and the Anderson-Darling p at or above 0.05. These are
diagnostics, not significance tests of a posterior quantity.

Writes results/shape_invariance_results.json.
Run:  python src/check_shape_invariance.py
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

from adopted_model import load_sample
from test_shape_invariance import (N_BOOT, SEED, SHAPE_STATS, anderson_ksample_shape, cluster_bootstrap_diff,
                                   cluster_bootstrap_slope, make_groups)

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "shape_invariance_results.json"
AD_LINE = 0.05


def axis_result(axis, s, cluster, rng, n_boot=N_BOOT, n_groups=4):
    """The location, shape and drift statistics of `s` along one axis."""
    grp = make_groups(axis, n_groups)
    kw = stats.kruskal(*[s[grp == g] for g in range(n_groups)])
    ad = anderson_ksample_shape(s, grp)
    out = {"n_groups": n_groups,
           "group_sizes": [int(np.sum(grp == g)) for g in range(n_groups)],
           "location_kruskal_wallis": {"H": float(kw.statistic), "p": float(kw.pvalue)},
           "shape_anderson_darling": ad,
           "top_less_bottom_quartile": {}, "decile_slope": {}}
    covers = [] if ad is None else [ad["p"] >= AD_LINE]
    for label, fn in SHAPE_STATS.items():
        d = cluster_bootstrap_diff(s, cluster, grp, fn, n_groups - 1, 0, rng, n=n_boot)
        sl = cluster_bootstrap_slope(s, cluster, axis, fn, rng, n=n_boot)
        out["top_less_bottom_quartile"][label] = None if d is None else {
            "median": d["point"], "interval_95_cluster_bootstrap": list(d["ci"]), "n_boot": d["n_boot"]}
        out["decile_slope"][label] = {"slope": sl["slope"],
                                      "interval_95_cluster_bootstrap": list(sl["ci"]) if sl.get("ci") else None}
        for block in (d and {"ci": d["ci"]}, sl):
            ci = (block or {}).get("ci")
            covers.append(bool(ci) and ci[0] <= 0.0 <= ci[1])
    out["no_drift"] = bool(covers) and all(covers)
    return out


def run(S, R, H, syn, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    axes = {"size_opening_reserves": axis_result(R, S, syn, rng, n_boot),
            "concentration_hhi": axis_result(H, S, syn, rng, n_boot)}
    return {
        "purpose": ("rescale-invariant shape tests along the size and concentration axes, on the working sample "
                    "the calibration is fitted on (the review of 2 October 2026, P-17)"),
        "method": ("src/test_shape_invariance.py's statistics: Kruskal-Wallis on the quartiles' locations; k-sample "
                   "Anderson-Darling on the quartiles, each centred by its median and scaled by its IQR; Bowley "
                   "skewness, the tail-skew ratio and Moors kurtosis, compared top less bottom quartile and as a "
                   "slope across deciles, each with a 95% interval from a cluster bootstrap over syndicates"),
        "population": "adopted_model.load_sample(): the gross-basis working sample",
        "n": int(len(S)), "n_syndicates": int(len(np.unique(syn))),
        "seed": seed, "n_boot": n_boot, "anderson_darling_line": AD_LINE,
        "anderson_darling_p_note": "scipy reports the k-sample Anderson-Darling p within [0.001, 0.25]: 0.25 is "
                                   "its cap, not an estimate",
        "axes": axes,
        "no_drift_on_either_axis": all(a["no_drift"] for a in axes.values()),
        "reading": ("'no drift' means every interval covers zero and the Anderson-Darling p is at or above the "
                    "line; it is the absence of evidence of drift at this sample size, not evidence of none"),
    }


def main():
    S, R, H, _yr, syn, _ritc = load_sample()
    out = run(S, R, H, syn)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print("n=%d (%d syndicates); no drift on either axis: %s" % (out["n"], out["n_syndicates"],
                                                                   out["no_drift_on_either_axis"]))
    for name, a in out["axes"].items():
        ad = a["shape_anderson_darling"] or {}
        print("  %-24s AD p=%s  no drift: %s" % (name, ad.get("p"), a["no_drift"]))
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
