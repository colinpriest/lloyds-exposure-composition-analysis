"""Check 5 (referee): the vignette VaRs under both transfer operators.

The paper's headline operator is the size-only one (gamma = 0, set to zero in every retained
posterior draw of the adopted fit, not a refit: transfer_operator.py); the fitted concentration
overlay is a labelled sensitivity. This check computes Vignette 1's VaR99 and VaR99.5 and
Vignette 2's paired change at 99.5% under each, the centre on the full pool at the posterior
means, with cluster-bootstrap x posterior intervals (a conditional resampling interval, one
posterior draw per replicate; the posterior intervals are vignette_uncertainty_results.json's),
and records how far the overlay moves each figure. Both operators start the generator at the same
seed, so they are compared on the same resampled syndicates and draw indices.

Until 29 September 2026 this file was keyed `full_operator` / `size_only_gamma0`, and the paper
reported the first as its headline while calling the second its default (review MAT-1). The keys
now name the operators, and each block carries `operator` (transfer_operator.stamp).

Writes check_gamma0_vignette_results.json.
Usage:  python src/check_gamma0_vignette.py [B]
"""
import json, sys
from pathlib import Path
import numpy as np

import transfer_operator
from vignette_uncertainty import (load_pool, load_draws, load_ritc, load_targets,
                                  transfer, var_q, build_resampler, ci)

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_gamma0_vignette_results.json"
B = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4000
SEED = 20240704
QUANTITIES = ("V1_v99", "V1_v995", "V2_d995")


def centres(mode, pool, draws_fitted, cfg, ritc, targets):
    """The vignette figures on the full pool at the posterior means, under one operator.

    Returns (the posterior means with gamma as in force, the centres). Separate so that the transfer tool's
    test can compare its JavaScript with this implementation on the committed inputs, not with a record."""
    S, R, H, _synd, _year = pool
    v1, v2o, v2n = targets
    draws = transfer_operator.params(draws_fitted, mode)
    thbar = {p: float(draws[p].mean()) for p in draws}
    a1 = transfer(S, R, H, v1, thbar, cfg, ritc)
    ao = transfer(S, R, H, v2o, thbar, cfg, ritc)
    an = transfer(S, R, H, v2n, thbar, cfg, ritc)
    return thbar, {"V1_v99": var_q(a1, 0.99), "V1_v995": var_q(a1, 0.995),
                   "V2_old_v995": var_q(ao, 0.995), "V2_new_v995": var_q(an, 0.995),
                   "V2_d995": var_q(an, 0.995) - var_q(ao, 0.995)}


def operator_vignettes(mode, pool, draws_fitted, cfg, ritc, targets, b=None, seed=SEED):
    """Centre and cluster-bootstrap intervals of the vignette figures under one operator."""
    S, R, H, synd, year = pool
    v1, v2o, v2n = targets
    draws = transfer_operator.params(draws_fitted, mode)
    ndraw = len(draws["k"])
    draw_syn = build_resampler(synd, year, "cluster")
    rng = np.random.default_rng(seed)
    thbar, centre = centres(mode, pool, draws_fitted, cfg, ritc, targets)
    acc = {"V1_v99": [], "V1_v995": [], "V2_d995": []}
    for _ in range(B if b is None else b):
        idx, _w = draw_syn(rng)          # the cluster resampler returns (rows, None)
        i = rng.integers(0, ndraw)
        th = {p: draws[p][i] for p in draws}
        a1b = transfer(S[idx], R[idx], H[idx], v1, th, cfg, ritc[idx])
        acc["V1_v99"].append(var_q(a1b, 0.99)); acc["V1_v995"].append(var_q(a1b, 0.995))
        aob = transfer(S[idx], R[idx], H[idx], v2o, th, cfg, ritc[idx])
        anb = transfer(S[idx], R[idx], H[idx], v2n, th, cfg, ritc[idx])
        acc["V2_d995"].append(var_q(anb, 0.995) - var_q(aob, 0.995))
    return {**transfer_operator.stamp(mode), "gamma_in_force_posterior_mean": thbar["gamma"],
            "centre": centre, "intervals": {k: ci(v) for k, v in acc.items()}}


def compute(b=None):
    pool = load_pool()
    draws, ref, hlo, hce = load_draws()
    cfg = (ref, hlo, hce)
    ritc = load_ritc(pool[3], pool[4])
    targets = load_targets()
    blocks = {mode: operator_vignettes(mode, pool, draws, cfg, ritc, targets, b)
              for mode in transfer_operator.MODES}
    head, sens = blocks[transfer_operator.HEADLINE], blocks[transfer_operator.SENSITIVITY]
    return {
        "headline_operator": transfer_operator.HEADLINE,
        "seed": SEED, "B": B if b is None else b,
        "estimator": ("centre on the full pool at the posterior means; intervals are the 2.5 and 97.5 percentiles over "
                      "a cluster bootstrap by syndicate with one posterior draw per replicate (a conditional "
                      "resampling interval, not the posterior interval of vignette_uncertainty_results.json)"),
        "note": "size_only = size + floor operator (the headline); overlay = size + concentration + floor",
        transfer_operator.SIZE_ONLY: blocks[transfer_operator.SIZE_ONLY],
        transfer_operator.OVERLAY: blocks[transfer_operator.OVERLAY],
        "overlay_relative_to_headline": {
            "note": "overlay centre / headline centre - 1: what switching the concentration overlay on does",
            **{q: sens["centre"][q] / head["centre"][q] - 1.0 for q in QUANTITIES}},
        "headline_relative_to_overlay": {
            "note": "headline centre / overlay centre - 1: what switching the concentration overlay off does",
            **{q: head["centre"][q] / sens["centre"][q] - 1.0 for q in QUANTITIES}},
        "gamma_posterior_mean": float(draws["gamma"].mean()),
    }


def main():
    out = compute()
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    so, ov = out[transfer_operator.SIZE_ONLY], out[transfer_operator.OVERLAY]
    for q in QUANTITIES:
        print(f"  {q:8s} size-only (headline) {so['centre'][q]:+.4f}   overlay (sensitivity) "
              f"{ov['centre'][q]:+.4f}   ({100 * out['overlay_relative_to_headline'][q]:+.1f}%)")
    print(f"  V1 VaR99.5 interval: size-only [{so['intervals']['V1_v995']['lo']:.3f},"
          f"{so['intervals']['V1_v995']['hi']:.3f}]  overlay [{ov['intervals']['V1_v995']['lo']:.3f},"
          f"{ov['intervals']['V1_v995']['hi']:.3f}]")


if __name__ == "__main__":
    sys.exit(main())
