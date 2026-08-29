"""Is treating RITC as a tail-only effect defensible, and what does the simplification cost?

The manuscript said that because the HDI for beta_RITC straddles zero, this "licenses"
treating RITC as a tail effect only. That is evidence of absence: the posterior is
centred at -0.146 and this repository already records P(|beta_RITC| > 0.1) = 0.67. An
interval containing zero establishes nothing about a term the operator then omits.

This replaces the claim with three things that can be checked.

1. What the posterior actually says about beta_RITC, including the implied scale
   multiplier exp(beta) for a flagged observation.

2. What omitting it costs the operator. Equation (7) standardises a donor by
   sigma(R, H), which carries no exp(beta*1[RITC]) factor, so a flagged donor is
   divided by a scale that is too large by exp(-beta) if beta is real. We recompute
   both vignette stresses with the term propagated into the donor standardisation,
   across all 6,000 posterior draws, and report the difference. This is the
   practical-equivalence question in the units the paper actually reports.

3. Whether the data prefer the term at all: PSIS-LOO on the full adopted model with
   beta free against beta fixed at zero, summarised by a by-syndicate Bayesian
   bootstrap of the ELPD difference, as everywhere else in the paper.

Run: python check_ritc_scale_term.py
"""
import io
import json

import numpy as np
import pytensor
from scipy import stats

pytensor.config.mode = "NUMBA"
import arviz as az
import pymc as pm

from adopted_model import SD, REFERENCE_SIZE, load_sample, scale_block
from dispersion_mle import deritc_z

OUT = SD / "results" / "check_ritc_scale_term_results.json"
SEED = 42
BB = 20000
V1 = (500.0, 0.17)


def hdi95(x):
    a = np.asarray(x, float).ravel()
    if a.min() == a.max():
        return [float(a[0]), float(a[0])]
    return [float(v) for v in az.hdi(a, hdi_prob=0.95)]


def summ(x):
    a = np.asarray(x, float).ravel()
    return {"mean": float(a.mean()), "hdi": hdi95(a)}


def sigma_of(R, H, k, g, su, sd):
    return np.sqrt(su ** 2 + sd ** 2 * (R * (1.0 / H) ** g / REFERENCE_SIZE)
                   ** (2.0 * (k - 1.0)))


def transferred_var(S, R, H, ritc, tgt, d, alpha, propagate):
    """VaR of donor movements transferred to `tgt` for one posterior draw."""
    sig_i = sigma_of(R, H, d["k"], d["gamma"], d["sd_undiv"], d["sd_div"])
    if propagate:
        sig_i = sig_i * np.exp(d["beta_ritc"] * ritc)
    sig_q = sigma_of(np.array([tgt[0]]), np.array([tgt[1]]), d["k"], d["gamma"],
                     d["sd_undiv"], d["sd_div"])[0]
    z = deritc_z(S / sig_i, ritc, d["nu_clean"], d["nu_ritc"])
    return float(np.percentile(z * sig_q, 100.0 * alpha, method="linear"))


def fit(S, R, H, yr, ritc, free_beta):
    with pm.Model():
        b = scale_block(R, H, yr, ritc)
        sigma = b["sigma"]
        if not free_beta:
            # rebuild the scale without the RITC term; everything else is identical
            sigma = sigma / pm.math.exp(b["beta_ritc"] * ritc)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=sigma, observed=S)
        return pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                         random_seed=SEED, progressbar=False,
                         idata_kwargs={"log_likelihood": True})


def bb_delta(e_a, e_b, syn):
    d = np.asarray(e_a) - np.asarray(e_b)
    ok = np.isfinite(d)
    tot = {}
    for di, sj in zip(d[ok], np.asarray(syn)[ok]):
        tot[sj] = tot.get(sj, 0.0) + di
    v = np.array(list(tot.values()), float)
    rng = np.random.default_rng(SEED)
    draws = len(v) * (rng.dirichlet(np.ones(len(v)), size=BB) @ v)
    return {"delta_ELPD": float(d[ok].sum()), "n_syndicates": int(len(v)),
            "bb_mean": float(draws.mean()),
            "bb_2.5": float(np.percentile(draws, 2.5)),
            "bb_97.5": float(np.percentile(draws, 97.5)),
            "P_free_beta_better": float((draws > 0).mean())}


def main():
    S, R, H, yr, syn, ritc = load_sample()
    t2 = json.load(io.open(SD / "vignettes/vignette-2/target_transition.json",
                           encoding="utf-8"))
    v2o = (float(t2["old_reserve_size"]), float(t2["old_hhi"]))
    v2n = (float(t2["new_reserve_size"]), float(t2["new_hhi"]))
    print("n=%d  RITC=%d  syndicates=%d" % (len(S), int(ritc.sum()), len(set(syn))))

    dr = np.load(SD / "model" / "dispersion_posterior_draws_ritc.npz")
    beta = dr["beta_ritc"]
    n_draw = len(beta)

    res = {"n": int(len(S)), "n_ritc": int(ritc.sum()), "n_draws": int(n_draw),
           "seed": SEED,
           "beta_ritc": {**summ(beta),
                         "P_lt_0": float((beta < 0).mean()),
                         "P_abs_gt_0.05": float((np.abs(beta) > 0.05).mean()),
                         "P_abs_gt_0.10": float((np.abs(beta) > 0.10).mean()),
                         "P_abs_gt_0.20": float((np.abs(beta) > 0.20).mean())},
           "scale_multiplier_exp_beta": summ(np.exp(beta))}
    b = res["beta_ritc"]
    print("\nbeta_RITC %+.3f  HDI [%+.3f, %+.3f]  P(<0)=%.2f  "
          "P(|b|>0.05)=%.2f  P(|b|>0.10)=%.2f  P(|b|>0.20)=%.2f"
          % (b["mean"], b["hdi"][0], b["hdi"][1], b["P_lt_0"],
             b["P_abs_gt_0.05"], b["P_abs_gt_0.10"], b["P_abs_gt_0.20"]))
    m = res["scale_multiplier_exp_beta"]
    print("scale multiplier for a flagged observation: %.3f  HDI [%.3f, %.3f]"
          % (m["mean"], m["hdi"][0], m["hdi"][1]))

    # ---- 2. what the omission costs the operator, over the full posterior ----
    print("\npropagating the term through the donor standardisation (%d draws)..."
          % n_draw)
    keys = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "beta_ritc")
    out = {n: {"as_published": [], "propagated": []}
           for n in ("V1_VaR99", "V1_VaR995", "V2_change995")}
    for j in range(n_draw):
        d = {p: float(dr[p][j]) for p in keys}
        for prop, tag in ((False, "as_published"), (True, "propagated")):
            out["V1_VaR99"][tag].append(
                transferred_var(S, R, H, ritc, V1, d, 0.99, prop))
            out["V1_VaR995"][tag].append(
                transferred_var(S, R, H, ritc, V1, d, 0.995, prop))
            out["V2_change995"][tag].append(
                transferred_var(S, R, H, ritc, v2n, d, 0.995, prop)
                - transferred_var(S, R, H, ritc, v2o, d, 0.995, prop))

    res["operator_sensitivity"] = {}
    for n, v in out.items():
        a = np.array(v["as_published"]); p = np.array(v["propagated"])
        res["operator_sensitivity"][n] = {
            "as_published": summ(a), "propagated": summ(p),
            "difference": summ(p - a),
            "relative_difference_mean": float((p - a).mean() / abs(a.mean()))
            if a.mean() != 0 else None,
            "P_difference_gt_0": float((p - a > 0).mean())}
        r = res["operator_sensitivity"][n]
        print("  %-13s published %+.4f  propagated %+.4f  diff %+.4f "
              "[%+.4f, %+.4f]  (%.1f%%)"
              % (n, r["as_published"]["mean"], r["propagated"]["mean"],
                 r["difference"]["mean"], r["difference"]["hdi"][0],
                 r["difference"]["hdi"][1],
                 100.0 * (r["relative_difference_mean"] or 0.0)))

    # ---- 3. do the data prefer the term? ----
    print("\nPSIS-LOO: beta free vs beta fixed at zero ...")
    i_free = fit(S, R, H, yr, ritc, True)
    i_zero = fit(S, R, H, yr, ritc, False)
    e_free = np.asarray(az.loo(i_free, pointwise=True).loo_i.values, float)
    e_zero = np.asarray(az.loo(i_zero, pointwise=True).loo_i.values, float)
    res["predictive_comparison"] = bb_delta(e_free, e_zero, syn)
    pc = res["predictive_comparison"]
    print("  dELPD (beta free minus beta=0) %+.2f  95%% [%+.2f, %+.2f]  P=%.2f"
          % (pc["delta_ELPD"], pc["bb_2.5"], pc["bb_97.5"],
             pc["P_free_beta_better"]))

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\nwritten to", OUT)


if __name__ == "__main__":
    main()
