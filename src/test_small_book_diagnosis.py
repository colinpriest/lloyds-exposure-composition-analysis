#!/usr/bin/env python3
"""The small-book diagnosis (check_small_book_diagnosis.py): calibration by size band from the backtest's per-target flags.

No fit runs here. A small synthetic sample stands in for the primary, and a backtest record is built from it with the
backtest's own scoring function, so that the producer's checks run against a record that is right and against records
that are not:

  * the bands: the fixed original cutoffs are the three given numbers; a book at a cutoff falls in the band above it
    (np.searchsorted side="right", the backtest's rule); the primary's own quartiles are recomputed from its reserves and
    are a different grouping from the fixed bands, with the same flags counted in both;
  * a band's row: targets, distinct syndicates, exceedances, expected count, rate, event syndicates and event record
    ids, from a toy flag vector;
  * the thresholds: recomputed from the fold fits' stored means, equal to the function the backtest itself calls; the
    smallest band's events carry them under both pool rules;
  * the record against the sample: a flag that does not reproduce, a record on other books or in another order, or
    size quartiles that are not the primary's own stop the run;
  * the cross-check against the prototype is labelled and does not stand in for a result.

Run:  python -m pytest src/test_small_book_diagnosis.py -q
"""
import copy
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

import check_operator_backtest as BT  # noqa: E402
import check_small_book_diagnosis as SB  # noqa: E402

CFG = (500.0, 0.01, 1.0)
YEARS = (2018, 2019, 2020, 2021, 2022)
MEANS = {"k": 0.6, "sd_undiv": 0.03, "sd_div": 0.05, "nu_clean": 4.0, "nu_ritc": 6.0, "lambda_ritc": 0.1,
         "beta_ritc": 0.1, "tau_s": 0.1}


def sample(n_syn=12):
    """(S, R, H, yr, syn, ritc): 12 syndicates of five years; the smallest syndicate's years are severe, so the smallest
    band holds events."""
    rng = np.random.default_rng(11)
    syn = np.repeat(np.arange(1001, 1001 + n_syn), len(YEARS))
    yr = np.tile(np.array(YEARS), n_syn)
    n = len(syn)
    R = np.repeat(np.linspace(40.0, 1500.0, n_syn), len(YEARS)) * rng.uniform(0.9, 1.1, n)
    H = rng.uniform(0.15, 0.6, n)
    S = rng.standard_t(4, n) * 0.05
    S[syn == 1001] += np.array([0.9, 0.7, 0.05, 0.6, 0.0])
    ritc = np.zeros(n, bool)
    ritc[::9] = True
    return S, R, H, yr, syn, ritc


def theta_of(fold):
    m = {p: v + 0.004 * fold if p == "k" else v for p, v in MEANS.items()}
    return {**m, "gamma": 0.0}


def backtest_record(S, R, H, yr, syn, ritc, draws_flag_rate=0.04):
    """A backtest record on the sample: plug-in flags from BT.leave_out_quantiles at hand-built thetas, draw-version
    flags from a fixed random draw, the fold fits' means, the targets and the own quartiles."""
    folds = BT.fold_assignment(syn, 10)
    thetas = {f: BT.operator_params({p: theta_of(f)[p] for p in BT.OPERATOR_PARAMS}) for f in range(10)}
    rng = np.random.default_rng(3)
    flags = {"honest_plug_in": {}, "honest_posterior_draws": {}}
    for rule, drop in (("leave_out", False), ("leave_out_and_target_year", True)):
        q = BT.leave_out_quantiles(S, R, H, ritc, folds, syn, yr, thetas, CFG, drop, SB.LEVELS)[BT.OPERATOR_METHOD]
        flags["honest_plug_in"][rule] = {SB.level_key(a): (S > q[a]).astype(int).tolist() for a in SB.LEVELS}
        flags["honest_posterior_draws"][rule] = {SB.level_key(a): (rng.random(len(S)) < draws_flag_rate).astype(int)
                                                 .tolist() for a in SB.LEVELS}
    edges = SB.own_edges(R)
    return {
        "n": int(len(S)), "size_quartiles": {"edges_gbp_m": list(edges)},
        "honest": {"folds": 10, "fits": [{"fold": f, "params": {p: {"mean": theta_of(f)[p]} for p in MEANS}}
                                         for f in range(10)]},
        "per_target": {"targets": {"syndicate": syn.tolist(), "year": yr.tolist(), "R_gbp_m": R.tolist(),
                                   "size_quartile": SB.band_of(R, edges).tolist(), "ritc": ritc.astype(int).tolist()},
                       "exceedance_flags": flags}}


@pytest.fixture(scope="module")
def fixture():
    S, R, H, yr, syn, ritc = sample()
    return {"arrays": (S, R, H, yr, syn, ritc), "rec": backtest_record(S, R, H, yr, syn, ritc)}


def run(fixture, rec=None, fixed=None):
    S, R, H, yr, syn, ritc = fixture["arrays"]
    return SB.compute(fixture["rec"] if rec is None else rec, S, R, H, yr, syn, ritc, CFG,
                      fixed_edges=SB.FIXED_BAND_EDGES if fixed is None else fixed)


# ------------------------------------------------------------------------------------------------ the bands
def test_the_fixed_original_cutoffs_are_the_three_given_numbers():
    assert SB.FIXED_BAND_EDGES == (172.5745, 425.362, 837.0151141803343)
    assert SB.LEVELS == (0.99, 0.995)
    assert set(SB.RULES) == {"leave_out", "leave_out_and_target_year"}


def test_a_book_at_a_cutoff_falls_in_the_band_above_it():
    R = np.array([172.5744, 172.5745, 425.361, 425.362, 837.0151141803342, 837.0151141803343, 5000.0])
    assert SB.band_of(R, SB.FIXED_BAND_EDGES).tolist() == [1, 2, 2, 3, 3, 4, 4]


def test_the_own_quartiles_are_recomputed_from_the_reserves():
    R = np.arange(1.0, 101.0)
    assert SB.own_edges(R) == tuple(np.quantile(R, [0.25, 0.5, 0.75]))
    # a different sample has different own quartiles, and the fixed cutoffs do not move with it
    assert SB.own_edges(R * 2.0) != SB.own_edges(R)
    assert SB.FIXED_BAND_EDGES == (172.5745, 425.362, 837.0151141803343)


def test_a_bands_row_from_a_toy_flag_vector():
    syn = np.array([1, 1, 2, 2, 3, 3, 4, 4])
    yr = np.array([2018, 2019, 2018, 2019, 2018, 2019, 2018, 2019])
    flags = np.array([1, 1, 0, 1, 0, 0, 1, 0], bool)
    bands = np.array([1, 1, 1, 1, 2, 2, 2, 2])
    t = SB.band_table(flags, bands, syn, yr, 0.99)
    b1, b2 = t["band_1"], t["band_2"]
    assert (b1["n_targets"], b1["n_syndicates"], b1["exceedances"]) == (4, 2, 3)
    assert b1["expected"] == pytest.approx(0.04) and b1["rate"] == pytest.approx(0.75)
    assert b1["event_syndicates"] == [1, 2] and b1["n_event_syndicates"] == 2
    assert b1["event_record_ids"] == ["1_2018", "1_2019", "2_2019"]
    assert (b2["n_targets"], b2["exceedances"], b2["event_record_ids"]) == (4, 1, ["4_2018"])
    assert t["band_3"]["n_targets"] == 0 and t["band_3"]["rate"] is None and t["band_3"]["event_record_ids"] == []
    assert b1["nominal_rate"] == pytest.approx(0.01)


# --------------------------------------------------------------------------------------------------- the record
def test_the_record_counts_the_stored_flags_in_both_groupings(fixture):
    S, R, H, yr, syn, ritc = fixture["arrays"]
    out = run(fixture)
    flags = fixture["rec"]["per_target"]["exceedance_flags"]["honest_plug_in"]["leave_out"]
    own = SB.band_of(R, SB.own_edges(R))
    fixed = SB.band_of(R, SB.FIXED_BAND_EDGES)
    for a in SB.LEVELS:
        f = np.asarray(flags[SB.level_key(a)], bool)
        row_own = out["versions"]["honest_plug_in"]["pool_rules"]["leave_out"]["own_quartiles"][SB.level_key(a)]
        row_fix = out["versions"]["honest_plug_in"]["pool_rules"]["leave_out"]["fixed_original_bands"][SB.level_key(a)]
        for j in range(1, 5):
            assert row_own["band_%d" % j]["n_targets"] == int((own == j).sum())
            assert row_own["band_%d" % j]["exceedances"] == int((f & (own == j)).sum())
            assert row_fix["band_%d" % j]["n_targets"] == int((fixed == j).sum())
            assert row_fix["band_%d" % j]["exceedances"] == int((f & (fixed == j)).sum())
    # the groupings are different groupings, kept under separate labels, and the sample is split differently
    assert out["groupings"]["own_quartiles"]["edges_gbp_m"] != out["groupings"]["fixed_original_bands"]["edges_gbp_m"]
    assert out["groupings"]["fixed_original_bands"]["edges_gbp_m"] == list(SB.FIXED_BAND_EDGES)
    assert out["groupings"]["own_quartiles"]["counts"] != out["groupings"]["fixed_original_bands"]["counts"]


def test_the_two_groupings_count_the_same_flags_and_differ_in_who_is_in_the_smallest_band(fixture):
    """The regrouping moves books across a cutoff and changes denominators; it never changes a flag."""
    S, R, H, yr, syn, ritc = fixture["arrays"]
    # a fixed cutoff chosen so that exactly one book sits between it and the own first-quartile boundary
    own1 = SB.own_edges(R)[0]
    between = np.sort(R[(R < own1)])[-1]
    fixed = (float(between), SB.own_edges(R)[1], SB.own_edges(R)[2])
    out = run(fixture, fixed=fixed)
    only_own = out["regrouping"]["in_own_quartile_1_not_fixed_band_1"]
    assert [x["R_gbp_m"] for x in only_own] == [float(between)]
    assert out["regrouping"]["in_fixed_band_1_not_own_quartile_1"] == []
    f = np.asarray(fixture["rec"]["per_target"]["exceedance_flags"]["honest_plug_in"]["leave_out"]["0.995"], bool)
    total = lambda t: sum(t["band_%d" % j]["exceedances"] for j in range(1, 5))     # noqa: E731
    a = out["versions"]["honest_plug_in"]["pool_rules"]["leave_out"]
    assert total(a["own_quartiles"]["0.995"]) == total(a["fixed_original_bands"]["0.995"]) == int(f.sum())


def test_the_thresholds_are_the_backtests_own_and_ride_with_the_smallest_bands_events(fixture):
    S, R, H, yr, syn, ritc = fixture["arrays"]
    out = run(fixture)
    folds = BT.fold_assignment(syn, 10)
    thetas = {f: BT.operator_params({p: theta_of(f)[p] for p in BT.OPERATOR_PARAMS}) for f in range(10)}
    for rule, drop in (("leave_out", False), ("leave_out_and_target_year", True)):
        q = BT.leave_out_quantiles(S, R, H, ritc, folds, syn, yr, thetas, CFG, drop, SB.LEVELS)[BT.OPERATOR_METHOD]
        for a in SB.LEVELS:
            for ev in out["smallest_band_events"][SB.level_key(a)]["own_quartile_1"]:
                i = [k for k in range(len(S)) if "%s_%s" % (syn[k], yr[k]) == ev["record_id"]][0]
                assert ev["thresholds"][rule]["threshold"] == float(q[a][i])
                assert ev["observed_S"] == float(S[i])
    # the fixture has events in the smallest band, so this test is not vacuous
    assert out["smallest_band_events"]["0.99"]["own_quartile_1"]
    # every listed event is an event of the stored flags, and every stored event of the band is listed
    flags = np.asarray(fixture["rec"]["per_target"]["exceedance_flags"]["honest_plug_in"]["leave_out"]["0.99"], bool)
    band1 = SB.band_of(R, SB.own_edges(R)) == 1
    assert sorted(e["record_id"] for e in out["smallest_band_events"]["0.99"]["own_quartile_1"]) == sorted(
        "%s_%s" % (s, y) for s, y in zip(syn[flags & band1], yr[flags & band1]))


def test_the_draw_versions_flags_are_counted_and_its_thresholds_are_said_to_be_unavailable(fixture):
    out = run(fixture)
    v = out["versions"]["honest_posterior_draws"]
    assert "not available" in v["thresholds"]
    flags = np.asarray(fixture["rec"]["per_target"]["exceedance_flags"]["honest_posterior_draws"]["leave_out"]["0.99"])
    rows = v["pool_rules"]["leave_out"]["own_quartiles"]["0.99"]
    assert sum(rows["band_%d" % j]["exceedances"] for j in range(1, 5)) == int(flags.sum())


def test_the_stamp_and_the_headline_operator(fixture):
    out = run(fixture)
    assert (out["operator"], out["operator_role"]) == ("size_only", "headline")
    assert out["levels"] == ["0.99", "0.995"]


# ------------------------------------------------------------------ the record against the sample: stop, not guess
def test_a_flag_that_does_not_reproduce_stops_the_run(fixture):
    rec = copy.deepcopy(fixture["rec"])
    flags = rec["per_target"]["exceedance_flags"]["honest_plug_in"]["leave_out"]["0.995"]
    flags[7] = 1 - flags[7]
    with pytest.raises(SystemExit, match="differ from the record's"):
        run(fixture, rec=rec)


def test_a_flag_that_differs_only_under_the_target_year_rule_stops_the_run(fixture):
    rec = copy.deepcopy(fixture["rec"])
    flags = rec["per_target"]["exceedance_flags"]["honest_plug_in"]["leave_out_and_target_year"]["0.99"]
    flags[11] = 1 - flags[11]
    with pytest.raises(SystemExit, match="leave_out_and_target_year"):
        run(fixture, rec=rec)


def test_a_record_on_other_books_stops_the_run(fixture):
    rec = copy.deepcopy(fixture["rec"])
    rec["per_target"]["targets"]["R_gbp_m"][3] += 1.0
    with pytest.raises(SystemExit, match="opening reserves differ"):
        run(fixture, rec=rec)


def test_a_record_in_another_order_stops_the_run(fixture):
    rec = copy.deepcopy(fixture["rec"])
    t = rec["per_target"]["targets"]
    for k in t:
        t[k][0], t[k][1] = t[k][1], t[k][0]
    with pytest.raises(SystemExit, match="not on the loader's working sample"):
        run(fixture, rec=rec)


def test_a_record_with_a_different_count_stops_the_run(fixture):
    rec = copy.deepcopy(fixture["rec"])
    rec["n"] = rec["n"] - 1
    with pytest.raises(SystemExit, match="scores"):
        run(fixture, rec=rec)


def test_a_record_whose_quartile_edges_are_not_the_primarys_own_stops_the_run(fixture):
    rec = copy.deepcopy(fixture["rec"])
    rec["size_quartiles"]["edges_gbp_m"][0] += 1.0
    with pytest.raises(SystemExit, match="edges"):
        run(fixture, rec=rec)


# ------------------------------------------------------------------------------------------- the cross-check
def test_the_prototype_is_a_labelled_cross_check_and_does_not_set_a_result(fixture):
    out = run(fixture)
    cross = out["codex_prototype_cross_check"]
    assert "cross-check" in cross["reference"]["label"] and "recommendation of the Codex analysis" in cross["reference"]["label"]
    assert cross["expected_to_differ"]
    assert cross["same_counts_as_prototype"] is False
    # the prototype's numbers are not in the result tables
    assert cross["reference"]["own_quartile_1"]["0.995"] == [6, 161]
    assert out["versions"]["honest_plug_in"]["pool_rules"]["leave_out"]["own_quartiles"]["0.995"]["band_1"][
        "n_targets"] != 161


def test_the_events_of_one_syndicate_are_not_independent_firms(fixture):
    out = run(fixture)
    band = out["versions"]["honest_plug_in"]["pool_rules"]["leave_out"]["own_quartiles"]["0.99"]["band_1"]
    assert band["exceedances"] > band["n_event_syndicates"] >= 1
    assert "repeated outcomes" in out["note"]
