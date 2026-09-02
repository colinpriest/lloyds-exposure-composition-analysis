"""Check 5 (referee): size-only (gamma=0) operator vignette VaRs.

Sets gamma=0 (per posterior draw) and recomputes V1 VaR99/99.5 and the V2 paired delta,
with cluster-bootstrap x posterior intervals, alongside the full-operator values.

Writes check_gamma0_vignette_results.json.
Usage:  python src/check_gamma0_vignette.py [B]
"""
import json, sys
from pathlib import Path
import numpy as np

from vignette_uncertainty import (load_pool, load_draws, load_ritc, load_targets,
                                  transfer, var_q, build_resampler, ci)

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_gamma0_vignette_results.json"
B = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
SEED = 20240704


def main():
    S, R, H, synd, year = load_pool()
    draws, ref, hlo, hce = load_draws()
    cfg = (ref, hlo, hce)
    ritc = load_ritc(synd, year)
    v1, v2o, v2n = load_targets()
    ndraw = len(draws["k"])
    draw_syn = build_resampler(synd, year, "cluster")
    rng = np.random.default_rng(SEED)

    def run(gamma0):
        def theta(i):
            th = {p: draws[p][i] for p in draws}
            if gamma0:
                th["gamma"] = 0.0
            return th
        thbar = {p: float(draws[p].mean()) for p in draws}
        if gamma0:
            thbar["gamma"] = 0.0
        a1 = transfer(S, R, H, v1, thbar, cfg, ritc)
        ao = transfer(S, R, H, v2o, thbar, cfg, ritc)
        an = transfer(S, R, H, v2n, thbar, cfg, ritc)
        centre = {"V1_v99": var_q(a1, 0.99), "V1_v995": var_q(a1, 0.995),
                  "V2_old_v995": var_q(ao, 0.995), "V2_new_v995": var_q(an, 0.995),
                  "V2_d995": var_q(an, 0.995) - var_q(ao, 0.995)}
        acc = {"V1_v99": [], "V1_v995": [], "V2_d995": []}
        for _ in range(B):
            idx = draw_syn(rng)
            th = theta(rng.integers(0, ndraw))
            a1b = transfer(S[idx], R[idx], H[idx], v1, th, cfg, ritc[idx])
            acc["V1_v99"].append(var_q(a1b, 0.99)); acc["V1_v995"].append(var_q(a1b, 0.995))
            aob = transfer(S[idx], R[idx], H[idx], v2o, th, cfg, ritc[idx])
            anb = transfer(S[idx], R[idx], H[idx], v2n, th, cfg, ritc[idx])
            acc["V2_d995"].append(var_q(anb, 0.995) - var_q(aob, 0.995))
        return centre, {k: ci(v) for k, v in acc.items()}

    c_full, ci_full = run(gamma0=False)
    c_size, ci_size = run(gamma0=True)
    out = {"seed": SEED, "B": B, "note": "gamma=0 = size+floor operator; full = size+conc+floor",
           "full_operator": {"centre": c_full, "intervals": ci_full},
           "size_only_gamma0": {"centre": c_size, "intervals": ci_size},
           "gamma_posterior_mean": float(draws["gamma"].mean())}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  V1 VaR99    full {c_full['V1_v99']:.3f}  size-only {c_size['V1_v99']:.3f}")
    print(f"  V1 VaR99.5  full {c_full['V1_v995']:.3f}  size-only {c_size['V1_v995']:.3f}")
    print(f"  V2 delta995 full {c_full['V2_d995']:+.3f}  size-only {c_size['V2_d995']:+.3f}")
    print(f"  V1 VaR99.5 CI full [{ci_full['V1_v995']['lo']:.3f},{ci_full['V1_v995']['hi']:.3f}]  "
          f"size-only [{ci_size['V1_v995']['lo']:.3f},{ci_size['V1_v995']['hi']:.3f}]")


if __name__ == "__main__":
    sys.exit(main())
