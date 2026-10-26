#!/usr/bin/env python3
"""The cohort-depth sensitivity (check_cohort_depth_sensitivity.py): the outcome on u <= t-3 in place of u <= t-2.

Each part is held to a hand computation, to the extraction's estimator, or to the committed record:

  * the estimator at depth 3 drops the u = t-2 column's step and nothing else, and building it does not move the
    depth-2 estimator;
  * a record is reproduced only when a stored grid of its own gives its primary figure to the tolerance, and each
    reason for leaving a record out fires on a record that has it (a mutation of the rule would not pass);
  * the partition of the primary covers every record once, on the real corpus;
  * the cheap backtest is check_operator_backtest's leave-one-syndicate-out with its quartile table;
  * the committed record (DEFERRED-TO-REFIT: written by the recorded pass).

Needs the extraction checkout (LLOYDS_EXTRACTION_REPO, default D:/dev/lloyds_reserve_stress_testing) at the pinned
commit, as build_mature_cohort_figures does; the real-corpus tests skip, with the reason, when it is absent.

Run:  python -m pytest src/test_cohort_depth_sensitivity.py -q
"""
import copy
import io
import json
import os
import subprocess

import numpy as np
import pytest

import build_mature_cohort_figures as bm
import check_cohort_depth_sensitivity as D
import check_cohort_scope as CS
import check_operator_backtest as BT
import refit_vignettes as RV
import sample_scope as SS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _extraction_available():
    import record_tests
    root = bm.extraction_root()
    r = subprocess.run(["git", "-C", root, "cat-file", "-e", "%s:test_gemini.py" % record_tests.extraction_pin()],
                       capture_output=True)
    return r.returncode == 0


pytestmark = pytest.mark.skipif(not _extraction_available(),
                                reason="no extraction repository at %s: set LLOYDS_EXTRACTION_REPO to the extraction "
                                       "repository, or this cross-repository check does not run"
                                       % bm.extraction_root())


@pytest.fixture(scope="module")
def fns():
    return D.lag_estimator(2), D.lag_estimator(3)


@pytest.fixture(scope="module")
def primary():
    return {CS.key_of(o): o for o in SS.primary()}


def _data(key):
    return D.load_record(key)


# ------------------------------------------------------------------ the estimator at depth 3 ------
def test_depth_three_drops_the_youngest_mature_columns_step_and_nothing_else(fns):
    """1084/2015: the grid's columns are 2011..2015 and t-2 = 2013. The depth-2 figure is 18.5m, the depth-3 figure 9.7m,
    and the difference is the 2013 column's step on the report-year diagonal, 586.1 - 577.3 = 8.8, read from the grid."""
    fn2, fn3 = fns
    key = "1084_2015"
    data = _data(key)
    grid = data["models"][bm.canonical_key(data)]["_rag_triangle"]
    f2, f3 = bm.compute(fn2, grid, 2015)[0], bm.compute(fn3, grid, 2015)[0]
    assert (f2, f3) == (18.5, 9.7)
    c = grid["underwriting_years"].index(2013)
    assert grid["development_rows"][2][c] - grid["development_rows"][1][c] == pytest.approx(8.8)
    assert f2 - f3 == pytest.approx(8.8)


def test_building_the_depth_three_estimator_leaves_the_depth_two_one_alone():
    fn2 = D.lag_estimator(2)
    fn3 = D.lag_estimator(3)
    assert fn2.__globals__["PYD_EXCLUDED_RECENT_UW_YEARS"] == 2 and fn3.__globals__["PYD_EXCLUDED_RECENT_UW_YEARS"] == 3
    assert fn2.__globals__ is not fn3.__globals__
    data = _data("1084_2015")
    grid = data["models"][bm.canonical_key(data)]["_rag_triangle"]
    assert bm.compute(fn2, grid, 2015)[0] == 18.5
    # the pinned constants are what the primary's estimator uses
    assert bm.TABLE_CONSTANTS["PYD_EXCLUDED_RECENT_UW_YEARS"] == D.PRIMARY_LAG == 2 and D.SENSITIVITY_LAG == 3


def test_a_grid_with_no_underwriting_year_up_to_t_minus_3_gives_no_figure_at_depth_three(fns):
    """1200/2023 reports on a grid whose oldest usable year is t-2: the estimator reads a figure at depth 2 and none at 3."""
    fn2, fn3 = fns
    data = _data("1200_2023")
    grid = data["models"][bm.canonical_key(data)]["_rag_triangle"]
    assert bm.compute(fn2, grid, 2023)[0] is not None
    figure, why = D.at_depth("1200_2023", grid, fn3)
    assert figure is None and "no usable UW years" in why


# ------------------------------------------------------------------ reproducing the primary figure ------
def test_a_record_is_reproduced_only_by_a_stored_grid_that_gives_its_figure_to_the_tolerance(fns):
    fn2, _ = fns
    data = _data("1084_2015")
    rep = D.reproduce("1084_2015", 18.5, data, fn2)
    assert rep is not None and rep["figure_gbp_m"] == 18.5 and rep["field"] == "_rag_triangle"
    tol = max(D.TOL_ABS, D.TOL_REL * 18.5)                  # 0.05% of the figure here, the larger of the two
    assert D.reproduce("1084_2015", 18.5 + 0.95 * tol, data, fn2) is not None
    assert D.reproduce("1084_2015", 18.5 - 0.95 * tol, data, fn2) is not None
    assert D.reproduce("1084_2015", 18.5 + 1.05 * tol, data, fn2) is None
    assert D.reproduce("1084_2015", 18.5 - 1.05 * tol, data, fn2) is None
    assert D.reproduce("1084_2015", 19.5, data, fn2) is None
    # a figure only a reading of the filing gave (1274/2022, confirmed) has no stored grid that reproduces it
    assert D.reproduce("1274_2022", 7.419061025089013, _data("1274_2022"), fn2) is None


def test_the_candidate_grids_come_canonical_block_first_then_the_registers_then_the_rest():
    data = _data("1084_2015")
    grids = D.candidate_grids("1084_2015", data)
    assert grids[0][:2] == (bm.canonical_key(data), "_rag_triangle")
    assert len({(m, f) for m, f, _ in grids}) == len(grids)
    assert all(f in D.GRID_FIELDS for _m, f, _g in grids)
    named = {"1084_2015": {"triangle": {"model": sorted(data["models"])[-1]}}}
    assert D.candidate_grids("1084_2015", data, named)[1][:2] == (sorted(data["models"])[-1], "_rag_triangle") \
        or sorted(data["models"])[-1] == bm.canonical_key(data)


# ------------------------------------------------------------------ the reasons a record is left out ------
def test_a_kept_record_carries_both_depths_figures_and_its_severities(fns, primary):
    fn2, fn3 = fns
    o = primary["1084_2015"]
    row, left = D.judge(o, _data("1084_2015"), fn2, fn3)
    assert left is None and row["record"] == "1084_2015"
    assert (row["figure_t_minus_2_gbp_m"], row["figure_t_minus_3_gbp_m"]) == (18.5, 9.7)
    assert row["severity_t_minus_2"] == o["s_raw_a"] and row["severity_t_minus_3"] == pytest.approx(9.7 / o["opening_reserves_gbp_m"])
    assert row["grid"].endswith(":_rag_triangle")


def test_each_reason_for_leaving_a_record_out_fires_on_a_record_that_has_it(fns, primary):
    fn2, fn3 = fns
    o, data = primary["1084_2015"], _data("1084_2015")
    flipped = dict(o, sign_flipped=True)
    assert D.judge(flipped, data, fn2, fn3)[1][0] == "sign_flipped_by_the_loader"
    moved = dict(o, pyd_gbp_m=o["pyd_gbp_m"] + 1.0)
    assert D.judge(moved, data, fn2, fn3)[1][0] == "figure_not_reproduced_from_a_stored_grid"
    assert D.judge(primary["1200_2023"], _data("1200_2023"), fn2, fn3)[1][0] == "no_figure_at_t_minus_3"
    odd = dict(o, s_raw_a=o["s_raw_a"] + 1e-6)
    assert D.judge(odd, data, fn2, fn3)[1][0] == "severity_is_not_the_figure_over_the_opening_reserves"
    assert set(D.REASONS) == {"sign_flipped_by_the_loader", "figure_not_reproduced_from_a_stored_grid",
                              "no_figure_at_t_minus_3", "severity_is_not_the_figure_over_the_opening_reserves"}


def test_the_partition_covers_every_primary_record_once_on_the_real_corpus():
    recs = SS.primary()
    with io.open(os.path.join(HERE, "data", "mature_cohort_figures.json"), encoding="utf-8") as fh:
        register = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    rows, left = D.partition(recs, register)
    keys = [CS.key_of(o) for o in recs]
    kept, out = [r["record"] for r in rows], [x["record"] for x in left]
    # 643 primary records at the recorded pass of 38cd750 (649 before the round-5 adjudication and review 8's decisions
    # took six records out of the primary: 4 restated-base tables, 1 unmeasurable take-on and one fifth FX record,
    # 3000/2022, among them); the partition is exhaustive at either size.
    # Re-pinned on 26 October 2026 to 632 on the regeneration at f15a357f: rule 8 (the source-history rule) set the
    # census's 11 records aside (cccdbe06), so the primary is 632 records.
    assert len(rows) + len(left) == len(recs) == 632
    assert sorted(kept + out) == sorted(keys) and not set(kept) & set(out)
    assert kept == [k for k in keys if k in set(kept)], "the kept records are in the primary's order"
    assert {x["reason"] for x in left} <= set(D.REASONS)
    # the depth really moves most severities: a depth that did not (lag 3 read as 2) would leave every one unchanged
    moved = sum(1 for r in rows if abs(r["severity_t_minus_3"] - r["severity_t_minus_2"]) > 1e-12)
    assert moved > len(rows) // 2
    # the kept records' depth-2 figure is the primary's
    pr = {CS.key_of(o): o for o in recs}
    for r in rows:
        assert abs(r["figure_t_minus_2_gbp_m"] - pr[r["record"]]["pyd_gbp_m"]) <= max(D.TOL_ABS, D.TOL_REL * abs(pr[r["record"]]["pyd_gbp_m"]))


# ------------------------------------------------------------------ the cohort-depth repair (26 October 2026) ------
#: the records whose primary figure is a register figure no stored grid computes: each carries its per-cohort cells
REGISTER_CELL_RECORDS = ["1274_2016", "1274_2022", "1609_2023", "1991_2018", "2232_2020", "318_2024", "3330_2017",
                         "3330_2018", "3334_2018", "3500_2018", "382_2015", "382_2016", "382_2017", "382_2018",
                         "382_2019", "382_2020", "4242_2022", "4444_2022", "4472_2022", "4472_2023"]


@pytest.fixture(scope="module")
def cells():
    return D.load_cell_registers()


def _obs_from_register(key, cells):
    """An observation whose primary figure is the register's figure at the loader's rate (fixed input: the committed
    exposure_results.json is the previous loader pass)."""
    c = cells[key]
    gbp = bm.fx_gbp(key, c["figure_m"])[1]
    syn, year = key.split("_")
    return {"syndicate": int(syn), "year": int(year), "pyd_gbp_m": gbp, "s_raw_a": gbp / 100.0,
            "opening_reserves_gbp_m": 100.0, "sign_flipped": False}


def test_the_register_cells_serve_every_record_no_stored_grid_reproduces(fns, cells):
    """Each of the 20 records whose figure is a register figure: no stored grid of its own gives it, the register's
    cells do (their u <= t-2 sum equals the figure at the loader's rate), and the u <= t-3 figure is the cells' sum over the
    older cohorts, read from the register, in the report's currency at the loader's rate. 1609/2023 has no cohort older
    than t-2 (inception 2021): no figure at t-3, never 0."""
    fn2, fn3 = fns
    assert sorted(cells) == REGISTER_CELL_RECORDS
    import run_analysis as ra
    for key in REGISTER_CELL_RECORDS:
        o = _obs_from_register(key, cells)
        data = _data(key)
        assert D.reproduce(key, o["pyd_gbp_m"], data, fn2) is None, "%s: a stored grid reproduces it" % key
        row, left = D.judge(o, data, fn2, fn3, None, cells)
        cc = cells[key]["cohort_cells"]
        if key == "1609_2023":
            assert row is None and left[0] == "no_figure_at_t_minus_3" and "never 0" in left[1]
            assert ra.cohort_cells_figure_m(cc, 3) is None
            continue
        assert left is None, (key, left)
        assert row["grid"] == "register:%s" % cells[key]["source"] and row["cells"]["source"] == cells[key]["source"]
        fig3 = ra.cohort_cells_figure_m(cc, 3)
        assert row["figure_t_minus_3_gbp_m"] == pytest.approx(bm.fx_gbp(key, fig3)[1]) and fig3 is not None
        assert row["figure_t_minus_2_gbp_m"] == pytest.approx(o["pyd_gbp_m"], abs=D.TOL_ABS)
        assert row["severity_t_minus_3"] == pytest.approx(row["figure_t_minus_3_gbp_m"] / 100.0)
        # without the register's cells the same record is left out as before the repair
        assert D.judge(o, data, fn2, fn3, None, None)[1][0] == "figure_not_reproduced_from_a_stored_grid"


def test_a_cell_the_register_does_not_support_leaves_the_record_out_as_not_reproduced(fns, cells):
    """Mutation check: breaking one cell (or a term) of the register makes the u <= t-2 sum differ from the primary's figure,
    and the record is left out; the depth script trusts no cell it cannot tie to the primary."""
    import run_analysis as ra
    fn2, fn3 = fns
    key = "4472_2022"
    o = _obs_from_register(key, cells)
    bad = copy.deepcopy(cells)
    bad[key]["cohort_cells"]["terms"][3]["term"] += 1.0
    bad[key]["cohort_cells"]["terms"][3]["latest"] = "1,101.3"
    row, left = D.judge(o, _data(key), fn2, fn3, None, bad)
    assert row is None and left[0] == "figure_not_reproduced_from_a_stored_grid"
    assert "not the primary's" in left[1]
    # the loader's own check of the same register refuses it before the depth script is reached
    entry = {"figure_m": cells[key]["figure_m"], "cohort_cells": bad[key]["cohort_cells"]}
    assert any("sum to figure_m" in g or "equal to its cells" in g for g in ra.cohort_cells_gaps(entry))
    # a register with no cohort_cells for a record no grid reproduces leaves it out too
    assert D.judge(o, _data(key), fn2, fn3, None, {})[1][0] == "figure_not_reproduced_from_a_stored_grid"


def test_an_empty_set_of_years_is_no_figure_at_t_minus_3_and_never_zero(fns):
    """5678/2016: its 2012 and 2013 columns print nothing (the syndicate began in 2014), so u <= t-3 is an empty sum that
    the estimator turned into 0.0 ('all-zero column, PYD=0'). The guard makes it no figure; a printed zero (1796/2024's
    14 -> 14) is an observation and stays."""
    fn2, fn3 = fns
    data = _data("5678_2016")
    tri = data["models"][bm.canonical_key(data)]["_rag_triangle"]
    assert D.at_depth("5678_2016", tri, fn3, guard=False)[0] == 0.0, "the estimator's empty sum is a zero"
    fig, why = D.at_depth("5678_2016", tri, fn3)
    assert fig is None and "empty sum is not a zero" in why
    assert D.at_depth("5678_2016", tri, fn2)[0] is not None, "u <= t-2 has the 2014 column's step"
    gbp = D.at_depth("5678_2016", tri, fn2)[0]
    o = {"syndicate": 5678, "year": 2016, "pyd_gbp_m": gbp, "s_raw_a": gbp / 87.761, "opening_reserves_gbp_m": 87.761}
    row, left = D.judge(o, data, fn2, fn3, None, {})
    assert row is None and left[0] == "no_figure_at_t_minus_3"
    row0, left0 = D.judge(o, data, fn2, fn3, None, None)
    assert left0 is None and row0["figure_t_minus_3_gbp_m"] == 0.0, "before the repair the zero was kept"
    d96 = _data("1796_2024")
    tri96 = d96["models"][bm.canonical_key(d96)]["_rag_triangle"]
    assert D.at_depth("1796_2024", tri96, fn3)[0] == 0.0, "a printed 14 -> 14 is a real zero and stays"
    # the details of the guard: a step line is a printed step, an all-zero line is not
    assert D.printed_steps("  2012: all-zero column (no claims activity), PYD=0") == []
    assert len(D.printed_steps("  2013: 14.0 (3yr later) - 14.0 (2yr later) = +0.000")) == 1


def test_1274_2016_takes_its_derived_cell_at_both_depths_and_reports_the_range(fns, cells):
    fn2, fn3 = fns
    key = "1274_2016"
    o = _obs_from_register(key, cells)
    row, left = D.judge(o, _data(key), fn2, fn3, None, cells)
    c = row["cells"]
    assert left is None and c["derived"] is True and c["cohorts_at_t_minus_2"] == 7 and c["cohorts_at_t_minus_3"] == 6
    assert c["figure_t_minus_2_report_m"] == pytest.approx(22.6943) and c["figure_t_minus_3_report_m"] == pytest.approx(12.0693)
    assert c["range_t_minus_2_report_m"] == [21.806, 25.659]
    assert c["range_t_minus_3_report_m"] == [11.181, 15.034], "11.18m to 15.03m USD at t-3"
    assert row["figure_t_minus_3_gbp_m"] == pytest.approx(bm.fx_gbp(key, 12.0693)[1], abs=1e-4)
    # the derived 2012 term is u = t-4: it is in both depths' sums
    terms = {t["u"]: t for t in cells[key]["cohort_cells"]["terms"]}
    assert terms[2012]["derived"] is True and terms[2012]["term"] == 9254.3


def test_3334_2018_and_3500_2018_are_single_cohort_at_t_minus_3_on_the_tables_own_base(fns, cells):
    fn2, fn3 = fns
    r1, l1 = D.judge(_obs_from_register("3334_2018", cells), _data("3334_2018"), fn2, fn3, None, cells)
    r2, l2 = D.judge(_obs_from_register("3500_2018", cells), _data("3500_2018"), fn2, fn3, None, cells)
    assert l1 is None and l2 is None
    assert r1["cells"]["cohorts_at_t_minus_3"] == 1 and r1["cells"]["single_cohort_at_t_minus_3"] is True
    assert r1["cells"]["figure_t_minus_3_report_m"] == pytest.approx(-0.014)
    assert r2["cells"]["cohorts_at_t_minus_3"] == 1 and r2["cells"]["single_cohort_at_t_minus_3"] is True
    assert r2["figure_t_minus_3_gbp_m"] == pytest.approx(r2["figure_t_minus_2_gbp_m"]), "t-3 equals t-2 for 3500/2018"


@pytest.fixture(scope="module")
def loader_primary():
    """The primary on fixed inputs: the loader's own 632 working-sample records (no committed output is read)."""
    import run_analysis as ra
    records = ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)[0]
    return [r for r in records if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] and r["hhi"] is not None
            and r["pyd_basis"] == "gross"]


def test_the_partition_before_and_after_the_repair_on_the_loaders_primary(loader_primary):
    """On the loader's 632 records: before the repair 570 are kept and 62 left out (20 whose figure no stored grid computes,
    42 with no figure at t-3); after it 588 are kept and 44 left out, all for want of a figure at t-3 (the 42 young books
    still, 1609/2023 whose first cohort is t-2, and 5678/2016 whose empty sum was a zero). 1609/2024 reproduces from its
    stored grid as labelled and its u <= t-3 figure is -11.123m USD."""
    with io.open(os.path.join(HERE, "data", "mature_cohort_figures.json"), encoding="utf-8") as fh:
        register = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    rows0, left0 = D.partition(loader_primary, register, cells=None)
    rows, left = D.partition(loader_primary, register)
    assert len(loader_primary) == 632 == len(rows0) + len(left0) == len(rows) + len(left)
    assert (len(rows0), len(left0)) == (570, 62) and (len(rows), len(left)) == (588, 44)
    assert sum(1 for x in left0 if x["reason"] == "figure_not_reproduced_from_a_stored_grid") == 20
    assert {x["reason"] for x in left} == {"no_figure_at_t_minus_3"}
    keys = {r["record"]: r for r in rows}
    out = {x["record"] for x in left}
    assert {"1609_2023", "5678_2016"} <= out and set(REGISTER_CELL_RECORDS) - {"1609_2023"} <= set(keys)
    assert sum(1 for r in rows if r["grid"].startswith("register:")) == 19
    assert keys["1609_2024"]["grid"].endswith(":_rag_triangle")
    import run_analysis as ra
    assert keys["1609_2024"]["figure_t_minus_3_gbp_m"] == pytest.approx(-11.123 / ra.FX_RATES[2024]["usd_per_gbp"], abs=1e-6)
    # the records that moved are exactly the repaired ones, plus 5678/2016 leaving
    moved = sorted(set(keys) - {r["record"] for r in rows0})
    assert moved == sorted(set(REGISTER_CELL_RECORDS) - {"1609_2023"}) and {r["record"] for r in rows0} - set(keys) == {"5678_2016"}
    rep = D.repair_report(rows, left, rows0, left0)
    assert sorted(x["record"] for x in rep) == sorted(set(REGISTER_CELL_RECORDS) | {"5678_2016"})
    by = {x["record"]: x for x in rep}
    assert by["5678_2016"]["before"] == "kept" and by["5678_2016"]["after"] == "no_figure_at_t_minus_3"
    assert by["1609_2023"]["before"] == "figure_not_reproduced_from_a_stored_grid" and by["1609_2023"]["after"] == "no_figure_at_t_minus_3"
    assert by["1274_2022"]["after"] == "kept" and by["1274_2022"]["source"].startswith("register:")
    summ = D.partition_summary(rows0, left0)
    assert summ["n_kept"] == 570 and summ["n_left_out"] == 62 and len(summ["left_out"]) == 62
    assert summ["left_out_by_reason"]["figure_not_reproduced_from_a_stored_grid"] == 20 


# ------------------------------------------------------------------ the sample and the cheap backtest ------
def test_the_sample_at_a_depth_takes_that_depths_severity_in_the_primarys_order():
    recs = [{"syndicate": 1, "year": 2016, "s_raw_a": 0.1}, {"syndicate": 2, "year": 2016, "s_raw_a": 0.2},
            {"syndicate": 3, "year": 2017, "s_raw_a": 0.3}]
    rows = [{"record": "3_2017", "severity_t_minus_2": 0.3, "severity_t_minus_3": 0.35},
            {"record": "1_2016", "severity_t_minus_2": 0.1, "severity_t_minus_3": 0.15}]
    deep = D.sample_at(recs, rows, "t_minus_3")
    assert [(o["syndicate"], o["s_raw_a"]) for o in deep] == [(1, 0.15), (3, 0.35)]
    assert [(o["syndicate"], o["s_raw_a"]) for o in D.sample_at(recs, rows, "t_minus_2")] == [(1, 0.1), (3, 0.3)]
    assert recs[0]["s_raw_a"] == 0.1, "the primary's observations are copied, not changed"


class _Post(dict):
    pass


class _Arr:
    def __init__(self, v):
        self.values = np.asarray(v, float)


class _Idata:
    def __init__(self, means):
        self.posterior = _Post({p: _Arr([m, m]) for p, m in means.items() if p != "gamma"})


def test_the_cheap_backtest_is_leave_one_syndicate_out_with_the_quartile_table():
    rng = np.random.default_rng(4)
    n = 24
    recs = [{"syndicate": 100 + i // 3, "year": 2015 + i % 3, "s_raw_a": float(rng.normal(0, 0.05)),
             "opening_reserves_gbp_m": float(np.exp(rng.normal(np.log(300), 0.8))), "hhi": float(rng.uniform(0.1, 0.5))}
            for i in range(n)]
    means = {"k": 0.6, "gamma": 0.0, "sd_undiv": 0.03, "sd_div": 0.05, "nu_clean": 4.0, "nu_ritc": 6.0}
    cfg = (500.0, 0.01, 1.0)
    out = D.cheap_backtest(recs, _Idata(means), cfg, levels=(0.9, 0.99))
    S, R, H, yr, key = CS.arrays(recs)
    syn = np.array([o["syndicate"] for o in recs])
    th = BT.operator_params(means)
    q = BT.leave_out_quantiles(S, R, H, CS.ritc_flag(key).astype(bool), syn, syn, yr, {s: th for s in set(syn.tolist())},
                               cfg, False, (0.9, 0.99))["operator_size_only"]
    for a in (0.9, 0.99):
        key_a = "%g" % a
        assert out["exceedances"][key_a] == int((S > q[a]).sum())
        tab = out["by_size_quartile"][key_a]
        assert sum(tab["size_quartile_%d" % j]["exceedances"] for j in (1, 2, 3, 4)) == out["exceedances"][key_a]
        assert out["expected"][key_a] == pytest.approx(n * (1 - a))
    assert "honest ten-fold version is not run" in out["version"] and out["n"] == n


def test_the_donor_pool_is_rounded_as_the_shipped_tool_rounds_its_donors():
    recs = [{"syndicate": 1084, "year": 2015, "s_raw_a": 0.0123456789012, "opening_reserves_gbp_m": 123.456789,
             "hhi": 0.3333339999}]
    (S, R, H, synd, year), ritc = D.donor_pool(recs)
    assert (S[0], R[0], H[0]) == (0.01234568, 123.46, 0.333334) and synd[0] == 1084 and year[0] == 2015 and len(ritc) == 1


# ------------------------------------------------------------------ the retry of a divergent full refit ------
def _diag(divergences=0, rhat=1.001):
    return {"divergences": divergences, "max_rhat": rhat, "min_ess_bulk": 900.0, "min_ess_tail": 900.0, "parameters": ["k"]}


class _Stub:
    """A stand-in for check_cohort_scope.fit: the n-th call returns a distinct sentinel 'idata' (named "idata-n",
    carrying the n-th diagnostics), so that a test can tell WHICH attempt's idata a figure was computed from."""

    def __init__(self, diags):
        self.diags, self.calls = list(diags), []

    def fit(self, S, R, H, yr, ritc, target_accept=0.98):
        self.calls.append(target_accept)
        n = len(self.calls)
        return None, {"name": "idata-%d" % n, "diag": self.diags[n - 1]}


def _diagnose(idata):
    return idata["diag"]


_ARGS = (np.zeros(3), np.ones(3), np.ones(3), np.zeros(3), np.zeros(3))


def _converging(stub, label="u <= t-3", figures=None):
    return D.converging_fit(*_ARGS, label, fit=stub.fit, diagnose=_diagnose, figures=figures)


def test_a_fit_that_converges_at_098_is_reported_at_098_and_not_retried():
    stub = _Stub([_diag(0)])
    seen = []
    idata, diag, attempts, ta = _converging(stub, figures=lambda i: seen.append(i) or {"x": 1})
    assert stub.calls == [0.98] and ta == 0.98 and diag == _diag(0) and idata["name"] == "idata-1"
    assert attempts == [{"target_accept": 0.98, "diagnostics": _diag(0), "converged": True, "reported": True}]
    assert seen == [], "nothing is discarded, so no figures are computed for a discarded attempt"


def test_a_divergent_fit_is_refitted_once_at_0995_and_reported_if_that_converges():
    stub = _Stub([_diag(1), _diag(0, 1.004)])
    idata, diag, attempts, ta = _converging(stub)
    assert stub.calls == [0.98, 0.995] and ta == 0.995
    assert diag == _diag(0, 1.004) == attempts[-1]["diagnostics"]
    assert [(a["target_accept"], a["converged"], a["diagnostics"]["divergences"]) for a in attempts] == [
        (0.98, False, 1), (0.995, True, 0)]


def test_the_retry_returns_the_converged_attempts_idata_with_its_diagnostics():
    """The idata returned is the SECOND attempt's, the one the diagnostics describe (a function returning the first
    attempt's idata with the second's diagnostics would pass the tests above and report a divergent fit's figures)."""
    stub = _Stub([_diag(1), _diag(0, 1.004)])
    idata, diag, attempts, ta = _converging(stub)
    assert idata["name"] == "idata-2" and idata["diag"] is diag


def test_a_discarded_attempt_keeps_the_figures_of_its_own_idata_and_is_marked_not_reported():
    stub = _Stub([_diag(1), _diag(0, 1.004)])
    seen = []

    def figures(idata):
        seen.append(idata["name"])
        return {"unrounded_summary": {"from": idata["name"]}, "vignette_centre": {"V1_v99": idata["name"]}}

    idata, diag, attempts, ta = _converging(stub, figures=figures)
    assert seen == ["idata-1"], "figures are computed once, for the discarded attempt only, from its own idata"
    assert [a["reported"] for a in attempts] == [False, True]
    assert attempts[0]["unrounded_summary"] == {"from": "idata-1"} and attempts[0]["vignette_centre"] == {"V1_v99": "idata-1"}
    assert "unrounded_summary" not in attempts[1] and "vignette_centre" not in attempts[1]
    assert attempts[0]["diagnostics"] == _diag(1) and attempts[1]["diagnostics"] == _diag(0, 1.004)


def test_the_full_refit_reports_every_figure_from_the_converged_attempts_idata(monkeypatch):
    """fit_and_transfer's summary, operator draws, centres, intervals and cheap backtest are all computed from the
    converged attempt's idata; the discarded attempt's idata reaches only its own record in fit_attempts."""
    recs = [{"syndicate": 100 + i, "year": 2015, "s_raw_a": 0.01 * i, "opening_reserves_gbp_m": 100.0 + i, "hhi": 0.3}
            for i in range(4)]
    cen = ("V1_v99", "V1_v995", "V2_old_v99", "V2_old_v995", "V2_new_v99", "V2_new_v995", "V2_d995")
    calls = {"summary": [], "draws": [], "backtest": [], "centres": [], "vignettes": []}

    def summary(idata):
        calls["summary"].append(idata["name"])
        return {"k": {"mean": idata["name"]}}

    def draws(idata):
        calls["draws"].append(idata["name"])
        return ("draws", idata["name"])

    def centres(d, pool, ritc, cfg):
        calls["centres"].append(d[1])
        return {q: d[1] for q in cen}

    def vignettes(d, pool, ritc, cfg, recorded):
        calls["vignettes"].append(d[1])
        return {"centre": {q: d[1] for q in cen}, "intervals": {"from": d[1]}}

    def backtest(recs_, idata, cfg):
        calls["backtest"].append(idata["name"])
        return {"from": idata["name"]}

    monkeypatch.setattr(SS, "unrounded_summary", summary)
    monkeypatch.setattr(RV, "operator_draws", draws)
    monkeypatch.setattr(SS, "centres_all", centres)
    monkeypatch.setattr(RV, "vignettes", vignettes)
    monkeypatch.setattr(D, "cheap_backtest", backtest)
    monkeypatch.setattr(D, "donor_pool", lambda r: ((np.zeros(1),) * 5, np.zeros(1)))
    stub = _Stub([_diag(2), _diag(0, 1.003)])
    out = D.fit_and_transfer(recs, "u <= t-3", {}, (500.0, 0.01, 1.0), fit=stub.fit, diagnose=_diagnose)
    assert stub.calls == [0.98, 0.995] and out["fit_target_accept"] == 0.995
    # the reported figures: the second attempt's
    assert out["fit"] == {"k": {"mean": "idata-2"}}
    assert out["vignettes"]["centre"] == {q: "idata-2" for q in cen}
    assert out["vignettes"]["intervals"] == {"from": "idata-2"}
    assert out["operator_backtest_by_size_quartile"] == {"from": "idata-2"}
    assert calls["vignettes"] == ["idata-2"] and calls["backtest"] == ["idata-2"]
    assert out["fit_convergence"] == _diag(0, 1.003)
    # the first attempt's idata is used only for its own entry in fit_attempts
    first, second = out["fit_attempts"]
    assert (first["reported"], second["reported"]) == (False, True)
    assert first["unrounded_summary"] == {"k": {"mean": "idata-1"}}
    assert first["vignette_centre"] == {q: "idata-1" for q in cen}
    assert first["diagnostics"] == _diag(2) and second["diagnostics"] == _diag(0, 1.003)
    assert sorted(calls["summary"]) == ["idata-1", "idata-2"] and sorted(calls["draws"]) == ["idata-1", "idata-2"]


def test_a_fit_that_diverges_twice_stops_and_names_both_attempts():
    stub = _Stub([_diag(1), _diag(2)])
    with pytest.raises(SystemExit) as e:
        _converging(stub)
    assert stub.calls == [0.98, 0.995]
    msg = str(e.value)
    assert "has not converged" in msg and "target_accept 0.98" in msg and "target_accept 0.995" in msg
    assert "'divergences': 1" in msg and "'divergences': 2" in msg and "no figures are written" in msg


def test_the_retry_fit_must_pass_the_same_rule_not_only_have_no_divergence():
    """A retry with no divergence but an R-hat above 1.01 is not reported."""
    stub = _Stub([_diag(1), _diag(0, 1.02)])
    with pytest.raises(SystemExit):
        _converging(stub)
    assert stub.calls == [0.98, 0.995]


def test_an_rhat_failure_without_a_divergence_is_not_retried():
    stub = _Stub([_diag(0, 1.05), _diag(0)])
    with pytest.raises(SystemExit):
        _converging(stub)
    assert stub.calls == [0.98]


def test_the_full_refits_go_through_the_retry_and_keep_both_attempts():
    """fit_and_transfer takes its fit from converging_fit, and passes the stubbed fit down."""
    recs = [{"syndicate": 100 + i, "year": 2015, "s_raw_a": 0.01 * i, "opening_reserves_gbp_m": 100.0 + i, "hhi": 0.3}
            for i in range(4)]
    stub = _Stub([_diag(1), _diag(3)])
    with pytest.raises(SystemExit) as e:
        D.fit_and_transfer(recs, "u <= t-3", {}, (500.0, 0.01, 1.0), fit=stub.fit, diagnose=_diagnose)
    assert stub.calls == [0.98, 0.995] and "u <= t-3 fit has not converged" in str(e.value)


class _Stop(Exception):
    pass


def test_check_cohort_scope_fit_takes_target_accept_with_the_headlines_as_its_default(monkeypatch):
    seen = []

    def sample(*a, **kw):
        seen.append(kw)
        raise _Stop

    monkeypatch.setattr(CS.pm, "sample", sample)
    S, R, H, yr = np.array([0.01, -0.02, 0.0, 0.03]), np.full(4, 100.0), np.full(4, 0.3), np.array([2015, 2015, 2016, 2016])
    for kw in ({}, {"target_accept": 0.995}):
        with pytest.raises(_Stop):
            CS.fit(S, R, H, yr, np.zeros(4), **kw)
    assert [s["target_accept"] for s in seen] == [0.98, 0.995]
    assert seen[0]["random_seed"] == seen[1]["random_seed"] == CS.SEED
    assert {k: v for k, v in seen[0].items() if k != "target_accept"} == {k: v for k, v in seen[1].items() if k != "target_accept"}


# ------------------------------------------------------------------ the committed record (DEFERRED-TO-REFIT) ------
@pytest.fixture(scope="module")
def rec():
    with io.open(os.path.join(HERE, "results", "check_cohort_depth_sensitivity_results.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_the_record_counts_every_primary_record_and_every_reason(rec):
    # 643 primary records = 581 kept + 62 left out at the recorded pass of 38cd750 (649 = 592 + 57 before the round-5
    # adjudication and review 8's decisions; see test_the_partition_covers_every_primary_record_once_on_the_real_corpus)
    # Re-pinned on 26 October 2026 to the record regenerated at f15a357f (rule 8 took the census's 11 records out of the
    # primary: 632): 588 kept + 44 left out. The record's own partition_before_repair (the script without the cohort-depth
    # repair of b04812d3) is 570 kept + 62 left out; the repair keeps 19 of the 20 records whose stored grid does not
    # reproduce their figure (from their register cells), sends 1609/2023 (no cohort at t-3) to "no figure at t-3", and
    # sends 5678/2016 there too (its older-cohort sum is empty; it was kept on a zero): 570 + 19 - 1 = 588.
    assert rec["n_primary"] == 632 == rec["n_kept"] + rec["n_left_out"] == len(rec["records"]) + len(rec["left_out"])
    assert (rec["n_kept"], rec["n_left_out"]) == (588, 44)
    assert rec["lags"] == {"primary": 2, "sensitivity": 3} and rec["operator"] == "size_only"
    assert sum(rec["left_out_by_reason"].values()) == rec["n_left_out"]
    assert set(rec["left_out_by_reason"]) == set(D.REASONS)
    for r in D.REASONS:
        assert rec["left_out_by_reason"][r] == sum(1 for x in rec["left_out"] if x["reason"] == r)
    keys = [r["record"] for r in rec["records"]] + [x["record"] for x in rec["left_out"]]
    assert len(keys) == len(set(keys)) == 632
    assert set(keys) == {CS.key_of(o) for o in SS.primary()}
    assert sum(rec["grids_used"].values()) == rec["n_kept"]
    # both honest backtests are run, on the same kept records (test_cohort_depth_honest_backtest.py): nothing is left to run
    assert rec["not_run"] == []
    assert {"honest_backtest_t_minus_3", "honest_backtest_t_minus_2_on_the_kept_records",
            "honest_t_minus_2_vs_t_minus_3", "left_out_by_primary_size_quartile"} <= set(rec)


def test_the_record_fits_both_samples_on_the_kept_records_and_both_converged(rec):
    for blk in (rec["kept_records_at_t_minus_2"], rec["cohort_depth_t_minus_3"]):
        assert blk["sample"]["n"] == rec["n_kept"]
        assert blk["fit_convergence"]["divergences"] == 0 and blk["fit_convergence"]["max_rhat"] <= 1.01
        # both attempts are kept; the reported figures come from the last, converged one, at the target_accept it names
        att = blk["fit_attempts"]
        assert 1 <= len(att) <= 2 and [a["target_accept"] for a in att] == [0.98, 0.995][:len(att)]
        assert all(not a["converged"] and a["diagnostics"]["divergences"] > 0 for a in att[:-1])
        assert att[-1]["converged"] and att[-1]["diagnostics"] == blk["fit_convergence"] and att[-1]["reported"] is True
        # an attempt that was discarded keeps what it would have reported, from its own draws
        for a in att[:-1]:
            assert a["reported"] is False and set(SS.VARS) <= set(a["unrounded_summary"])
            assert {"V1_v99", "V1_v995", "V2_old_v99", "V2_old_v995", "V2_new_v99", "V2_new_v995",
                    "V2_d995"} <= set(a["vignette_centre"])
            assert a["unrounded_summary"] != blk["fit"] and a["vignette_centre"] != blk["vignettes"]["centre"]
        assert blk["fit_target_accept"] == att[-1]["target_accept"]
        assert set(SS.VARS) <= set(blk["fit"]) and 0.5 < blk["fit"]["k"]["mean"] < 1.0
        assert blk["vignettes"]["pool"]["n_donors"] == rec["n_kept"]
        for q in ("V1_v99", "V1_v995", "V2_old_v99", "V2_old_v995", "V2_new_v99", "V2_new_v995", "V2_d995"):
            assert blk["vignettes"]["centre"][q] == blk["vignettes"]["centre"][q] and blk["vignettes"]["centre"][q] is not None
    deep = rec["cohort_depth_t_minus_3"]
    for q, v in deep["relative_to_primary"].items():
        assert v == pytest.approx(deep["vignettes"]["centre"][q] / rec["primary"]["vignette_centre"][q] - 1.0)
    assert deep["sample"]["severity"]["mean"] != rec["kept_records_at_t_minus_2"]["sample"]["severity"]["mean"]
    assert rec["severity_change_t_minus_3_minus_t_minus_2"]["n_changed"] > rec["n_kept"] // 2


def test_the_records_depth_three_figures_are_the_estimators_at_depth_three(rec, fns):
    """Three kept records recomputed from their stored grids at depth 3 equal the record's figures and severities."""
    _, fn3 = fns
    by = {r["record"]: r for r in rec["records"]}
    for key in ("1084_2015", "2012_2015", "4141_2018"):
        row = by[key]
        model, fld = row["grid"].split(":")
        grid = _data(key)["models"][model][fld]
        fig, why = D.at_depth(key, grid, fn3)
        assert fig == row["figure_t_minus_3_gbp_m"] and why is None
        assert row["severity_t_minus_3"] == fig / row["opening_reserves_gbp_m"]


def test_the_records_cheap_backtest_tables_add_up(rec):
    for blk in (rec["kept_records_at_t_minus_2"], rec["cohort_depth_t_minus_3"]):
        bt = blk["operator_backtest_by_size_quartile"]
        assert bt["n"] == rec["n_kept"] and "honest ten-fold version is not run" in bt["version"]
        for a in ("0.99", "0.995"):
            tab = bt["by_size_quartile"][a]
            assert sum(tab["size_quartile_%d" % j]["n_targets"] for j in (1, 2, 3, 4)) == rec["n_kept"]
            assert sum(tab["size_quartile_%d" % j]["exceedances"] for j in (1, 2, 3, 4)) == bt["exceedances"][a]
            assert bt["expected"][a] == pytest.approx(rec["n_kept"] * (1 - float(a)))
            for j in (1, 2, 3, 4):
                row = tab["size_quartile_%d" % j]
                lo, hi = row["rate_credible_interval_95"]
                assert lo <= row["rate_mean"] <= hi and row["n_syndicates_with_exceedances"] <= max(row["exceedances"], 0)


def test_the_run_time_sits_under_the_key_the_verifier_strips(rec):
    import reproduce
    assert "runtime_seconds" in reproduce.VOLATILE and "runtime_seconds" not in reproduce._strip_volatile(rec)
    assert reproduce.OUTPUTS["check_cohort_depth_sensitivity.py"] == ("results/check_cohort_depth_sensitivity_results.json",)
    assert any(s[0] == "check_cohort_depth_sensitivity.py" for s in reproduce.STEPS)
