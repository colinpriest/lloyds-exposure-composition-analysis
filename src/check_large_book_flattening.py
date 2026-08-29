"""Does observed dispersion FLATTEN across the largest well-populated sizes?

This is the evidence that bears most directly on the undiversifiable floor, and it is
separate from the held-out ELPD comparison in check_floor_large_syndicates.py.  A
floor predicts that median |S| stops falling as reserves grow; a floorless power law
predicts it keeps falling at rate R^{k-1}.

Reports median |S| by size vigintile (20 equal-count bins) with each bin's median
reserve size and syndicate count, and alongside it what the fitted floor and no-floor
models imply for the same bins.  Because |S| is a folded Student-t, the model-implied
median is sigma * F^{-1}_{|t_nu|}(0.5), not sigma itself, so the comparison is
like-for-like.

Also reports the same for the top few vigintiles pooled, and a rank test of whether
|S| still declines with size across the upper half of the size range.

Writes check_large_book_flattening_results.json.
Usage:  python check_large_book_flattening.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats

from oos_validation import load, REF, HLO, HCE

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_large_book_flattening_results.json"
CV = SD / "results" / "check_pooling_cv_extended_results.json"
NBIN = 20


def med_abs_t(nu):
    """Median of |T| for Student-t with nu df: the 75th percentile of T."""
    return float(stats.t.ppf(0.75, df=nu))


def sigma_of(R, H, k, gamma, su, sd):
    reff = (np.asarray(R, float) / REF) * (1.0 / np.clip(H, HLO, HCE)) ** gamma
    return np.sqrt(su ** 2 + sd ** 2 * reff ** (2.0 * (k - 1.0)))


def main():
    S, R, H, syn = load()
    A = np.abs(S)
    n = len(S)
    order = np.argsort(R)
    bins = np.array_split(order, NBIN)

    cv = json.load(io.open(CV, encoding="utf-8"))["full_sample_params"]
    f = cv["M1_free_k_floor"]; nf = cv["M7_free_k_nofloor"]
    kf, gf, suf, sdf, nuf = f["k"][0], f["gamma"][0], f["sd_undiv"][0], f["sd_div"][0], f["nu"][0]
    kn, gn, sun, sdn, nun = nf["k"][0], nf["gamma"][0], nf["sd_undiv"][0], nf["sd_div"][0], nf["nu"][0]
    cf, cn = med_abs_t(nuf), med_abs_t(nun)
    print(f"floor model   k={kf:.3f} floor={suf:.4f} sd_div={sdf:.4f} nu={nuf:.2f}  med|t|={cf:.3f}")
    print(f"no-floor model k={kn:.3f} floor={sun:.4f} sd_div={sdn:.4f} nu={nun:.2f}  med|t|={cn:.3f}")

    rows = []
    print(f"\n{'vig':>4}{'n':>5}{'syn':>5}{'medR(m)':>10}{'med|S|':>9}"
          f"{'floor':>9}{'nofloor':>9}")
    for i, idx in enumerate(bins, 1):
        r = R[idx]; a = A[idx]; h = H[idx]
        medR = float(np.median(r)); medA = float(np.median(a))
        pf = float(np.median(sigma_of(r, h, kf, gf, suf, sdf)) * cf)
        pn = float(np.median(sigma_of(r, h, kn, gn, sun, sdn)) * cn)
        rows.append({"vigintile": i, "n": int(len(idx)),
                     "n_syndicates": int(len(set(syn[idx]))),
                     "median_R_m": medR, "median_abs_S": medA,
                     "model_median_abs_S_floor": pf,
                     "model_median_abs_S_nofloor": pn})
        print(f"{i:>4}{len(idx):>5}{len(set(syn[idx])):>5}{medR:>10.1f}{medA:>9.4f}"
              f"{pf:>9.4f}{pn:>9.4f}")

    # Is the decline over? Rank correlation of |S| with size in the upper half.
    tests = {}
    for label, lo in [("upper_half", float(np.median(R))), ("above_1bn", 1000.0),
                      ("above_2bn", 2000.0)]:
        m = R >= lo
        if m.sum() > 8:
            sp = stats.spearmanr(R[m], A[m])
            tests[label] = {"n": int(m.sum()), "n_syndicates": int(len(set(syn[m]))),
                            "threshold_m": lo,
                            "spearman_absS_vs_R": float(sp.statistic),
                            "p": float(sp.pvalue),
                            "median_abs_S": float(np.median(A[m]))}
            print(f"\n{label}: n={m.sum()} ({len(set(syn[m]))} syndicates), "
                  f"Spearman(|S|, R) = {sp.statistic:+.3f} (p={sp.pvalue:.3f}), "
                  f"median |S| = {np.median(A[m]):.4f}")

    # Top-two vigintiles pooled, the figure the referee quotes.
    top2 = np.concatenate(bins[-2:])
    res = {
        "n": int(n), "n_bins": NBIN,
        "model_params": {
            "floor": {"k": kf, "gamma": gf, "sd_undiv": suf, "sd_div": sdf, "nu": nuf},
            "no_floor": {"k": kn, "gamma": gn, "sd_undiv": sun, "sd_div": sdn, "nu": nun}},
        "note": ("model column is sigma * median|t_nu| so it is comparable with the "
                 "empirical median |S|, not the scale itself"),
        "vigintiles": rows,
        "decline_tests": tests,
        "top_two_vigintiles": {
            "n": int(len(top2)), "n_syndicates": int(len(set(syn[top2]))),
            "median_R_m": float(np.median(R[top2])),
            "median_abs_S": float(np.median(A[top2]))},
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
