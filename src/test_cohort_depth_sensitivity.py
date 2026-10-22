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
import sample_scope as SS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _extraction_available():
    import record_tests
    root = bm.extraction_root()
    r = subprocess.run(["git", "-C", root, "cat-file", "-e", "%s:test_gemini.py" % record_tests.extraction_pin()],
                       capture_output=True)
    return r.returncode == 0


pytestmark = pytest.mark.skipif(not _extraction_available(),
                                reason="the extraction checkout at the pinned commit is not available (set "
                                       "LLOYDS_EXTRACTION_REPO): the estimator is read from it")


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
    register = {k: v for k, v in json.load(io.open(os.path.join(HERE, "data", "mature_cohort_figures.json"),
                                                   encoding="utf-8")).items() if not k.startswith("_")}
    rows, left = D.partition(recs, register)
    keys = [CS.key_of(o) for o in recs]
    kept, out = [r["record"] for r in rows], [x["record"] for x in left]
    assert len(rows) + len(left) == len(recs) == 649
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


# ------------------------------------------------------------------ the committed record (DEFERRED-TO-REFIT) ------
@pytest.fixture(scope="module")
def rec():
    with io.open(os.path.join(HERE, "results", "check_cohort_depth_sensitivity_results.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_the_record_counts_every_primary_record_and_every_reason(rec):
    assert rec["n_primary"] == 649 == rec["n_kept"] + rec["n_left_out"] == len(rec["records"]) + len(rec["left_out"])
    assert rec["lags"] == {"primary": 2, "sensitivity": 3} and rec["operator"] == "size_only"
    assert sum(rec["left_out_by_reason"].values()) == rec["n_left_out"]
    assert set(rec["left_out_by_reason"]) == set(D.REASONS)
    for r in D.REASONS:
        assert rec["left_out_by_reason"][r] == sum(1 for x in rec["left_out"] if x["reason"] == r)
    keys = [r["record"] for r in rec["records"]] + [x["record"] for x in rec["left_out"]]
    assert len(keys) == len(set(keys)) == 649
    assert set(keys) == {CS.key_of(o) for o in SS.primary()}
    assert sum(rec["grids_used"].values()) == rec["n_kept"]
    assert rec["not_run"] and "honest ten-fold" in rec["not_run"][0]


def test_the_record_fits_both_samples_on_the_kept_records_and_both_converged(rec):
    for blk in (rec["kept_records_at_t_minus_2"], rec["cohort_depth_t_minus_3"]):
        assert blk["sample"]["n"] == rec["n_kept"]
        assert blk["fit_convergence"]["divergences"] == 0 and blk["fit_convergence"]["max_rhat"] <= 1.01
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
