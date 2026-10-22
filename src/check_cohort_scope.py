"""Check (referee, 7 September 2026, M02; the owner's decision of 22 October 2026): the numerator's cohort coverage,
the primary outcome beside the 672-record sensitivity.

The manuscript defines every numerator as the sum of ultimate-estimate changes over underwriting years u <= t-2
(Equation 1). That restriction is enforced by construction only where the figure came from a triangle route, which
reads the development diagonal with the two most recent underwriting years excluded. Where the figure is the movement
the filing discloses for "prior years" (the provisions note, a model's reading), the filing does not partition by
cohort, so the figure may include u = t-1. The review's example was 780/2016.

Until 22 October 2026 the working sample was the extraction's precedence construction (672 records): 571 triangle
figures and 101 disclosed movements, two sign-only precedence rules having put a broader figure in the place of a
printed gross triangle's for 61 of them. This script refitted the adopted model on the 571 and reported the subset's
stresses. The owner then decided (option c) that the consistently scoped sample is the primary: every figure is the
mature-cohort movement (data/mature_cohort_figures.json; run_analysis.ANALYSIS_CONFIG["outcome"] "mature_cohort"), and
the 672 construction stays reproducible as a sensitivity (outcome "precedence_672"). So this script now reports the
two side by side: the primary is the headline (model/exposure_results.json, its fit and its vignette record), and the
sensitivity is the 672 construction, loaded in memory by run_analysis.load_and_classify("precedence_672") (no second
exposure_results.json), refitted with the headline's model and settings, and transferred from its own donors.

The record keeps the keys the paper reads with their meaning: n_gross_sample, n_mature_enforced, n_disclosed_prior_year,
share_enforced and n_syndicates_enforced describe the cohort coverage of the 672 construction (571 and 101 of 672), and
"headline" is the headline fit. The primary's own counts are under "primary" (every record mature-enforced, checked),
the two samples' membership under "membership", the 672 refit under "sensitivity_672_fit" (was enforced_subset_fit),
and the vignettes under vignettes.precedence_672 (was vignettes.triangle_only), with the same two centre-only legs (the
headline fit on the 672 donors: the pool alone; the 672 fit on the headline's donors: the posterior alone), the
inverse-CDF order statistics of both pools, the headline's most adverse Vignette 1 donors with their place in the 672
construction, and Vignette 1's fitted GPD VaR99.5 on both, by the headline GPD's own functions at their own settings
(gpd_var_uncertainty.gpd_var995 and bayesian_gpd.fit_one), with (i), the headline pool under the headline fit,
reproducing both recorded headline GPD figures exactly, against the 5% line Appendix 2.2 calls material. The figures
are written only for a fit with no divergence and every R-hat at most 1.01.

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
ENFORCED = "mature-enforced"

#: the headline GPD records the headline pool's figures must reproduce exactly
GPD_RECORDS = {"frequentist": SD / "results" / "gpd_var_uncertainty_results.json",
               "bayesian": SD / "results" / "bayesian_gpd_results.json"}
GPD_TARGET = "V1_adjusted"
#: the headline GPD's threshold: this percentile of the signed transferred-severity sample (both records state it)
GPD_U_Q = 90.0
#: Appendix 2.2's materiality line (the smooth-tail rule of 14 October 2026 used it for the triangle-only subset): the
#: sensitivity's fitted-tail move against the primary's is read against it
GPD_RULE_LINE = 0.05
#: what each Bayesian GPD fit reports here: bayesian_gpd.fit_one's keys, less its comparators
GPD_BAYES_KEYS = ("threshold_u", "N", "Nu", "var995_median", "var995_2.5", "var995_97.5", "xi_median", "xi_2.5",
                  "xi_97.5", "sigma_median", "sigma_2.5", "sigma_97.5", "max_rhat", "divergences", "tail_shape")
#: the GPD legs: the headline pool under the headline fit, the sensitivity's pool under its fit, and the two
#: single-change legs
GPD_LEGS = ("sensitivity_672_fit", "headline_fit_on_sensitivity_pool", "sensitivity_fit_on_headline_pool")


def in_working_sample(o):
    return (o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None
            and o.get("pyd_basis") == "gross")


def load():
    """The primary's working sample: model/exposure_results.json's observations."""
    with io.open(SD / "model" / "exposure_results.json", encoding="utf-8") as _fh:
        d = json.load(_fh)
    return [o for o in d["observations"] if in_working_sample(o)]


def load_sensitivity(loader=None):
    """The 672 construction, in memory: every record run_analysis.load_and_classify("precedence_672") parses, with the
    eligibility flags the headline run sets (event groups, subsets, compute_eligibility), and its working sample."""
    import run_analysis as ra
    if loader is None:
        def loader():
            return ra.load_and_classify(ra.PRECEDENCE_672_OUTCOME)
    records, _counters, _log, _files = loader()
    ra.assign_event_groups(records, min_events=ra.ANALYSIS_CONFIG["min_events_for_fe"])
    _meta, subsets = ra.build_subsets(records)
    ra.compute_eligibility(records, subsets)
    return records, [o for o in records if in_working_sample(o)]


def key_of(o):
    return "%s_%s" % (o["syndicate"], o["year"])


def coverage(recs):
    enforced = [o for o in recs if o.get("pyd_cohort_scope") == ENFORCED]
    return {"n_gross_sample": len(recs), "n_mature_enforced": len(enforced),
            "n_disclosed_prior_year": len(recs) - len(enforced),
            "share_enforced": round(len(enforced) / len(recs), 6) if recs else None,
            "n_syndicates": len({o["syndicate"] for o in recs}),
            "n_syndicates_enforced": len({o["syndicate"] for o in enforced}),
            "years": [min(o["year"] for o in recs), max(o["year"] for o in recs)] if recs else None}


def membership(primary, sensitivity):
    """The two samples' records: in both with the same figure and severity, in both with another figure, and in one
    only."""
    p = {key_of(o): o for o in primary}
    s = {key_of(o): o for o in sensitivity}
    both = sorted(set(p) & set(s), key=lambda k: tuple(int(x) for x in k.split("_")))
    changed = [k for k in both if p[k]["s_raw_a"] != s[k]["s_raw_a"]]
    order = (lambda ks: sorted(ks, key=lambda k: tuple(int(x) for x in k.split("_"))))
    return {"n_both_same_severity": len(both) - len(changed), "both_other_severity": changed,
            "n_both_other_severity": len(changed),
            "primary_only": order(set(p) - set(s)), "n_primary_only": len(set(p) - set(s)),
            "sensitivity_only": order(set(s) - set(p)), "n_sensitivity_only": len(set(s) - set(p))}


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


def donor_pool(records):
    """(pool, assumed-business flags, keys): the 672 construction's vignette donors, chosen and rounded as the
    headline run chooses and embeds its own in the shipped tool (run_analysis._vig_donor_pool, the tool's 2, 8 and 6
    decimals), in the loader's order."""
    import run_analysis as ra
    donors = ra._vig_donor_pool(records)
    S = np.array([round(r["s_raw_a"], 8) for r in donors], float)
    R = np.array([round(r["opening_reserves_gbp_m"], 2) for r in donors], float)
    H = np.array([round(r.get("hhi", 0), 6) for r in donors], float)
    synd = np.array([r["syndicate"] for r in donors])
    year = np.array([r["year"] for r in donors])
    pool = (S, R, H, synd, year)
    return pool, RV.load_ritc(synd, year), RV.donor_keys(synd, year)


def top_donor_place(top, primary, sensitivity):
    """The headline's most adverse Vignette 1 donors, each with its place in the 672 construction: absent, or present
    with another severity (its figure was a broader movement there)."""
    p = {key_of(o): o for o in primary}
    s = {key_of(o): o for o in sensitivity}
    rows = []
    for i, row in enumerate(top):
        k = row["donor"]
        rows.append(dict(row, rank=i + 1, in_sensitivity=k in s,
                         sensitivity_severity_differs=bool(k in s and s[k]["s_raw_a"] != p[k]["s_raw_a"])))
    absent = [r["donor"] for r in rows if not r["in_sensitivity"]]
    differs = [r["donor"] for r in rows if r["sensitivity_severity_differs"]]
    return {"n": len(rows), "donors": rows, "n_absent_from_sensitivity": len(absent),
            "absent_from_sensitivity": absent, "n_other_severity_in_sensitivity": len(differs),
            "other_severity_in_sensitivity": differs}


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
    recs = {}
    for k, p in GPD_RECORDS.items():
        with io.open(p, encoding="utf-8") as _fh:
            recs[k] = json.load(_fh)
    for k, rec in recs.items():
        if rec.get("operator") != RV.OPERATOR:
            raise SystemExit("%s does not record the %s operator as its headline" % (GPD_RECORDS[k].name, RV.OPERATOR))
        if not rec["meta"]["threshold_rule"].startswith("%.0fth percentile " % GPD_U_Q):
            raise SystemExit("%s's threshold is not the %.0fth percentile: %r"
                             % (GPD_RECORDS[k].name, GPD_U_Q, rec["meta"]["threshold_rule"]))
    return recs


def check_gpd_reproduces(full, recs):
    """(i), the headline pool under the headline fit, must equal both recorded headline GPD figures exactly: the POT
    point, its threshold, exceedance count and parameters, and every Bayesian GPD figure. Otherwise nothing is
    written."""
    f = recs["frequentist"]["distributions"][GPD_TARGET]
    b = recs["bayesian"]["distributions"][GPD_TARGET]
    want = {"N": recs["frequentist"]["meta"]["n_donors"], "threshold_u": f["point_threshold_u"], "Nu": f["point_Nu"],
            "point_var995": f["point_var995"], "point_xi": f["point_xi"], "point_sigma": f["point_sigma"],
            "empirical_var995": f["empirical"]}
    bad = {k: (full[k], x) for k, x in want.items() if full[k] != x}
    bad.update({"bayesian." + k: (full["bayesian"][k], b[k]) for k in GPD_BAYES_KEYS if full["bayesian"][k] != b[k]})
    if bad:
        raise SystemExit("the headline pool's GPD VaR99.5 under the headline fit does not reproduce the headline's "
                         "recorded GPD figures (computed, recorded): %s; no figures are written" % bad)


def gpd_tail_block(head_draws, draws, pool, ritc, full_pool, full_ritc, cfg, bayes_fit=None, recs=None):
    """Vignette 1's fitted tail: (i) the headline pool under the headline fit, reproduced against the records first;
    (ii) the sensitivity's pool under its own fit; and the two single-change legs, each relative to (i)."""
    full = v1_gpd_tail(head_draws, full_pool, full_ritc, cfg, bayes_fit)
    check_gpd_reproduces(full, gpd_records() if recs is None else recs)
    legs = {"sensitivity_672_fit": v1_gpd_tail(draws, pool, ritc, cfg, bayes_fit),
            "headline_fit_on_sensitivity_pool": v1_gpd_tail(head_draws, pool, ritc, cfg, bayes_fit),
            "sensitivity_fit_on_headline_pool": v1_gpd_tail(draws, full_pool, full_ritc, cfg, bayes_fit)}
    for name, leg in [("full_pool_headline_fit", full)] + list(legs.items()):
        if not RV.converged(leg["bayesian"]):
            raise SystemExit("the Bayesian GPD fit of %s has not converged (%d divergences, max R-hat %.4f): no figures "
                             "are written" % (name, leg["bayesian"]["divergences"], leg["bayesian"]["max_rhat"]))

    def rel(leg):
        return {"point_var995": leg["point_var995"] / full["point_var995"] - 1.0,
                "bayesian_var995_median": leg["bayesian"]["var995_median"] / full["bayesian"]["var995_median"] - 1.0}

    relative = {k: rel(v) for k, v in legs.items()}
    head = relative["sensitivity_672_fit"]
    return {
        **transfer_operator.stamp(RV.OPERATOR),
        "question": ("Vignette 1's fitted GPD VaR99.5, with the headline GPD's method and settings, on (i) the primary's "
                     "donor pool under the headline fit and (ii) the 672 construction's pool under its own fit, with "
                     "the two single-change legs"),
        "rule": ("(ii)/(i) - 1 is read against Appendix 2.2's materiality line (5%); the record states the comparison "
                 "and draws no other conclusion"),
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
        "rule_comparison": line_comparison(head),
    }


def line_comparison(rel):
    """|(ii)/(i) - 1| against the 5% line, for each of the headline GPD's two figures: a move either way counts."""
    return {"note": "|(ii)/(i) - 1| against the 5% line, for each of the headline GPD's two figures",
            "point_var995": rel["point_var995"],
            "point_var995_at_or_above_line": bool(abs(rel["point_var995"]) >= GPD_RULE_LINE),
            "bayesian_var995_median": rel["bayesian_var995_median"],
            "bayesian_var995_median_at_or_above_line": bool(abs(rel["bayesian_var995_median"]) >= GPD_RULE_LINE)}


def sensitivity_vignettes(sens_records, primary, sensitivity, idata):
    """The 672 fit's vignette figures on the 672 construction's own donors, beside the headline's (refit_vignettes.py).
    The headline's donor pool is the shipped tool's, checked to be the primary's working sample."""
    recorded = RV.headline_record()
    head, head_draws, cfg = RV.headline_block(recorded)
    full_pool, full_ritc, full_keys = RV.pool_for()
    pS, pR, _pH, _pyr, pkey = arrays(primary)
    RV.check_pool_is_the_fit_sample(full_pool, full_keys, pkey.tolist(), pS, pR)
    pool, ritc, keys = donor_pool(sens_records)
    if sorted(keys.tolist()) != sorted(key_of(o) for o in sensitivity):
        raise SystemExit("the 672 construction's donors (%d) are not its working sample (%d)"
                         % (len(keys), len(sensitivity)))
    draws = RV.operator_draws(idata)
    block = RV.vignettes(draws, pool, ritc, cfg, recorded)
    pool_only = RV.centre_only(head_draws, pool, ritc, cfg)
    fit_only = RV.centre_only(draws, full_pool, full_ritc, cfg)
    gpd = gpd_tail_block(head_draws, draws, pool, ritc, full_pool, full_ritc, cfg)
    top = RV.v1_top_donors(head_draws, full_pool, full_ritc, full_keys, cfg)
    top_sens = RV.v1_top_donors(draws, pool, ritc, keys, cfg)
    pkeys = {key_of(o) for o in primary}
    return {
        "question": ("what do the vignette stresses become under the 672 construction (the extraction's precedence "
                     "rules, the working sample before the owner's decision of 22 October 2026), fitted and transferred "
                     "from its own donors, beside the primary's?"),
        "seed": recorded["seed"], "B": recorded["B"], "estimator": RV.ESTIMATOR,
        "pool": {"n_donors": int(len(keys)), "n_syndicates": int(len(set(pool[3].tolist()))),
                 "n_assumed_business": int(ritc.sum()),
                 "definition": ("the 672 construction's vignette donors (run_analysis._vig_donor_pool on "
                                "load_and_classify('precedence_672')), rounded as the shipped tool rounds its donors, "
                                "in the loader's order")},
        "headline": {"source": "results/check_gamma0_vignette_results.json, the headline operator's block "
                               "(its centre recomputed here and found equal)", **head},
        "precedence_672": block,
        "relative_to_headline": {"note": "672 construction's centre / headline centre - 1",
                                 **RV.relative(block["centre"], head["centre"])},
        "centre_decomposition": {
            "note": ("centre-only legs at the posterior means: the headline fit on the 672 construction's donors "
                     "changes the pool alone; the 672 fit on the headline's donors changes the posterior alone"),
            "headline_fit_on_sensitivity_pool": pool_only,
            "headline_fit_on_sensitivity_pool_relative_to_headline": RV.relative(pool_only, head["centre"]),
            "sensitivity_fit_on_headline_pool": fit_only,
            "sensitivity_fit_on_headline_pool_relative_to_headline": RV.relative(fit_only, head["centre"]),
        },
        "order_statistics": {
            "note": ("the inverse-CDF VaR of n donors is one order statistic of the transferred severities, counted "
                     "here from the largest; a pool of another size reads another one, so part of a change in VaR is "
                     "that index and not the donors"),
            **{q: {"headline_pool": RV.rank_from_top(len(full_keys), a),
                   "sensitivity_pool": RV.rank_from_top(len(keys), a)}
               for q, a in (("V1_v99", 0.99), ("V1_v995", 0.995))}},
        "v1_top_donors_headline": top_donor_place(top, primary, sensitivity),
        "v1_top_donors_sensitivity": {
            "n": len(top_sens),
            "donors": [dict(r, rank=i + 1, in_primary=r["donor"] in pkeys) for i, r in enumerate(top_sens)],
            "not_in_primary": [r["donor"] for r in top_sens if r["donor"] not in pkeys]},
        "v1_gpd_tail": gpd,
    }


def main():
    primary = load()
    off = [key_of(o) for o in primary if o.get("pyd_cohort_scope") != ENFORCED]
    if off:
        raise SystemExit("model/exposure_results.json is not the primary outcome: %d working-sample records are not "
                         "mature-enforced (%s); regenerate it under ANALYSIS_CONFIG['outcome'] 'mature_cohort'"
                         % (len(off), ", ".join(off[:5])))
    sens_records, sensitivity = load_sensitivity()
    cov672 = coverage(sensitivity)
    out = {
        "purpose": ("the cohort coverage of the numerators: the primary outcome (every figure the mature-cohort "
                    "movement over u <= t-2; the owner's decision of 22 October 2026) beside the 672 construction (the "
                    "extraction's precedence rules), refitted and transferred as a sensitivity"),
        "estimand_note": ("a triangle route computes the sum of ultimate-estimate changes over u <= t-2 directly; a "
                          "disclosed prior-year movement is whatever the filing reports for prior years and is not "
                          "partitioned by cohort, so the restriction is not established for those records"),
        "count_note": ("n_gross_sample, n_mature_enforced, n_disclosed_prior_year, share_enforced and "
                       "n_syndicates_enforced describe the 672 construction (the working sample before the owner's "
                       "decision of 22 October 2026), as they always have; the primary's counts are under 'primary'. "
                       "n_mature_enforced counts the figures whose recorded route is a triangle: the route field the "
                       "extraction writes, read as the basis rule reads it, or, for a block from before that field, a "
                       "triangle's override annotation (the review of 2 October 2026, M-2)"),
        "n_gross_sample": cov672["n_gross_sample"],
        "n_mature_enforced": cov672["n_mature_enforced"],
        "n_disclosed_prior_year": cov672["n_disclosed_prior_year"],
        "share_enforced": cov672["share_enforced"],
        "n_syndicates_enforced": cov672["n_syndicates_enforced"],
        "primary": dict(coverage(primary), outcome="mature_cohort",
                        source="model/exposure_results.json (run_analysis.ANALYSIS_CONFIG['outcome'] "
                               "'mature_cohort')"),
        "sensitivity_672": dict(cov672, outcome="precedence_672",
                                source="run_analysis.load_and_classify('precedence_672'), in memory",
                                disclosed_keys=sorted((key_of(o) for o in sensitivity
                                                       if o.get("pyd_cohort_scope") != ENFORCED),
                                                      key=lambda k: tuple(int(x) for x in k.split("_")))),
        "membership": membership(primary, sensitivity),
    }

    S, R, H, yr, key = arrays(sensitivity)
    out["sensitivity_672_fit"], idata = fit(S, R, H, yr, ritc_flag(key))
    out["headline"] = headline()
    out["shifts_vs_headline"] = {
        v: round(out["sensitivity_672_fit"][v]["mean"] - float(out["headline"][v]["mean"]), 6)
        for v in VARS if v in out["headline"]
    }
    out["reading"] = ("the 672 construction holds %d disclosed figures, and %d records it shares with the primary carry "
                      "another severity there (a broader figure a sign-only precedence rule put in the triangle's "
                      "place); the check is how far the parameters and stresses move with them"
                      % (out["n_disclosed_prior_year"], out["membership"]["n_both_other_severity"]))
    diag = RV.convergence(idata)
    out["sensitivity_672_fit_convergence"] = diag
    if not RV.converged(diag):
        raise SystemExit("the 672 construction's fit has not converged (%s): no figures are written" % diag)
    out["vignettes"] = sensitivity_vignettes(sens_records, primary, sensitivity, idata)

    with io.open(OUT, "w", encoding="utf-8", newline="") as _fh:
        _fh.write(json.dumps(out, indent=1) + "\n")
    print("wrote", OUT.name)
    print("  primary %d (all mature-enforced); 672 construction %d: enforced %d, disclosed %d"
          % (out["primary"]["n_gross_sample"], out["n_gross_sample"], out["n_mature_enforced"],
             out["n_disclosed_prior_year"]))
    m = out["membership"]
    print("  in both with the same severity %d, another severity %d; primary only %d; 672 only %d"
          % (m["n_both_same_severity"], m["n_both_other_severity"], m["n_primary_only"], m["n_sensitivity_only"]))
    for v in VARS:
        if v in out["shifts_vs_headline"]:
            print("  %-10s 672 %.4f   headline %.4f   shift %+.4f"
                  % (v, out["sensitivity_672_fit"][v]["mean"],
                     float(out["headline"][v]["mean"]), out["shifts_vs_headline"][v]))
    print("  convergence: %d divergences, max R-hat %.4f, min ESS bulk %.0f tail %.0f"
          % (diag["divergences"], diag["max_rhat"], diag["min_ess_bulk"], diag["min_ess_tail"]))
    vig = out["vignettes"]
    for q in ("V1_v99", "V1_v995", "V2_d995"):
        print("  %s (%s) %-8s headline %.4f   672 %.4f   (%+.2f%%)"
              % (transfer_operator.HEADLINE, vig["precedence_672"]["operator_role"], q, vig["headline"]["centre"][q],
                 vig["precedence_672"]["centre"][q], 100 * vig["relative_to_headline"][q]))
    t = vig["v1_top_donors_headline"]
    print("  of the headline's top %d Vignette 1 donors, %d are absent from the 672 construction and %d carry another "
          "severity there" % (t["n"], t["n_absent_from_sensitivity"], t["n_other_severity_in_sensitivity"]))
    g = vig["v1_gpd_tail"]
    for leg in ("full_pool_headline_fit",) + GPD_LEGS:
        r, b = g[leg], g[leg]["bayesian"]
        rel = g["relative_to_full_pool_headline_fit"].get(leg)
        print("  V1 GPD VaR99.5 %-34s N %d u %.5f Nu %d  POT %.4f%s  Bayes %.4f [%.4f, %.4f]%s"
              % (leg, r["N"], r["threshold_u"], r["Nu"], r["point_var995"],
                 "" if rel is None else " (%+.2f%%)" % (100 * rel["point_var995"]),
                 b["var995_median"], b["var995_2.5"], b["var995_97.5"],
                 "" if rel is None else " (%+.2f%%)" % (100 * rel["bayesian_var995_median"])))


if __name__ == "__main__":
    main()
