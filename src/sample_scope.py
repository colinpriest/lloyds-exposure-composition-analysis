"""The primary sample refitted and transferred without a named set of records: one implementation for the scope
sensitivities of the adjudication of 22 October 2026 (results/extraction_error_rate/mature-cohort/adjudication.md, the
author's choices (i) on Q4 and Q5):

  - check_earned_basis_sensitivity.py: without the records whose filings say the t-2 cohort was still earning (Q4,
    option B's named records);
  - check_bucket_share_sensitivity.py: without the records whose "X and prior" bucket, printed without development,
    holds more than 30% of the gross reserves (Q5, option B).

Each refits the adopted model (adopted_model.scale_block, gamma = 0, the headline's sampler, seed and settings, through
check_cohort_scope.fit) on the primary working sample less the records, and transfers the vignettes from the remaining
donors through refit_vignettes (check_gamma0_vignette.operator_vignettes under the headline size-only operator, at the
seed and B of check_gamma0_vignette.py's record), beside the primary's own fit and figures. The primary's figures are
the headline calibration (model/dispersion_calibration_ritc.json) and check_gamma0_vignette.py's record, whose centre is
recomputed first and must be equal. Figures are written only for a fit with no divergence and every R-hat at most 1.01.

The adjudication's population measures, which both read, are archived with it under
results/extraction_error_rate/mature-cohort/measures/ (measures/measure_pop.py, measures/classify_pop.py and their outputs, and the
design's scan of the restored grids); sets.json there is the design's population, not the primary, which is read from
model/exposure_results.json.
"""
import io
import json

import arviz as az
import numpy as np

import check_cohort_scope as CS
import refit_vignettes as RV
from adopted_model import SD, HEADLINE_DRAWS, headline
from pool_quantile import var_q
from vignette_uncertainty import load_targets, transfer
import transfer_operator

MEASURES = SD / "results" / "extraction_error_rate" / "mature-cohort" / "measures"
POP_MEASURES = MEASURES / "pop_measures.json"
POP_CLASSIFIED = MEASURES / "pop_classified.json"
SCAN_RESTORED = MEASURES / "scan_restored.json"
CENSUS = SD / "results" / "extraction_error_rate" / "triangle-table-scan" / "triangle-table-scan.json"
#: the parameters reported against the primary's: k, the floor sd_undiv, the diversifiable scale, both tail indices and
#: the year-shock scale (check_cohort_scope.VARS)
VARS = CS.VARS


def load_json(path):
    with io.open(path, encoding="utf-8") as _fh:
        return json.load(_fh)


def key_of(o):
    return CS.key_of(o)


def primary():
    """The primary working sample (model/exposure_results.json), refused unless every record is mature-enforced."""
    recs = CS.load()
    off = [key_of(o) for o in recs if o.get("pyd_cohort_scope") != CS.ENFORCED]
    if off:
        raise SystemExit("model/exposure_results.json is not the primary outcome: %d records are not mature-enforced "
                         "(%s)" % (len(off), ", ".join(off[:5])))
    return recs


def order_key(k):
    return tuple(int(x) for x in k.split("_"))


def unrounded_summary(idata, names=VARS):
    """{name: mean, sd and 95% HDI} of a fit's posterior, unrounded (check_cohort_scope.fit's summary rounds them)."""
    s = az.summary(idata, var_names=list(names), hdi_prob=0.95, round_to="none")
    return {v: {"mean": float(s.loc[v, "mean"]), "sd": float(s.loc[v, "sd"]), "hdi_2.5%": float(s.loc[v, "hdi_2.5%"]),
                "hdi_97.5%": float(s.loc[v, "hdi_97.5%"])} for v in names}


def primary_params(names=VARS):
    """The primary's posterior mean and SD of each of `names`: from the headline fit's draws
    (model/dispersion_posterior_draws_ritc.npz), unrounded, where they are stored, else from its calibration JSON
    (adopted_model.headline(), rounded to three decimals: tau_s)."""
    js = headline()
    with np.load(HEADLINE_DRAWS) as z:
        stored = {k: z[k] for k in z.files}
    out = {}
    for v in names:
        if v in stored:
            out[v] = {"mean": float(np.mean(stored[v])), "sd": float(np.std(stored[v], ddof=1)),
                      "source": "model/dispersion_posterior_draws_ritc.npz"}
        elif v in js:
            out[v] = {"mean": float(js[v]["mean"]), "sd": float(js[v]["sd"]),
                      "source": "model/dispersion_calibration_ritc.json (rounded to three decimals)"}
    return out


def centres_all(draws, pool, ritc, cfg):
    """V1 VaR99 and VaR99.5, Vignette 2's VaR99 and VaR99.5 before and after, and the change at 99.5%, on `pool` at
    the posterior means of `draws` under the headline operator."""
    S, R, H, _s, _y = pool
    v1, v2o, v2n = load_targets()
    th = transfer_operator.params(draws, RV.OPERATOR)
    thbar = {p: float(th[p].mean()) for p in th}
    a1, ao, an = (transfer(S, R, H, t, thbar, cfg, ritc) for t in (v1, v2o, v2n))
    return {"V1_v99": var_q(a1, 0.99), "V1_v995": var_q(a1, 0.995),
            "V2_old_v99": var_q(ao, 0.99), "V2_old_v995": var_q(ao, 0.995),
            "V2_new_v99": var_q(an, 0.99), "V2_new_v995": var_q(an, 0.995),
            "V2_d99": var_q(an, 0.99) - var_q(ao, 0.99), "V2_d995": var_q(an, 0.995) - var_q(ao, 0.995)}


def refit_without(drop, label, rule):
    """The primary refitted and transferred without the records `drop` (keys "SSSS_YYYY"), beside the primary.

    `label` names the sensitivity and `rule` says which records were left out and why. Every key must be a primary
    record: a key outside it is an error, not a smaller drop."""
    recs = primary()
    keys = [key_of(o) for o in recs]
    drop = sorted(set(drop), key=order_key)
    missing = [k for k in drop if k not in set(keys)]
    if missing:
        raise SystemExit("%d of the records to leave out are not in the primary working sample: %s"
                         % (len(missing), missing))
    kept = [o for o in recs if key_of(o) not in set(drop)]
    S, R, H, yr, key = CS.arrays(kept)
    _rounded, idata = CS.fit(S, R, H, yr, CS.ritc_flag(key))
    fit_summary = unrounded_summary(idata)
    diag = RV.convergence(idata)
    if not RV.converged(diag):
        raise SystemExit("the %s fit has not converged (%s): no figures are written" % (label, diag))

    recorded = RV.headline_record()
    head, head_draws, cfg = RV.headline_block(recorded)
    full_pool, full_ritc, full_keys = RV.pool_for()
    pS, pR, _pH, _pyr, pkey = CS.arrays(recs)
    RV.check_pool_is_the_fit_sample(full_pool, full_keys, pkey.tolist(), pS, pR)
    pool, ritc, pkeys = RV.pool_for([key_of(o) for o in kept])
    draws = RV.operator_draws(idata)
    block = RV.vignettes(draws, pool, ritc, cfg, recorded)
    mine = centres_all(draws, pool, ritc, cfg)
    head_all = centres_all(head_draws, full_pool, full_ritc, cfg)
    for q in ("V1_v99", "V1_v995", "V2_d995"):
        if mine[q] != block["centre"][q] or head_all[q] != head["centre"][q]:
            raise SystemExit("the centres computed here differ from operator_vignettes': %s" % q)
    pool_only = centres_all(head_draws, pool, ritc, cfg)
    fit_only = centres_all(draws, full_pool, full_ritc, cfg)
    top = RV.v1_top_donors(head_draws, full_pool, full_ritc, full_keys, cfg)
    by_key = {key_of(o): o for o in recs}
    h = primary_params()
    rel = lambda a, b: {q: a[q] / b[q] - 1.0 if b[q] != 0 else None for q in a}
    return {
        **transfer_operator.stamp(RV.OPERATOR),
        "sensitivity": label,
        "rule": rule,
        "n_primary": len(recs), "n_left_out": len(drop), "n_fit": len(kept),
        "n_syndicates_fit": len({o["syndicate"] for o in kept}),
        "left_out": [{"record": k, "severity": by_key[k]["s_raw_a"],
                      "opening_reserves_gbp_m": by_key[k]["opening_reserves_gbp_m"],
                      "v1_top_donor_rank": next((i + 1 for i, r in enumerate(top) if r["donor"] == k), None)}
                     for k in drop],
        "fit": fit_summary,
        "fit_convergence": diag,
        "primary_fit": {v: {"mean": float(h[v]["mean"]), "sd": float(h[v]["sd"]), "source": h[v]["source"]}
                        for v in VARS if v in h},
        "shift_vs_primary": {v: fit_summary[v]["mean"] - float(h[v]["mean"]) for v in VARS if v in h},
        "shift_vs_primary_in_primary_sd": {v: (fit_summary[v]["mean"] - float(h[v]["mean"])) / float(h[v]["sd"])
                                          for v in VARS if v in h and float(h[v]["sd"]) > 0},
        "vignettes": {
            "estimator": RV.ESTIMATOR,
            "seed": recorded["seed"], "B": recorded["B"],
            "pool": {"n_donors": int(len(pkeys)), "n_assumed_business": int(ritc.sum())},
            "centre": mine,
            "intervals": block["intervals"],
            "primary_centre": head_all,
            "primary_intervals": head["intervals"],
            "relative_to_primary": rel(mine, head_all),
            "centre_decomposition": {
                "note": ("centre-only legs at the posterior means: the primary fit on the reduced pool changes the pool "
                         "alone; the reduced fit on the primary's pool changes the posterior alone"),
                "primary_fit_on_reduced_pool": pool_only,
                "primary_fit_on_reduced_pool_relative": rel(pool_only, head_all),
                "reduced_fit_on_primary_pool": fit_only,
                "reduced_fit_on_primary_pool_relative": rel(fit_only, head_all)},
            "order_statistics": {q: {"primary_pool": RV.rank_from_top(len(full_keys), a),
                                     "reduced_pool": RV.rank_from_top(len(pkeys), a)}
                                 for q, a in (("v99", 0.99), ("v995", 0.995))},
        },
    }
