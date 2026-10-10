"""Sensitivity: the adopted model with the pooling exponent k on a wider support.

Theory bounds the pooling exponent to [1/2, 1] (finite-variance independent sqrt-N pooling to comonotonic
pooling), and the headline prior keeps k inside that bracket: k = 1/2 + 1/2 logistic(theta), theta ~ N(0, 1.5).
The bracket's lower end therefore cannot be tested by the headline fit: its posterior cannot put any mass below
1/2, whatever the data say. This script refits the adopted two-regime model with k on two wider supports,

    k = k_lo + (1 - k_lo) logistic(theta),   theta ~ N(0, 1.5),   k_lo = 1/4 and k_lo = 0,

(scale_block's k_prior="logistic_0.25" and "logistic_0", the only departure; data, other priors, sampler and seed
as the headline calibration), and records for each fit, beside the published one:

  - the posterior of k: mean, 95% HDI, the 0.5% quantile and the minimum draw;
  - the posterior mass below 1/2, beside the PRIOR mass below 1/2 on the same support. The prior mass is computed
    here, in closed form from the theta prior read off the model graph, and checked by draws from the model's own
    prior; check_prior_masses.prior_masses is not used for it, because that function states P(k > 1/2) as one,
    which is true only on the bracketed support. A posterior mass is evidence only beside the prior's;
  - the same two masses at the edges of the support (within 5% of its width of each end), so a bound that binds
    shows as a pile-up the prior does not put there;
  - the floor sigma_undiv, sigma_div, the tail indices, divergences, R-hat and effective sample size;
  - Vignette 1's VaR99 and VaR99.5 and Vignette 2's paired change at 99.5%, through the transfer, targets,
    cluster resampler, seed and B of check_gamma0_vignette.py (its own function, called here), under the headline
    size-only operator and, as the labelled sensitivity, the fitted concentration overlay. The published fit's
    centres must equal that script's record, or the comparison is not like for like and nothing is written;
  - each headline quantity's relative change, and the list of those that move by 2% or more.

k below 1/2 has no finite-variance exchangeable-block reading (heavy tails or heteroskedasticity can also
produce it), so a wider fit is a diagnostic of the bracket, not a candidate headline.

Writes check_k_support_results.json.
Usage:  python src/check_k_support.py [B]
"""
import io
import json
import sys
import time

import numpy as np
from scipy import stats
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

import adopted_model
from adopted_model import SD, K_LOWER, load_sample, scale_block, headline, check_against_headline, SAMPLE_CORES
import transfer_operator
from check_gamma0_vignette import operator_vignettes
from check_prior_masses import prior_of
from vignette_uncertainty import load_pool, load_draws, load_ritc, load_targets

OUT = SD / "results" / "check_k_support_results.json"
GAMMA0 = SD / "results" / "check_gamma0_vignette_results.json"
B = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4000
VIG_SEED = 20240704          # check_gamma0_vignette.py's
FIT_SEED = 42                # the headline calibration's
DRAWS, TUNE, CHAINS, TARGET_ACCEPT = 1500, 1500, 4, 0.98
PRIOR_MC_DRAWS, PRIOR_MC_SEED = 200000, 20261010
PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s")
DRAW_PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")
SUPPORTS = ("logistic_0.25", "logistic_0")
QUANTILES = (0.005, 0.025, 0.5, 0.975)
EDGE = 0.05                  # an edge zone is this share of the support's width, at each end
HEADLINE_QUANTITIES = ("k", "sd_undiv", "V1_v995", "V2_d995")
RELATIVE_FLAG = 0.02
VIG_QUANTITIES = ("V1_v99", "V1_v995", "V2_d995")


def k_cdf_prior(k_lo, c, mu, sd):
    """Prior P(k < c) on the support (k_lo, 1), k = k_lo + (1 - k_lo) logistic(theta), theta ~ N(mu, sd): exact.

    Zero at or below the lower end and one at or above 1. On the bracket k_lo = 1/2 it is zero below 1/2, so the
    event 'k < 1/2' has prior mass 0 there and P(k > 1/2) is one only because the bracket excludes the rest."""
    if c <= k_lo:
        return 0.0
    if c >= 1.0:
        return 1.0
    u = (c - k_lo) / (1.0 - k_lo)
    return float(stats.norm.cdf((np.log(u / (1.0 - u)) - mu) / sd))


def prior_model(k_prior):
    S, R, H, yr, syn, ritc = load_sample()
    with pm.Model() as m:
        scale_block(R=R, H=H, yr=yr, ritc=ritc, k_prior=k_prior)
    return m


def prior_masses(k_prior):
    """Prior P(k < 1/2) and the edge masses on one support, in closed form, and by draws from the model's prior."""
    m = prior_model(k_prior)
    fam, (mu, sd) = prior_of(m, "theta")
    if fam != "NormalRV":
        raise SystemExit("the prior on theta is now %s, not NormalRV: the closed form must be re-derived" % fam)
    k_lo = K_LOWER[k_prior]
    width = 1.0 - k_lo
    lo_edge, hi_edge = k_lo + EDGE * width, 1.0 - EDGE * width
    closed = {"k_lt_0.5": k_cdf_prior(k_lo, 0.5, mu, sd), "k_lt_0.55": k_cdf_prior(k_lo, 0.55, mu, sd),
              "k_in_lower_edge": k_cdf_prior(k_lo, lo_edge, mu, sd),
              "k_in_upper_edge": 1.0 - k_cdf_prior(k_lo, hi_edge, mu, sd)}
    draws = np.asarray(pm.draw(m["k"], draws=PRIOR_MC_DRAWS, random_seed=PRIOR_MC_SEED)).ravel()
    mc = {"k_lt_0.5": float((draws < 0.5).mean()), "k_lt_0.55": float((draws < 0.55).mean()),
          "k_in_lower_edge": float((draws < lo_edge).mean()), "k_in_upper_edge": float((draws > hi_edge).mean())}
    for key, p in closed.items():
        tol = 5.0 * np.sqrt(max(p * (1.0 - p), 1e-12) / PRIOR_MC_DRAWS) + 1e-3
        if abs(mc[key] - p) > tol:
            raise SystemExit("the prior mass %s on %s disagrees with a draw from the model's own prior: %.4f against "
                             "%.4f" % (key, k_prior, p, mc[key]))
    return {"theta_prior": {"family": fam, "mu": mu, "sd": sd}, "k_lower": k_lo, "edge_share_of_support": EDGE,
            "edge_zone": [lo_edge, hi_edge], "closed_form": closed, "monte_carlo": mc,
            "monte_carlo_draws": PRIOR_MC_DRAWS, "monte_carlo_seed": PRIOR_MC_SEED,
            "monte_carlo_tolerance": "5 binomial standard errors + 0.001"}


def k_posterior(k, k_lo):
    """The posterior of k on a support whose lower end is k_lo: moments, quantiles, masses below 1/2 and at the edges."""
    width = 1.0 - k_lo
    lo_edge, hi_edge = k_lo + EDGE * width, 1.0 - EDGE * width
    hdi = az.hdi(np.asarray(k, float), hdi_prob=0.95, round_to="none")
    return {"mean": float(np.mean(k)), "sd": float(np.std(k, ddof=1)),
            "hdi_2.5": float(hdi[0]), "hdi_97.5": float(hdi[1]),
            "quantiles": {"%g" % q: float(np.quantile(k, q)) for q in QUANTILES},
            "min": float(np.min(k)), "max": float(np.max(k)), "n_draws": int(np.size(k)),
            "k_lt_0.5": float((k < 0.5).mean()), "k_lt_0.55": float((k < 0.55).mean()),
            "k_in_lower_edge": float((k < lo_edge).mean()), "k_in_upper_edge": float((k > hi_edge).mean())}


def fit_support(k_prior):
    S, R, H, yr, syn, ritc = load_sample()
    with pm.Model():
        b = scale_block(R, H, yr, ritc, k_prior=k_prior)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=SAMPLE_CORES,
                          target_accept=TARGET_ACCEPT, random_seed=FIT_SEED, progressbar=False)
    return idata


def summarise(idata):
    summ = az.summary(idata, var_names=list(PARAMS), hdi_prob=0.95, round_to="none")
    params = {p: {"mean": float(summ.loc[p, "mean"]), "sd": float(summ.loc[p, "sd"]),
                  "hdi_2.5": float(summ.loc[p, "hdi_2.5%"]), "hdi_97.5": float(summ.loc[p, "hdi_97.5%"]),
                  "r_hat": float(summ.loc[p, "r_hat"]), "ess_bulk": float(summ.loc[p, "ess_bulk"])}
              for p in PARAMS}
    diagnostics = {"max_rhat": float(summ["r_hat"].max()), "min_ess_bulk": float(summ["ess_bulk"].min()),
                   "divergences": int(idata.sample_stats["diverging"].sum())}
    post = idata.posterior
    lam = post["lambda_ritc"].values.ravel()
    every = {p: post[p].values.ravel() for p in PARAMS}      # for the headline guard's rows
    draws = {p: every[p] for p in DRAW_PARAMS}               # what the transfer reads
    return params, diagnostics, {"nu_ritc_lt_nu_clean": float((lam > 0).mean())}, draws, every


def relative(new, old):
    return new / old - 1.0


def compare_vignettes(mode, pool, draws_adopted, draws_fits, cfg, ritc, targets, recorded):
    """Both operators' blocks for the adopted fit (checked against check_gamma0_vignette.py's record) and each
    wider fit, from check_gamma0_vignette.operator_vignettes."""
    blk_a = operator_vignettes(mode, pool, draws_adopted, cfg, ritc, targets, b=B, seed=VIG_SEED)
    if recorded[mode]["centre"] != blk_a["centre"]:
        raise SystemExit("the published fit's %s vignette centres differ from check_gamma0_vignette.py's record: "
                         "%s against %s" % (mode, blk_a["centre"], recorded[mode]["centre"]))
    ca = blk_a["centre"]
    out = {**transfer_operator.stamp(mode), "adopted": {"centre": ca, "intervals": blk_a["intervals"]}}
    for name, draws in draws_fits.items():
        blk = operator_vignettes(mode, pool, draws, cfg, ritc, targets, b=B, seed=VIG_SEED)
        cf = blk["centre"]
        out[name] = {"centre": cf, "intervals": blk["intervals"],
                     "centre_pct_change": {q: 100.0 * relative(cf[q], ca[q]) for q in ca},
                     "centre_change": {q: cf[q] - ca[q] for q in ca}}
    return out


def main():
    t0 = time.time()
    fits, draws_fits, every_fits, priors = {}, {}, {}, {}
    for k_prior in SUPPORTS:
        idata = fit_support(k_prior)
        params, diagnostics, probs, draws, every = summarise(idata)
        k_lo = K_LOWER[k_prior]
        priors[k_prior] = prior_masses(k_prior)
        post_k = k_posterior(draws["k"], k_lo)
        fits[k_prior] = {"spec": "adopted_model.scale_block(k_prior=%r): k = %g + %g logistic(theta), theta ~ N(0, 1.5); "
                                 "every other term as the headline calibration" % (k_prior, k_lo, 1.0 - k_lo),
                         "k_lower": k_lo, "params": params, "diagnostics": diagnostics, "posterior_prob": probs,
                         "k_posterior": post_k,
                         "mass_below_half": {"posterior": post_k["k_lt_0.5"],
                                             "prior": priors[k_prior]["closed_form"]["k_lt_0.5"]}}
        draws_fits[k_prior] = draws
        every_fits[k_prior] = every
    S, R, H, yr, syn, ritc_s = load_sample()
    sample = {"n": int(len(S)), "n_ritc": int(ritc_s.sum()), "n_years": int(len(np.unique(yr)))}

    draws_adopted, ref, hlo, hce = load_draws()
    cfg = (ref, hlo, hce)
    pool = load_pool()
    ritc = load_ritc(pool[3], pool[4])
    targets = load_targets()
    recorded = json.load(io.open(GAMMA0, encoding="utf-8"))
    head = compare_vignettes(transfer_operator.HEADLINE, pool, draws_adopted, draws_fits, cfg, ritc, targets, recorded)
    over = compare_vignettes(transfer_operator.SENSITIVITY, pool, draws_adopted, draws_fits, cfg, ritc, targets,
                             recorded)

    full = json.load(io.open(adopted_model.HEADLINE_JSON, encoding="utf-8"))
    h = headline()
    adopted_params = {p: {"mean": float(full[p]) if p in full else float(h[p]["mean"]), "sd": float(h[p]["sd"]),
                          "hdi_2.5": float(h[p]["hdi_2.5"]), "hdi_97.5": float(h[p]["hdi_97.5"])} for p in PARAMS}
    k_a = draws_adopted["k"]
    adopted_k = k_posterior(k_a, 0.5)
    adopted_k["mass_below_half_prior"] = 0.0

    moved, relative_change, guard = {}, {}, {}
    for name in SUPPORTS:
        rc = {p: relative(fits[name]["params"][p]["mean"], adopted_params[p]["mean"]) for p in PARAMS}
        rc.update({q: relative(head[name]["centre"][q], head["adopted"]["centre"][q])
                   for q in head["adopted"]["centre"]})
        relative_change[name] = rc
        moved[name] = sorted(q for q in HEADLINE_QUANTITIES if abs(rc[q]) >= RELATIVE_FLAG)
        ok, rows = check_against_headline(every_fits[name])
        guard[name] = {"within_tolerance": bool(ok), "rows": rows}

    out = {
        "question": ("What do the data say about the pooling exponent below 1/2, the lower end of its theoretical "
                     "bracket, when the prior allows it, and does the bracket drive the numbers a practitioner uses?"),
        **sample, "fit_seed": FIT_SEED, "draws": DRAWS, "tune": TUNE, "chains": CHAINS,
        "target_accept": TARGET_ACCEPT,
        "supports": list(SUPPORTS),
        "adopted": {"support": "k = 1/2 + 1/2 logistic(theta): the bracket [1/2, 1]", "params": adopted_params,
                    "k_posterior": adopted_k, "mass_below_half": {"posterior": adopted_k["k_lt_0.5"], "prior": 0.0}},
        "fits": fits,
        "prior_masses": priors,
        "prior_masses_note": ("computed here from the theta prior read off the model graph (closed form) and checked "
                              "against draws from the model's own prior; check_prior_masses.prior_masses is not used, "
                              "because it states P(k > 1/2) as one, true only on the bracketed support"),
        "relative_change_of_means": relative_change,
        "headline_quantities_moved_by_2pct_or_more": moved,
        "relative_flag": RELATIVE_FLAG,
        "headline_guard": {"enforced": False,
                           "why_not": ("k is the parameter these fits free; the rows record how far each shared "
                                       "parameter sits from the published posterior, in its posterior SDs"),
                           "fits": guard},
        "vignettes": {
            "seed": VIG_SEED, "B": B,
            "estimator": ("check_gamma0_vignette.py's run for each operator: centre on the whole pool at the "
                          "posterior means; intervals are the 2.5 and 97.5 percentiles over a cluster bootstrap by "
                          "syndicate with one posterior draw per replicate (not a posterior interval)"),
            **head,
            "overlay_sensitivity": over},
        "runtime_seconds": time.time() - t0,
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=2) + "\n")
    print("Wrote %s" % OUT)
    for name in SUPPORTS:
        f, kp = fits[name], fits[name]["k_posterior"]
        print("  %s: divergences %d, max R-hat %.3f, min bulk ESS %.0f"
              % (name, f["diagnostics"]["divergences"], f["diagnostics"]["max_rhat"], f["diagnostics"]["min_ess_bulk"]))
        print("    k %.4f [%.4f, %.4f]  0.5%% quantile %.4f  P(k<1/2): posterior %.3f, prior %.3f"
              % (kp["mean"], kp["hdi_2.5"], kp["hdi_97.5"], kp["quantiles"]["0.005"], kp["k_lt_0.5"],
                 priors[name]["closed_form"]["k_lt_0.5"]))
        print("    floor %.4f" % f["params"]["sd_undiv"]["mean"])
        for q in VIG_QUANTITIES:
            print("    %-8s adopted %.4f   wide %.4f   (%+.2f%%)"
                  % (q, head["adopted"]["centre"][q], head[name]["centre"][q], head[name]["centre_pct_change"][q]))
        if moved[name]:
            print("    MOVED BY 2%% OR MORE: %s" % ", ".join(moved[name]))


if __name__ == "__main__":
    sys.exit(main())
