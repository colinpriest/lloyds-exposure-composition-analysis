"""Check 1 (referee): Vignette-1 tail support counted in SYNDICATE units.

Concern: the top transferred severities repeat syndicates (1183 at ranks 2 & 7, 2008 at
4 & 10), so "about four donors" in the VaR99/99.5 exceedance region may be fewer than four
independent syndicates.

(a) On the de-RITC transferred V1 pool (posterior-mean operator), take the exceedance sets
    {S_adj >= VaR99} and {>= VaR99.5}; report distinct syndicates vs distinct syndicate-years.
(b) Syndicate random-intercept on z = S/sigma_hat (M0 posterior-mean scale; meant to be
    homoscedastic), syndicates with >=3 obs; report ICC = tau_a^2/(tau_a^2 + sigma_e^2).
(c) Syndicate-block bootstrap (whole syndicates, B): distribution of the number of distinct
    syndicates supplying the exceedances, and VaR99/99.5.

Writes check_tail_support_syndicate_results.json.
Usage:  python src/check_tail_support_syndicate.py [B]
"""
import io, json, sys
from pathlib import Path
import numpy as np

from vignette_uncertainty import (load_pool, load_draws, load_ritc, load_targets,
                                  transfer, var_q)

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_tail_support_syndicate_results.json"
CALIB = SD / "model" / "dispersion_calibration_ritc.json"
B = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
SEED = 20240704
HLO, HCE = 0.01, 1.0


def icc_random_intercept(z, synd, min_obs=3):
    """One-way random-intercept ICC via REML-free moment estimator (Searle), on
    syndicates with >= min_obs observations. Returns ICC, tau_a^2, sigma_e^2, groups."""
    keep_syn = [s for s in set(synd) if (synd == s).sum() >= min_obs]
    m = np.isin(synd, list(keep_syn))
    z, g = z[m], synd[m]
    groups = list(keep_syn)
    a = len(groups)
    N = len(z)
    ni = np.array([(g == s).sum() for s in groups], float)
    grand = z.mean()
    means = np.array([z[g == s].mean() for s in groups])
    SSB = float((ni * (means - grand) ** 2).sum())
    SSW = float(sum(((z[g == s] - means[i]) ** 2).sum() for i, s in enumerate(groups)))
    dfb, dfw = a - 1, N - a
    MSB, MSW = SSB / dfb, SSW / dfw
    n0 = (N - (ni ** 2).sum() / N) / (a - 1)
    tau_a2 = max(0.0, (MSB - MSW) / n0)
    sigma_e2 = MSW
    icc = tau_a2 / (tau_a2 + sigma_e2) if (tau_a2 + sigma_e2) > 0 else 0.0
    return {"icc": float(icc), "tau_alpha2": float(tau_a2), "sigma_eps2": float(sigma_e2),
            "n_syndicates_ge_min": a, "n_obs": N, "min_obs": min_obs}


def main():
    S, R, H, synd, year = load_pool()
    draws, ref, hlo, hce = load_draws()
    cfg = (ref, hlo, hce)
    ritc = load_ritc(synd, year)
    v1, _, _ = load_targets()
    thbar = {p: float(draws[p].mean()) for p in draws}

    # (a) exceedance sets on the de-RITC transferred pool
    a1 = transfer(S, R, H, v1, thbar, cfg, ritc)
    q99, q995 = var_q(a1, 0.99), var_q(a1, 0.995)
    def exc_report(q):
        m = a1 >= q
        sy = [f"{s}_{y}" for s, y in zip(synd[m], year[m])]
        ss = list(synd[m])
        order = np.argsort(-a1[m])
        ranked = [(f"{synd[m][i]}_{year[m][i]}", round(float(a1[m][i]), 4)) for i in order]
        return {"threshold": float(q), "n_syndicate_years": int(m.sum()),
                "n_distinct_syndicates": int(len(set(ss))),
                "distinct_syndicates": sorted(set(int(x) for x in ss)),
                "ranked_exceedances": ranked}
    exc = {"VaR99": exc_report(q99), "VaR995": exc_report(q995)}

    # (b) ICC on standardised residual z = S/sigma_hat(M0 posterior mean)
    c = json.load(io.open(CALIB, encoding="utf-8"))
    Hc = np.clip(H, HLO, HCE)
    log_reff = np.log(np.maximum(R, 1e-9) / c["reference_size"]) - c["gamma"] * np.log(Hc)
    sigma_hat = np.sqrt(c["sd_undiv"] ** 2 + c["sd_div"] ** 2
                        * np.exp(2.0 * (c["k"] - 1.0) * log_reff))
    z = S / sigma_hat
    icc = icc_random_intercept(z, synd, min_obs=3)

    # (c) syndicate-block bootstrap
    groups = {}
    for i, s in enumerate(synd):
        groups.setdefault(s, []).append(i)
    keys = list(groups.keys()); idx_lists = [np.array(groups[k]) for k in keys]
    rng = np.random.default_rng(SEED)
    n_distinct99, n_distinct995, v99b, v995b = [], [], [], []
    for _ in range(B):
        pick = rng.integers(0, len(keys), len(keys))
        idx = np.concatenate([idx_lists[p] for p in pick])
        boot_synd = synd[idx]
        a = transfer(S[idx], R[idx], H[idx], v1, thbar, cfg, ritc[idx])
        qq99, qq995 = var_q(a, 0.99), var_q(a, 0.995)
        v99b.append(qq99); v995b.append(qq995)
        # distinct syndicates among exceedances (dedup the resampled multiplicities)
        e99 = a >= qq99; e995 = a >= qq995
        n_distinct99.append(len(set(boot_synd[e99])))
        n_distinct995.append(len(set(boot_synd[e995])))
    def dist(v):
        v = np.asarray(v, float)
        return {"mean": float(v.mean()), "median": float(np.median(v)),
                "lo2.5": float(np.percentile(v, 2.5)), "hi97.5": float(np.percentile(v, 97.5))}
    boot = {"B": B,
            "distinct_syndicates_at_VaR99": dist(n_distinct99),
            "distinct_syndicates_at_VaR995": dist(n_distinct995),
            "VaR99": dist(v99b), "VaR995": dist(v995b)}

    out = {"target_V1": {"reserve_size": v1[0], "hhi": v1[1]},
           "operator": "de-RITC shape-aware, posterior-mean parameters",
           "n_donors": len(S), "n_syndicates": int(len(set(synd))),
           "a_exceedance_sets": exc, "b_icc": icc, "c_syndicate_block_bootstrap": boot,
           "seed": SEED}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"(a) VaR99  : {exc['VaR99']['n_syndicate_years']} synd-years, "
          f"{exc['VaR99']['n_distinct_syndicates']} distinct syndicates {exc['VaR99']['distinct_syndicates']}")
    print(f"    VaR99.5: {exc['VaR995']['n_syndicate_years']} synd-years, "
          f"{exc['VaR995']['n_distinct_syndicates']} distinct syndicates {exc['VaR995']['distinct_syndicates']}")
    print(f"(b) ICC = {icc['icc']:.3f}  (tau_a^2={icc['tau_alpha2']:.4f}, sigma_e^2={icc['sigma_eps2']:.4f}, "
          f"{icc['n_syndicates_ge_min']} syndicates >=3 obs)")
    print(f"(c) distinct syndicates supplying VaR99 exceedances: "
          f"median {boot['distinct_syndicates_at_VaR99']['median']:.0f} "
          f"[{boot['distinct_syndicates_at_VaR99']['lo2.5']:.0f}, {boot['distinct_syndicates_at_VaR99']['hi97.5']:.0f}]")
    print(f"    VaR99.5 exceedances: median {boot['distinct_syndicates_at_VaR995']['median']:.0f} "
          f"[{boot['distinct_syndicates_at_VaR995']['lo2.5']:.0f}, {boot['distinct_syndicates_at_VaR995']['hi97.5']:.0f}]")
    print(f"    VaR99.5 = {boot['VaR995']['median']:.3f} [{boot['VaR995']['lo2.5']:.3f}, {boot['VaR995']['hi97.5']:.3f}]")


if __name__ == "__main__":
    sys.exit(main())
