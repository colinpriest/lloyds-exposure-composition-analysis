#!/usr/bin/env python3
"""Is Vignette 2's rise evidence, or is it imposed by the model's own constraints?

Review's finding: the manuscript reported P(rise) = 1.00 for the post-exit vignette and
called it the stronger evidence in the paper. It is not evidence at all. The transfer is

    S_adj = z0 * sigma(target),     z0 = deRITC(S / sigma(source)),

so z0 does not depend on the target. Every positively homogeneous statistic of the
transferred pool -- the 99.5% quantile among them -- therefore scales EXACTLY with
sigma(target):

    VaR_q( z0 * sigma(new) ) / VaR_q( z0 * sigma(old) ) = sigma(new) / sigma(old)

whenever VaR_q(z0) > 0, which it is here. The scenario moves reserves 800 -> 650 and
concentration 0.21 -> 0.2618, and under the adopted support (k <= 1, gamma >= 0) the
fitted scale is non-increasing in reserves and non-decreasing in concentration. So both
changes push the same way for EVERY posterior draw, and no reweighting of the donors --
bootstrap, Bayesian bootstrap or otherwise -- can change the sign, because the donors
cancel from the ratio.

That makes P(rise) = 1 a statement about the model's support and the scenario, not about
the strength of the evidence. What the posterior does carry is the MAGNITUDE, and the
distance to the constraint boundary: this script reports the ratio across all committed
draws and solves for the pooling exponent at which the direction would reverse.

Run:  python src/check_vignette2_sign.py
"""
import io
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAWS = os.path.join(HERE, "model", "dispersion_posterior_draws_ritc.npz")
TARGETS = os.path.join(HERE, "vignettes", "vignette-2", "target_transition.json")
OUT = os.path.join(HERE, "results", "check_vignette2_sign_results.json")


def sigma(R, H, k, g, su, sd, ref, hlo, hce):
    Hc = np.clip(H, hlo, hce)
    reff = (np.maximum(R, 1e-9) / ref) * (1.0 / Hc) ** g
    return np.sqrt(su * su + sd * sd * reff ** (2.0 * (k - 1.0)))


def reversing_k(Ro, Ho, Rn, Hn, g, su, sd, ref, hlo, hce):
    """The pooling exponent at which sigma(new) = sigma(old): the boundary the model
    would have to cross for the direction to reverse. Bisection on a monotone
    difference; None if the difference does not change sign on [0.5, 5]."""
    def f(k):
        return (sigma(Rn, Hn, k, g, su, sd, ref, hlo, hce)
                - sigma(Ro, Ho, k, g, su, sd, ref, hlo, hce))
    lo, hi = 0.5, 5.0
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def main():
    z = np.load(DRAWS)
    tg = json.load(io.open(TARGETS, encoding="utf-8"))
    Ro, Rn = float(tg["old_reserve_size"]), float(tg["new_reserve_size"])
    Ho, Hn = float(tg["old_hhi"]), float(tg["new_hhi"])
    ref = float(z["reference_size"][0])
    hlo, hce = float(z["hhi_floor"][0]), float(z["hhi_ceil"][0])
    k, g, su, sd = z["k"], z["gamma"], z["sd_undiv"], z["sd_div"]

    so = sigma(Ro, Ho, k, g, su, sd, ref, hlo, hce)
    sn = sigma(Rn, Hn, k, g, su, sd, ref, hlo, hce)
    ratio = sn / so

    # each channel on its own, at every draw
    size_only = sigma(Rn, Ho, k, g, su, sd, ref, hlo, hce) / so
    conc_only = sigma(Ro, Hn, k, g, su, sd, ref, hlo, hce) / so

    kbar, gbar = float(k.mean()), float(g.mean())
    kstar = reversing_k(Ro, Ho, Rn, Hn, gbar, float(su.mean()), float(sd.mean()),
                        ref, hlo, hce)

    out = {
        "question": ("whether P(rise)=1 in Vignette 2 is empirical resolution or a "
                     "consequence of the adopted support"),
        "answer": ("consequence: the donor residuals cancel from the ratio, and under "
                   "k <= 1 with gamma >= 0 both scenario changes raise the fitted "
                   "scale at every posterior draw. The posterior informs the MAGNITUDE "
                   "of the rise, not its direction"),
        "identity": ("VaR_q(z0*sigma(new))/VaR_q(z0*sigma(old)) = sigma(new)/sigma(old) "
                     "for any positively homogeneous quantile, since z0 is independent "
                     "of the target; no donor reweighting can change the sign"),
        "scenario": {"reserves": [Ro, Rn], "hhi": [Ho, Hn]},
        "n_draws": int(len(k)),
        "constraints": {
            "frac_draws_k_le_1": float((k <= 1.0).mean()),
            "frac_draws_gamma_ge_0": float((g >= 0.0).mean()),
            "k_support": [float(k.min()), float(k.max())],
            "gamma_support": [float(g.min()), float(g.max())]},
        "scale_ratio_new_over_old": {
            "min": float(ratio.min()), "max": float(ratio.max()),
            "mean": float(ratio.mean()),
            "q2.5": float(np.percentile(ratio, 2.5)),
            "q97.5": float(np.percentile(ratio, 97.5)),
            "frac_draws_above_one": float((ratio > 1.0).mean())},
        "channel_ratios": {
            "size_only_mean": float(size_only.mean()),
            "size_only_frac_above_one": float((size_only > 1.0).mean()),
            "concentration_only_mean": float(conc_only.mean()),
            "concentration_only_frac_above_one": float((conc_only > 1.0).mean())},
        "reversal": {
            "k_at_which_direction_reverses": kstar,
            "posterior_mean_k": kbar,
            "note": ("the reversing exponent is exactly 1, the bracket's upper endpoint: "
                     "at k=1 the scale law is flat in both size and concentration, so "
                     "the exponent on effective size vanishes. P(rise)=1 is therefore "
                     "the same statement as P(k<1)=1, which the manuscript already "
                     "records as tautological on the bracketed support")},
    }
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=2) + "\n")

    print("Vignette 2: is the rise evidence?\n")
    print("  scale ratio new/old across %d draws: %.4f to %.4f (mean %.4f)"
          % (len(k), ratio.min(), ratio.max(), ratio.mean()))
    print("  draws with k <= 1: %.3f;  with gamma >= 0: %.3f"
          % ((k <= 1.0).mean(), (g >= 0.0).mean()))
    print("  size channel alone raises the scale in %.3f of draws; concentration in %.3f"
          % ((size_only > 1.0).mean(), (conc_only > 1.0).mean()))
    print("  direction reverses only at k = %s (posterior mean %.3f, bracket [0.5, 1])"
          % ("none in [0.5, 5]" if kstar is None else "%.3f" % kstar, kbar))
    print("\n  => P(rise) = 1 is imposed by the monotone scale law and the constrained")
    print("     support, not by the strength of the evidence. The posterior speaks to")
    print("     the magnitude of the rise.")
    print("\nwritten %s" % os.path.relpath(OUT, HERE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
