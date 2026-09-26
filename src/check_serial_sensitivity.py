"""Exploratory subgroup and thinning diagnostics for within-syndicate dependence.

check_pyd_temporal_correlation.py (f) finds positive lag-1 association in the adopted model's own
residuals, given size, HHI, regime and reporting year: the likelihood's conditional independence is
not supported. The diagnostics below describe stability across selected subsamples; they do not
calibrate posterior uncertainty (frozen review of 26 September 2026, M01).

The likelihood multiplies one density per syndicate-YEAR, so if a syndicate's years carry common
information the posterior is narrower than the evidence warrants. Two questions, two designs, both of
them refits of the adopted model through adopted_model.scale_block with nothing changed but which
observations are included:

  A. GROUP DISPERSION. Split the syndicates into G disjoint groups and fit each. The ratio of the
     spread of subgroup posterior means to the subgroup posterior SD is descriptive only. Even under
     a correctly specified independent Bayesian model it need not equal one: prior shrinkage,
     different covariates and different information across groups all affect it. It is therefore not
     an uncertainty-inflation factor for the full-data posterior.

  B. THE ADJACENCY COMPONENT.  A thinned half keeps every other year within each syndicate, so
     consecutive-year pairs are removed; a random half keeps the same NUMBER of years per syndicate,
     drawn without regard to adjacency. The two have the same n and the same cluster sizes and differ
     in how much adjacency survives. One matched split is a stability contrast, not identification
     of a serial component: retained covariates and realised observations also differ.

What this is not: a cluster-aware likelihood, a repeated cluster-weighted full-data refit, a bound
on dependence at lags a lag-1 statistic cannot see, or a correction to the width the paper prints.

Writes check_serial_sensitivity_results.json.
Usage:  python src/check_serial_sensitivity.py
"""
import io
import json
from pathlib import Path

import numpy as np
import pytensor

pytensor.config.mode = "NUMBA"
import pymc as pm  # noqa: E402
import arviz as az  # noqa: E402

import adopted_model  # noqa: E402
from adopted_model import scale_block, SAMPLE_CORES  # noqa: E402

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_serial_sensitivity_results.json"
SEED = 20260925
#: the diagnostic's fits are shorter than the headline's 1500/1500: they are read for their spread and
#: their width, not for a published posterior, and eight of them run in about ten minutes.
DRAWS, TUNE, CHAINS = 1000, 1000, 4
#: disjoint syndicate groups for design A. Six keeps about twenty syndicates and a hundred-odd
#: observations in each, enough for k to be identified in every group.
N_GROUPS = 6
#: the parameters the comparison is read on: the two the paper's results turn on.
FOCUS = ("k", "gamma")
MAX_RHAT = 1.05
#: a group fit whose reported SD is at least this share of the parameter's PRIOR SD is not being driven
#: by its own data, and design A's ratio is then a statement about the prior. Read as "uninterpretable".
PRIOR_DOMINATED = 0.7


def prior_sds():
    """The prior SD of each focus parameter, drawn from the model's OWN prior.

    Design A compares the spread of group estimates with the width each group fit reports. That
    comparison only means anything where the group fits are driven by their data: on about twenty
    syndicates a weakly identified parameter reverts to its prior, its reported SD is the prior's, and
    the ratio measures the prior rather than any understatement. So the prior is sampled here, from
    scale_block itself rather than a retyped copy, and a parameter whose group fits sit within
    PRIOR_DOMINATED of it is reported as uninterpretable instead of as a finding.
    """
    S, R, H, yr, syn, ritc = adopted_model.load_sample()
    with pm.Model():
        scale_block(R=R, H=H, yr=yr, ritc=ritc)
        idata = pm.sample_prior_predictive(draws=4000, random_seed=SEED)
    pri = idata.prior
    return {p: float(np.asarray(pri[p]).ravel().std()) for p in FOCUS if p in pri}


def consecutive_pairs(yr, syn, mask):
    """How many consecutive-year pairs survive inside a subsample: the quantity design B varies."""
    n = 0
    for s in set(syn[mask].tolist()):
        years = sorted(yr[mask][syn[mask] == s].tolist())
        n += sum(1 for a, b in zip(years, years[1:]) if b == a + 1)
    return n


def fit(mask, label):
    """The adopted model on the observations `mask` selects, and nothing else changed."""
    S, R, H, yr, syn, ritc = adopted_model.load_sample()
    with pm.Model():
        b = scale_block(R=R[mask], H=H[mask], yr=yr[mask], ritc=ritc[mask])
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S[mask])
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=SAMPLE_CORES, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    post = idata.posterior
    draws = {p: np.asarray(post[p]).ravel() for p in adopted_model.SHARED if p in post}
    rhat = float(az.rhat(idata).to_array().max())
    div = int(idata.sample_stats["diverging"].sum())
    if rhat > MAX_RHAT:
        raise SystemExit("%s did not converge: max R-hat %.3f" % (label, rhat))
    ok, rows = adopted_model.check_against_headline(draws)
    out = {"label": label,
           # the manuscript's audit reports every recorded fit whose shared parameters move; a fit
           # without a spec string prints as "?" there, which tells a reader nothing
           "spec": "the adopted model on a subsample (%s): only the observations differ" % label,
           "n": int(mask.sum()),
           "n_syndicates": int(len(set(syn[mask].tolist()))),
           "n_consecutive_year_pairs": consecutive_pairs(yr, syn, mask),
           "max_rhat": rhat, "divergences": div,
           "adopted_model_consistent": bool(ok),
           "must_match_headline": False,
           "why_it_need_not": "a subsample of the working sample is expected to move the shared parameters; the "
                              "comparison is recorded to show HOW FAR it moves, not as a pass condition.",
           "gap_from_headline_in_sd": {r["param"]: r["gap_in_sd"] for r in rows}}
    for p in adopted_model.SHARED:
        if p in draws:
            out[p] = {"mean": float(draws[p].mean()), "sd": float(draws[p].std())}
    print("  %-14s n=%3d  syn=%3d  adj-pairs=%3d  " % (label, out["n"], out["n_syndicates"],
                                                       out["n_consecutive_year_pairs"])
          + "  ".join("%s %.4f (%.4f)" % (p, out[p]["mean"], out[p]["sd"]) for p in FOCUS))
    return out


def syndicate_groups(syn, n_groups, rng):
    """`n_groups` disjoint groups of syndicates, balanced on observation count.

    Balanced because a group holding only the short histories would be wide for a reason that has
    nothing to do with dependence: the syndicates are sorted by their number of years and dealt
    round-robin, with the order inside each size band shuffled.
    """
    counts = {s: int((syn == s).sum()) for s in set(syn.tolist())}
    order = sorted(counts, key=lambda s: (-counts[s], rng.random()))
    groups = [[] for _ in range(n_groups)]
    for i, s in enumerate(order):
        groups[i % n_groups].append(s)
    return groups


def main():
    S, R, H, yr, syn, ritc = adopted_model.load_sample()
    rng = np.random.default_rng(SEED)
    h = adopted_model.headline()
    print("headline: " + "  ".join("%s %.4f (%.4f)" % (p, h[p]["mean"], h[p]["sd"]) for p in FOCUS))

    # ---- A. descriptive dispersion across disjoint syndicate groups ------------------------------
    print("A. %d disjoint syndicate groups" % N_GROUPS)
    groups = syndicate_groups(syn, N_GROUPS, rng)
    group_fits = []
    for i, members in enumerate(groups):
        mask = np.isin(syn, members)
        group_fits.append(fit(mask, "group_%d" % (i + 1)))
    prior = prior_sds()
    group_dispersion = {}
    for p in FOCUS:
        est = np.array([g[p]["mean"] for g in group_fits])
        rep = np.array([g[p]["sd"] for g in group_fits])
        # the spread of independent estimates against the width each fit reports for itself
        between = float(est.std(ddof=1))
        reported = float(np.sqrt(np.mean(rep ** 2)))
        share = float(reported / prior[p]) if prior.get(p) else None
        dominated = bool(share is not None and share >= PRIOR_DOMINATED)
        group_dispersion[p] = {
            "group_means": [float(v) for v in est],
            "between_group_sd": between,
            "mean_reported_sd": reported,
            "prior_sd": prior.get(p),
            "reported_sd_as_share_of_prior_sd": share,
            "prior_dominated": dominated,
            "descriptive_ratio_between_over_reported": (
                float(between / reported) if reported > 0 else None
            ),
            "data_informative": not dominated,
            "headline_sd_for_context_only": float(h[p]["sd"])}
        if dominated:
            calibration[p]["why_not_interpretable"] = (
                "each group fit reports %.0f%% of the prior SD, at or above the %.0f%% mark, so on twenty "
                "syndicates this parameter is not identified by its group's own data and the ratio mostly describes "
                "the prior rather than subgroup sampling variation."
                % (100 * share, 100 * PRIOR_DOMINATED))
        print("   %-6s between-group sd %.4f against reported %.4f -> descriptive ratio %.2f  [%s]"
              % (p, between, reported, group_dispersion[p]["descriptive_ratio_between_over_reported"],
                 "prior-dominated" if dominated else "not an uncertainty multiplier"))

    # ---- B. how much of it is adjacency? --------------------------------------------------------
    print("B. thinned against random at matched n")
    thin = np.zeros(len(S), bool)
    for s in set(syn.tolist()):
        idx = np.where(syn == s)[0]
        idx = idx[np.argsort(yr[idx])]
        thin[idx[0::2]] = True
    rand = np.zeros(len(S), bool)
    for s in set(syn.tolist()):
        idx = np.where(syn == s)[0]
        take = int(thin[idx].sum())
        rand[rng.choice(idx, take, replace=False)] = True
    b_fits = [fit(thin, "thinned"), fit(rand, "random_matched")]
    adjacency = {
        "thinned": {"n": b_fits[0]["n"], "adjacent_pairs": b_fits[0]["n_consecutive_year_pairs"]},
        "random_matched": {"n": b_fits[1]["n"], "adjacent_pairs": b_fits[1]["n_consecutive_year_pairs"]},
        "sd_ratio_thinned_over_random": {
            p: (float(b_fits[0][p]["sd"] / b_fits[1][p]["sd"]) if b_fits[1][p]["sd"] > 0 else None)
            for p in FOCUS},
        "note": "the two subsamples hold the same number of years per syndicate and differ in how many "
                "consecutive-year pairs survive, but also in which realised years and covariates survive. "
                "The ratio is an exploratory stability contrast and does not isolate a serial component or "
                "calibrate the full-data posterior width."}
    for p in FOCUS:
        print("   %-6s sd thinned %.4f / random %.4f = %.2f"
              % (p, b_fits[0][p]["sd"], b_fits[1][p]["sd"], adjacency["sd_ratio_thinned_over_random"][p]))

    out = {"seed": SEED, "draws": DRAWS, "tune": TUNE, "chains": CHAINS, "n_groups": N_GROUPS,
           "question": "how stable are selected parameter fits across disjoint syndicate groups and a matched "
                       "thinning contrast?",
           "design_a_group_dispersion": group_dispersion,
           "design_b_adjacency": adjacency,
           "fits": group_fits + b_fits,
           "reading": "The subgroup ratio and thinning ratio are descriptive diagnostics only. They are not "
                      "posterior-SD multipliers, do not correct the original likelihood's parameter covariance, "
                      "and are not applied to any reported interval. Syndicate-level donor resampling measures "
                      "donor-composition uncertainty; crossing those weights with draws from the original "
                      "likelihood does not make the parameter posterior cluster-aware.",
           "limits": "Six heterogeneous subgroup fits are influenced by their covariate mix, information and "
                     "priors. The single thinning contrast changes realised observations as well as adjacency. "
                     "No parameter, including k, gamma, the floor, tail parameters or a transferred stress, "
                     "receives dependence-calibrated uncertainty from this script."}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
