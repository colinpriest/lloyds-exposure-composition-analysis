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
    transfer, targets, cluster resampler, seed and B of check_gamma0_vignette.py (its own
    function, called here): the centre at the posterior means, and intervals over the cluster
    bootstrap with one posterior draw per replicate. Both fits read the same resampled
    syndicates and draw indices. The figures are computed under the paper's headline
    size-only operator (gamma zeroed in each draw of each fit, transfer_operator.py) and,
    as the labelled sensitivity, under the fitted concentration overlay;
  - the 100m/2,000m scale ratio at H = 0.4, and the fitted scale across the size range, at
    the posterior means: properties of each fitted scale law, gamma as fitted.

The published fit's centres must equal check_gamma0_vignette.py's record for the same
operator, or the comparison is not like for like and nothing is written.

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
import transfer_operator
from check_gamma0_vignette import operator_vignettes
from vignette_uncertainty import load_pool, load_draws, load_ritc, load_targets, sigma_theta

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


def vignettes(draws, cfg, pool, ritc, targets, mode):
    """check_gamma0_vignette.py's run for one operator, on the given draws: the same function, not a copy."""
    block = operator_vignettes(mode, pool, draws, cfg, ritc, targets, b=B, seed=VIG_SEED)
    thbar = {p: float(np.mean(draws[p])) for p in draws}      # the fitted means (gamma as fitted)
    return thbar, block


def comparison(mode, draws_adopted, draws_half, cfg, pool, ritc, targets, recorded):
    """Both fits' vignette figures under one operator, the adopted fit's checked against the record."""
    mean_a, blk_a = vignettes(draws_adopted, cfg, pool, ritc, targets, mode)
    mean_h, blk_h = vignettes(draws_half, cfg, pool, ritc, targets, mode)
    if recorded[mode]["centre"] != blk_a["centre"]:
        raise SystemExit("the published fit's %s vignette centres differ from check_gamma0_vignette.py's record: "
                         "%s against %s" % (mode, blk_a["centre"], recorded[mode]["centre"]))
    ca, ch = blk_a["centre"], blk_h["centre"]
    return mean_a, mean_h, {
        **transfer_operator.stamp(mode),
        "adopted": {"posterior_means": mean_a, "centre": ca, "intervals": blk_a["intervals"]},
        "k_half": {"posterior_means": mean_h, "centre": ch, "intervals": blk_h["intervals"]},
        "centre_pct_change": {q: 100.0 * (ch[q] / ca[q] - 1.0) for q in ca},
    }


def main():
    idata, sample = fit_k_half()
    params, diagnostics, probs, draws_half = summarise(idata)

    draws_adopted, ref, hlo, hce = load_draws()
    cfg = (ref, hlo, hce)
    pool = load_pool()
    ritc = load_ritc(pool[3], pool[4])
    targets = load_targets()
    recorded = json.load(io.open(GAMMA0, encoding="utf-8"))
    mean_a, mean_h, head = comparison(transfer_operator.HEADLINE, draws_adopted, draws_half, cfg, pool, ritc,
                                      targets, recorded)
    _ma, _mh, over = comparison(transfer_operator.SENSITIVITY, draws_adopted, draws_half, cfg, pool, ritc,
                                targets, recorded)

    def sig(m, r, h=H_RATIO):
        return float(sigma_theta(r, h, m["k"], m["gamma"], m["sd_undiv"], m["sd_div"], *cfg))

    ratio_a = sig(mean_a, 100.0) / sig(mean_a, 2000.0)
    ratio_h = sig(mean_h, 100.0) / sig(mean_h, 2000.0)
    # the same ratio under the paper's headline operator, gamma zeroed as the operator zeroes it: the concentration
    # term drops out, so the ratio is the same at every H (round 62's verification, N-V-A-4: the sentence printed
    # the overlay's ratio at H = 0.4 and named neither)
    so_a, so_h = (transfer_operator.params(m, transfer_operator.HEADLINE) for m in (mean_a, mean_h))
    ratio_so_a = sig(so_a, 100.0) / sig(so_a, 2000.0)
    ratio_so_h = sig(so_h, 100.0) / sig(so_h, 2000.0)
    for h in (0.2, 1.0):
        if abs(sig(so_a, 100.0, h) / sig(so_a, 2000.0, h) - ratio_so_a) > 1e-12:
            raise SystemExit("the size-only 100m/2,000m ratio depends on H: gamma is not zeroed")
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
        # the transferred stresses under the paper's headline (size-only) operator, at the top level of this
        # block as before; the same comparison under the concentration overlay is the labelled sensitivity
        "vignettes": {
            "seed": VIG_SEED, "B": B,
            "estimator": ("check_gamma0_vignette.py's run for each operator: centre on the whole pool at the "
                          "posterior means; intervals are the 2.5 and 97.5 percentiles over a cluster bootstrap by "
                          "syndicate with one posterior draw per replicate (not a posterior interval)"),
            **head,
            "overlay_sensitivity": over,
        },
        # the fitted scale law of each fit (gamma as fitted in each), which is a property of the fit, not a transfer:
        # the scale law the concentration overlay applies, at H = 0.4
        "size_ratio_100_2000": {"H": H_RATIO, "scale_law": "each fit's posterior-mean scale law, gamma as fitted",
                                **transfer_operator.stamp(transfer_operator.SENSITIVITY),
                                "adopted": ratio_a, "k_half": ratio_h,
                                "pct_change": 100.0 * (ratio_h / ratio_a - 1.0)},
        # and the scale law the headline size-only operator applies (gamma zeroed): the same at every H
        "size_ratio_100_2000_size_only": {"H": "any: with gamma zeroed the ratio does not depend on H",
                                          "scale_law": "each fit's posterior-mean scale law, gamma zeroed",
                                          **transfer_operator.stamp(transfer_operator.HEADLINE),
                                          "adopted": ratio_so_a, "k_half": ratio_so_h,
                                          "pct_change": 100.0 * (ratio_so_h / ratio_so_a - 1.0)},
        "sigma_by_size": {"H": H_RATIO, "scale_law": "each fit's posterior-mean scale law, gamma as fitted",
                          "rows": rows},
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("Wrote %s" % OUT)
    print("  k = 1/2 fit: divergences %d, max R-hat %.3f, min bulk ESS %.0f"
          % (diagnostics["divergences"], diagnostics["max_rhat"], diagnostics["min_ess_bulk"]))
    for tag, blk in (("size-only", head), ("overlay", over)):
        for q in ("V1_v99", "V1_v995", "V2_d995"):
            print("  %-9s %-8s adopted %.4f   k = 1/2 %.4f   (%+.2f%%)"
                  % (tag, q, blk["adopted"]["centre"][q], blk["k_half"]["centre"][q], blk["centre_pct_change"][q]))
    print("  100m/2,000m ratio: adopted %.3f   k = 1/2 %.3f" % (ratio_a, ratio_h))


if __name__ == "__main__":
    sys.exit(main())
