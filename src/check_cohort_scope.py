"""Check (referee, 7 September 2026, M02): the numerator's cohort coverage.

The manuscript defines every numerator as the sum of ultimate-estimate changes over
underwriting years u <= t-2. That restriction is enforced by construction only where
the figure came from a triangle route, which reads the development diagonal with the
two most recent underwriting years excluded. Where the figure is the movement the
filing discloses for "prior years" -- the provisions fallback and a retained narrative
value -- the filing does not partition by cohort, so the record may include u = t-1.
The review's example is 780/2016, whose -US$15.6m is the disclosed gross prior-year
provisions movement with no cohort decomposition.

This is a statement about evidence, not a measured bias: nothing here establishes that
the disclosed-scope records contain a t-1 contribution. The check refits the adopted
model on the observations whose cohort coverage IS enforced and reports how the
parameters move, so the manuscript can declare the source-dependent estimands and show
what the consistently constructed subset gives.

Since the author's decision of 14 October 2026 it also reports what the subset does to the
stresses: Vignette 1's VaR99 and VaR99.5 and Vignette 2's paired change at 99.5%, under the
headline size-only operator (gamma = 0), from the subset fit's own posterior and the subset's
own donors (the vignette pool restricted to the cohort-enforced records), through the headline
estimator's own function with its seed and B (refit_vignettes.py), beside the headline's figures
and the relative changes. Two centre-only legs separate the two things the subset changes: the
headline fit on the subset's donors (the pool alone), and the subset fit on the whole pool (the
posterior alone). The most adverse Vignette 1 donors of the headline are listed with their
cohort scope, so the reader sees which of them the subset drops. The figures are written only
for a fit with no divergence and every R-hat at most 1.01. This script, not a sibling, carries
them, because the fit they need is the one it already makes: a sibling would refit it or read
its draws from a file this script would then have to write.

Writes check_cohort_scope_results.json.
Usage:  python src/check_cohort_scope.py
"""
import io
import json
from pathlib import Path

import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from adopted_model import scale_block, headline, SAMPLE_CORES
import assumed_business
import transfer_operator
import refit_vignettes as RV

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_cohort_scope_results.json"
RITC = SD / "pdf_extraction" / "ritc_scan.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42
#: gamma is 0 in the likelihood (the headline's since option B, 10 October 2026): not a fitted parameter here
VARS = ["k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "tau_s"]


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None and o.get("pyd_basis") == "gross"]
    return recs


def arrays(recs):
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    key = np.array(["%s_%s" % (o["syndicate"], o["year"]) for o in recs])
    return S, R, H, yr, key


def ritc_flag(key):
    occ = assumed_business.keys()
    return np.array([k in occ for k in key], float)


def fit(S, R, H, yr, ritc):
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    logR, logH = np.log(R / REF), np.log(H)
    with pm.Model():
        b = scale_block(ritc=ritc, logR=logR, logH=logH, yidx=yidx, n_y=len(years))
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=SAMPLE_CORES, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    s = az.summary(idata, var_names=VARS, hdi_prob=0.95)
    return {v: {"mean": float(s.loc[v, "mean"]), "sd": float(s.loc[v, "sd"]),
                "hdi_2.5%": float(s.loc[v, "hdi_2.5%"]),
                "hdi_97.5%": float(s.loc[v, "hdi_97.5%"])} for v in VARS}, idata


def top_donor_scope(top, scope):
    """The headline's most adverse Vignette 1 donors, each with its cohort scope, and the ones the subset drops."""
    rows = [dict(row, rank=i + 1, pyd_cohort_scope=scope[row["donor"]]) for i, row in enumerate(top)]
    leaving = [row for row in rows if row["pyd_cohort_scope"] != "mature-enforced"]
    return {"n": len(rows), "donors": rows, "n_leaving": len(leaving),
            "leaving": [row["donor"] for row in leaving]}


def subset_vignettes(enforced, recs, idata, S, R):
    """The subset fit's vignette figures on the subset's own donors, beside the headline's (refit_vignettes.py)."""
    recorded = RV.headline_record()
    head, head_draws, cfg = RV.headline_block(recorded)
    keys = ["%s_%s" % (o["syndicate"], o["year"]) for o in enforced]
    pool, ritc, pkeys = RV.pool_for(keys)
    RV.check_pool_is_the_fit_sample(pool, pkeys, keys, S, R)
    full_pool, full_ritc, full_keys = RV.pool_for()
    draws = RV.operator_draws(idata)
    block = RV.vignettes(draws, pool, ritc, cfg, recorded)
    pool_only = RV.centre_only(head_draws, pool, ritc, cfg)
    fit_only = RV.centre_only(draws, full_pool, full_ritc, cfg)
    scope = {"%s_%s" % (o["syndicate"], o["year"]): o.get("pyd_cohort_scope") for o in recs}
    return {
        "question": ("what do the vignette stresses become when both the fit and the donors are the records whose "
                     "figure a triangle produced (u <= t-2 enforced by construction)?"),
        "seed": recorded["seed"], "B": recorded["B"], "estimator": RV.ESTIMATOR,
        "pool": {"n_donors": int(len(pkeys)), "n_syndicates": int(len(set(pool[3].tolist()))),
                 "n_assumed_business": int(ritc.sum()),
                 "definition": ("the vignette donor pool (the shipped tool's donors, in its order) restricted to the "
                                "cohort-enforced records; each donor keeps its own severity, size and concentration, "
                                "checked equal to the fitted records'")},
        "headline": {"source": "results/check_gamma0_vignette_results.json, the headline operator's block "
                               "(its centre recomputed here and found equal)", **head},
        "triangle_only": block,
        "relative_to_headline": {"note": "triangle-only centre / headline centre - 1",
                                 **RV.relative(block["centre"], head["centre"])},
        "centre_decomposition": {
            "note": ("centre-only legs at the posterior means: the headline fit on the subset's donors changes the "
                     "pool alone; the subset fit on the whole 672-donor pool changes the posterior alone"),
            "headline_fit_on_subset_pool": pool_only,
            "headline_fit_on_subset_pool_relative_to_headline": RV.relative(pool_only, head["centre"]),
            "subset_fit_on_full_pool": fit_only,
            "subset_fit_on_full_pool_relative_to_headline": RV.relative(fit_only, head["centre"]),
        },
        "order_statistics": {
            "note": ("the inverse-CDF VaR of n donors is one order statistic of the transferred severities, counted "
                     "here from the largest; the subset's smaller pool reads another one, so part of a change in VaR "
                     "is that index and not the donors"),
            **{q: {"headline_pool": RV.rank_from_top(len(full_keys), a), "subset_pool": RV.rank_from_top(len(pkeys), a)}
               for q, a in (("V1_v99", 0.99), ("V1_v995", 0.995))}},
        "v1_top_donors_headline": top_donor_scope(
            RV.v1_top_donors(head_draws, full_pool, full_ritc, full_keys, cfg), scope),
    }


def main():
    recs = load()
    enforced = [o for o in recs if o.get("pyd_cohort_scope") == "mature-enforced"]
    disclosed = [o for o in recs if o.get("pyd_cohort_scope") != "mature-enforced"]

    out = {
        "purpose": ("the cohort coverage of the admitted numerators, and the adopted model "
                    "refitted on the observations whose u <= t-2 restriction is enforced by "
                    "construction"),
        "estimand_note": ("a triangle route computes the sum of ultimate-estimate changes over "
                          "u <= t-2 directly; a disclosed prior-year movement is whatever the "
                          "filing reports for prior years and is not partitioned by cohort, so "
                          "the restriction is not established for those records"),
        "count_note": ("n_mature_enforced counts the figures whose recorded route is a "
                       "triangle: the route field the extraction writes, read as the basis "
                       "rule reads it, or, for a block from before that field, a triangle's "
                       "override annotation (the review of 2 October 2026, M-2: the annotation "
                       "alone missed the triangle figures the model had already matched)"),
        "n_gross_sample": len(recs),
        "n_mature_enforced": len(enforced),
        "n_disclosed_prior_year": len(disclosed),
        "share_enforced": round(len(enforced) / len(recs), 6) if recs else None,
        "n_syndicates_enforced": len({o["syndicate"] for o in enforced}),
    }

    S, R, H, yr, key = arrays(enforced)
    out["enforced_subset_fit"], idata = fit(S, R, H, yr, ritc_flag(key))
    out["headline"] = headline()
    out["shifts_vs_headline"] = {
        v: round(out["enforced_subset_fit"][v]["mean"] - float(out["headline"][v]["mean"]), 6)
        for v in VARS if v in out["headline"]
    }
    out["reading"] = ("the subset is smaller, so wider intervals are expected; the check is "
                      "whether the enforced-cohort subset moves the parameters beyond that")
    diag = RV.convergence(idata)
    out["enforced_subset_fit_convergence"] = diag
    if not RV.converged(diag):
        raise SystemExit("the cohort-enforced fit has not converged (%s): no figures are written" % diag)
    out["vignettes"] = subset_vignettes(enforced, recs, idata, S, R)

    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="")
    print("wrote", OUT.name)
    print("  gross sample %d; cohort enforced %d; disclosed %d"
          % (out["n_gross_sample"], out["n_mature_enforced"], out["n_disclosed_prior_year"]))
    for v in VARS:
        if v in out["shifts_vs_headline"]:
            print("  %-10s enforced %.4f   headline %.4f   shift %+.4f"
                  % (v, out["enforced_subset_fit"][v]["mean"],
                     float(out["headline"][v]["mean"]), out["shifts_vs_headline"][v]))
    print("  convergence: %d divergences, max R-hat %.4f, min ESS bulk %.0f tail %.0f"
          % (diag["divergences"], diag["max_rhat"], diag["min_ess_bulk"], diag["min_ess_tail"]))
    vig = out["vignettes"]
    for q in ("V1_v99", "V1_v995", "V2_d995"):
        print("  %s (%s) %-8s headline %.4f   triangle-only %.4f   (%+.2f%%)"
              % (transfer_operator.HEADLINE, vig["triangle_only"]["operator_role"], q, vig["headline"]["centre"][q],
                 vig["triangle_only"]["centre"][q], 100 * vig["relative_to_headline"][q]))
    print("  of the headline's top %d Vignette 1 donors, %d leave: %s"
          % (vig["v1_top_donors_headline"]["n"], vig["v1_top_donors_headline"]["n_leaving"],
             ", ".join(vig["v1_top_donors_headline"]["leaving"])))


if __name__ == "__main__":
    main()
