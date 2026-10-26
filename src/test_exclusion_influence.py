#!/usr/bin/env python3
"""The influence sensitivities (check_exclusion_influence.py), without a real fit.

A small synthetic base stands in for the included-data comparison, and a stand-in for the fitter (no sampler runs)
returns fits with known parameters, so the machinery around the fits is held to hand-computed cases:

  * the masks: the primary is the base without the rule-8 set-aside records, the included-data comparison is the base,
    the third population is the primary without every Syndicate 1991 record; they nest, and a set-aside record is in the
    comparison only;
  * the folds are never redealt: each population takes the base map restricted to its syndicates, which differs from the
    map a fresh deal on that population's syndicates would give (the fixture is built so that it does);
  * the size bands are the fixed ones: the base must reproduce them from its own quartiles, and a population is scored
    against them and not against its own;
  * the fits: 3 populations x (1 full + 10 folds) = 33 tasks, each fold's training rows the rows of every other fold; the
    retry rule (0.98, then 0.995 once, both recorded, stop if the second does not converge);
  * the plug-in backtest on the rebuilt pools, and the common-target comparison: the targets present in every
    population, each origin's own forecasts, and the paired per-row differences taken before weighting, so that identical
    forecasts give exactly zero (a toy case worked by hand);
  * Vignette 1 per population: the centre and the cutpoint donor on the shipped precision, the interval's seed and B;
  * the real loader builds the base: 643 records from 118 syndicates, the 11 set-aside records among them, the register
    put back afterwards.

Run:  python -m pytest src/test_exclusion_influence.py -q
"""
import io
import json
import os
import sys
from unittest import mock

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

import check_cohort_scope as CS  # noqa: E402
import check_exclusion_influence as EI  # noqa: E402
import check_operator_backtest as BT  # noqa: E402
import check_small_book_diagnosis as SB  # noqa: E402
import transfer_operator as TO  # noqa: E402
from oos_validation import fold_assignment  # noqa: E402
from pool_quantile import var_q  # noqa: E402
from vignette_uncertainty import transfer  # noqa: E402

CFG = (500.0, 0.01, 1.0)
TARGET = (500.0, 0.17)
MEANS = {"k": 0.6, "sd_undiv": 0.03, "sd_div": 0.05, "nu_clean": 4.0, "nu_ritc": 6.0, "lambda_ritc": 0.1,
         "beta_ritc": 0.1, "tau_s": 0.1}
# syndicate 1100 (the analogue of 2008) leaves with its two records; 2200_2020 leaves too; 1991 is in every other population
SYNDICATES = sorted([1100, 1991] + [1200 + 100 * i for i in range(22)])
SET_ASIDE = ["1100_2019", "1100_2020", "2200_2021"]
RITC_KEYS = {"1300_2020", "1300_2021", "2100_2022", "2200_2021"}
YEARS = (2019, 2020, 2021, 2022)


def records():
    rng = np.random.default_rng(5)
    recs = []
    for s in SYNDICATES:
        years = (2019, 2020) if s == 1100 else YEARS
        base = 30.0 + 60.0 * SYNDICATES.index(s)
        for y in years:
            recs.append({"syndicate": s, "year": y, "opening_reserves_gbp_m": round(base * rng.uniform(0.8, 1.2), 4),
                         "hhi": float(rng.uniform(0.15, 0.6)),
                         "s_raw_a": float(rng.standard_t(4) * 0.05 + (0.4 if s == 1991 and y in (2019, 2020) else 0.0))})
    return recs


def frame():
    with mock.patch.object(CS.assumed_business, "keys", return_value=RITC_KEYS):
        return EI.build_frame(records(), SET_ASIDE)


def edges_of(fr):
    return tuple(float(e) for e in np.quantile(fr["R"], [0.25, 0.5, 0.75]))


def stub_result(task, target_accept=0.98, divergences=0):
    name, tag, S, R, H, yr, syn, ritc, train = task
    rng = np.random.default_rng(len(name) * 1000 + len(tag) * 7 + int(train.sum()))
    draws = {p: v * (1.0 + 0.01 * rng.standard_normal((4, 50))) for p, v in MEANS.items()}
    return {"population": name, "tag": tag, "n_train": int(train.sum()), "n_held_out": int((~train).sum()),
            "n_train_syndicates": int(len(set(syn[train].tolist()))),
            "n_held_out_syndicates": int(len(set(syn[~train].tolist()))),
            "params": {p: {"mean": float(draws[p].mean()), "sd": float(draws[p].std()), "hdi_2.5": float(draws[p].min()),
                           "hdi_97.5": float(draws[p].max())} for p in MEANS},
            "means": {**{p: float(draws[p].mean()) for p in BT.OPERATOR_PARAMS if p in draws}, "gamma": 0.0},
            "draws": draws, "diagnostics": {"max_rhat": 1.001, "min_ess_bulk": 1500.0, "divergences": divergences},
            "seconds": 0.0}


def stub_fitter(task):
    f = stub_result(task)
    return {**f, "target_accept": 0.98, "attempts": [{"target_accept": 0.98, "diagnostics": f["diagnostics"],
                                                      "converged": True, "reported": True}]}


@pytest.fixture(scope="module")
def run():
    fr = frame()
    record, arrays = EI.compute(fr, CFG, TARGET, fitter=stub_fitter, workers=1, edges=edges_of(fr), b=40, reps=60)
    return {"frame": fr, "record": record, "arrays": arrays}


# ---------------------------------------------------------------------------------------------------- the masks
def test_the_three_populations_are_declared_masks_over_the_base():
    fr = frame()
    m = EI.population_masks(fr)
    assert list(m) == ["primary", "included_data_643", "primary_without_1991"]
    keys, syn = fr["key"], fr["syn"]
    assert len(keys) == 94 and m["included_data_643"].all()
    assert set(keys[~m["primary"]]) == set(SET_ASIDE)
    assert int(m["primary"].sum()) == 91
    # 1991 stays in the primary and in the comparison, and leaves only the third population
    assert int(((syn == 1991) & m["primary"]).sum()) == 4 and int(((syn == 1991) & m["included_data_643"]).sum()) == 4
    assert not ((syn == 1991) & m["primary_without_1991"]).any()
    assert int(m["primary_without_1991"].sum()) == 87
    # the third population is the primary less 1991: nothing else leaves it, and the set-aside records are not in it
    assert set(keys[m["primary"] & ~m["primary_without_1991"]]) == {k for k in keys if k.startswith("1991_")}
    assert not m["primary_without_1991"][~m["primary"]].any()
    # nested
    assert (m["primary_without_1991"] <= m["primary"]).all() and (m["primary"] <= m["included_data_643"]).all()


def test_a_set_aside_key_that_is_not_a_base_record_stops_the_run():
    with mock.patch.object(CS.assumed_business, "keys", return_value=RITC_KEYS):
        with pytest.raises(SystemExit, match="not in the included-data base"):
            EI.build_frame(records(), SET_ASIDE + ["9999_2020"])


def test_the_assumed_business_flag_follows_the_loaders_register():
    fr = frame()
    assert set(fr["key"][fr["ritc"] == 1.0]) == RITC_KEYS
    assert fr["ritc"].dtype == float


def test_the_labels_say_what_the_included_data_comparison_is_not():
    lab = EI.POPULATION_LABELS["included_data_643"]
    assert "not the earlier 643-record sample" in lab and "pre-census" in lab
    assert EI.POPULATIONS == ("primary", "included_data_643", "primary_without_1991")


# ---------------------------------------------------------------------------------------------- folds unchanged
def test_no_population_redeals_its_folds():
    fr = frame()
    fmap = EI.fold_map(fr)
    base_folds = fold_assignment(fr["syn"], 10)
    assert fmap == {int(s): int(f) for s, f in zip(fr["syn"], base_folds)}
    masks = EI.population_masks(fr)
    for name, mask in masks.items():
        p = EI.population_arrays(fr, mask, fmap)
        # the base's fold of each row, restricted
        assert np.array_equal(p["fold"], base_folds[mask]), name
    # the fixture has power: a fresh deal on the primary's or the third population's syndicates is another map
    for name in ("primary", "primary_without_1991"):
        p = EI.population_arrays(fr, masks[name], fmap)
        assert not np.array_equal(p["fold"], fold_assignment(p["syn"], 10)), name
    # and the included-data comparison is the one population a fresh deal would leave as it is
    p = EI.population_arrays(fr, masks["included_data_643"], fmap)
    assert np.array_equal(p["fold"], fold_assignment(p["syn"], 10))


def test_a_syndicates_rows_share_a_fold():
    fr = frame()
    p = EI.population_arrays(fr, EI.population_masks(fr)["primary"], EI.fold_map(fr))
    for s in set(p["syn"].tolist()):
        assert len(set(p["fold"][p["syn"] == s].tolist())) == 1


def test_the_fit_tasks_are_33_each_fold_trained_on_the_other_folds():
    fr = frame()
    pops = {n: EI.population_arrays(fr, m, EI.fold_map(fr)) for n, m in EI.population_masks(fr).items()}
    tasks = EI.fit_tasks(pops)
    assert len(tasks) == 33
    assert [(t[0], t[1]) for t in tasks if t[0] == "primary"] == [("primary", "full")] + [
        ("primary", "fold_%d" % f) for f in range(10)]
    for name, tag, S, R, H, yr, syn, ritc, train in tasks:
        p = pops[name]
        if tag == "full":
            assert train.all()
        else:
            f = int(tag.split("_")[1])
            assert np.array_equal(train, p["fold"] != f)
            # a held-out syndicate is in no training row
            held = set(syn[~train].tolist())
            assert held.isdisjoint(set(syn[train].tolist()))
        assert len(S) == len(p["S"])


def test_an_empty_or_whole_fold_stops_the_run():
    fr = frame()
    p = EI.population_arrays(fr, EI.population_masks(fr)["primary"], EI.fold_map(fr))
    p["fold"] = np.zeros(len(p["S"]), int)
    with pytest.raises(SystemExit, match="fold"):
        EI.fit_tasks({"primary": p})


# ---------------------------------------------------------------------------------------------- fixed size bands
def test_the_base_must_reproduce_the_fixed_bands_from_its_own_quartiles():
    fr = frame()
    own = edges_of(fr)
    assert EI.check_fixed_bands(fr, own) == list(own)
    off = (own[0] * 1.01, own[1], own[2])
    with pytest.raises(SystemExit, match="not the fixed original size bands"):
        EI.check_fixed_bands(fr, off)


def test_the_fixed_cutoffs_are_the_given_numbers_and_shared_with_the_diagnosis():
    assert EI.FIXED_BAND_EDGES == (172.5745, 425.362, 837.0151141803343) == SB.FIXED_BAND_EDGES


def test_a_population_is_scored_against_the_fixed_bands_and_not_its_own(run):
    rec = run["record"]
    fr = run["frame"]
    edges = edges_of(fr)
    prim = EI.population_masks(fr)["primary"]
    R = fr["R"][prim]
    own = SB.own_edges(R)
    assert own != edges                      # the primary's own quartiles are not the base's, so the test has power
    bands = SB.band_of(R, edges)
    row = rec["plug_in_backtest"]["primary"]["leave_out"]["0.99"]
    for j in range(1, 5):
        assert row["fixed_band_%d" % j]["n_targets"] == int((bands == j).sum())
    assert row["all"]["n_targets"] == int(prim.sum())
    assert rec["fixed_bands"]["edges_gbp_m"] == list(edges)
    assert rec["populations"]["primary"]["own_quartile_edges_gbp_m"] == list(own)


def test_the_base_count_check_stops_a_base_on_other_records():
    fr = frame()
    with pytest.raises(SystemExit, match="not the 643 from 118"):
        EI.compute(fr, CFG, TARGET, fitter=stub_fitter, workers=1, edges=edges_of(fr), expected_base=(643, 118))


# ------------------------------------------------------------------------------- one small synthetic fit
def test_fit_attempt_fits_the_adopted_model_on_the_training_rows_only(monkeypatch):
    """A tiny sampler run (two chains of 40 draws on 36 synthetic rows, not a result): the fit's bookkeeping is the
    task's, its draws are the eight reported parameters with their chains and draws, gamma is not a parameter, and only the
    training rows count."""
    monkeypatch.setattr(BT, "DRAWS", 40)
    monkeypatch.setattr(BT, "TUNE", 40)
    monkeypatch.setattr(BT, "CHAINS", 2)
    rng = np.random.default_rng(2)
    n = 36
    syn = np.repeat(np.arange(1, 10), 4)
    yr = np.tile(np.array([2019, 2020, 2021, 2022]), 9)
    R = rng.uniform(40.0, 1200.0, n)
    H = rng.uniform(0.15, 0.6, n)
    S = rng.standard_t(4, n) * 0.04
    ritc = np.zeros(n)
    ritc[::7] = 1.0
    train = syn != 3
    calls = []
    real = EI.scale_block

    def spy(*a, **k):
        calls.append((len(a[0]), k))
        return real(*a, **k)

    monkeypatch.setattr(EI, "scale_block", spy)
    out = EI.fit_attempt(("primary", "fold_2", S, R, H, yr, syn, ritc, train), 0.98)
    # the adopted model exactly (no keyword departs from scale_block's defaults: gamma fixed at 0), on the 32 training rows
    assert calls == [(32, {})]
    assert (out["population"], out["tag"]) == ("primary", "fold_2")
    assert (out["n_train"], out["n_held_out"]) == (int(train.sum()), int((~train).sum())) == (32, 4)
    assert (out["n_train_syndicates"], out["n_held_out_syndicates"]) == (8, 1)
    assert set(out["draws"]) == set(BT.FIT_PARAMS) and all(v.shape == (2, 40) for v in out["draws"].values())
    assert set(out["params"]) == set(BT.FIT_PARAMS) and set(out["means"]) == set(BT.OPERATOR_PARAMS)
    assert out["means"]["gamma"] == 0.0 and "gamma" not in out["draws"]
    assert out["means"]["k"] == pytest.approx(float(out["draws"]["k"].mean()))
    assert 0.5 <= out["means"]["k"] <= 1.0                      # k = 1/2 + 1/2 logistic(theta)
    assert set(out["diagnostics"]) == {"max_rhat", "min_ess_bulk", "divergences"}


# ------------------------------------------------------------------------------------------ the retry rule
def _diag(div, rhat=1.001):
    return {"max_rhat": rhat, "min_ess_bulk": 1000.0, "divergences": div}


def _stub_attempts(sequence):
    calls = []

    def fit(task, target_accept):
        calls.append(target_accept)
        div, rhat = sequence[len(calls) - 1]
        return {"params": {"k": {"mean": 0.6 + 0.01 * len(calls)}}, "means": {"k": 0.6 + 0.01 * len(calls)},
                "diagnostics": _diag(div, rhat), "draws": {}}
    return fit, calls


TASK = ("primary", "fold_3")


def test_a_converged_first_attempt_is_one_attempt():
    fit, calls = _stub_attempts([(0, 1.002)])
    out = EI.converging_task(TASK, fit=fit)
    assert calls == [0.98] and out["target_accept"] == 0.98
    assert [(a["target_accept"], a["converged"], a["reported"]) for a in out["attempts"]] == [(0.98, True, True)]


def test_a_divergent_fit_is_refitted_once_at_0_995_and_both_attempts_are_recorded():
    fit, calls = _stub_attempts([(2, 1.003), (0, 1.004)])
    out = EI.converging_task(TASK, fit=fit)
    assert calls == [0.98, 0.995] and out["target_accept"] == 0.995
    a0, a1 = out["attempts"]
    assert (a0["target_accept"], a0["converged"], a0["reported"]) == (0.98, False, False)
    assert (a1["target_accept"], a1["converged"], a1["reported"]) == (0.995, True, True)
    assert a0["diagnostics"]["divergences"] == 2 and a1["diagnostics"]["divergences"] == 0
    # the unreported attempt keeps what it would have reported; the reported fit is the second
    assert a0["params"]["k"]["mean"] == pytest.approx(0.61) and out["params"]["k"]["mean"] == pytest.approx(0.62)


def test_a_retry_that_does_not_converge_stops_the_run_naming_both_attempts():
    fit, calls = _stub_attempts([(2, 1.003), (1, 1.004)])
    with pytest.raises(SystemExit, match="target_accept 0.98.*target_accept 0.995"):
        EI.converging_task(TASK, fit=fit)
    assert calls == [0.98, 0.995]


def test_a_slow_mixing_fit_with_no_divergence_is_not_retried():
    fit, calls = _stub_attempts([(0, 1.05)])
    with pytest.raises(SystemExit, match="has not converged"):
        EI.converging_task(TASK, fit=fit)
    assert calls == [0.98]


def test_the_retry_constants_are_the_repositorys():
    assert (EI.TARGET_ACCEPT_FIRST, EI.TARGET_ACCEPT_RETRY) == (0.98, 0.995) == (BT.TARGET_ACCEPT, 0.995)
    rec = EI.__doc__
    assert "0.98" in rec and "0.995" in rec and "seed 42" in rec


# ------------------------------------------------------------------------------------------------ the record
def test_the_record_has_the_three_populations_and_thirty_three_fits(run):
    rec = run["record"]
    assert set(rec["populations"]) == set(EI.POPULATIONS)
    assert [rec["populations"][n]["n"] for n in EI.POPULATIONS] == [91, 94, 87]
    assert [rec["populations"][n]["n_syndicates"] for n in EI.POPULATIONS] == [23, 24, 22]
    assert [rec["populations"][n]["n_syndicate_1991_records"] for n in EI.POPULATIONS] == [4, 4, 0]
    for name in EI.POPULATIONS:
        assert list(rec["fits"][name]) == ["full"] + ["fold_%d" % f for f in range(10)]
    assert sum(len(v) for v in rec["fits"].values()) == 33
    assert rec["masks"]["rule_8_set_aside_records"] == sorted(SET_ASIDE)


def test_the_fits_train_on_the_base_maps_other_folds(run):
    rec, fr = run["record"], run["frame"]
    fmap = EI.fold_map(fr)
    masks = EI.population_masks(fr)
    for name in EI.POPULATIONS:
        syn = fr["syn"][masks[name]]
        folds = np.array([fmap[int(s)] for s in syn])
        for f in range(10):
            assert rec["fits"][name]["fold_%d" % f]["n_train"] == int((folds != f).sum())
            assert rec["fits"][name]["fold_%d" % f]["n_held_out"] == int((folds == f).sum())
        assert rec["fits"][name]["full"]["n_train"] == int(masks[name].sum())
    assert rec["fold_map"]["syndicate_to_fold"] == {str(s): f for s, f in sorted(fmap.items())}
    assert "never" in rec["fold_map"]["rule"] or "no fold is redealt" in rec["fold_map"]["rule"]


def test_the_backtest_rebuilds_each_populations_pool_from_its_own_rows(run):
    """Each population's thresholds are the headline operator's at its own fold fit's means on its own rows of the other
    folds (and, under the target-year rule, other years)."""
    fr = run["frame"]
    fmap = EI.fold_map(fr)
    masks = EI.population_masks(fr)
    for name in EI.POPULATIONS:
        p = EI.population_arrays(fr, masks[name], fmap)
        thr = run["arrays"]
        for rule, drop in (("leave_out", False), ("leave_out_and_target_year", True)):
            q = thr["%s__threshold__%s__0.995" % (name, rule)]
            assert len(q) == len(p["S"])
            for i in (0, len(q) // 2, len(q) - 1):
                f = int(p["fold"][i])
                keep = p["fold"] != f
                if drop:
                    keep &= p["yr"] != p["yr"][i]
                means = stub_result(("%s" % name, "fold_%d" % f, p["S"], p["R"], p["H"], p["yr"], p["syn"], p["ritc"],
                                     p["fold"] != f))["means"]
                th = TO.params(means, TO.HEADLINE)
                pool = transfer(p["S"][keep], p["R"][keep], p["H"][keep], (p["R"][i], p["H"][i]), th, CFG,
                                np.asarray(p["ritc"][keep], bool))
                assert q[i] == var_q(pool, 0.995)


def test_the_counts_follow_the_exceedances_the_thresholds_give(run):
    fr = run["frame"]
    masks = EI.population_masks(fr)
    for name in EI.POPULATIONS:
        S = fr["S"][masks[name]]
        for rule in EI.RULES:
            for a in EI.LEVELS:
                q = run["arrays"]["%s__threshold__%s__%s" % (name, rule, EI.level_key(a))]
                row = run["record"]["plug_in_backtest"][name][rule][EI.level_key(a)]["all"]
                assert row["exceedances"] == int((S > q).sum())
                assert row["pinball_mean"] == pytest.approx(float(BT.pinball(S, q, a).mean()))
                assert row["expected"] == pytest.approx(len(S) * (1 - a))


def test_the_record_states_its_weights_and_the_sampler(run):
    rec = run["record"]
    assert rec["sampler"]["seed"] == 42 and rec["sampler"]["draws"] == 1500 and rec["sampler"]["chains"] == 4
    assert rec["sampler"]["target_accept"] == 0.98 and rec["sampler"]["target_accept_retry"] == 0.995
    assert "unweighted" in rec["weighting"]["likelihood"] and "equal mass" in rec["weighting"]["donor_cdf"]
    assert "w_s / sum_t(n_t w_t)" in rec["weighting"]["bootstrap"] and "not w_s / n_s" in rec["weighting"]["bootstrap"]
    assert (rec["operator"], rec["operator_role"]) == ("size_only", "headline")
    assert "influence" in rec["reading"] and "do not select the sample" in rec["reading"]


def test_the_draws_are_stored_joint_and_the_thinning_is_the_backtests(run):
    arr = run["arrays"]
    for name in EI.POPULATIONS:
        for tag in ["full"] + ["fold_%d" % f for f in range(10)]:
            cols = [arr["%s__%s__%s" % (name, tag, p)] for p in BT.FIT_PARAMS]
            assert all(len(c) == len(cols[0]) == 200 for c in cols)        # 4 chains x 50 draws in the stub
        full = [arr["%s__full_all__%s" % (name, p)] for p in BT.FIT_PARAMS]
        assert all(c.shape == (4, 50) for c in full)
        # the full fit's thinned draws are rows of its full draws at the same indices for every parameter
        idx = np.linspace(0, 199, 200).astype(int)
        for p in BT.FIT_PARAMS:
            assert np.array_equal(arr["%s__full__%s" % (name, p)], arr["%s__full_all__%s" % (name, p)].reshape(-1)[idx])
        assert len(arr["%s__keys" % name]) == run["record"]["populations"][name]["n"]
        assert len(arr["%s__v1_var995_replicates" % name]) == 40
    assert sorted(arr) == run["record"]["arrays"]["names"]


def test_thin_is_check_operator_backtests_rule():
    class Var:
        def __init__(self, v):
            self.values = v

    a = np.arange(6000, dtype=float).reshape(4, 1500)
    post = {"k": Var(a), "z": Var(a * 2)}
    ref = BT.thin_draws(post, names=("k", "z"), n=600)
    assert np.array_equal(EI.thin(a), ref["k"]) and np.array_equal(EI.thin(a * 2), ref["z"])
    assert len(EI.thin(a[:, :10])) == 40


# ----------------------------------------------------------------------- the common-target comparison, by hand
def toy():
    """Eight books, four syndicates; the primary drops the last row, the third population drops the last syndicate's
    rows. Bands: R below 100 is band 1."""
    keys = np.array(["1_2018", "1_2019", "2_2018", "2_2019", "3_2018", "3_2019", "4_2018", "4_2019"])
    syn = np.array([1, 1, 2, 2, 3, 3, 4, 4])
    yr = np.array([2018, 2019] * 4)
    R = np.array([50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0])
    S = np.array([0.5, 0.2, 0.1, 0.9, 0.3, 0.4, 0.2, 0.2])
    n_rows = {"included_data_643": 8, "primary": 7, "primary_without_1991": 6}
    pops = {name: {"S": S[:n], "R": R[:n], "syn": syn[:n], "yr": yr[:n], "key": keys[:n], "idx": np.arange(n)}
            for name, n in n_rows.items()}
    inc = np.array([0.4, 0.3, 0.2, 0.5, 0.35, 0.3, 0.1, 0.1])
    no1991 = inc[:6].copy()
    no1991[0], no1991[4] = 0.6, 0.25
    thr = {"included_data_643": inc, "primary": inc[:7].copy(), "primary_without_1991": no1991}
    full = {name: {rule: {a: thr[name].copy() for a in EI.LEVELS} for rule in EI.RULES} for name in pops}
    return pops, full


def pinball(y, q, a):
    return np.where(y < q, (a - 1.0) * (y - q), a * (y - q))


def test_paired_draws_is_the_weighted_mean_of_per_row_differences():
    W = np.array([[1.0, 2.0, 3.0, 4.0], [2.0, 1.0, 1.0, 1.0]])
    delta = np.array([1.0, -1.0, 0.5, 2.0])
    mask = np.array([True, True, False, True])
    d = EI.paired_draws(delta, mask, W)
    assert d == pytest.approx([(1 * 1 + 2 * -1 + 4 * 2) / 7.0, (2 * 1 + 1 * -1 + 1 * 2) / 4.0])
    # the normaliser is the weight of the rows in the group, not of the whole set
    assert d[0] != pytest.approx((1 * 1 + 2 * -1 + 4 * 2) / 10.0)


def test_the_common_targets_are_those_in_every_population_and_the_populations_are_aligned():
    pops, thr = toy()
    out = EI.common_target_comparison(pops, thr, (100.0, 200.0, 300.0), reps=50)
    assert out["targets"]["n"] == 6 and out["targets"]["record_ids"] == ["1_2018", "1_2019", "2_2018", "2_2019", "3_2018",
                                                                         "3_2019"]
    assert out["targets"]["n_syndicates"] == 3
    # R below 100: the first five of the six
    assert out["targets"]["n_in_fixed_band_1"] == 5
    assert EI.common_index(pops).tolist() == [0, 1, 2, 3, 4, 5]


def test_each_origin_keeps_its_own_forecasts_on_the_common_targets():
    pops, thr = toy()
    out = EI.common_target_comparison(pops, thr, (100.0, 200.0, 300.0), reps=50)
    S = np.array([0.5, 0.2, 0.1, 0.9, 0.3, 0.4])
    for name in pops:
        q = thr[name]["leave_out"][0.99][:6]
        row = out["origins"][name]["leave_out"]["0.99"]["all"]
        assert row["exceedances"] == int((S > q).sum()) and row["n_targets"] == 6
        assert row["pinball_mean"] == pytest.approx(float(pinball(S, q, 0.99).mean()))
    band1 = out["origins"]["primary_without_1991"]["leave_out"]["0.99"]["fixed_band_1"]
    # rows 0..4 are band 1: the third population's events there are rows 3 and 4 (S .9 > .5, S .3 > .25)
    assert band1["exceedances"] == 2 and band1["event_record_ids"] == ["2_2019", "3_2018"]
    prim1 = out["origins"]["primary"]["leave_out"]["0.99"]["fixed_band_1"]
    assert prim1["event_record_ids"] == ["1_2018", "2_2019"]


def test_identical_forecasts_give_exactly_zero_paired_differences():
    pops, thr = toy()
    out = EI.common_target_comparison(pops, thr, (100.0, 200.0, 300.0), reps=80)
    for rule in EI.RULES:
        for a in ("0.99", "0.995"):
            for g in EI.GROUPS:
                c = out["paired"]["included_data_643_minus_primary"][rule][a][g]
                assert c["new_events"] == 0 and c["removed_events"] == 0
                assert c["rate_difference_point"] == 0.0 and c["pinball_difference_point"] == 0.0
                assert c["pinball_difference_bootstrap"] == {"mean": 0.0, "interval_95": [0.0, 0.0]}
                assert c["rate_difference_bootstrap"] == {"mean": 0.0, "interval_95": [0.0, 0.0]}
                assert c["p_rate_increase"] == 0.0 and c["p_pinball_improvement"] == 0.0


def test_the_paired_contrast_is_built_row_by_row_before_weighting():
    pops, thr = toy()
    reps, seed = 120, 77
    out = EI.common_target_comparison(pops, thr, (100.0, 200.0, 300.0), reps=reps, seed=seed)
    S = np.array([0.5, 0.2, 0.1, 0.9, 0.3, 0.4])
    syn = np.array([1, 1, 2, 2, 3, 3])
    a = 0.99
    old, new = thr["primary"]["leave_out"][a][:6], thr["primary_without_1991"]["leave_out"][a]
    d_loss = pinball(S, new, a) - pinball(S, old, a)
    d_evt = (S > new).astype(float) - (S > old).astype(float)
    # the bootstrap weights: one Dirichlet weight per syndicate shared by its rows
    W = BT.bayes_bootstrap_weights(syn, reps=reps, seed=seed)
    assert np.array_equal(W[:, 0], W[:, 1]) and np.array_equal(W[:, 4], W[:, 5])
    for g, mask in (("all", np.ones(6, bool)), ("fixed_band_1", np.arange(6) < 5)):
        c = out["paired"]["primary_without_1991_minus_primary"]["leave_out"]["0.99"][g]
        exp_l = np.array([(W[r][mask] * d_loss[mask]).sum() / W[r][mask].sum() for r in range(reps)])
        exp_e = np.array([(W[r][mask] * d_evt[mask]).sum() / W[r][mask].sum() for r in range(reps)])
        assert c["pinball_difference_point"] == pytest.approx(float(d_loss[mask].mean()))
        assert c["rate_difference_point"] == pytest.approx(float(d_evt[mask].mean()))
        assert c["pinball_difference_bootstrap"]["mean"] == pytest.approx(float(exp_l.mean()))
        assert c["pinball_difference_bootstrap"]["interval_95"] == pytest.approx(
            [float(x) for x in np.percentile(exp_l, [2.5, 97.5])])
        assert c["rate_difference_bootstrap"]["mean"] == pytest.approx(float(exp_e.mean()))
        assert c["p_pinball_improvement"] == pytest.approx(float((exp_l < 0).mean()))
    band = out["paired"]["primary_without_1991_minus_primary"]["leave_out"]["0.99"]["fixed_band_1"]
    assert (band["events_old"], band["events_new"], band["new_events"], band["removed_events"]) == (2, 2, 1, 1)
    assert band["rate_difference_point"] == 0.0     # one event gained, one lost: no net change in the rate


def test_the_bootstrap_reading_says_it_is_conditional():
    pops, thr = toy()
    out = EI.common_target_comparison(pops, thr, (100.0, 200.0, 300.0), reps=20)
    b = out["bootstrap"]
    assert "taken first and then weighted" in b["paired_difference_arithmetic"]
    assert "exactly zero" in b["paired_difference_arithmetic"]
    assert "conditional" in b["reading"] and "not a total uncertainty" in b["reading"]
    assert "shared by its rows" in b["weights"]


def test_a_population_whose_common_rows_are_not_the_others_stops_the_run():
    pops, thr = toy()
    pops["primary"] = {**pops["primary"], "R": pops["primary"]["R"] + 1.0}
    with pytest.raises(SystemExit, match="common targets are not the other populations' rows"):
        EI.common_target_comparison(pops, thr, (100.0, 200.0, 300.0), reps=20)


def test_no_common_target_stops_the_run():
    pops, thr = toy()
    pops["primary"]["idx"] = pops["primary"]["idx"] + 100
    with pytest.raises(SystemExit, match="no target is present in every population"):
        EI.common_target_comparison(pops, thr, (100.0, 200.0, 300.0), reps=20)


def test_the_record_compares_on_the_common_targets_of_the_synthetic_run(run):
    c = run["record"]["common_target_comparison"]
    masks = EI.population_masks(run["frame"])
    common = masks["primary_without_1991"]          # the populations nest, so the smallest is the common set
    assert c["targets"]["n"] == int(common.sum())
    assert c["targets"]["record_ids"] == run["frame"]["key"][common].tolist()
    assert set(c["paired"]) == {"%s_minus_%s" % pair for pair in EI.CONTRASTS}


# ----------------------------------------------------------------------------------------------- Vignette 1
def test_the_shipped_precision_is_pythons_round_to_8_2_and_6_decimals():
    p = {"S": np.array([0.123456785, 0.1000000049999]), "R": np.array([123.455, 99.995]),
         "H": np.array([0.1234565, 0.5]), "syn": np.array([1, 2]), "yr": np.array([2020, 2021]),
         "ritc": np.array([0.0, 1.0]), "key": np.array(["1_2020", "2_2021"])}
    S, R, H, syn, yr, ritc, keys = EI.shipped_precision(p)
    assert S.tolist() == [round(0.123456785, 8), round(0.1000000049999, 8)]
    assert R.tolist() == [round(123.455, 2), round(99.995, 2)]
    assert H.tolist() == [round(0.1234565, 6), 0.5]
    assert ritc.tolist() == [False, True] and keys.tolist() == ["1_2020", "2_2021"]
    # what the shipped tool reads back from its JSON is these same numbers
    assert json.loads(json.dumps(S.tolist())) == S.tolist()


def test_vignette_1_centre_and_cutpoint_donor(run):
    fr, rec = run["frame"], run["record"]
    masks = EI.population_masks(fr)
    for name in EI.POPULATIONS:
        p = EI.population_arrays(fr, masks[name], EI.fold_map(fr))
        S, R, H, syn, yr, ritc, keys = EI.shipped_precision(p)
        full = stub_result((name, "full", p["S"], p["R"], p["H"], p["yr"], p["syn"], p["ritc"], np.ones(len(S), bool)))
        th = TO.params({k: float(np.asarray(full["draws"][k]).mean()) if k != "gamma" else 0.0
                        for k in BT.OPERATOR_PARAMS}, TO.HEADLINE)
        adj = transfer(S, R, H, TARGET, th, CFG, ritc)
        q = var_q(adj, 0.995)
        v = rec["vignette_1"][name]
        assert v["centre_reserve_fraction"] == q and v["centre_gbp_m"] == q * 500.0
        assert v["cutpoint_donor"] == keys[adj == q].tolist() and len(v["cutpoint_donor"]) >= 1
        assert v["most_adverse_donors"][0]["transferred_severity"] == float(adj.max())
        assert v["n_donors"] == len(S) and v["target"] == {"reserve_size_gbp_m": 500.0, "hhi": 0.17}
        lo, hi = v["conditional_interval_95"]
        assert lo <= hi and v["conditional_interval_95_gbp_m"] == [lo * 500.0, hi * 500.0]
        assert "not a total uncertainty" in v["reading"] and "conditional" in v["reading"]


def test_the_cutpoint_donor_is_the_atom_at_the_var_not_the_tail_beyond_it():
    """With 250 donors the inverse-CDF VaR99.5 is the second largest transferred severity: one donor is the cutpoint, two
    are at or above it. (With fewer than 200 the VaR is the maximum and the two readings coincide.)"""
    rng = np.random.default_rng(21)
    n = 250
    syn = np.repeat(np.arange(3001, 3051), 5)
    p = {"S": rng.standard_t(4, n) * 0.05, "R": rng.uniform(30.0, 1500.0, n), "H": rng.uniform(0.15, 0.6, n),
         "syn": syn, "yr": np.tile(np.arange(2018, 2023), 50), "ritc": np.zeros(n),
         "key": np.array(["%s_%s" % (s, y) for s, y in zip(syn, np.tile(np.arange(2018, 2023), 50))])}
    full = stub_result(("primary", "full", p["S"], p["R"], p["H"], p["yr"], p["syn"], p["ritc"], np.ones(n, bool)))
    v, _reps = EI.vignette1_block(p, full, CFG, TARGET, b=8)
    S, R, H, _s, _y, ritc, keys = EI.shipped_precision(p)
    th = TO.params({k: float(np.asarray(full["draws"][k]).mean()) if k != "gamma" else 0.0 for k in BT.OPERATOR_PARAMS},
                   TO.HEADLINE)
    adj = transfer(S, R, H, TARGET, th, CFG, ritc)
    order = np.argsort(-adj, kind="stable")
    assert v["cutpoint_donor"] == [str(keys[order[1]])]
    assert v["support_at_or_above"] == 2
    assert v["centre_reserve_fraction"] == float(adj[order[1]])


def test_the_vignette_interval_is_deterministic_in_its_seed():
    fr = frame()
    p = EI.population_arrays(fr, EI.population_masks(fr)["primary"], EI.fold_map(fr))
    full = stub_result(("primary", "full", p["S"], p["R"], p["H"], p["yr"], p["syn"], p["ritc"],
                        np.ones(len(p["S"]), bool)))
    a, ra = EI.vignette1_block(p, full, CFG, TARGET, b=30, seed=1)
    b, rb = EI.vignette1_block(p, full, CFG, TARGET, b=30, seed=1)
    c, rc = EI.vignette1_block(p, full, CFG, TARGET, b=30, seed=2)
    assert np.array_equal(ra, rb) and not np.array_equal(ra, rc) and a == b
    assert a["interval"] == {"B": 30, "seed": 1, "rule": "2.5 and 97.5 percentiles of the replicates' VaRs"}


def test_the_vignette_seed_and_b_are_vignette_uncertaintys_records():
    """vignette_uncertainty.py reads B and SEED from sys.argv at import, so they are not imported (this script's first
    argument is its worker count); they must equal the committed record's."""
    with io.open(os.path.join(HERE, "results", "vignette_uncertainty_results.json"), encoding="utf-8") as fh:
        meta = json.load(fh)["meta"]
    assert (EI.V1_SEED, EI.V1_B) == (meta["seed"], meta["B"])
    with open(os.path.join(HERE, "src", "check_exclusion_influence.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "import SEED" not in src and "SEED as" not in src and "B as" not in src


def test_the_operator_draws_have_gamma_as_exact_zeros_in_the_headline_order():
    full = stub_result(("primary", "full", np.zeros(3), np.ones(3), np.ones(3), np.arange(3), np.arange(3),
                        np.zeros(3), np.ones(3, bool)))
    d = EI.operator_draws_of(full)
    assert list(d) == list(BT.OPERATOR_PARAMS) and not d["gamma"].any() and d["k"].shape == (200,)


# ------------------------------------------------------------------------------------------------ the controls
def test_the_primary_must_be_the_stored_working_sample():
    fr = frame()
    prim = [o for o in records() if "%s_%s" % (o["syndicate"], o["year"]) not in SET_ASIDE]
    out = EI.check_base_is_the_stored_sample(fr, prim)
    assert out == {"keys_equal": True, "same_order": True, "figures_equal": True, "n": 91}
    shuffled = prim[::-1]
    assert EI.check_base_is_the_stored_sample(fr, shuffled)["same_order"] is False
    stale = [dict(o) for o in prim]
    stale[4]["s_raw_a"] += 1e-9
    with pytest.raises(SystemExit, match="figure differs|severity"):
        EI.check_base_is_the_stored_sample(fr, stale)
    with pytest.raises(SystemExit, match="records differ"):
        EI.check_base_is_the_stored_sample(fr, prim[:-1])
    with pytest.raises(SystemExit, match="records differ"):
        EI.check_base_is_the_stored_sample(fr, records())        # the file still holds the set-aside records


def test_the_primary_pool_must_be_the_shipped_tool_to_its_rounding():
    fr = frame()
    p = EI.population_arrays(fr, EI.population_masks(fr)["primary"], EI.fold_map(fr))
    S, R, H, syn, yr, ritc, keys = EI.shipped_precision(p)
    ship = (S.copy(), R.copy(), H.copy(), syn.copy(), yr.copy())
    assert EI.check_shipped_pool(p, ship) == {"n": 91, "equal": True}
    bad = (S + np.eye(len(S))[0] * 1e-7, R, H, syn, yr)
    with pytest.raises(SystemExit, match="differ between the shipped tool and the primary"):
        EI.check_shipped_pool(p, bad)
    with pytest.raises(SystemExit, match="rebuild distortion_tool.html"):
        EI.check_shipped_pool(p, (S[:-1], R[:-1], H[:-1], syn[:-1], yr[:-1]))


def test_a_primary_refit_that_is_not_the_published_headline_stops_the_run():
    fr = frame()
    # the stub's means are the synthetic fixture's, not the published fit's: the guard refuses them
    with pytest.raises(SystemExit, match="published headline fit"):
        EI.compute(fr, CFG, TARGET, fitter=stub_fitter, workers=1, edges=edges_of(fr), b=10, reps=10, headline_check=True)


def test_the_primary_vignette_is_set_beside_the_vignette_records_figure():
    block = {"centre_reserve_fraction": 0.34, "conditional_interval_95": [0.2, 0.5]}
    rec = {"centres_full_pool_posterior_mean": {"V1_adj": {"v995": 0.3343}},
           "vignette1": {"adjusted": {"var995": {"lo": 0.2346, "hi": 0.5051}}}}
    c = EI.vignette_control(block, rec)
    assert c["centre_difference"] == pytest.approx(0.34 - 0.3343) and c["interval_recorded"] == [0.2346, 0.5051]


# --------------------------------------------------------------------------------------- dry run and the loader
def test_a_dry_run_fits_nothing(capsys):
    fr = frame()
    with mock.patch.object(EI, "fit_attempt", side_effect=AssertionError("a fit ran")), \
            mock.patch.object(EI, "converging_task", side_effect=AssertionError("a fit ran")):
        assert EI.dry_run(fr, 3) == 0
    text = capsys.readouterr().out
    assert "fits: 33 (3 populations x (1 full + 10 folds))" in text and "nothing is fitted" in text
    assert "primary" in text and "included_data_643" in text and "primary_without_1991" in text


def test_the_real_loader_gives_the_included_data_base_and_puts_the_register_back():
    import run_analysis as ra
    before = ra.load_source_history_set_aside
    records_, keys = EI.load_base()
    assert ra.load_source_history_set_aside is before
    assert len(keys) == 11 and "6131_2021" in keys and "2008_2023" in keys
    fr = EI.build_frame(records_, keys)
    assert (len(fr["S"]), len(set(fr["syn"].tolist()))) == EI.EXPECTED_BASE == (643, 118)
    masks = EI.population_masks(fr)
    assert int(masks["primary"].sum()) == 632 and int(masks["primary_without_1991"].sum()) == 626
    assert set(fr["key"][~masks["primary"]]) == set(keys)
    # every set-aside record has a figure in the base (that is what makes the comparison included-data)
    assert np.isfinite(fr["S"][~masks["primary"]]).all()
    # the one syndicate the census removes leaves the primary, so a fresh deal would move other syndicates' folds
    assert 2008 in set(fr["syn"].tolist()) and 2008 not in set(fr["syn"][masks["primary"]].tolist())
    assert EI.check_fixed_bands(fr, EI.FIXED_BAND_EDGES)
