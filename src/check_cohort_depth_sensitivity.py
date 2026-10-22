"""Cohort-depth sensitivity: the outcome on the underwriting years u <= t-3 instead of u <= t-2 (the review of
23 October 2026, m6).

Equation (1)'s outcome is the gross movement over the underwriting years u <= t-2. The youngest of those, u = t-2, is
read at its second development period, where a growing book's step can be large (1945/2020, whose severity went from
-36.1m to +58.4m under the primary, is mostly that one cell). This sensitivity leaves the u = t-2 year out and asks
what the fit, the vignette stresses and the operator's size-quartile calibration become.

Each primary record's mature-cohort figure is recomputed from the stored gross triangle grid the primary figure comes
from, by the extraction's own estimator at the pinned commit (build_mature_cohort_figures.estimator, parsed from the
extraction checkout, LLOYDS_EXTRACTION_REPO), first at its own cutoff, u <= t-2 (PYD_EXCLUDED_RECENT_UW_YEARS = 2), and
the recomputation must reproduce the primary's figure (model/exposure_results.json, in GBP at the loader's rate) to
the rounding of the extraction's table (an absolute 0.0015m or 0.05% of the figure) or the record is left out. The same
estimator with the constant at 3 gives the figure on u <= t-3. A record is left out, and counted by reason, where:

  * the primary figure is not reproduced from any stored grid of the record (a figure two readings of the filing
    confirmed, whose printed table the extraction did not store);
  * the loader sign-flipped the figure (the severity's sign was reversed against the model's direction);
  * the estimator returns no figure on u <= t-3 (the grid has no underwriting year up to t-3 with a usable step);
  * the primary's severity is not the figure over the opening reserves (a check of the arithmetic, not a measure).

The adopted model is refitted twice on the records that remain, with check_cohort_scope.fit (the headline's block,
sampler, seed and settings): once on their primary severities (u <= t-2), so that dropping records is separated from
changing the depth, and once on the u <= t-3 severities. Both fits are transferred to the vignettes as the other
scope sensitivities are (refit_vignettes: the donors are these records' own, rounded as the shipped tool rounds them),
and the record reports n, k, the floor and diversifiable scale, both tail indices and the year-shock scale, Vignette 1's
VaR99 and VaR99.5 and Vignette 2's before and after, each against the primary's.

The operator's calibration by size quartile at 99 and 99.5% is first the cheap version of check_operator_backtest.py:
each target is scored against the VaR the operator reads from every other syndicate's donors at the sample's own
full-fit posterior means (leave-one-syndicate-out; the scale law and tail indices were fitted with the held-out
syndicate in, which the honest ten-fold version does not do), with check_operator_backtest's quartile table (exceedances
against expected, the by-syndicate Bayesian-bootstrap posterior of the rate with its 95% credible interval and the
posterior probability that it exceeds nominal, and the distinct syndicates carrying the exceedances).

It is also the honest ten-fold version, the one the primary's backtest has (check_operator_backtest.py): the kept
records' syndicates are split into 10 folds by oos_validation.fold_assignment, the adopted model is REFITTED on each
fold's training syndicates (check_operator_backtest.run_folds with this sample), and each held-out syndicate-year is
transferred from the training pool at that fold's posterior means (the plug-in) and over 600 of its posterior draws (the
posterior-draw version). The record holds the exceedances against the expected counts overall, by size quartile of the
targets' R and for clean and RITC years, the pinball loss, the by-syndicate Bayesian bootstrap, every target's exceedance
flag at each level and the by-size-quartile table with the syndicates carrying the exceedances
(check_operator_backtest.per_target_block). It is run twice, on the SAME kept records: at the primary's u <= t-2
severities (honest_backtest_t_minus_2_on_the_kept_records) and at the u <= t-3 severities (honest_backtest_t_minus_3).
honest_t_minus_2_vs_t_minus_3 sets the two side by side with one set of size quartile edges (the targets' R is the same
at both depths), each depth's exceedances against the expected count by quartile, its by-syndicate bootstrap rate with
the 95% credible interval and the posterior probability that the rate exceeds nominal, the syndicates carrying the
exceedances, the targets that exceed at both depths or at one, and every target whose flag differs. That is the
comparison that isolates the depth.

The comparison with the primary's own backtest (honest_backtest_t_minus_3.against_the_primarys_backtest) is NOT
like for like. The primary's backtest is on 649 records and this one on the 592 kept, so they differ in sample, and so in
the quartile edges (the primary's 172/419/830 against 195/448/913): "quartile 1" is a different set of books in each. The
57 records left out are not a random 57. By the PRIMARY's size quartile they are 36 of its 162 smallest books (22%), 5 of
162 in quartile 2, 11 of 162 in quartile 3 and 5 of 163 in quartile 4
(left_out_by_primary_size_quartile in the record). By reason: 43 have no figure on u <= t-3 (32, 2, 8 and 1 in quartiles
1 to 4) and 14 have a figure no stored grid reproduces (4, 3, 3 and 4). A record left out for having no figure on
u <= t-3 is a young book whose only mature cell is u = t-2; it is OUTSIDE a test of that cell by construction, so the
u <= t-3 backtest cannot say anything about the very books whose u = t-2 cell is in question. Syndicate 1991 has two
records left out, 1991/2015 (no figure at t-3) and 1991/2018 (no stored grid), both in the primary's quartile 1, where
syndicate 1991 carries six of the primary's nine exceedances at 99%. Syndicate 382 has six (2015 to 2020, no stored grid). Forty-eight
syndicates have a record left out. The t-3 backtest is therefore not a test of the primary's quartile 1 finding; the
side-by-side table on the 592 is.

Writes check_cohort_depth_sensitivity_results.json.
Usage:  python src/check_cohort_depth_sensitivity.py [workers]
"""
import io
import json
import os
import sys
import time

import numpy as np

import build_mature_cohort_figures as bm
import check_cohort_scope as CS
import check_operator_backtest as BT
import refit_vignettes as RV
import sample_scope as SS
import transfer_operator
from adopted_model import SD

OUT = SD / "results" / "check_cohort_depth_sensitivity_results.json"
#: the primary's honest ten-fold backtest (check_operator_backtest.py), whose size-quartile tables this record sets
#: beside its own
BACKTEST_RECORD = SD / "results" / "check_operator_backtest_results.json"
RECORDS = SD / "pdf_extraction"
#: the primary's cutoff and the sensitivity's, in years before the report year: u <= t - LAG
PRIMARY_LAG, SENSITIVITY_LAG = 2, 3
#: how closely a recomputed figure must equal the primary's: the table's own rounding (build_mature_cohort_figures.FIGURE_TOL)
#: or 0.05% of the figure, in GBP
TOL_ABS, TOL_REL = bm.FIGURE_TOL, 0.0005
#: how closely a record's severity must equal its figure over its opening reserves (the loader divides them)
SEVERITY_TOL = 1.0e-9
#: the stored grids a figure can come from, in the order tried: the adopted block's RAG triangle, the register's block,
#: then every block's RAG triangle and claims triangle
GRID_FIELDS = ("_rag_triangle", "_claims_triangle")
LEVELS = (0.99, 0.995)
#: the reasons a record is left out, in the order they are decided
REASONS = ("sign_flipped_by_the_loader", "figure_not_reproduced_from_a_stored_grid", "no_figure_at_t_minus_3",
           "severity_is_not_the_figure_over_the_opening_reserves")


# ----------------------------------------------------------------------------- the estimator at another depth
def lag_estimator(lag):
    """The extraction's compute_pyd_from_triangle at the pinned commit with its recent-years exclusion set to `lag`
    (u <= t - lag). Each call builds its own namespace, so the two depths do not share the constant."""
    fn = bm.estimator()
    fn.__globals__["PYD_EXCLUDED_RECENT_UW_YEARS"] = lag
    return fn


def candidate_grids(key, data, register=None):
    """[(model, field, grid)] the record's stored triangle grids in the order tried: the canonical block's RAG
    triangle, the register's block (an entry of data/mature_cohort_figures.json names its model), then every block's."""
    blocks = data.get("models") or {}
    out, seen = [], set()

    def add(mk, fld):
        b = blocks.get(mk)
        if isinstance(b, dict) and isinstance(b.get(fld), dict) and (mk, fld) not in seen:
            seen.add((mk, fld))
            out.append((mk, fld, b[fld]))

    add(bm.canonical_key(data), GRID_FIELDS[0])
    named = ((register or {}).get(key) or {}).get("triangle", {}).get("model")
    if named:
        add(named, GRID_FIELDS[0])
    for mk in sorted(blocks):
        for fld in GRID_FIELDS:
            add(mk, fld)
    return out


def reproduce(key, primary_gbp, data, fn, register=None):
    """The first stored grid whose u <= t-2 figure, in GBP, equals the primary's `primary_gbp` to the tolerance, as
    {"model", "field", "grid", "figure_gbp_m"}, or None."""
    year = int(key.split("_")[1])
    tol = max(TOL_ABS, TOL_REL * abs(primary_gbp))
    for mk, fld, tri in candidate_grids(key, data, register):
        figure, _details = bm.compute(fn, tri, year)
        if figure is None:
            continue
        _currency, gbp = bm.fx_gbp(key, figure)
        if abs(gbp - primary_gbp) <= tol:
            return {"model": mk, "field": fld, "grid": tri, "figure_gbp_m": gbp}
    return None


def at_depth(key, grid, fn):
    """The grid's figure on u <= t-lag in GBP under `fn`, or (None, the estimator's reason)."""
    figure, details = bm.compute(fn, grid, int(key.split("_")[1]))
    if figure is None:
        return None, str(details)
    return bm.fx_gbp(key, figure)[1], None


def judge(o, data, fn2, fn3, register=None):
    """(row, None) for a record that stays in the sensitivity, or (None, (reason, detail)) for one that is left out.

    row: the record's figure at each depth and its severities (the primary's and the depth-3 one)."""
    key = CS.key_of(o)
    if o.get("sign_flipped"):
        return None, (REASONS[0], "the loader reversed the figure's sign against the model's direction")
    rep = reproduce(key, o["pyd_gbp_m"], data, fn2, register)
    if rep is None:
        return None, (REASONS[1], "no stored grid of the record gives %.6fm on u <= t-2" % o["pyd_gbp_m"])
    fig3, why = at_depth(key, rep["grid"], fn3)
    if fig3 is None:
        return None, (REASONS[2], why)
    opening = o["opening_reserves_gbp_m"]
    if abs(o["s_raw_a"] - o["pyd_gbp_m"] / opening) > SEVERITY_TOL:
        return None, (REASONS[3], "severity %r against %r" % (o["s_raw_a"], o["pyd_gbp_m"] / opening))
    return {"record": key, "grid": "%s:%s" % (rep["model"], rep["field"]), "opening_reserves_gbp_m": opening,
            "figure_t_minus_2_gbp_m": rep["figure_gbp_m"], "figure_t_minus_3_gbp_m": fig3,
            "severity_t_minus_2": o["s_raw_a"], "severity_t_minus_3": fig3 / opening}, None


def load_record(key):
    with io.open(str(RECORDS / ("syndicate_%s.json" % key)), encoding="utf-8") as fh:
        return json.load(fh)


def partition(recs, register=None, load=load_record):
    """The primary records split into those that stay (rows, in the primary's order) and those left out, with reasons."""
    fn2, fn3 = lag_estimator(PRIMARY_LAG), lag_estimator(SENSITIVITY_LAG)
    rows, out = [], []
    for o in recs:
        row, left = judge(o, load(CS.key_of(o)), fn2, fn3, register)
        if row is not None:
            rows.append(row)
        else:
            out.append({"record": CS.key_of(o), "reason": left[0], "detail": left[1],
                        "primary_figure_gbp_m": o["pyd_gbp_m"], "opening_reserves_gbp_m": o["opening_reserves_gbp_m"]})
    return rows, out


# ----------------------------------------------------------------------------- the sample at one depth
def sample_at(recs, rows, depth):
    """The kept records with their severities at `depth` ("t_minus_2": the primary's, "t_minus_3": the recomputed), as
    copies of the observations whose s_raw_a is that severity, in the primary's order."""
    by_key = {r["record"]: r for r in rows}
    out = []
    for o in recs:
        k = CS.key_of(o)
        if k in by_key:
            c = dict(o)
            c["s_raw_a"] = by_key[k]["severity_" + depth]
            out.append(c)
    return out


def counts_of(recs):
    S, R, H, yr, key = CS.arrays(recs)
    return {"n": int(len(S)), "n_syndicates": int(len({o["syndicate"] for o in recs})),
            "n_assumed_business": int(CS.ritc_flag(key).sum()),
            "severity": {"mean": float(S.mean()), "sd": float(S.std(ddof=1)), "min": float(S.min()),
                         "max": float(S.max())}}


def cheap_backtest(recs, idata, cfg, levels=LEVELS):
    """Leave-one-syndicate-out at the sample's own full-fit posterior means: the operator's exceedances at `levels` overall
    and by size quartile of R (check_operator_backtest.quartile_table), with the by-syndicate Bayesian bootstrap."""
    S, R, H, yr, key = CS.arrays(recs)
    ritc = CS.ritc_flag(key).astype(bool)
    syn = np.array([o["syndicate"] for o in recs])
    means = {p: (float(idata.posterior[p].values.mean()) if p in idata.posterior else 0.0) for p in BT.OPERATOR_PARAMS}
    th = BT.operator_params(means)
    thetas = {s: th for s in set(syn.tolist())}
    q = BT.leave_out_quantiles(S, R, H, ritc, syn, syn, yr, thetas, cfg, False, levels)[BT.OPERATOR_METHOD]
    edges, quart = BT.size_quartiles(R)
    W = BT.bayes_bootstrap_weights(syn)
    flags = {a: np.asarray(S > q[a], bool) for a in levels}
    return {"version": ("cheap: leave-one-syndicate-out at the sample's own full-fit posterior means (the held-out "
                        "syndicate is in the scale law and the tail indices; the honest ten-fold version is not run)"),
            "n": int(len(S)), "posterior_means_used": means,
            "size_quartile_edges_gbp_m": [float(e) for e in edges],
            "exceedances": {"%g" % a: int(flags[a].sum()) for a in levels},
            "expected": {"%g" % a: float(len(S) * (1.0 - a)) for a in levels},
            "by_size_quartile": BT.quartile_table(flags, quart, syn, W, levels)}


#: the outcome depths, as the words the labels and the record use
DEPTH_WORDS = {"t_minus_2": "u <= t-2", "t_minus_3": "u <= t-3"}


def honest_backtest(recs, cfg, workers=BT.DEFAULT_WORKERS, k=BT.K_HONEST, fits=None, depth="t_minus_3"):
    """The honest ten-fold operator backtest on `recs` (the kept records, at their severities at `depth`: the primary's
    u <= t-2 severities, or the u <= t-3 ones), as check_operator_backtest.compute runs it on the primary: the syndicates
    dealt into k folds by fold_assignment, the adopted model refitted on each fold's training syndicates (BT.run_folds on
    this sample), and each held-out syndicate-year scored against the VaR the headline operator reads from the training
    pool at the fold's posterior means (honest) and over its posterior draws (honest_posterior_draws), with the
    per-target flags and the by-size-quartile tables (BT.per_target_block). `fits` stands in for the fold fits (a
    test's)."""
    if depth not in DEPTH_WORDS:
        raise SystemExit("unknown outcome depth %r (one of %s)" % (depth, sorted(DEPTH_WORDS)))
    words = DEPTH_WORDS[depth]
    S, R, H, yr, key = CS.arrays(recs)
    ritc = CS.ritc_flag(key).astype(bool)
    syn = np.array([o["syndicate"] for o in recs])
    fold = BT.fold_assignment(syn, k)
    W = BT.bayes_bootstrap_weights(syn)
    edges, quart = BT.size_quartiles(R)
    t_fit = time.time()
    if fits is None:
        fits = BT.run_folds(workers, k, sample=(S, R, H, yr, syn, ritc.astype(float)))
    fit_wall = time.time() - t_fit
    thetas = {int(f["fold"]): BT.operator_params(f["means"]) for f in fits}
    plug_in_q, draw_q = {}, {}
    honest = BT.version_block(
        "honest: %d-fold by syndicate, adopted model refitted on each fold's training syndicates, %s outcome" % (k, words),
        "fold assignment is oos_validation.fold_assignment on this sample's syndicates; held-out syndicates are in "
        "neither the pool nor the fit",
        False, S, R, H, ritc, syn, yr, fold, thetas, cfg, W, capture=plug_in_q)
    honest["folds"] = k
    honest["fits"] = [{key_: f[key_] for key_ in ("fold", "n_train", "n_held_out", "n_train_syndicates",
                                                  "n_held_out_syndicates", "params", "diagnostics")} for f in fits]
    draws = BT.posterior_draws_block(S, R, H, ritc, syn, yr, fold, fits, cfg, W, honest["pool_rules"], capture=draw_q)
    targets = dict(zip(("V1", "V2_old", "V2_new"), BT.load_targets()))
    per_target = BT.per_target_block(S, R, ritc, syn, yr, W, plug_in_q, draw_q, targets)
    return {
        **transfer_operator.stamp(transfer_operator.HEADLINE),
        "label": ("the honest ten-fold operator backtest on the %s outcome (the kept records at their %s "
                  "severities), as check_operator_backtest.py runs it on the primary" % (words, words)),
        "depth": depth,
        "n": int(len(S)), "n_syndicates": int(len(set(syn.tolist()))), "n_ritc": int(ritc.sum()),
        "levels": list(BT.LEVELS), "methods": list(BT.METHODS),
        "size_quartiles": {"of": "R of the %d targets" % len(R), "edges_gbp_m": [float(e) for e in edges],
                           "counts": [int((quart == j).sum()) for j in range(4)]},
        "bayes_bootstrap": {"reps": BT.BB_REPS, "seed": BT.BB_SEED,
                            "weights": "uniform Dirichlet over syndicates, a syndicate's years sharing its weight",
                            "reading": "a posterior over the exceedance rate under the bootstrap, not a test"},
        "sampler": {"draws": BT.DRAWS, "tune": BT.TUNE, "chains": BT.CHAINS, "target_accept": BT.TARGET_ACCEPT,
                    "seed": BT.FIT_SEED},
        "honest": honest,
        "honest_posterior_draws": draws,
        "per_target": per_target,
        "runtime_seconds": {"fold_fits_wall": fit_wall, "workers": int(workers)},
    }


def against_primary_backtest(honest, path=None, honest_t2=None):
    """The u <= t-3 backtest's exceedances by size quartile (honest plug-in and posterior-draw versions, pool rule
    leave_out) beside the primary's committed ones (results/check_operator_backtest_results.json), or None where that
    record is absent. NOT a like-for-like comparison: the primary's 649 records and this one's kept records differ in
    SAMPLE (the left-out records fall mainly in the primary's smallest size quartile) and therefore in the quartile
    EDGES, so "quartile 1" is a different set of books in each. The comparison at one depth on one sample is
    depths_side_by_side. When `honest_t2` (the kept records at u <= t-2) is given its rows are added, so the effect of
    the sample alone (649 against the kept records, both at u <= t-2) is separate from the effect of the depth."""
    path = BACKTEST_RECORD if path is None else path
    if not os.path.exists(str(path)):
        return None
    with io.open(str(path), encoding="utf-8") as fh:
        prim = json.load(fh)
    out = {"differs_in": ("sample (%d records against %d) and so in the size quartile edges; not a like-for-like "
                          "comparison (depths_side_by_side is)" % (prim["n"], honest["n"])),
           "primary_n": prim["n"], "depth_n": honest["n"],
           "primary_size_quartile_edges_gbp_m": prim["size_quartiles"]["edges_gbp_m"],
           "depth_size_quartile_edges_gbp_m": honest["size_quartiles"]["edges_gbp_m"]}
    blocks = [("primary", prim["per_target"]), ("t_minus_3", honest["per_target"])]
    if honest_t2 is not None:
        blocks.insert(1, ("t_minus_2_on_the_kept_records", honest_t2["per_target"]))
    for src in ("honest_plug_in", "honest_posterior_draws"):
        out[src] = {}
        for a in ("0.99", "0.995"):
            row = {}
            for label, blk in blocks:
                tab = blk["by_size_quartile"][src]["leave_out"][a]
                row[label] = {"exceedances": [tab["size_quartile_%d" % j]["exceedances"] for j in (1, 2, 3, 4)],
                              "expected": [tab["size_quartile_%d" % j]["expected"] for j in (1, 2, 3, 4)],
                              "p_rate_above_nominal": [tab["size_quartile_%d" % j]["p_rate_above_nominal"]
                                                       for j in (1, 2, 3, 4)]}
            out[src][a] = row
    return out


#: what a quartile row of one depth carries into the side-by-side table
ROW_FIELDS = ("exceedances", "rate_mean", "rate_credible_interval_95", "p_rate_above_nominal",
              "n_syndicates_with_exceedances", "exceedances_by_syndicate")
SIDE_LEVELS = ("0.99", "0.995")


def depths_side_by_side(h2, h3):
    """The honest backtest at u <= t-2 (`h2`) and at u <= t-3 (`h3`) on the SAME records, side by side: for each version
    (plug-in, posterior draws), pool rule and level, the exceedances against the expected count overall and by size
    quartile (the same quartile edges for both, the targets' R being the same), each depth's by-syndicate Bayesian-
    bootstrap rate (mean, 95% credible interval), P(rate above nominal) and the syndicates carrying the exceedances,
    how many targets exceed at both depths, only at t-2 and only at t-3, and the targets whose flag differs. Refuses two
    backtests that are not on the same targets (the comparison is only like-for-like on one sample)."""
    t2, t3 = h2["per_target"]["targets"], h3["per_target"]["targets"]
    for key in ("syndicate", "year", "R_gbp_m", "size_quartile", "ritc"):
        if t2[key] != t3[key]:
            raise SystemExit("the two depths are not on the same targets (%s differs): no side-by-side table" % key)
    if h2["size_quartiles"]["edges_gbp_m"] != h3["size_quartiles"]["edges_gbp_m"]:
        raise SystemExit("the two depths have different size quartile edges: no side-by-side table")
    quart = t2["size_quartile"]
    out = {"reading": ("the honest ten-fold backtest on the same %d records at the primary's u <= t-2 outcome and at "
                       "u <= t-3, with one set of size quartile edges; exceedances against expected, and the "
                       "by-syndicate Bayesian-bootstrap posterior of the rate, are each depth's own; a record whose "
                       "only mature cell is u = t-2 is not among these records (it is outside a test of that cell by "
                       "construction)" % h2["n"]),
           "n": h2["n"], "size_quartile_edges_gbp_m": h2["size_quartiles"]["edges_gbp_m"],
           "size_quartile_counts": h2["size_quartiles"]["counts"]}
    for src in ("honest_plug_in", "honest_posterior_draws"):
        out[src] = {}
        for rule in BT.POOL_RULES:
            out[src][rule] = {}
            for a in SIDE_LEVELS:
                f2, f3 = (h["per_target"]["exceedance_flags"][src][rule][a] for h in (h2, h3))
                tab2, tab3 = (h["per_target"]["by_size_quartile"][src][rule][a] for h in (h2, h3))
                rows = {}
                for j in (1, 2, 3, 4):
                    name = "size_quartile_%d" % j
                    idx = [i for i, q in enumerate(quart) if q == j]
                    rows[name] = {
                        "n_targets": tab2[name]["n_targets"], "expected": tab2[name]["expected"],
                        "t_minus_2": {k_: tab2[name][k_] for k_ in ROW_FIELDS},
                        "t_minus_3": {k_: tab3[name][k_] for k_ in ROW_FIELDS},
                        "exceed_at_both": sum(1 for i in idx if f2[i] and f3[i]),
                        "only_at_t_minus_2": sum(1 for i in idx if f2[i] and not f3[i]),
                        "only_at_t_minus_3": sum(1 for i in idx if f3[i] and not f2[i])}
                block = {"total": {"t_minus_2": int(sum(f2)), "t_minus_3": int(sum(f3)),
                                   "expected": float(len(f2) * (1.0 - float(a)))},
                         "by_size_quartile": rows}
                if rule == "leave_out":
                    block["targets_whose_flag_differs"] = [
                        {"syndicate": t2["syndicate"][i], "year": t2["year"][i], "R_gbp_m": t2["R_gbp_m"][i],
                         "size_quartile": quart[i], "exceeds_at_t_minus_2": bool(f2[i]),
                         "exceeds_at_t_minus_3": bool(f3[i])} for i in range(len(f2)) if f2[i] != f3[i]]
                out[src][rule][a] = block
    return out


def left_out_by_primary_size_quartile(recs, left):
    """The records left out (`left`: the partition's list), by the quartile of the PRIMARY's size (R of the primary's own
    records, check_operator_backtest.size_quartiles' edges on them) and by reason, with the syndicates, per quartile and
    one by one (every syndicate's left-out records are named, 1991's among them). A left-out record is a young book or one
    whose figure no stored grid gives; the table shows where in the size distribution they fall."""
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    edges, quart = BT.size_quartiles(R)
    qof = {CS.key_of(o): int(q) + 1 for o, q in zip(recs, quart)}
    out = {"edges_gbp_m": [float(e) for e in edges],
           "reading": "quartiles of R over the primary's %d records (1 the smallest books), the primary backtest's own" % len(recs),
           "n_primary_in_quartile": [int((quart == j).sum()) for j in range(4)]}
    for j in (1, 2, 3, 4):
        rows = [x for x in left if qof[x["record"]] == j]
        n_j = int((quart == j - 1).sum())
        out["size_quartile_%d" % j] = {
            "n_primary": n_j, "n_left_out": len(rows), "share_left_out": (len(rows) / n_j if n_j else None),
            "by_reason": {r: sum(1 for x in rows if x["reason"] == r) for r in REASONS},
            "syndicates": sorted({int(x["record"].split("_")[0]) for x in rows}),
            "records": [x["record"] for x in rows]}
    by_syn = {}
    for x in left:
        by_syn.setdefault(int(x["record"].split("_")[0]), []).append(x)
    out["by_syndicate"] = {
        str(s): {"n_left_out": len(v), "records": [{"record": x["record"], "reason": x["reason"],
                                                    "primary_size_quartile": qof[x["record"]]} for x in v]}
        for s, v in sorted(by_syn.items(), key=lambda kv: (-len(kv[1]), kv[0]))}
    out["syndicate_1991"] = out["by_syndicate"].get("1991", {"n_left_out": 0, "records": []})
    return out


def fit_and_transfer(recs, label, recorded, cfg):
    """The adopted model refitted on `recs`, its convergence, the vignette block on the records' own donors, and the cheap
    backtest by size quartile. Nothing is returned for a fit that has not converged."""
    S, R, H, yr, key = CS.arrays(recs)
    _rounded, idata = CS.fit(S, R, H, yr, CS.ritc_flag(key))
    summary = SS.unrounded_summary(idata)
    diag = RV.convergence(idata)
    if not RV.converged(diag):
        raise SystemExit("the %s fit has not converged (%s): no figures are written" % (label, diag))
    donors, ritc = donor_pool(recs)
    draws = RV.operator_draws(idata)
    block = RV.vignettes(draws, donors, ritc, cfg, recorded)
    mine = SS.centres_all(draws, donors, ritc, cfg)
    for q in ("V1_v99", "V1_v995", "V2_d995"):
        if mine[q] != block["centre"][q]:
            raise SystemExit("the %s centres computed here differ from operator_vignettes': %s" % (label, q))
    return {"sample": counts_of(recs), "fit": summary, "fit_convergence": diag,
            "vignettes": {"pool": {"n_donors": int(len(donors[0])), "n_assumed_business": int(ritc.sum())},
                          "centre": mine, "intervals": block["intervals"]},
            "operator_backtest_by_size_quartile": cheap_backtest(recs, idata, cfg)}


def donor_pool(recs):
    """(pool, assumed-business flags): the records as vignette donors, rounded as the shipped tool rounds its own (the
    severity to 8 decimals, the opening reserves to 2, the HHI to 6), in the records' order."""
    S = np.array([round(o["s_raw_a"], 8) for o in recs], float)
    R = np.array([round(o["opening_reserves_gbp_m"], 2) for o in recs], float)
    H = np.array([round(o["hhi"], 6) for o in recs], float)
    synd = np.array([o["syndicate"] for o in recs])
    year = np.array([o["year"] for o in recs])
    return (S, R, H, synd, year), RV.load_ritc(synd, year)


def relative(a, b):
    return {q: (a[q] / b[q] - 1.0 if b[q] != 0 else None) for q in a}


# ----------------------------------------------------------------------------- the record
def compute(workers=BT.DEFAULT_WORKERS, fits=None):
    t0 = time.time()
    recs = SS.primary()
    with io.open(str(SD / "data" / "mature_cohort_figures.json"), encoding="utf-8") as fh:
        register = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    rows, left = partition(recs, register)
    if not rows:
        raise SystemExit("no primary record is reproduced and has a figure on u <= t-3")
    by_reason = {r: sum(1 for x in left if x["reason"] == r) for r in REASONS}
    kept2, kept3 = sample_at(recs, rows, "t_minus_2"), sample_at(recs, rows, "t_minus_3")

    recorded = RV.headline_record()
    head, head_draws, cfg = RV.headline_block(recorded)
    full_pool, full_ritc, full_keys = RV.pool_for()
    pS, pR, _pH, _pyr, pkey = CS.arrays(recs)
    RV.check_pool_is_the_fit_sample(full_pool, full_keys, pkey.tolist(), pS, pR)
    head_centre = SS.centres_all(head_draws, full_pool, full_ritc, cfg)
    primary_fit = SS.primary_params()

    same = fit_and_transfer(kept2, "u <= t-2 on the kept records", recorded, cfg)
    deep = fit_and_transfer(kept3, "u <= t-3", recorded, cfg)
    honest = honest_backtest(kept3, cfg, workers=workers, fits=fits)
    honest2 = honest_backtest(kept2, cfg, workers=workers, fits=fits, depth="t_minus_2")
    honest["against_the_primarys_backtest"] = against_primary_backtest(honest, honest_t2=honest2)
    side_by_side = depths_side_by_side(honest2, honest)

    def against(block):
        return {"relative_to_primary": relative(block["vignettes"]["centre"], head_centre),
                "relative_to_the_kept_records_at_t_minus_2": relative(block["vignettes"]["centre"],
                                                                      same["vignettes"]["centre"]),
                "shift_vs_primary_in_primary_sd": {
                    v: (block["fit"][v]["mean"] - float(primary_fit[v]["mean"])) / float(primary_fit[v]["sd"])
                    for v in SS.VARS if v in primary_fit and float(primary_fit[v]["sd"]) > 0},
                "shift_vs_kept_records_at_t_minus_2": {
                    v: block["fit"][v]["mean"] - same["fit"][v]["mean"] for v in SS.VARS}}

    change = np.array([r["severity_t_minus_3"] - r["severity_t_minus_2"] for r in rows])
    return {
        **transfer_operator.stamp(RV.OPERATOR),
        "question": ("what do the fit, the vignette stresses and the operator's calibration by size become if the "
                     "outcome leaves out the u = t-2 underwriting year (u <= t-3 in place of u <= t-2)?"),
        "estimator": ("build_mature_cohort_figures.estimator(): the extraction's compute_pyd_from_triangle at the pinned "
                      "commit, with PYD_EXCLUDED_RECENT_UW_YEARS = 2 (the primary's cutoff, to reproduce the primary's "
                      "figure) and 3 (the sensitivity)"),
        "lags": {"primary": PRIMARY_LAG, "sensitivity": SENSITIVITY_LAG},
        "tolerance": {"absolute_gbp_m": TOL_ABS, "relative": TOL_REL},
        "n_primary": int(len(recs)), "n_kept": int(len(rows)), "n_left_out": int(len(left)),
        "left_out_by_reason": by_reason,
        "left_out": left,
        "left_out_by_primary_size_quartile": left_out_by_primary_size_quartile(recs, left),
        "grids_used": {g: sum(1 for r in rows if r["grid"] == g) for g in sorted({r["grid"] for r in rows})},
        "records": rows,
        "severity_change_t_minus_3_minus_t_minus_2": {
            "n_unchanged": int((np.abs(change) <= 1e-12).sum()), "n_changed": int((np.abs(change) > 1e-12).sum()),
            "mean": float(change.mean()), "median": float(np.median(change)),
            "mean_abs": float(np.abs(change).mean()), "max_abs": float(np.abs(change).max())},
        "primary": {"fit": {v: primary_fit[v] for v in SS.VARS if v in primary_fit},
                    "vignette_centre": head_centre, "n": int(len(recs)),
                    "source": "model/dispersion_calibration_ritc.json and check_gamma0_vignette_results.json"},
        "kept_records_at_t_minus_2": same,
        "cohort_depth_t_minus_3": {**deep, **against(deep)},
        "honest_backtest_t_minus_3": honest,
        "honest_backtest_t_minus_2_on_the_kept_records": honest2,
        "honest_t_minus_2_vs_t_minus_3": side_by_side,
        "not_run": [],
        "runtime_seconds": time.time() - t0,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    workers = int(argv[0]) if argv and argv[0].isdigit() else BT.DEFAULT_WORKERS
    out = compute(workers)
    with io.open(str(OUT), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print("Wrote %s" % OUT)
    print("  %d primary records: %d kept, %d left out %s" % (out["n_primary"], out["n_kept"], out["n_left_out"],
                                                         out["left_out_by_reason"]))
    d, s = out["cohort_depth_t_minus_3"], out["kept_records_at_t_minus_2"]
    for v in SS.VARS:
        print("  %-9s t-3 %.4f   kept at t-2 %.4f   primary %.4f" % (v, d["fit"][v]["mean"], s["fit"][v]["mean"],
                                                                     out["primary"]["fit"][v]["mean"] if v in out["primary"]["fit"] else float("nan")))
    for q in ("V1_v99", "V1_v995", "V2_old_v99", "V2_old_v995", "V2_new_v99", "V2_new_v995", "V2_d995"):
        print("  %-12s t-3 %.4f  kept at t-2 %.4f  primary %.4f  (%+.1f%% against primary)"
              % (q, d["vignettes"]["centre"][q], s["vignettes"]["centre"][q], out["primary"]["vignette_centre"][q],
                 100 * d["relative_to_primary"][q]))
    for a in ("0.99", "0.995"):
        print("  cheap backtest %s: t-3 exceedances %d, kept at t-2 %d (expected %.1f); by size quartile t-3: %s"
              % (a, d["operator_backtest_by_size_quartile"]["exceedances"][a], s["operator_backtest_by_size_quartile"]["exceedances"][a],
                 d["operator_backtest_by_size_quartile"]["expected"][a],
                 [d["operator_backtest_by_size_quartile"]["by_size_quartile"][a]["size_quartile_%d" % j]["exceedances"]
                  for j in (1, 2, 3, 4)]))
    hb = out["honest_backtest_t_minus_3"]
    print("  honest ten-fold backtest on u <= t-3: n=%d, %d fold fits on %d workers, %.0f s; divergences %s, max R-hat %.4f"
          % (hb["n"], len(hb["honest"]["fits"]), hb["runtime_seconds"]["workers"], hb["runtime_seconds"]["fold_fits_wall"],
             [f["diagnostics"]["divergences"] for f in hb["honest"]["fits"]],
             max(f["diagnostics"]["max_rhat"] for f in hb["honest"]["fits"])))
    for src in ("honest_plug_in", "honest_posterior_draws"):
        for a in ("0.99", "0.995"):
            tab = hb["per_target"]["by_size_quartile"][src]["leave_out"][a]
            print("  %s %s by size quartile: exceedances %s of expected %s; P(rate above nominal) %s"
                  % (src, a, [tab["size_quartile_%d" % j]["exceedances"] for j in (1, 2, 3, 4)],
                     ["%.1f" % tab["size_quartile_%d" % j]["expected"] for j in (1, 2, 3, 4)],
                     ["%.2f" % tab["size_quartile_%d" % j]["p_rate_above_nominal"] for j in (1, 2, 3, 4)]))
    sb = out["honest_t_minus_2_vs_t_minus_3"]
    for src in ("honest_plug_in", "honest_posterior_draws"):
        for a in ("0.99", "0.995"):
            blk = sb[src]["leave_out"][a]
            print("  side by side, %s %s, the same %d records: total t-2 %d, t-3 %d (expected %.1f); by quartile t-2 %s, t-3 %s"
                  % (src, a, sb["n"], blk["total"]["t_minus_2"], blk["total"]["t_minus_3"], blk["total"]["expected"],
                     [blk["by_size_quartile"]["size_quartile_%d" % j]["t_minus_2"]["exceedances"] for j in (1, 2, 3, 4)],
                     [blk["by_size_quartile"]["size_quartile_%d" % j]["t_minus_3"]["exceedances"] for j in (1, 2, 3, 4)]))
    lo = out["left_out_by_primary_size_quartile"]
    print("  left out by the primary's size quartile: %s (of %s); syndicate 1991: %s"
          % ([lo["size_quartile_%d" % j]["n_left_out"] for j in (1, 2, 3, 4)], lo["n_primary_in_quartile"],
             [r["record"] for r in lo["syndicate_1991"]["records"]]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
