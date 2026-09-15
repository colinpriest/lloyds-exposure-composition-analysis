"""Sensitivity: the adopted model with the pooling exponent fixed at k = 1/2.

Theory bounds the pooling exponent to [1/2, 1]: 1/2 is finite-variance independent sqrt-N pooling, 1 is
comonotonic pooling with no diversification, and the headline prior keeps k inside that
bracket (adopted_model.scale_block, k = 1/2 + 1/2 logistic(theta)). By-syndicate
cross-validation does not separate the free exponent from the bracket's lower end, so this
script measures what that choice does to the numbers a practitioner uses. It refits the
adopted two-regime model with k fixed at 1/2 (scale_block's k_prior="fixed_0.5", the only
departure; data, priors, sampler and seed as the headline calibration) and recomputes,
beside the published fit:

  - Vignette 1's VaR99 and VaR99.5 and Vignette 2's paired change at 99.5%, through the
    transfer, targets, cluster resampler, seed and B of check_gamma0_vignette.py: the centre
    at the posterior means, and intervals over the cluster bootstrap with one posterior draw
    per replicate. Both fits read the same resampled syndicates and draw indices;
  - the 100m/2,000m scale ratio at H = 0.4, and the fitted scale across the size range, at
    the posterior means.

The published fit's centres must equal check_gamma0_vignette.py's full-operator record, or
the comparison is not like for like and nothing is written.

Writes check_k_half_sensitivity_results.json.
Usage:  python src/check_k_half_sensitivity.py [B]
"""
import io
import json
import sys

import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from adopted_model import SD, load_sample, scale_block, headline, SAMPLE_CORES
from vignette_uncertainty import (load_pool, load_draws, load_ritc, load_targets,
                                  transfer, var_q, build_resampler, ci, sigma_theta)

OUT = SD / "results" / "check_k_half_sensitivity_results.json"
GAMMA0 = SD / "results" / "check_gamma0_vignette_results.json"
B = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4000
VIG_SEED = 20240704          # check_gamma0_vignette.py's
FIT_SEED = 42                # the headline calibration's
DRAWS, TUNE, CHAINS, TARGET_ACCEPT = 1500, 1500, 4, 0.98
PARAMS = ("gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s")
SIZES = (25.0, 100.0, 500.0, 1000.0, 2000.0, 4750.0, 10000.0)
H_RATIO = 0.4


def fit_k_half():
    S, R, H, yr, syn, ritc = load_sample()
    with pm.Model():
        b = scale_block(R, H, yr, ritc, k_prior="fixed_0.5")
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=SAMPLE_CORES,
                          target_accept=TARGET_ACCEPT, random_seed=FIT_SEED, progressbar=False)
    return idata, {"n": int(len(S)), "n_ritc": int(ritc.sum()), "n_years": int(len(np.unique(yr)))}


def summarise(idata):
    summ = az.summary(idata, var_names=list(PARAMS), hdi_prob=0.95)
    params = {p: {"mean": float(summ.loc[p, "mean"]), "sd": float(summ.loc[p, "sd"]),
                  "hdi_2.5": float(summ.loc[p, "hdi_2.5%"]), "hdi_97.5": float(summ.loc[p, "hdi_97.5%"])}
              for p in PARAMS}
    diagnostics = {"max_rhat": float(summ["r_hat"].max()),
                   "min_ess_bulk": float(summ["ess_bulk"].min()),
                   "divergences": int(idata.sample_stats["diverging"].sum())}
    post = idata.posterior
    lam = post["lambda_ritc"].values.ravel()
    draws = {"k": np.full(lam.size, 0.5)}
    for p in ("gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc"):
        draws[p] = post[p].values.ravel()
    return params, diagnostics, {"nu_ritc_lt_nu_clean": float((lam > 0).mean())}, draws


def vignettes(draws, cfg, pool, ritc, targets):
    """check_gamma0_vignette.py's full-operator run, line for line, on the given draws."""
    S, R, H, synd, year = pool
    v1, v2o, v2n = targets
    ndraw = len(draws["k"])
    draw_syn = build_resampler(synd, year, "cluster")
    rng = np.random.default_rng(VIG_SEED)
    thbar = {p: float(draws[p].mean()) for p in draws}
    a1 = transfer(S, R, H, v1, thbar, cfg, ritc)
    ao = transfer(S, R, H, v2o, thbar, cfg, ritc)
    an = transfer(S, R, H, v2n, thbar, cfg, ritc)
    centre = {"V1_v99": var_q(a1, 0.99), "V1_v995": var_q(a1, 0.995),
              "V2_old_v995": var_q(ao, 0.995), "V2_new_v995": var_q(an, 0.995),
              "V2_d995": var_q(an, 0.995) - var_q(ao, 0.995)}
    acc = {"V1_v99": [], "V1_v995": [], "V2_d995": []}
    for _ in range(B):
        idx = draw_syn(rng)
        i = rng.integers(0, ndraw)
        th = {p: draws[p][i] for p in draws}
        a1b = transfer(S[idx], R[idx], H[idx], v1, th, cfg, ritc[idx])
        acc["V1_v99"].append(var_q(a1b, 0.99)); acc["V1_v995"].append(var_q(a1b, 0.995))
        aob = transfer(S[idx], R[idx], H[idx], v2o, th, cfg, ritc[idx])
        anb = transfer(S[idx], R[idx], H[idx], v2n, th, cfg, ritc[idx])
        acc["V2_d995"].append(var_q(anb, 0.995) - var_q(aob, 0.995))
    return thbar, centre, {k: ci(v) for k, v in acc.items()}


def main():
    idata, sample = fit_k_half()
    params, diagnostics, probs, draws_half = summarise(idata)

    draws_adopted, ref, hlo, hce = load_draws()
    cfg = (ref, hlo, hce)
    pool = load_pool()
    ritc = load_ritc(pool[3], pool[4])
    targets = load_targets()
    mean_a, centre_a, int_a = vignettes(draws_adopted, cfg, pool, ritc, targets)
    mean_h, centre_h, int_h = vignettes(draws_half, cfg, pool, ritc, targets)

    recorded = json.load(io.open(GAMMA0, encoding="utf-8"))["full_operator"]["centre"]
    if recorded != centre_a:
        raise SystemExit("the published fit's vignette centres differ from check_gamma0_vignette.py's record: "
                         "%s against %s" % (centre_a, recorded))

    def sig(m, r):
        return float(sigma_theta(r, H_RATIO, m["k"], m["gamma"], m["sd_undiv"], m["sd_div"], *cfg))

    ratio_a = sig(mean_a, 100.0) / sig(mean_a, 2000.0)
    ratio_h = sig(mean_h, 100.0) / sig(mean_h, 2000.0)
    rows = [{"R_m": r, "adopted": sig(mean_a, r), "k_half": sig(mean_h, r),
             "k_half_over_adopted": sig(mean_h, r) / sig(mean_a, r)} for r in SIZES]
    h = headline()

    out = {
        "question": ("What does fixing the pooling exponent at k = 1/2, the lower end of its theoretical bracket, "
                     "do to the fitted scale and the transferred stresses?"),
        **sample, "fit_seed": FIT_SEED, "draws": DRAWS, "tune": TUNE, "chains": CHAINS,
        "target_accept": TARGET_ACCEPT,
        "k_half_fit": {"spec": "adopted_model.scale_block(k_prior='fixed_0.5'): k = 1/2; every other term as the "
                               "headline calibration",
                       "params": params, "diagnostics": diagnostics, "posterior_prob": probs},
        "headline_params": {p: {"mean": float(h[p]["mean"]), "sd": float(h[p]["sd"]),
                                "hdi_2.5": float(h[p]["hdi_2.5"]), "hdi_97.5": float(h[p]["hdi_97.5"])}
                            for p in ("k",) + PARAMS},
        "vignettes": {
            "seed": VIG_SEED, "B": B,
            "estimator": ("check_gamma0_vignette.py's full-operator run: centre on the whole pool at the posterior "
                          "means; intervals are the 2.5 and 97.5 percentiles over a cluster bootstrap by syndicate "
                          "with one posterior draw per replicate (not a posterior interval)"),
            "adopted": {"posterior_means": mean_a, "centre": centre_a, "intervals": int_a},
            "k_half": {"posterior_means": mean_h, "centre": centre_h, "intervals": int_h},
            "centre_pct_change": {q: 100.0 * (centre_h[q] / centre_a[q] - 1.0) for q in centre_a},
        },
        "size_ratio_100_2000": {"H": H_RATIO, "adopted": ratio_a, "k_half": ratio_h,
                                "pct_change": 100.0 * (ratio_h / ratio_a - 1.0)},
        "sigma_by_size": {"H": H_RATIO, "rows": rows},
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("Wrote %s" % OUT)
    print("  k = 1/2 fit: divergences %d, max R-hat %.3f, min bulk ESS %.0f"
          % (diagnostics["divergences"], diagnostics["max_rhat"], diagnostics["min_ess_bulk"]))
    for q in ("V1_v99", "V1_v995", "V2_d995"):
        print("  %-8s adopted %.4f   k = 1/2 %.4f   (%+.2f%%)"
              % (q, centre_a[q], centre_h[q], out["vignettes"]["centre_pct_change"][q]))
    print("  100m/2,000m ratio: adopted %.3f   k = 1/2 %.3f" % (ratio_a, ratio_h))


if __name__ == "__main__":
    sys.exit(main())
