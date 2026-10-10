"""Sensitivity: the adopted model refitted with the concentration exponent gamma fixed at 0 in the likelihood.

The paper's headline operator is size-only: gamma is set to zero in every retained posterior draw of the
adopted, gamma-inclusive fit (transfer_operator.py). That is not a refit. The fit estimates the other
parameters while gamma absorbs part of the size signal, and nothing says they would keep their values if the
likelihood itself carried no concentration term. This script answers that. It refits the adopted two-regime
model with gamma the constant 0 (scale_block's gamma_prior="fixed_0", the only departure; data, priors, sampler
and seed as the headline calibration) and records, beside the published fit:

  - k, the floor sigma_undiv, sigma_div, nu_clean and nu_RITC (and lambda, beta_RITC, tau_s), each with its
    posterior mean and 95% HDI, and the refit's divergences, R-hat and effective sample size;
  - Vignette 1's VaR99 and VaR99.5 and Vignette 2's paired change at 99.5%, through the transfer, targets,
    cluster resampler, seed and B of check_gamma0_vignette.py (its own function, called here), under the
    headline size-only operator: the centre at the posterior means and intervals over the cluster bootstrap
    with one posterior draw per replicate; the published fit's centres must equal that script's record, or the
    comparison is not like for like and nothing is written;
  - each headline quantity's relative change, and the list of those that move by 2% or more;
  - the 100m/2,000m scale ratio of each fit's size-only scale law;
  - the refit's gaps from the published posterior in the units of adopted_model.check_against_headline, RECORDED
    and not enforced: gamma is 0 by construction (more than that guard's half posterior SD from the published
    gamma) and sigma_div moves with the concentration factor the published scale carries. The refit is a
    departure by declaration.

There is no overlay leg: with no gamma in the likelihood there is no fitted concentration exponent to apply.

Writes check_gamma0_refit_results.json.
Usage:  python src/check_gamma0_refit.py [B]
"""
import io
import json
import sys
import time

import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from adopted_model import (SD, HEADLINE_JSON, load_sample, scale_block, headline, check_against_headline,
                           SAMPLE_CORES)
import transfer_operator
from check_gamma0_vignette import operator_vignettes
from vignette_uncertainty import load_pool, load_draws, load_ritc, load_targets, sigma_theta

OUT = SD / "results" / "check_gamma0_refit_results.json"
GAMMA0 = SD / "results" / "check_gamma0_vignette_results.json"
B = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4000
VIG_SEED = 20240704          # check_gamma0_vignette.py's
FIT_SEED = 42                # the headline calibration's
DRAWS, TUNE, CHAINS, TARGET_ACCEPT = 1500, 1500, 4, 0.98
PARAMS = ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s")
#: the parameters the vignettes read; the published fit carries gamma as well, which the size-only operator zeroes
DRAW_PARAMS = ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")
QUANTITIES = ("V1_v99", "V1_v995", "V2_d995")
#: the quantities a move of RELATIVE_FLAG or more is reported on, as the brief for this check names them
HEADLINE_QUANTITIES = ("k", "sd_undiv", "V1_v995", "V2_d995")
RELATIVE_FLAG = 0.02
SIZE_RATIO_RS = (100.0, 2000.0)
H_RATIO = 0.4


def fit_gamma0():
    S, R, H, yr, syn, ritc = load_sample()
    with pm.Model():
        b = scale_block(R, H, yr, ritc, gamma_prior="fixed_0")
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=SAMPLE_CORES,
                          target_accept=TARGET_ACCEPT, random_seed=FIT_SEED, progressbar=False)
    return idata, {"n": int(len(S)), "n_ritc": int(ritc.sum()), "n_years": int(len(np.unique(yr)))}


def summarise(idata):
    summ = az.summary(idata, var_names=list(PARAMS), hdi_prob=0.95, round_to="none")
    params = {p: {"mean": float(summ.loc[p, "mean"]), "sd": float(summ.loc[p, "sd"]),
                  "hdi_2.5": float(summ.loc[p, "hdi_2.5%"]), "hdi_97.5": float(summ.loc[p, "hdi_97.5%"]),
                  "r_hat": float(summ.loc[p, "r_hat"]), "ess_bulk": float(summ.loc[p, "ess_bulk"])}
              for p in PARAMS}
    diagnostics = {"max_rhat": float(summ["r_hat"].max()),
                   "min_ess_bulk": float(summ["ess_bulk"].min()),
                   "divergences": int(idata.sample_stats["diverging"].sum())}
    post = idata.posterior
    lam = post["lambda_ritc"].values.ravel()
    draws = {p: post[p].values.ravel() for p in DRAW_PARAMS}
    draws["gamma"] = np.zeros(lam.size)                     # the likelihood has none: the operator's own value
    return params, diagnostics, {"nu_ritc_lt_nu_clean": float((lam > 0).mean())}, draws


def relative(new, old):
    return new / old - 1.0


def size_ratio(means, cfg):
    """sigma(100m) / sigma(2,000m) under one fit's scale law at its posterior means, gamma as the operator sets it."""
    so = transfer_operator.params(means, transfer_operator.HEADLINE)
    s = [float(sigma_theta(r, H_RATIO, so["k"], so["gamma"], so["sd_undiv"], so["sd_div"], *cfg))
         for r in SIZE_RATIO_RS]
    return s[0] / s[1]


def main():
    t0 = time.time()
    idata, sample = fit_gamma0()
    params, diagnostics, probs, draws_refit = summarise(idata)

    draws_adopted, ref, hlo, hce = load_draws()
    cfg = (ref, hlo, hce)
    pool = load_pool()
    ritc = load_ritc(pool[3], pool[4])
    targets = load_targets()
    recorded = json.load(io.open(GAMMA0, encoding="utf-8"))[transfer_operator.HEADLINE]
    mode = transfer_operator.HEADLINE
    blk_a = operator_vignettes(mode, pool, draws_adopted, cfg, ritc, targets, b=B, seed=VIG_SEED)
    if recorded["centre"] != blk_a["centre"]:
        raise SystemExit("the published fit's %s vignette centres differ from check_gamma0_vignette.py's record: "
                         "%s against %s" % (mode, blk_a["centre"], recorded["centre"]))
    blk_r = operator_vignettes(mode, pool, draws_refit, cfg, ritc, targets, b=B, seed=VIG_SEED)
    ca, cr = blk_a["centre"], blk_r["centre"]
    vignettes = {
        "seed": VIG_SEED, "B": B,
        "estimator": ("check_gamma0_vignette.py's run for the headline operator: centre on the whole pool at the "
                      "posterior means; intervals are the 2.5 and 97.5 percentiles over a cluster bootstrap by "
                      "syndicate with one posterior draw per replicate (not a posterior interval)"),
        **transfer_operator.stamp(mode),
        "adopted": {"centre": ca, "intervals": blk_a["intervals"]},
        "gamma0_refit": {"centre": cr, "intervals": blk_r["intervals"]},
        "centre_pct_change": {q: 100.0 * relative(cr[q], ca[q]) for q in ca},
        "centre_change": {q: cr[q] - ca[q] for q in ca},
    }

    means_a = {p: float(np.mean(draws_adopted[p])) for p in DRAW_PARAMS + ("gamma",)}
    means_r = {p: float(np.mean(draws_refit[p])) for p in DRAW_PARAMS + ("gamma",)}
    ratio_a, ratio_r = size_ratio(means_a, cfg), size_ratio(means_r, cfg)

    h = headline()
    full = json.load(io.open(HEADLINE_JSON, encoding="utf-8"))
    # the published means at the precision the calibration stores them (its params block rounds to three decimals)
    adopted_params = {p: {"mean": float(full[p]) if p in full else float(h[p]["mean"]), "sd": float(h[p]["sd"]),
                          "hdi_2.5": float(h[p]["hdi_2.5"]), "hdi_97.5": float(h[p]["hdi_97.5"])}
                      for p in PARAMS}
    relative_change = {p: relative(params[p]["mean"], adopted_params[p]["mean"]) for p in PARAMS}
    relative_change.update({q: relative(cr[q], ca[q]) for q in ca})
    moved = sorted(q for q in HEADLINE_QUANTITIES if abs(relative_change[q]) >= RELATIVE_FLAG)

    # gamma enters as the exact zeros the likelihood fixes it at, so the guard names all nine shared parameters
    # (src/test_model_variants.py holds every record's guard rows to that)
    guard_ok, guard_rows = check_against_headline({
        **{p: draws_refit[p] for p in DRAW_PARAMS + ("gamma",)},
        **{p: idata.posterior[p].values.ravel() for p in ("lambda_ritc", "beta_ritc", "tau_s")}})
    out = {
        "question": ("What does fixing the concentration exponent at 0 in the likelihood, a refit rather than a "
                     "zeroing of the retained draws, do to the fitted scale and the transferred stresses?"),
        **sample, "fit_seed": FIT_SEED, "draws": DRAWS, "tune": TUNE, "chains": CHAINS,
        "target_accept": TARGET_ACCEPT,
        "gamma0_fit": {"spec": "adopted_model.scale_block(gamma_prior='fixed_0'): gamma = 0, no concentration term in "
                               "the likelihood; every other term as the headline calibration",
                       "params": params, "diagnostics": diagnostics, "posterior_prob": probs},
        "adopted_params": adopted_params,
        "relative_change_of_means": relative_change,
        "headline_quantities_moved_by_2pct_or_more": moved,
        "relative_flag": RELATIVE_FLAG,
        "headline_guard": {"enforced": False,
                           "why_not": ("the refit is a departure by declaration: gamma is 0 by construction, "
                                       "which is itself more than TOL_SD posterior SDs from the published gamma, and "
                                       "sigma_div moves with the concentration factor the published scale carries; "
                                       "the rows are recorded so the size of each gap can be read"),
                           "within_tolerance": bool(guard_ok), "rows": guard_rows},
        "vignettes": vignettes,
        "size_ratio_100_2000_size_only": {
            "scale_law": "each fit's posterior-mean scale law, gamma zeroed (the refit has none)",
            **transfer_operator.stamp(mode),
            "adopted": ratio_a, "gamma0_refit": ratio_r, "pct_change": 100.0 * relative(ratio_r, ratio_a)},
        "runtime_seconds": time.time() - t0,
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=2) + "\n")
    print("Wrote %s" % OUT)
    print("  gamma = 0 refit: divergences %d, max R-hat %.3f, min bulk ESS %.0f"
          % (diagnostics["divergences"], diagnostics["max_rhat"], diagnostics["min_ess_bulk"]))
    for p in PARAMS:
        print("  %-11s adopted %8.4f   refit %8.4f [%8.4f, %8.4f]   (%+.2f%%)"
              % (p, adopted_params[p]["mean"], params[p]["mean"], params[p]["hdi_2.5"], params[p]["hdi_97.5"],
                 100 * relative_change[p]))
    for q in QUANTITIES:
        print("  %-8s adopted %.4f   refit %.4f   (%+.2f%%)" % (q, ca[q], cr[q], vignettes["centre_pct_change"][q]))
    print("  100m/2,000m size-only ratio: adopted %.3f   refit %.3f" % (ratio_a, ratio_r))
    print("  headline guard (recorded, not enforced): %s" % ("within tolerance" if guard_ok else "outside tolerance"))
    if moved:
        print("  MOVED BY 2%% OR MORE: %s" % ", ".join(moved))


if __name__ == "__main__":
    sys.exit(main())
