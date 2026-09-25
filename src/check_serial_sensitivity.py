"""Is the headline posterior's WIDTH honest, given the dependence within a syndicate?

check_pyd_temporal_correlation.py (f) finds positive lag-1 association in the adopted model's own
residuals, given size, HHI, regime and reporting year: the likelihood's conditional independence is
not supported. This measures the consequence for the fit, which is the part that matters for the
paper (frozen review of 25 September 2026, M01).

The likelihood multiplies one density per syndicate-YEAR, so if a syndicate's years carry common
information the posterior is narrower than the evidence warrants. Two questions, two designs, both of
them refits of the adopted model through adopted_model.scale_block with nothing changed but which
observations are included:

  A. CALIBRATION OF THE REPORTED WIDTH.  Split the syndicates into G disjoint groups and fit each.
     The groups share no syndicate, so their estimates are independent draws of the same quantity. If
     the reported posterior SD is honest, the spread of the G estimates should be about the size of a
     single group's reported SD. If the spread is larger, the likelihood is not seeing all the
     variation, and the ratio is how much it understates it. This catches dependence of any form
     within a syndicate, serial or persistent, not only the lag-1 part a correlation can see.

  B. THE ADJACENCY COMPONENT.  A thinned half keeps every other year within each syndicate, so
     consecutive-year pairs are removed; a random half keeps the same NUMBER of years per syndicate,
     drawn without regard to adjacency. The two have the same n and the same cluster sizes and differ
     only in how much adjacency survives, which isolates the serial part from the cluster part.

What this is not: a refit of the paper under an autoregressive likelihood, and not a bound on
dependence at lags a lag-1 statistic cannot see. It is the effect of the dependence that is there on
the width the paper prints.

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

    # ---- A. is the reported width honest at the syndicate level? --------------------------------
    print("A. %d disjoint syndicate groups" % N_GROUPS)
    groups = syndicate_groups(syn, N_GROUPS, rng)
    group_fits = []
    for i, members in enumerate(groups):
        mask = np.isin(syn, members)
        group_fits.append(fit(mask, "group_%d" % (i + 1)))
    prior = prior_sds()
    calibration = {}
    for p in FOCUS:
        est = np.array([g[p]["mean"] for g in group_fits])
        rep = np.array([g[p]["sd"] for g in group_fits])
        # the spread of independent estimates against the width each fit reports for itself
        between = float(est.std(ddof=1))
        reported = float(np.sqrt(np.mean(rep ** 2)))
        share = float(reported / prior[p]) if prior.get(p) else None
        dominated = bool(share is not None and share >= PRIOR_DOMINATED)
        calibration[p] = {
            "group_means": [float(v) for v in est],
            "between_group_sd": between,
            "mean_reported_sd": reported,
            "prior_sd": prior.get(p),
            "reported_sd_as_share_of_prior_sd": share,
            "prior_dominated": dominated,
            "understatement_factor": float(between / reported) if reported > 0 else None,
            "interpretable": not dominated,
            "headline_sd": float(h[p]["sd"]),
            "headline_sd_scaled_by_factor": (float(h[p]["sd"] * between / reported)
                                             if reported > 0 and not dominated else None)}
        if dominated:
            calibration[p]["why_not_interpretable"] = (
                "each group fit reports %.0f%% of the prior SD, at or above the %.0f%% mark, so on twenty "
                "syndicates this parameter is not identified by its group's own data and the ratio describes the "
                "prior rather than any understatement of the likelihood's width."
                % (100 * share, 100 * PRIOR_DOMINATED))
        print("   %-6s between-group sd %.4f against reported %.4f -> factor %.2f  [%s]"
              % (p, between, reported, calibration[p]["understatement_factor"],
                 "prior-dominated, not interpretable" if dominated
                 else "headline sd %.4f -> %.4f" % (h[p]["sd"], calibration[p]["headline_sd_scaled_by_factor"])))

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
                "consecutive-year pairs survive. A ratio near 1 says the reported width does not turn on "
                "adjacency, so the understatement in A is the clustering as a whole and not the lag-1 part "
                "alone."}
    for p in FOCUS:
        print("   %-6s sd thinned %.4f / random %.4f = %.2f"
              % (p, b_fits[0][p]["sd"], b_fits[1][p]["sd"], adjacency["sd_ratio_thinned_over_random"][p]))

    out = {"seed": SEED, "draws": DRAWS, "tune": TUNE, "chains": CHAINS, "n_groups": N_GROUPS,
           "question": "does within-syndicate dependence make the headline posterior narrower than the evidence "
                       "warrants, and by how much?",
           "design_a_group_calibration": calibration,
           "design_b_adjacency": adjacency,
           "fits": group_fits + b_fits,
           "reading": "design_a_group_calibration[p]['understatement_factor'] is the factor by which the "
                      "likelihood understates the spread of independent estimates of p, and is to be read only "
                      "where 'interpretable' is true: a parameter the group fits do not identify reverts to its "
                      "prior and the ratio then describes the prior. Above 1 the likelihood is understating, and "
                      "headline_sd_scaled_by_factor is the headline posterior SD widened by it -- a "
                      "dependence-adjusted width for the parameter, not a refit. The transferred stress is a "
                      "separate matter and is already resampled over whole syndicates "
                      "(vignette_uncertainty.py, scheme 'bayes'), whose interval is the wider of the two "
                      "recorded there.",
           "limits": "G independent estimates give the factor itself only to about 1/sqrt(2(G-1)) relative "
                     "precision, so it is an order of magnitude and not a calibrated multiplier. The groups are "
                     "smaller than the working sample, so each fit sits further up the prior's influence than the "
                     "headline does. Neither the factor nor the ratio in B is a bound on dependence at lags a "
                     "lag-1 statistic cannot see."}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
