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
estimator with the constant at 3 gives the figure on u <= t-3.

The cohort-depth repair (26 October 2026, a decision of the Claude analysis session): a primary figure that is a REGISTER
figure no stored grid computes (a corrected or confirmed table: transposed, net, one column off, incremental, a restated
base, a misprint, or no grid at all) carries the per-cohort cells it is the sum of (cohort_cells, in
data/mature_cohort_figures.json and data/pyd_confirmed_figures.json; every cell read twice, round9/depth/audit.md and
second_reading.md, and checked by run_analysis.cohort_cells_gaps). Where no stored grid reproduces the figure, the cells'
u <= t-2 sum must equal the primary's to the same tolerance, and the u <= t-3 figure is their sum over the older cohorts, in
the report's currency at the loader's rate. 1274/2016 uses the register's DERIVED 2012 cell at both depths and reports the
range the other defensible factors give at each (21.8m to 25.7m at t-2, 11.18m to 15.03m at t-3, USD); 3334/2018 and
3500/2018 enter as single-cohort t-3 figures on the table's own base. An empty set is NEVER zero: a register with no cohort
up to t-3 (1609/2023, whose first cohort is t-2) and a stored grid whose u <= t-3 columns print no cell at all (5678/2016: the
estimator's 'all-zero column' sum, an empty set returned as 0.0; at_depth's guard, printed_steps) both give no figure at
t-3. A printed zero (a step from 14 to 14) is an observation and stays. partition(cells=None) is the partition before the
repair and the record keeps it (partition_before_repair) beside the repairs (every record whose place changed). A record is
left out, and counted by reason, where:

  * the primary figure is not reproduced from any stored grid of the record or from the register's cohort_cells;
  * the loader sign-flipped the figure (the severity's sign was reversed against the model's direction);
  * there is no figure on u <= t-3 (the grid or the register's cells have no underwriting year up to t-3 with a usable
    step, or none that prints a cell);
  * the primary's severity is not the figure over the opening reserves (a check of the arithmetic, not a measure).

The adopted model is refitted twice on the records that remain, with check_cohort_scope.fit (the headline's block,
sampler, seed and settings, with target_accept raised once to 0.995 for a refit that diverges, as below): once on their primary severities (u <= t-2), so that dropping records is separated from
changing the depth, and once on the u <= t-3 severities. Both fits are transferred to the vignettes as the other
scope sensitivities are (refit_vignettes: the donors are these records' own, rounded as the shipped tool rounds them),
and the record reports n, k, the floor and diversifiable scale, both tail indices and the year-shock scale, Vignette 1's
VaR99 and VaR99.5 and Vignette 2's before and after, each against the primary's.

Each of those two full refits is first run at the headline's target_accept 0.98. If it DIVERGES (the u <= t-3 refit
did, once, in the regeneration pass of 23 October 2026), it is refitted ONCE at target_accept 0.995, with the same
seed and every other setting unchanged (check_cohort_scope.fit's target_accept argument, whose default is the
headline's 0.98), and its figures are reported only if that refit converges by the same rule (no divergence, max
R-hat <= 1.01: refit_vignettes.converged). If the second attempt also fails the run stops and writes nothing. A fit that
fails on R-hat with no divergence is not retried. The record keeps both attempts' diagnostics (fit_attempts) and the
target_accept the reported figures come from (fit_target_accept); fit_convergence is the reported attempt's. An attempt
that is not reported ("reported": false) also keeps what it would have reported, computed from its own draws with no
further fit: its unrounded_summary and its vignette_centre (Vignette 1's and Vignette 2's VaR99 and VaR99.5 among
them), so the record shows what the retry changed. The
honest-backtest fold fits follow the same rule (converging_fold_fit, run by this script's own run_converging_folds, so
check_operator_backtest.py's fold path is untouched): a fold refit that diverges at 0.98 is refitted once at 0.995 with
the same seed and every other setting unchanged, its figures are used only if that refit converges, and the run stops if
the retry also fails (or if a fold fails on R-hat with no divergence). Each fold keeps both attempts' diagnostics
(attempts, in honest.fits) and the target_accept its reported fit comes from (target_accept); an attempt that is not
reported keeps the parameters it would have reported. The retry is a decision of the
Claude analysis session; a higher target_accept changes the sampler's step size, not the model, and the posterior it
targets is the same.

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
like for like. The primary's backtest is on every primary record and this one only on the kept records, so they differ in
sample, and so in the quartile edges (both sets of edges are in the record): "quartile 1" is a different set of books in each.
The records left out are not a random subset. Their counts by the PRIMARY's size quartile, by reason, and by syndicate are
in left_out_by_primary_size_quartile in the record, and the counts before the repair are in partition_before_repair. After
the repair every record left out has no figure on u <= t-3. A record left out for having no figure on u <= t-3 is a young
book whose only mature cell is u = t-2 (or an older book whose filing prints no older cohort); it is OUTSIDE a test of that
cell by construction, so the u <= t-3 backtest cannot say anything about the very books whose u = t-2 cell is in question.
Syndicate 1991's 1991/2015 is such a book (inception 2013 = t-2); 1991/2018 now enters from its register cells, so syndicate
1991's u = t-2 dominance is in the like-for-like table. The t-3 backtest is therefore not a test of the primary's quartile 1
finding; the side-by-side table on the kept records is.

Writes check_cohort_depth_sensitivity_results.json.
Usage:  python src/check_cohort_depth_sensitivity.py [workers]
"""
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor

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
#: the full refits' and the fold refits' target_accept: the headline's 0.98 (check_operator_backtest.TARGET_ACCEPT, which the
#: fold refits use), and the one retry if that attempt diverges (same seed)
TARGET_ACCEPT_FIRST, TARGET_ACCEPT_RETRY = 0.98, 0.995
#: the reasons a record is left out, in the order they are decided
REASONS = ("sign_flipped_by_the_loader", "figure_not_reproduced_from_a_stored_grid", "no_figure_at_t_minus_3",
           "severity_is_not_the_figure_over_the_opening_reserves")
#: the two registers that carry a primary figure no stored grid computes, each entry with its per-cohort cells
#: (cohort_cells, the cohort-depth repair of 26 October 2026)
CELL_REGISTERS = ("data/mature_cohort_figures.json", "data/pyd_confirmed_figures.json")
#: a line of the estimator's details that is a printed step (year, latest cell, previous cell, signed difference); an
#: "all-zero column (no claims activity), PYD=0" line is a column with no printed cell at all
STEP_LINE = re.compile(r"^\s+\d{4}: .+ = [+-]\d")


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


def printed_steps(details):
    """The details lines that are a printed step. A figure with none is an EMPTY SUM, not a zero: every column in it is an
    estimator 'all-zero column' (the grid prints no cell for it), so the set of years up to the cutoff has no observation
    (5678/2016 at t-3, whose 2012 and 2013 columns print nothing: the syndicate began in 2014)."""
    return [ln for ln in str(details).splitlines() if STEP_LINE.match(ln)]


def at_depth(key, grid, fn, guard=True):
    """The grid's figure on u <= t-lag in GBP under `fn`, or (None, the reason). With `guard` a figure none of whose years
    has a printed step (printed_steps) is no figure: an empty u <= t-3 set is 'no figure at t-3', never 0. A printed zero
    (a step from 14 to 14) is an observation and stays."""
    figure, details = bm.compute(fn, grid, int(key.split("_")[1]))
    if figure is None:
        return None, str(details)
    if guard and not printed_steps(details):
        return None, ("no printed step on the years up to the cutoff (every column is an all-zero column): an empty "
                      "sum is not a zero")
    return bm.fx_gbp(key, figure)[1], None


def load_cell_registers():
    """{key: {"source", "cohort_cells", "figure_m", "correction"}} for every entry of the two registers that carries
    cohort_cells."""
    out = {}
    for rel in CELL_REGISTERS:
        with io.open(str(SD / rel), encoding="utf-8") as fh:
            reg = json.load(fh)
        for k, e in reg.items():
            if not k.startswith("_") and isinstance(e, dict) and isinstance(e.get("cohort_cells"), dict):
                if k in out:
                    raise SystemExit("%s: cohort_cells in both %s and %s" % (k, out[k]["source"], rel))
                out[k] = {"source": rel, "cohort_cells": e["cohort_cells"], "figure_m": e.get("figure_m"),
                          "correction": e.get("correction")}
    return out


def from_cells(key, o, cells):
    """(part, None) for a record whose primary figure is a register figure, from its cohort_cells: the u <= t-2 sum, in
    GBP at the loader's rate, must equal the primary's to the tolerance (else the record stays out as not reproduced); the
    u <= t-3 sum is the figure at t-3, or no figure when no term is that old (1609/2023). (None, (reason, detail)) when
    the register's cells cannot serve."""
    import run_analysis as ra
    c = cells.get(key)
    if c is None:
        return None, (REASONS[1], "no stored grid of the record gives %.6fm on u <= t-2 and its register has no "
                      "cohort_cells" % o["pyd_gbp_m"])
    cc = c["cohort_cells"]
    fig2 = ra.cohort_cells_figure_m(cc, PRIMARY_LAG)
    if fig2 is None:
        return None, (REASONS[1], "the register's cohort_cells hold no term up to t-2")
    gbp2 = bm.fx_gbp(key, fig2)[1]
    tol = max(TOL_ABS, TOL_REL * abs(o["pyd_gbp_m"]))
    if abs(gbp2 - o["pyd_gbp_m"]) > tol:
        return None, (REASONS[1], "the register's cohort_cells give %.6fm on u <= t-2, not the primary's %.6fm"
                      % (gbp2, o["pyd_gbp_m"]))
    fig3 = ra.cohort_cells_figure_m(cc, SENSITIVITY_LAG)
    n3 = len(ra.cohort_cells_cutoff_terms(cc, SENSITIVITY_LAG))
    if fig3 is None:
        return None, (REASONS[2], "no cohort up to t-3 has a cell in the register's cohort_cells (%s): there is no figure "
                      "at t-3, and it is never 0" % c["source"])
    part = {"grid": "register:%s" % c["source"], "figure_t_minus_2_gbp_m": gbp2,
            "figure_t_minus_3_gbp_m": bm.fx_gbp(key, fig3)[1],
            "cells": {"source": c["source"], "report_currency": cc["currency"], "unit": cc["unit"],
                      "table_kind": cc["table_kind"],
                      "cohorts_at_t_minus_2": len(ra.cohort_cells_cutoff_terms(cc, PRIMARY_LAG)),
                      "cohorts_at_t_minus_3": n3, "single_cohort_at_t_minus_3": n3 == 1,
                      "figure_t_minus_2_report_m": fig2, "figure_t_minus_3_report_m": fig3}}
    corr = c.get("correction") or {}
    rng = corr.get("range_other_factors_m")
    if corr.get("derived_figure_m") is not None and rng:
        # a derived figure (1274/2016) is reported with the range the other defensible factors give at each depth: the
        # range at t-2 less the terms that drop out at t-3
        dropped = fig2 - fig3
        part["cells"]["derived"] = True
        part["cells"]["range_t_minus_2_report_m"] = list(rng)
        part["cells"]["range_t_minus_3_report_m"] = [round(rng[0] - dropped, 3), round(rng[1] - dropped, 3)]
    return part, None


def judge(o, data, fn2, fn3, register=None, cells=None):
    """(row, None) for a record that stays in the sensitivity, or (None, (reason, detail)) for one that is left out.

    row: the record's figure at each depth and its severities (the primary's and the depth-3 one).

    `cells` (load_cell_registers) is the cohort-depth repair of 26 October 2026: a record whose primary figure no stored
    grid computes (a register figure) takes its figures at both depths from the register's per-cohort cells, and a stored
    grid's figure on an empty set of years is no figure (at_depth's guard). With `cells` None the judgement is the one
    before the repair (a stored grid or nothing, no guard): partition(cells=None) is the partition_before_repair."""
    key = CS.key_of(o)
    if o.get("sign_flipped"):
        return None, (REASONS[0], "the loader reversed the figure's sign against the model's direction")
    opening = o["opening_reserves_gbp_m"]
    rep = reproduce(key, o["pyd_gbp_m"], data, fn2, register)
    if rep is None:
        if cells is None:
            return None, (REASONS[1], "no stored grid of the record gives %.6fm on u <= t-2" % o["pyd_gbp_m"])
        part, left = from_cells(key, o, cells)
        if left is not None:
            return None, left
        if abs(o["s_raw_a"] - o["pyd_gbp_m"] / opening) > SEVERITY_TOL:
            return None, (REASONS[3], "severity %r against %r" % (o["s_raw_a"], o["pyd_gbp_m"] / opening))
        fig3 = part["figure_t_minus_3_gbp_m"]
        return {"record": key, "grid": part["grid"], "opening_reserves_gbp_m": opening,
                "figure_t_minus_2_gbp_m": part["figure_t_minus_2_gbp_m"], "figure_t_minus_3_gbp_m": fig3,
                "severity_t_minus_2": o["s_raw_a"], "severity_t_minus_3": fig3 / opening, "cells": part["cells"]}, None
    fig3, why = at_depth(key, rep["grid"], fn3, guard=cells is not None)
    if fig3 is None:
        return None, (REASONS[2], why)
    if abs(o["s_raw_a"] - o["pyd_gbp_m"] / opening) > SEVERITY_TOL:
        return None, (REASONS[3], "severity %r against %r" % (o["s_raw_a"], o["pyd_gbp_m"] / opening))
    return {"record": key, "grid": "%s:%s" % (rep["model"], rep["field"]), "opening_reserves_gbp_m": opening,
            "figure_t_minus_2_gbp_m": rep["figure_gbp_m"], "figure_t_minus_3_gbp_m": fig3,
            "severity_t_minus_2": o["s_raw_a"], "severity_t_minus_3": fig3 / opening}, None


def load_record(key):
    with io.open(str(RECORDS / ("syndicate_%s.json" % key)), encoding="utf-8") as fh:
        return json.load(fh)


def partition(recs, register=None, load=load_record, cells="committed"):
    """The primary records split into those that stay (rows, in the primary's order) and those left out, with reasons.
    `cells` is the cohort-depth repair's register cells (load_cell_registers; "committed" reads the committed registers);
    None gives the partition before the repair (stored grids only, no empty-sum guard)."""
    fn2, fn3 = lag_estimator(PRIMARY_LAG), lag_estimator(SENSITIVITY_LAG)
    if isinstance(cells, str):
        cells = load_cell_registers()
    rows, out = [], []
    for o in recs:
        row, left = judge(o, load(CS.key_of(o)), fn2, fn3, register, cells)
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


def partition_summary(rows, left):
    """A partition as the record keeps it: the counts, the reasons and every left-out record with its reason."""
    return {"n_kept": len(rows), "n_left_out": len(left),
            "left_out_by_reason": {r: sum(1 for x in left if x["reason"] == r) for r in REASONS},
            "left_out": [{"record": x["record"], "reason": x["reason"], "detail": x["detail"]} for x in left]}


def repair_report(rows, left, rows0, left0):
    """Every record whose place changed with the cohort-depth repair: where it stood before (kept, or the reason it was
    left out), where it stands now, and for a record the register's cells now serve the source and the cells' check against
    the primary. A record the repair moves out (5678/2016: an empty sum was a zero) is listed too."""
    now = {r["record"]: ("kept", r) for r in rows}
    now.update({x["record"]: (x["reason"], x) for x in left})
    before = {r["record"]: ("kept", r) for r in rows0}
    before.update({x["record"]: (x["reason"], x) for x in left0})
    out = []
    for k in sorted(before, key=lambda k: tuple(int(p) for p in k.split("_"))):
        (b, bx), (a, ax) = before[k], now[k]
        if b == a and (b != "kept" or bx["grid"] == ax["grid"]):
            continue
        row = {"record": k, "before": b, "after": a}
        if a == "kept":
            row.update({"source": ax["grid"], "figure_t_minus_2_gbp_m": ax["figure_t_minus_2_gbp_m"],
                        "figure_t_minus_3_gbp_m": ax["figure_t_minus_3_gbp_m"], "cells": ax.get("cells")})
        else:
            row["detail"] = ax["detail"]
        out.append(row)
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


def fit_fold_at(fold, k, sample, target_accept):
    """check_operator_backtest.fit_training for one fold at `target_accept`. fit_training reads the module's
    TARGET_ACCEPT when it samples and takes no such argument (the primary's backtest, whose file this script does not
    change, always runs it at 0.98), so the constant is set for the call and put back afterwards, in the process that
    runs the fold (a pool worker, or the caller when workers <= 1). At 0.98 this is the primary's own call."""
    saved = BT.TARGET_ACCEPT
    BT.TARGET_ACCEPT = target_accept
    try:
        return BT.fit_training(fold, k, sample)
    finally:
        BT.TARGET_ACCEPT = saved


def converging_fold_fit(fold, k=BT.K_HONEST, sample=None, fit=None):
    """One fold's refit under the rule the full refits use (converging_fit): the fold is fitted at TARGET_ACCEPT_FIRST;
    if that DIVERGES it is fitted once more at TARGET_ACCEPT_RETRY, with the same seed and every other setting
    unchanged, and its figures are used only if that refit converges (no divergence, max R-hat <= 1.01:
    refit_vignettes.converged). A fold that fails on R-hat with no divergence is not retried. If the last attempt has not
    converged the run stops and names both attempts' diagnostics.

    Returns the reported attempt's fit (check_operator_backtest.fit_training's dict) with "target_accept" (that
    attempt's) and "attempts" (every attempt: target_accept, diagnostics, converged, reported; an attempt that
    is not reported also keeps the "params" and "means" it would have reported, from its own draws, so the record shows
    what the retry changed). `fit(fold, k, sample, target_accept)` stands in for fit_fold_at (a test's). A top-level
    function with picklable arguments, so a pool of worker processes can run it."""
    fit = fit_fold_at if fit is None else fit
    attempts, fitted = [], []
    for target_accept in (TARGET_ACCEPT_FIRST, TARGET_ACCEPT_RETRY):
        f = fit(fold, k, sample, target_accept)
        diag = f["diagnostics"]
        ok = bool(RV.converged(diag))
        attempts.append({"target_accept": target_accept, "diagnostics": diag, "converged": ok})
        fitted.append(f)
        if ok:
            for i, (a, earlier) in enumerate(zip(attempts, fitted)):
                a["reported"] = i == len(attempts) - 1
                if not a["reported"]:
                    a["params"], a["means"] = earlier["params"], earlier["means"]
            return {**f, "target_accept": target_accept, "attempts": attempts}
        if diag["divergences"] == 0:
            break
    raise SystemExit("fold %d has not converged (%s): no figures are written"
                     % (fold, "; ".join("target_accept %g: %s" % (a["target_accept"], a["diagnostics"])
                                         for a in attempts)))


def run_converging_folds(workers, k=BT.K_HONEST, sample=None, fit=None):
    """check_operator_backtest.run_folds with converging_fold_fit in place of fit_training: the k fold refits, in fold
    order, on `workers` worker processes (the count does not change the numbers). `fit` stands in for
    converging_fold_fit (a test's; it must be picklable where workers > 1)."""
    fit = converging_fold_fit if fit is None else fit
    if workers <= 1:
        return [fit(f, k, sample) for f in range(k)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fit, range(k), [k] * k, [sample] * k))


def fold_attempts(f):
    """(target_accept, attempts) of a fold fit: the reported attempt's target_accept and every attempt's diagnostics. A
    fit that did not come through converging_fold_fit (a test's stand-in) is one attempt at the primary's target_accept."""
    if "attempts" in f:
        return f["target_accept"], f["attempts"]
    return BT.TARGET_ACCEPT, [{"target_accept": BT.TARGET_ACCEPT, "diagnostics": f["diagnostics"],
                               "converged": bool(RV.converged(f["diagnostics"])), "reported": True}]


def honest_backtest(recs, cfg, workers=BT.DEFAULT_WORKERS, k=BT.K_HONEST, fits=None, depth="t_minus_3"):
    """The honest ten-fold operator backtest on `recs` (the kept records, at their severities at `depth`: the primary's
    u <= t-2 severities, or the u <= t-3 ones), as check_operator_backtest.compute runs it on the primary: the syndicates
    dealt into k folds by fold_assignment, the adopted model refitted on each fold's training syndicates (run_converging_folds
    on this sample: a fold that diverges at 0.98 is refitted once at 0.995, as the full refits are), and each held-out
    syndicate-year scored against the VaR the headline operator reads from the training pool at the fold's posterior means
    (honest) and over its posterior draws (honest_posterior_draws), with the per-target flags and the by-size-quartile
    tables (BT.per_target_block). `fits` stands in for the fold fits (a test's)."""
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
        fits = run_converging_folds(workers, k, sample=(S, R, H, yr, syn, ritc.astype(float)))
    fit_wall = time.time() - t_fit
    thetas = {int(f["fold"]): BT.operator_params(f["means"]) for f in fits}
    plug_in_q, draw_q = {}, {}
    honest = BT.version_block(
        "honest: %d-fold by syndicate, adopted model refitted on each fold's training syndicates, %s outcome" % (k, words),
        "fold assignment is oos_validation.fold_assignment on this sample's syndicates; held-out syndicates are in "
        "neither the pool nor the fit",
        False, S, R, H, ritc, syn, yr, fold, thetas, cfg, W, capture=plug_in_q)
    honest["folds"] = k
    honest["fits"] = [{**{key_: f[key_] for key_ in ("fold", "n_train", "n_held_out", "n_train_syndicates",
                                                     "n_held_out_syndicates", "params", "diagnostics")},
                       "target_accept": fold_attempts(f)[0], "attempts": fold_attempts(f)[1]} for f in fits]
    honest["folds_retried"] = [int(f["fold"]) for f in fits if len(fold_attempts(f)[1]) > 1]
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
                    "seed": BT.FIT_SEED, "target_accept_retry": TARGET_ACCEPT_RETRY,
                    "retry_rule": ("a fold fit that diverges at target_accept is refitted once at target_accept_retry, "
                                   "same seed, and used only if that refit converges (no divergence, max R-hat <= "
                                   "1.01); the run stops if it does not")},
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


def converging_fit(S, R, H, yr, ritc, label, fit=None, diagnose=None, figures=None):
    """A full refit of the adopted model (check_cohort_scope.fit) that is reported only if it converges (no divergence,
    max R-hat <= 1.01: refit_vignettes.converged). The first attempt is at target_accept TARGET_ACCEPT_FIRST. If it
    DIVERGES, it is refitted once at TARGET_ACCEPT_RETRY, with the same seed and every other setting unchanged, and
    reported only if that refit converges by the same rule. A fit that fails on R-hat without a divergence is not
    retried (a higher target_accept answers divergent transitions, not slow mixing). If the last attempt has not
    converged the run stops and names both attempts' diagnostics.

    Returns (idata, diagnostics of the reported attempt, [every attempt: target_accept, diagnostics, converged,
    reported], the target_accept of the reported attempt). When a later attempt is reported, each earlier attempt is
    marked "reported": false and carries `figures(its idata)` (a dict, merged into its entry: what its own fit would
    have reported, computed from its own draws with no further fit), so the record shows what the retry changed.
    `fit` and `diagnose` stand in for check_cohort_scope.fit and refit_vignettes.convergence (a test's)."""
    fit = CS.fit if fit is None else fit
    diagnose = RV.convergence if diagnose is None else diagnose
    attempts, idatas = [], []
    for target_accept in (TARGET_ACCEPT_FIRST, TARGET_ACCEPT_RETRY):
        _rounded, idata = fit(S, R, H, yr, ritc, target_accept=target_accept)
        diag = diagnose(idata)
        ok = bool(RV.converged(diag))
        attempts.append({"target_accept": target_accept, "diagnostics": diag, "converged": ok})
        idatas.append(idata)
        if ok:
            for i, (a, earlier) in enumerate(zip(attempts, idatas)):
                a["reported"] = i == len(attempts) - 1
                if not a["reported"] and figures is not None:
                    a.update(figures(earlier))
            return idata, diag, attempts, target_accept
        if diag["divergences"] == 0:
            break
    raise SystemExit("the %s fit has not converged (%s): no figures are written"
                     % (label, "; ".join("target_accept %g: %s" % (a["target_accept"], a["diagnostics"])
                                         for a in attempts)))


def fit_and_transfer(recs, label, recorded, cfg, fit=None, diagnose=None):
    """The adopted model refitted on `recs` (converging_fit: target_accept 0.98, and once at 0.995 if that diverges),
    its convergence and both attempts' diagnostics, the vignette block on the records' own donors, and the cheap
    backtest by size quartile. Nothing is returned for a fit that has not converged."""
    S, R, H, yr, key = CS.arrays(recs)
    donors, ritc = donor_pool(recs)

    def discarded(first):
        """What an attempt that is not reported would have reported: its fit summary and its vignette centres (V1 and
        V2 VaR99 and VaR99.5 among them), from its own idata."""
        return {"unrounded_summary": SS.unrounded_summary(first),
                "vignette_centre": SS.centres_all(RV.operator_draws(first), donors, ritc, cfg)}

    idata, diag, attempts, reported_ta = converging_fit(S, R, H, yr, CS.ritc_flag(key), label, fit=fit,
                                                           diagnose=diagnose, figures=discarded)
    summary = SS.unrounded_summary(idata)
    draws = RV.operator_draws(idata)
    block = RV.vignettes(draws, donors, ritc, cfg, recorded)
    mine = SS.centres_all(draws, donors, ritc, cfg)
    for q in ("V1_v99", "V1_v995", "V2_d995"):
        if mine[q] != block["centre"][q]:
            raise SystemExit("the %s centres computed here differ from operator_vignettes': %s" % (label, q))
    return {"sample": counts_of(recs), "fit": summary, "fit_convergence": diag,
            "fit_target_accept": reported_ta, "fit_attempts": attempts,
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
    rows0, left0 = partition(recs, register, cells=None)
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
        "partition_before_repair": partition_summary(rows0, left0),
        "repairs": repair_report(rows, left, rows0, left0),
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
    for name in ("honest_backtest_t_minus_2_on_the_kept_records", "honest_backtest_t_minus_3"):
        for f in out[name]["honest"]["fits"]:
            if len(f["attempts"]) > 1:
                print("  %s fold %d retried: %s" % (name, f["fold"], "; ".join(
                    "target_accept %g divergences %d max R-hat %.4f min bulk ESS %.0f %s" % (
                        a["target_accept"], a["diagnostics"]["divergences"], a["diagnostics"]["max_rhat"],
                        a["diagnostics"]["min_ess_bulk"], "(reported)" if a["reported"] else "(not reported)")
                    for a in f["attempts"])))
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
