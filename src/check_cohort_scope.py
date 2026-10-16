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

The smooth-tail check (the smooth-tail rule of 14 October 2026, written by the Claude analysis session on the author's
instruction before the check was run; the author's instruction: do the smooth-tail check, and if it suggests option b
is required, do option b, otherwise option a; the session wrote the estimator and the 5% line): Vignette 1's fitted GPD
VaR99.5, which does not move by one order statistic when the pool shrinks, on (i) the full pool
under the headline fit and (ii) the triangle-only pool under the subset fit, with the same two
legs as above. Each figure is computed by the headline GPD's own functions at their own settings:
the peaks-over-threshold point of gpd_var_uncertainty.py (gpd_var995, threshold the 90th
percentile of the transferred sample) and the Bayesian GPD of bayesian_gpd.py (fit_one, its
priors and seed) on the same exceedances. (i) must reproduce both recorded headline figures
(results/gpd_var_uncertainty_results.json and results/bayesian_gpd_results.json) exactly, and
every Bayesian GPD fit must have no divergence and every R-hat at most 1.01, or nothing is written.
The rule: if (ii)/(i) - 1 >= +5%, the composition effect counts as real (option b); otherwise
option a. The record states the rule and the comparison; it draws no other conclusion.

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
import bayesian_gpd
import gpd_var_uncertainty
import transfer_operator
import refit_vignettes as RV
from pool_quantile import var_q
from vignette_uncertainty import load_targets, transfer

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_cohort_scope_results.json"
RITC = SD / "pdf_extraction" / "ritc_scan.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42
#: gamma is 0 in the likelihood (the headline's since option B, 10 October 2026): not a fitted parameter here
VARS = ["k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "tau_s"]

#: the headline GPD records the full pool's figures must reproduce exactly (the smooth-tail check)
GPD_RECORDS = {"frequentist": SD / "results" / "gpd_var_uncertainty_results.json",
               "bayesian": SD / "results" / "bayesian_gpd_results.json"}
GPD_TARGET = "V1_adjusted"
#: the headline GPD's threshold: this percentile of the signed transferred-severity sample (both records state it)
GPD_U_Q = 90.0
#: the smooth-tail rule's line (14 October 2026), written by the Claude analysis session on the author's instruction
#: before the check was run: (ii)/(i) - 1 at or above it counts the composition effect as real
GPD_RULE_LINE = 0.05
#: what each Bayesian GPD fit reports here: bayesian_gpd.fit_one's keys, less its comparators
GPD_BAYES_KEYS = ("threshold_u", "N", "Nu", "var995_median", "var995_2.5", "var995_97.5", "xi_median", "xi_2.5",
                  "xi_97.5", "sigma_median", "sigma_2.5", "sigma_97.5", "max_rhat", "divergences", "tail_shape")


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


def v1_gpd_tail(draws, pool, ritc, cfg, bayes_fit=None):
    """Vignette 1's GPD VaR99.5 on `pool` at the posterior means of `draws`, under the headline operator, by the headline
    GPD's own functions: the POT point (gpd_var_uncertainty.gpd_var995 at the GPD_U_Q-th percentile threshold) and the
    Bayesian GPD (bayesian_gpd.fit_one, or `bayes_fit` with its signature) on the same exceedances."""
    S, R, H, _synd, _year = pool
    th = transfer_operator.params(draws, RV.OPERATOR)
    thbar = {p: float(th[p].mean()) for p in th}
    a1 = transfer(S, R, H, load_targets()[0], thbar, cfg, ritc)
    v, xi, sigma, nu, u = gpd_var_uncertainty.gpd_var995(a1, GPD_U_Q)
    if not np.isfinite(v):
        raise SystemExit("the POT fit failed on %d donors (%d exceedances): no figures are written" % (len(a1), nu))
    exc = a1[a1 > u] - u
    emp = var_q(a1, 0.995)
    fit = (bayes_fit or bayesian_gpd.fit_one)(GPD_TARGET, exc, len(a1), len(exc), u, emp, RV.OPERATOR)
    return {"N": int(len(a1)), "threshold_u": float(u), "Nu": int(nu),
            "point_var995": float(v), "point_xi": float(xi), "point_sigma": float(sigma),
            "empirical_var995": float(emp),
            "bayesian": {k: fit[k] for k in GPD_BAYES_KEYS}}


def gpd_records():
    """The headline GPD records, each stamped with the headline operator and the GPD_U_Q-th percentile threshold."""
    recs = {k: json.load(io.open(p, encoding="utf-8")) for k, p in GPD_RECORDS.items()}
    for k, rec in recs.items():
        if rec.get("operator") != RV.OPERATOR:
            raise SystemExit("%s does not record the %s operator as its headline" % (GPD_RECORDS[k].name, RV.OPERATOR))
        if not rec["meta"]["threshold_rule"].startswith("%.0fth percentile " % GPD_U_Q):
            raise SystemExit("%s's threshold is not the %.0fth percentile: %r"
                             % (GPD_RECORDS[k].name, GPD_U_Q, rec["meta"]["threshold_rule"]))
    return recs


def check_gpd_reproduces(full, recs):
    """(i), the full pool under the headline fit, must equal both recorded headline GPD figures exactly: the POT point,
    its threshold, exceedance count and parameters, and every Bayesian GPD figure. Otherwise nothing is written."""
    f = recs["frequentist"]["distributions"][GPD_TARGET]
    b = recs["bayesian"]["distributions"][GPD_TARGET]
    want = {"N": recs["frequentist"]["meta"]["n_donors"], "threshold_u": f["point_threshold_u"], "Nu": f["point_Nu"],
            "point_var995": f["point_var995"], "point_xi": f["point_xi"], "point_sigma": f["point_sigma"],
            "empirical_var995": f["empirical"]}
    bad = {k: (full[k], x) for k, x in want.items() if full[k] != x}
    bad.update({"bayesian." + k: (full["bayesian"][k], b[k]) for k in GPD_BAYES_KEYS if full["bayesian"][k] != b[k]})
    if bad:
        raise SystemExit("the full pool's GPD VaR99.5 under the headline fit does not reproduce the headline's recorded "
                         "GPD figures (computed, recorded): %s; no figures are written" % bad)


def gpd_tail_block(head_draws, draws, pool, ritc, full_pool, full_ritc, cfg, bayes_fit=None, recs=None):
    """The smooth-tail check: (i) the full pool under the headline fit, reproduced against the records first; (ii) the
    subset's pool under the subset fit; and the two single-change legs, each relative to (i)."""
    full = v1_gpd_tail(head_draws, full_pool, full_ritc, cfg, bayes_fit)
    check_gpd_reproduces(full, gpd_records() if recs is None else recs)
    legs = {"triangle_only_subset_fit": v1_gpd_tail(draws, pool, ritc, cfg, bayes_fit),
            "headline_fit_on_subset_pool": v1_gpd_tail(head_draws, pool, ritc, cfg, bayes_fit),
            "subset_fit_on_full_pool": v1_gpd_tail(draws, full_pool, full_ritc, cfg, bayes_fit)}
    for name, leg in [("full_pool_headline_fit", full)] + list(legs.items()):
        if not RV.converged(leg["bayesian"]):
            raise SystemExit("the Bayesian GPD fit of %s has not converged (%d divergences, max R-hat %.4f): no figures "
                             "are written" % (name, leg["bayesian"]["divergences"], leg["bayesian"]["max_rhat"]))

    def rel(leg):
        return {"point_var995": leg["point_var995"] / full["point_var995"] - 1.0,
                "bayesian_var995_median": leg["bayesian"]["var995_median"] / full["bayesian"]["var995_median"] - 1.0}

    relative = {k: rel(v) for k, v in legs.items()}
    head = relative["triangle_only_subset_fit"]
    return {
        **transfer_operator.stamp(RV.OPERATOR),
        "question": ("the smooth-tail check under the smooth-tail rule (14 October 2026), written by the Claude analysis "
                     "session on the author's instruction before the check was run (the instruction: do the smooth-tail "
                     "check; if it suggests option b is required, do option b; otherwise option a; the session wrote the "
                     "estimator and the 5% line): Vignette 1's fitted GPD VaR99.5, with "
                     "the headline GPD's method and settings, on (i) the full pool under the headline fit and (ii) the "
                     "triangle-only pool under the subset fit"),
        "rule": ("if (ii)/(i) - 1 >= +5%, the composition effect counts as real (option b); otherwise option a"),
        "rule_line": GPD_RULE_LINE,
        "estimator": ("under the headline size-only operator at the fit's posterior means: the POT point is "
                      "gpd_var_uncertainty.gpd_var995 (threshold the %.0fth percentile of the signed transferred "
                      "sample, scipy genpareto with location 0, the POT return level at 0.995); the Bayesian GPD is "
                      "bayesian_gpd.fit_one on the same exceedances (its priors, seed %d and sampler settings): "
                      "posterior median and 95%% equal-tailed credible interval of the return level"
                      % (GPD_U_Q, bayesian_gpd.SEED)),
        "reproduced": ("(i) is recomputed here and equals results/gpd_var_uncertainty_results.json's V1_adjusted point "
                       "(threshold, exceedances, xi, sigma, empirical) and results/bayesian_gpd_results.json's "
                       "V1_adjusted fit exactly; the script refuses to write otherwise"),
        "full_pool_headline_fit": full,
        **legs,
        "relative_to_full_pool_headline_fit": relative,
        "rule_comparison": {"note": "(ii)/(i) - 1 against the pre-stated line, for each of the headline GPD's two figures",
                            "point_var995": head["point_var995"],
                            "point_var995_at_or_above_line": bool(head["point_var995"] >= GPD_RULE_LINE),
                            "bayesian_var995_median": head["bayesian_var995_median"],
                            "bayesian_var995_median_at_or_above_line":
                                bool(head["bayesian_var995_median"] >= GPD_RULE_LINE)},
    }


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
    gpd = gpd_tail_block(head_draws, draws, pool, ritc, full_pool, full_ritc, cfg)
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
        "v1_gpd_tail": gpd,
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

    io.open(OUT, "w", encoding="utf-8", newline="").write(json.dumps(out, indent=1) + "\n")
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
    g = vig["v1_gpd_tail"]
    for leg in ("full_pool_headline_fit", "triangle_only_subset_fit", "headline_fit_on_subset_pool",
                "subset_fit_on_full_pool"):
        r, b = g[leg], g[leg]["bayesian"]
        rel = g["relative_to_full_pool_headline_fit"].get(leg)
        print("  V1 GPD VaR99.5 %-28s N %d u %.5f Nu %d  POT %.4f%s  Bayes %.4f [%.4f, %.4f]%s"
              % (leg, r["N"], r["threshold_u"], r["Nu"], r["point_var995"],
                 "" if rel is None else " (%+.2f%%)" % (100 * rel["point_var995"]),
                 b["var995_median"], b["var995_2.5"], b["var995_97.5"],
                 "" if rel is None else " (%+.2f%%)" % (100 * rel["bayesian_var995_median"])))


if __name__ == "__main__":
    main()
