#!/usr/bin/env python3
"""The honest ten-fold operator backtest on the u <= t-3 outcome (check_cohort_depth_sensitivity.honest_backtest).

check_operator_backtest.py backtests the operator on the primary: the syndicates are dealt into ten folds, the adopted
model is refitted on each fold's training syndicates, and each held-out syndicate-year is transferred from the training
pool. The depth sensitivity runs the same backtest on the kept records at their u <= t-3 severities. Held to:

  * the sample reaches the fold fits: fit_training and run_folds take the sample they are given, and the fold of a
    target is oos_validation.fold_assignment on the depth sample's own syndicates (a spy on the scoring call);
  * on synthetic fold fits, the plug-in and posterior-draw exceedances equal an independent computation from
    check_operator_backtest's own functions, the quartile tables add up to the totals, and the per-target flags are
    one per target;
  * the u <= t-3 tables are set beside the primary's committed ones;
  * a fold refit that diverges at target_accept 0.98 is refitted once at 0.995 (the full refits' rule), reported only if
    the retry converges, and stops the run if it does not; the primary's fold path (check_operator_backtest.run_folds)
    is unchanged;
  * the committed record (DEFERRED-TO-REFIT: written by the recorded pass).

Run:  python -m pytest src/test_cohort_depth_honest_backtest.py -q
"""
import io
import json
import os
import re

import numpy as np
import pytest

from fold_test_support import deal_on_the_fly  # noqa: E402
import check_cohort_depth_sensitivity as D
import check_cohort_scope as CS
import check_operator_backtest as BT
import sample_scope as SS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEANS = {"k": 0.6, "gamma": 0.0, "sd_undiv": 0.03, "sd_div": 0.05, "nu_clean": 4.0, "nu_ritc": 6.0}
CFG = (500.0, 0.01, 1.0)


@pytest.fixture(autouse=True)
def _synthetic_folds(monkeypatch):
    """Every test here is on synthetic syndicates, which are not in the frozen fold map (data/fold_map.json): they are
    dealt in turn (fold_test_support.deal_on_the_fly)."""
    deal_on_the_fly(monkeypatch)


def _recs(n_syn=24, years=3, seed=11):
    rng = np.random.default_rng(seed)
    recs = []
    for s in range(n_syn):
        for y in range(years):
            recs.append({"syndicate": 2000 + s, "year": 2015 + y, "s_raw_a": float(rng.normal(0, 0.06)),
                         "opening_reserves_gbp_m": float(np.exp(rng.normal(np.log(300), 0.9))),
                         "hhi": float(rng.uniform(0.1, 0.5))})
    return recs


def _fits(k=10, n_draws=8, seed=3):
    """Synthetic fold fits: the same posterior means in every fold, a few draws around them."""
    rng = np.random.default_rng(seed)
    out = []
    for f in range(k):
        draws = {p: (np.full(n_draws, m) + (rng.normal(0, 0.002, n_draws) if p != "gamma" else 0.0)).tolist()
                 for p, m in MEANS.items()}
        out.append({"fold": f, "n_train": 0, "n_held_out": 0, "n_train_syndicates": 0, "n_held_out_syndicates": 0,
                    "params": {}, "means": dict(MEANS), "draws": draws,
                    "diagnostics": {"max_rhat": 1.0, "min_ess_bulk": 1000.0, "divergences": 0}})
    return out


@pytest.fixture(scope="module")
def run():
    mp = pytest.MonkeyPatch()
    deal_on_the_fly(mp)
    try:
        recs = _recs()
        fits = _fits()
        return recs, fits, D.honest_backtest(recs, CFG, fits=fits)
    finally:
        mp.undo()


def test_the_sample_reaches_the_fold_fits(monkeypatch):
    """fit_training takes the sample it is given (the training part of its folds) and not the primary's; run_folds passes
    it on."""
    recs = _recs(n_syn=12)
    S, R, H, yr, key = CS.arrays(recs)
    syn = np.array([o["syndicate"] for o in recs])
    ritc = CS.ritc_flag(key)

    class Stop(Exception):
        pass

    seen = {}

    def spy(R_, H_, yr_, ritc_):
        seen["R"], seen["yr"] = R_, yr_
        raise Stop()

    def never():
        raise AssertionError("the primary sample was loaded although a sample was given")

    monkeypatch.setattr(BT, "scale_block", spy)
    monkeypatch.setattr(BT, "load_sample", never)
    with pytest.raises(Stop):
        BT.fit_training(2, 5, (S, R, H, yr, syn, ritc))
    tr = BT.fold_assignment(syn, 5) != 2
    assert np.array_equal(seen["R"], R[tr]) and np.array_equal(seen["yr"], yr[tr]) and 0 < tr.sum() < len(S)
    # run_folds passes the sample (and k) to every fold
    monkeypatch.setattr(BT, "fit_training", lambda f, k=10, sample=None: (f, k, sample))
    assert BT.run_folds(1, 3, sample="S") == [(0, 3, "S"), (1, 3, "S"), (2, 3, "S")]
    assert BT.run_folds(1, 2) == [(0, 2, None), (1, 2, None)]


# ------------------------------------------------------------------ the fold refits' convergence rule
def _k_of(target_accept):
    """The stand-in fit's posterior mean of k at a target_accept, so the attempt a figure comes from can be told."""
    return 0.5 + 0.1 * target_accept


def _stub_fold_fit(plan):
    """A stand-in for fit_fold_at: plan[target_accept] is (divergences, max R-hat) for every fold, or a function of the
    fold; the calls are kept. Each attempt has its own posterior means, so the attempt a record keeps can be told."""
    calls = []

    def fit(fold, k, sample, target_accept):
        calls.append((fold, k, sample, target_accept))
        div, rhat = plan[target_accept](fold) if callable(plan[target_accept]) else plan[target_accept]
        means = dict(MEANS, k=_k_of(target_accept))
        return {"fold": fold, "n_train": 10, "n_held_out": 2, "n_train_syndicates": 5, "n_held_out_syndicates": 1,
                "params": {"k": {"mean": _k_of(target_accept)}}, "means": means,
                "draws": {p: [m] * 3 for p, m in means.items()}, "seconds": 1.0,
                "diagnostics": {"max_rhat": rhat, "min_ess_bulk": 1500.0, "divergences": div}}
    return fit, calls


def test_a_fold_that_diverges_is_refitted_once_at_the_higher_target_accept_and_the_retry_is_reported():
    fit, calls = _stub_fold_fit({0.98: (1, 1.0016), 0.995: (0, 1.002)})
    out = D.converging_fold_fit(4, 10, "S", fit=fit)
    assert calls == [(4, 10, "S", 0.98), (4, 10, "S", 0.995)]
    assert out["target_accept"] == 0.995 and out["diagnostics"] == {"max_rhat": 1.002, "min_ess_bulk": 1500.0, "divergences": 0}
    assert out["means"]["k"] == pytest.approx(_k_of(0.995))                # the retry's figures, not the first attempt's
    first, second = out["attempts"]
    assert (first["target_accept"], first["converged"], first["reported"]) == (0.98, False, False)
    assert first["diagnostics"]["divergences"] == 1 and first["diagnostics"]["max_rhat"] == 1.0016
    assert (second["target_accept"], second["converged"], second["reported"]) == (0.995, True, True)
    assert second["diagnostics"]["divergences"] == 0
    # the attempt that is not reported keeps what it would have reported
    assert first["means"]["k"] == pytest.approx(_k_of(0.98)) and first["params"] == {"k": {"mean": _k_of(0.98)}}
    assert "means" not in second and "params" not in second


def test_a_fold_that_converges_at_the_first_target_accept_is_not_retried():
    fit, calls = _stub_fold_fit({0.98: (0, 1.004), 0.995: (1, 1.5)})
    out = D.converging_fold_fit(2, 10, None, fit=fit)
    assert [c[3] for c in calls] == [0.98]
    assert out["target_accept"] == 0.98 and len(out["attempts"]) == 1
    assert (out["attempts"][0]["converged"], out["attempts"][0]["reported"]) == (True, True)
    assert out["means"]["k"] == pytest.approx(_k_of(0.98))


def test_a_fold_whose_retry_also_diverges_stops_the_run_and_names_both_attempts():
    fit, calls = _stub_fold_fit({0.98: (2, 1.003), 0.995: (1, 1.002)})
    with pytest.raises(SystemExit, match=r"fold 7 has not converged.*target_accept 0\.98.*target_accept 0\.995"):
        D.converging_fold_fit(7, 10, None, fit=fit)
    assert [c[3] for c in calls] == [0.98, 0.995]                      # one retry, no more


def test_a_retry_that_does_not_diverge_but_fails_on_r_hat_is_not_reported():
    fit, calls = _stub_fold_fit({0.98: (1, 1.003), 0.995: (0, 1.02)})
    with pytest.raises(SystemExit, match="has not converged"):
        D.converging_fold_fit(1, 10, None, fit=fit)
    assert [c[3] for c in calls] == [0.98, 0.995]


def test_a_fold_that_fails_on_r_hat_with_no_divergence_is_not_retried_and_stops_the_run():
    fit, calls = _stub_fold_fit({0.98: (0, 1.02), 0.995: (0, 1.0)})
    with pytest.raises(SystemExit, match="has not converged"):
        D.converging_fold_fit(3, 10, None, fit=fit)
    assert [c[3] for c in calls] == [0.98]


def test_only_the_fold_that_diverges_is_retried_and_the_record_keeps_every_fold_s_attempts():
    plan = {0.98: lambda fold: (1, 1.002) if fold == 4 else (0, 1.001), 0.995: (0, 1.001)}
    fit, calls = _stub_fold_fit(plan)
    fits = D.run_converging_folds(1, 10, None, fit=lambda f, k, s: D.converging_fold_fit(f, k, s, fit=fit))
    assert [f["fold"] for f in fits] == list(range(10))
    assert sorted(c[3] for c in calls) == [0.98] * 10 + [0.995]
    recs = _recs()
    out = D.honest_backtest(recs, CFG, fits=fits)
    rec = out["honest"]["fits"]
    assert out["honest"]["folds_retried"] == [4]
    assert [f["target_accept"] for f in rec] == [0.995 if i == 4 else 0.98 for i in range(10)]
    assert [len(f["attempts"]) for f in rec] == [2 if i == 4 else 1 for i in range(10)]
    assert [a["reported"] for a in rec[4]["attempts"]] == [False, True]
    assert all(f["attempts"][-1]["reported"] and f["attempts"][-1]["converged"] for f in rec)
    # the reported diagnostics are the last attempt's, and the operator reads the retry's means
    assert rec[4]["diagnostics"] == rec[4]["attempts"][-1]["diagnostics"] and rec[4]["diagnostics"]["divergences"] == 0
    assert out["sampler"]["target_accept"] == 0.98 and out["sampler"]["target_accept_retry"] == 0.995
    th = {f["fold"]: BT.operator_params(f["means"]) for f in fits}
    assert th[4]["k"] == pytest.approx(_k_of(0.995)) and th[3]["k"] == pytest.approx(_k_of(0.98))


def test_a_fold_fit_that_did_not_come_through_the_rule_is_one_attempt_at_the_primarys_target_accept():
    out = D.honest_backtest(_recs(), CFG, fits=_fits())
    assert out["honest"]["folds_retried"] == []
    for f in out["honest"]["fits"]:
        assert f["target_accept"] == BT.TARGET_ACCEPT == 0.98
        assert f["attempts"] == [{"target_accept": 0.98, "diagnostics": f["diagnostics"], "converged": True,
                                  "reported": True}]


def test_honest_backtest_runs_its_folds_through_the_rule_and_not_through_the_primarys_run_folds(monkeypatch):
    seen = {}

    def spy(workers, k=10, sample=None, fit=None):
        seen["args"] = (workers, k, sample)
        return _fits()

    def refused(*a, **kw):
        raise AssertionError("the primary's run_folds was used for the depth sensitivity's folds")

    monkeypatch.setattr(D, "run_converging_folds", spy)
    monkeypatch.setattr(BT, "run_folds", refused)
    recs = _recs()
    D.honest_backtest(recs, CFG, workers=5)
    workers, k, sample = seen["args"]
    S, R, H, yr, key = CS.arrays(recs)
    assert (workers, k) == (5, 10) and np.array_equal(sample[0], S) and np.array_equal(sample[2], H)
    assert list(sample[4]) == [o["syndicate"] for o in recs]


def test_fit_fold_at_sets_the_target_accept_for_the_call_and_puts_the_primarys_back(monkeypatch):
    during = []

    def fake_fit_training(fold, k=10, sample=None):
        during.append(BT.TARGET_ACCEPT)
        if fold == 9:
            raise RuntimeError("sampler failed")
        return {"fold": fold, "k": k, "sample": sample}

    monkeypatch.setattr(BT, "fit_training", fake_fit_training)
    assert BT.TARGET_ACCEPT == D.TARGET_ACCEPT_FIRST == 0.98
    assert D.fit_fold_at(2, 10, "S", 0.995) == {"fold": 2, "k": 10, "sample": "S"}
    assert during == [0.995] and BT.TARGET_ACCEPT == 0.98
    assert D.fit_fold_at(3, 10, "S", 0.98)["fold"] == 3 and during == [0.995, 0.98]
    with pytest.raises(RuntimeError):
        D.fit_fold_at(9, 10, "S", 0.995)
    assert during[-1] == 0.995 and BT.TARGET_ACCEPT == 0.98                 # put back although the fit raised


def test_the_primarys_fold_path_is_unchanged(monkeypatch):
    """check_operator_backtest.run_folds still maps its own fit_training over (fold, k, sample) with no retry and no
    target_accept argument; the depth sensitivity's rule is its own."""
    import inspect
    assert list(inspect.signature(BT.run_folds).parameters) == ["workers", "k", "sample"]
    assert list(inspect.signature(BT.fit_training).parameters) == ["fold", "k", "sample"]
    assert BT.TARGET_ACCEPT == 0.98 and BT.FIT_SEED == 42 and BT.DRAWS == 1500 and BT.TUNE == 1500 and BT.CHAINS == 4

    def refused(*a, **kw):
        raise AssertionError("the primary's fold path went through the depth sensitivity's rule")

    monkeypatch.setattr(D, "converging_fold_fit", refused)
    monkeypatch.setattr(D, "fit_fold_at", refused)
    monkeypatch.setattr(D, "run_converging_folds", refused)
    monkeypatch.setattr(BT, "fit_training", lambda f, k=10, sample=None: (f, k, sample))
    assert BT.run_folds(1, 3, sample="S") == [(0, 3, "S"), (1, 3, "S"), (2, 3, "S")]
    assert BT.run_folds(1, 2) == [(0, 2, None), (1, 2, None)]
    assert BT.TARGET_ACCEPT == 0.98


def test_run_converging_folds_runs_the_folds_in_order_on_one_worker_and_on_a_pool():
    """pow(fold, k, sample) is a picklable stand-in for the fit: a different value for every fold."""
    want = [pow(f, 10, 1009) for f in range(10)]
    assert D.run_converging_folds(1, 10, 1009, fit=pow) == want
    assert D.run_converging_folds(2, 10, 1009, fit=pow) == want


def test_the_fold_fits_of_the_committed_record_come_through_the_rule_and_keep_their_attempts():
    """DEFERRED-TO-REFIT: written by the recorded pass."""
    with io.open(os.path.join(HERE, "results", "check_cohort_depth_sensitivity_results.json"), encoding="utf-8") as fh:
        rec = json.load(fh)
    for name in ("honest_backtest_t_minus_2_on_the_kept_records", "honest_backtest_t_minus_3"):
        honest = rec[name]["honest"]
        assert rec[name]["sampler"]["target_accept"] == D.TARGET_ACCEPT_FIRST
        assert rec[name]["sampler"]["target_accept_retry"] == D.TARGET_ACCEPT_RETRY
        assert len(honest["fits"]) == 10
        retried = []
        for f in honest["fits"]:
            att = f["attempts"]
            assert 1 <= len(att) <= 2 and [a["target_accept"] for a in att] == [D.TARGET_ACCEPT_FIRST,
                                                                                 D.TARGET_ACCEPT_RETRY][:len(att)]
            reported = [a for a in att if a["reported"]]
            assert len(reported) == 1 and reported[0] is att[-1] and reported[0]["converged"] is True
            assert f["target_accept"] == reported[0]["target_accept"] and f["diagnostics"] == reported[0]["diagnostics"]
            assert f["diagnostics"]["divergences"] == 0 and f["diagnostics"]["max_rhat"] <= 1.01
            if len(att) == 2:
                retried.append(f["fold"])
                # a retry is made only for a divergent first attempt, and keeps what that attempt would have reported
                assert att[0]["diagnostics"]["divergences"] > 0 and att[0]["converged"] is False
                assert att[0]["reported"] is False and set(att[0]["means"]) == set(BT.OPERATOR_PARAMS)
                assert f["target_accept"] == D.TARGET_ACCEPT_RETRY
            else:
                assert f["target_accept"] == D.TARGET_ACCEPT_FIRST
        assert honest["folds_retried"] == retried


def test_the_folds_are_the_depth_samples_own_syndicates(monkeypatch):
    """The held-out label of every target is fold_assignment on the depth sample's syndicates (a mutation to the
    primary's syndicates, or to one fold, changes it)."""
    recs = _recs(n_syn=13)
    syn = np.array([o["syndicate"] for o in recs])
    got = {}
    real = BT.version_block

    def spy(label, note, leaks, S, R, H, ritc, syn_, yr, held, thetas, cfg, W, capture=None):
        got["held"], got["leaks"] = np.asarray(held).copy(), leaks
        return real(label, note, leaks, S, R, H, ritc, syn_, yr, held, thetas, cfg, W, capture=capture)

    monkeypatch.setattr(BT, "version_block", spy)
    D.honest_backtest(recs, CFG, fits=_fits())
    assert np.array_equal(got["held"], BT.fold_assignment(syn, 10)) and got["leaks"] is False
    assert len(set(got["held"].tolist())) == 10


def test_the_exceedances_equal_an_independent_computation(run):
    recs, fits, out = run
    S, R, H, yr, key = CS.arrays(recs)
    ritc = CS.ritc_flag(key).astype(bool)
    syn = np.array([o["syndicate"] for o in recs])
    fold = BT.fold_assignment(syn, 10)
    th = BT.operator_params(MEANS)
    q = BT.leave_out_quantiles(S, R, H, ritc, fold, syn, yr, {f: th for f in range(10)}, CFG, False)
    assert out["n"] == len(recs) and out["n_syndicates"] == 24 and out["honest"]["folds"] == 10
    for a in BT.LEVELS:
        key_a = "%g" % a
        for m in BT.METHODS:
            want = int((S > q[m][a]).sum())
            assert out["honest"]["pool_rules"]["leave_out"][m][key_a]["exceedances"]["all"] == want, (m, a)
        flags = out["per_target"]["exceedance_flags"]["honest_plug_in"]["leave_out"][key_a]
        assert flags == (S > q[BT.OPERATOR_METHOD][a]).astype(int).tolist()
    # the posterior-draw version: 8 draws around the same means, so its VaRs are the plug-in's to within the draw spread
    assert out["honest_posterior_draws"]["draws_per_fold"] == BT.N_PRED_DRAWS
    for a in BT.LEVELS:
        assert len(out["per_target"]["exceedance_flags"]["honest_posterior_draws"]["leave_out"]["%g" % a]) == len(recs)


def test_the_quartile_tables_add_up_to_the_totals_and_the_flags(run):
    recs, _fits_, out = run
    n = len(recs)
    pt = out["per_target"]
    assert len(pt["targets"]["syndicate"]) == n == len(pt["targets"]["size_quartile"])
    assert sorted(set(pt["targets"]["size_quartile"])) == [1, 2, 3, 4]
    for src in ("honest_plug_in", "honest_posterior_draws"):
        for rule in BT.POOL_RULES:
            for a in ("0.99", "0.995"):
                tab = pt["by_size_quartile"][src][rule][a]
                flags = pt["exceedance_flags"][src][rule][a]
                assert sum(tab["size_quartile_%d" % j]["n_targets"] for j in (1, 2, 3, 4)) == n
                assert sum(tab["size_quartile_%d" % j]["exceedances"] for j in (1, 2, 3, 4)) == sum(flags)
                for j in (1, 2, 3, 4):
                    row = tab["size_quartile_%d" % j]
                    lo, hi = row["rate_credible_interval_95"]
                    assert lo <= row["rate_mean"] <= hi and 0.0 <= row["p_rate_above_nominal"] <= 1.0
                    assert row["expected"] == pytest.approx(row["n_targets"] * (1.0 - float(a)))
    assert set(pt["vignette_size_quartiles"]) == {"V1", "V2_old", "V2_new"}
    assert pt["by_size_quartile"]["edges_gbp_m"] == out["size_quartiles"]["edges_gbp_m"]


def test_the_depth_tables_are_set_beside_the_primarys_committed_ones(run):
    _recs_, _fits_, out = run
    cmp_ = D.against_primary_backtest(out)
    prim = SS.load_json(D.BACKTEST_RECORD)
    assert cmp_["primary_n"] == prim["n"] and cmp_["depth_n"] == out["n"]
    for src in ("honest_plug_in", "honest_posterior_draws"):
        for a in ("0.99", "0.995"):
            row = cmp_[src][a]
            assert len(row["primary"]["exceedances"]) == len(row["t_minus_3"]["exceedances"]) == 4
            assert sum(row["primary"]["exceedances"]) == sum(
                prim["per_target"]["exceedance_flags"][src]["leave_out"][a])
            assert sum(row["t_minus_3"]["exceedances"]) == sum(out["per_target"]["exceedance_flags"][src]["leave_out"][a])
    assert D.against_primary_backtest(out, path=os.path.join(HERE, "results", "no_such_record.json")) is None


# ------------------------------------------------------------------ the two depths on one sample
def _two_depths(seed=5):
    """The same records at two depths: R, syndicates and years identical, the severities of the second a different draw
    (some records exceed at one depth only)."""
    recs2 = _recs(seed=11)
    rng = np.random.default_rng(seed)
    recs3 = [dict(o, s_raw_a=float(o["s_raw_a"] + rng.normal(0, 0.05))) for o in recs2]
    fits = _fits()
    return recs2, recs3, D.honest_backtest(recs2, CFG, fits=fits, depth="t_minus_2"), \
        D.honest_backtest(recs3, CFG, fits=fits, depth="t_minus_3")


@pytest.fixture(scope="module")
def depths():
    mp = pytest.MonkeyPatch()
    deal_on_the_fly(mp)
    try:
        return _two_depths()
    finally:
        mp.undo()


def test_the_depth_names_the_backtest_and_an_unknown_depth_is_refused(depths):
    _r2, _r3, h2, h3 = depths
    assert h2["depth"] == "t_minus_2" and "u <= t-2" in h2["label"] and "u <= t-3" not in h2["label"]
    assert h3["depth"] == "t_minus_3" and "u <= t-3" in h3["label"] and "u <= t-2" not in h3["label"]
    assert "u <= t-2" in h2["honest"]["label"] and "u <= t-3" in h3["honest"]["label"]
    with pytest.raises(SystemExit, match="unknown outcome depth"):
        D.honest_backtest(_recs(), CFG, fits=_fits(), depth="t_minus_4")


def test_each_depth_scores_its_own_severities_on_the_same_targets(depths):
    """A mutation that scores the t-3 severities with the t-2 backtest (or the reverse) changes the flags."""
    recs2, recs3, h2, h3 = depths
    assert h2["per_target"]["targets"] == h3["per_target"]["targets"]
    S2 = np.array([o["s_raw_a"] for o in recs2])
    S3 = np.array([o["s_raw_a"] for o in recs3])
    assert not np.array_equal(S2, S3)
    thetas = {f: BT.operator_params(MEANS) for f in range(10)}
    var = {}
    for depth, recs in (("t_minus_2", recs2), ("t_minus_3", recs3)):
        S, R, H, yr, key = CS.arrays(recs)
        syn = np.array([o["syndicate"] for o in recs])
        var[depth] = (S, BT.leave_out_quantiles(S, R, H, CS.ritc_flag(key).astype(bool), BT.fold_assignment(syn, 10), syn,
                                                yr, thetas, CFG, False)[BT.OPERATOR_METHOD])
    for a in ("0.99", "0.995"):
        for depth, h in (("t_minus_2", h2), ("t_minus_3", h3)):
            S, q = var[depth]
            assert h["per_target"]["exceedance_flags"]["honest_plug_in"]["leave_out"][a] == (
                S > q[float(a)]).astype(int).tolist(), (depth, a)
    # the two depths' flags differ somewhere, so a mutation that scores one depth with the other's severities is seen
    assert any(h2["per_target"]["exceedance_flags"]["honest_plug_in"]["leave_out"][a]
               != h3["per_target"]["exceedance_flags"]["honest_plug_in"]["leave_out"][a] for a in ("0.99", "0.995"))


def test_the_side_by_side_table_adds_up_and_names_the_targets_whose_flag_differs(depths):
    _r2, _r3, h2, h3 = depths
    sb = D.depths_side_by_side(h2, h3)
    n = h2["n"]
    assert sb["n"] == n and sb["size_quartile_edges_gbp_m"] == h2["size_quartiles"]["edges_gbp_m"] == h3["size_quartiles"]["edges_gbp_m"]
    t = h2["per_target"]["targets"]
    for src in ("honest_plug_in", "honest_posterior_draws"):
        for rule in BT.POOL_RULES:
            for a in D.SIDE_LEVELS:
                f2 = h2["per_target"]["exceedance_flags"][src][rule][a]
                f3 = h3["per_target"]["exceedance_flags"][src][rule][a]
                blk = sb[src][rule][a]
                assert blk["total"]["t_minus_2"] == sum(f2) and blk["total"]["t_minus_3"] == sum(f3)
                assert blk["total"]["expected"] == pytest.approx(n * (1.0 - float(a)))
                tot = {"both": 0, "only2": 0, "only3": 0}
                for j in (1, 2, 3, 4):
                    row = blk["by_size_quartile"]["size_quartile_%d" % j]
                    idx = [i for i in range(n) if t["size_quartile"][i] == j]
                    assert row["n_targets"] == len(idx) and row["expected"] == pytest.approx(len(idx) * (1 - float(a)))
                    assert row["t_minus_2"]["exceedances"] == sum(f2[i] for i in idx)
                    assert row["t_minus_3"]["exceedances"] == sum(f3[i] for i in idx)
                    assert row["exceed_at_both"] + row["only_at_t_minus_2"] == row["t_minus_2"]["exceedances"]
                    assert row["exceed_at_both"] + row["only_at_t_minus_3"] == row["t_minus_3"]["exceedances"]
                    for d in ("t_minus_2", "t_minus_3"):
                        lo, hi = row[d]["rate_credible_interval_95"]
                        assert lo <= row[d]["rate_mean"] <= hi and 0.0 <= row[d]["p_rate_above_nominal"] <= 1.0
                    tot["both"] += row["exceed_at_both"]
                    tot["only2"] += row["only_at_t_minus_2"]
                    tot["only3"] += row["only_at_t_minus_3"]
                assert tot["both"] + tot["only2"] == sum(f2) and tot["both"] + tot["only3"] == sum(f3)
                if rule == "leave_out":
                    diff = blk["targets_whose_flag_differs"]
                    assert len(diff) == tot["only2"] + tot["only3"] == sum(1 for x, y in zip(f2, f3) if x != y)
                    for d in diff:
                        i = next(i for i in range(n) if (t["syndicate"][i], t["year"][i]) == (d["syndicate"], d["year"]))
                        assert d["exceeds_at_t_minus_2"] == bool(f2[i]) and d["exceeds_at_t_minus_3"] == bool(f3[i])
                        assert d["exceeds_at_t_minus_2"] != d["exceeds_at_t_minus_3"] and d["size_quartile"] == t["size_quartile"][i]
                else:
                    assert "targets_whose_flag_differs" not in blk
    assert any(sb["honest_plug_in"]["leave_out"][a]["targets_whose_flag_differs"] for a in D.SIDE_LEVELS)


def test_the_side_by_side_table_refuses_two_backtests_that_are_not_on_the_same_targets(depths):
    recs2, _r3, h2, h3 = depths
    other = [dict(o, opening_reserves_gbp_m=o["opening_reserves_gbp_m"] * (1.5 if i == 3 else 1.0)) for i, o in enumerate(recs2)]
    h_other = D.honest_backtest(other, CFG, fits=_fits(), depth="t_minus_3")
    with pytest.raises(SystemExit, match="not on the same targets"):
        D.depths_side_by_side(h2, h_other)
    h_edges = json.loads(json.dumps(h3))
    h_edges["size_quartiles"]["edges_gbp_m"][0] += 1.0
    with pytest.raises(SystemExit, match="edges"):
        D.depths_side_by_side(h2, h_edges)
    fewer = json.loads(json.dumps(h3))
    fewer["per_target"]["targets"]["year"][0] += 1
    with pytest.raises(SystemExit, match="year"):
        D.depths_side_by_side(h2, fewer)


def test_the_comparison_with_the_primary_says_it_differs_in_sample_and_edges_and_adds_the_t_minus_2_rows(depths):
    _r2, _r3, h2, h3 = depths
    cmp_ = D.against_primary_backtest(h3, honest_t2=h2)
    assert "sample" in cmp_["differs_in"] and "edges" in cmp_["differs_in"] and "not a like-for-like" in cmp_["differs_in"]
    row = cmp_["honest_plug_in"]["0.99"]
    assert set(row) == {"primary", "t_minus_2_on_the_kept_records", "t_minus_3"}
    assert row["t_minus_2_on_the_kept_records"]["exceedances"] == [
        h2["per_target"]["by_size_quartile"]["honest_plug_in"]["leave_out"]["0.99"]["size_quartile_%d" % j]["exceedances"]
        for j in (1, 2, 3, 4)]
    assert set(D.against_primary_backtest(h3)["honest_plug_in"]["0.99"]) == {"primary", "t_minus_3"}


def _left(keys_reasons):
    return [{"record": k, "reason": r} for k, r in keys_reasons]


def test_the_left_out_records_are_counted_by_the_primarys_size_quartile_reason_and_syndicate():
    """A primary of 8 records with R = 10, 20, ..., 80 (edges 27.5, 45, 62.5: two records per quartile); the records left
    out are counted in the quartile of their own R, with their reason and syndicate, and syndicate 1991 is named."""
    recs = [{"syndicate": s, "year": 2015 + i % 2, "opening_reserves_gbp_m": 10.0 * (i + 1)}
            for i, s in enumerate([1991, 1991, 5, 6, 7, 7, 8, 9])]
    left = _left([("1991_2015", "no_figure_at_t_minus_3"), ("1991_2016", "figure_not_reproduced_from_a_stored_grid"),
                  ("7_2015", "no_figure_at_t_minus_3"), ("9_2016", "no_figure_at_t_minus_3")])
    out = D.left_out_by_primary_size_quartile(recs, left)
    assert out["n_primary_in_quartile"] == [2, 2, 2, 2]
    q = [out["size_quartile_%d" % j] for j in (1, 2, 3, 4)]
    assert [x["n_left_out"] for x in q] == [2, 0, 1, 1]
    assert [x["share_left_out"] for x in q] == [1.0, 0.0, 0.5, 0.5]
    assert q[0]["by_reason"]["no_figure_at_t_minus_3"] == 1 and q[0]["by_reason"]["figure_not_reproduced_from_a_stored_grid"] == 1
    assert q[0]["syndicates"] == [1991] and q[2]["syndicates"] == [7] and q[3]["syndicates"] == [9]
    assert sum(x["n_left_out"] for x in q) == len(left)
    assert out["syndicate_1991"]["n_left_out"] == 2
    assert [r["record"] for r in out["syndicate_1991"]["records"]] == ["1991_2015", "1991_2016"]
    assert all(r["primary_size_quartile"] == 1 for r in out["syndicate_1991"]["records"])
    assert list(out["by_syndicate"])[0] == "1991"
    assert out["edges_gbp_m"] == pytest.approx([27.5, 45.0, 62.5])
    # a mutation to the quartile of the LEFT-OUT records alone (their own R among themselves) would put both of 7's and 9's
    # records in other quartiles; the primary's edges are what count
    none = D.left_out_by_primary_size_quartile(recs, [])
    assert none["syndicate_1991"] == {"n_left_out": 0, "records": []} and none["size_quartile_1"]["n_left_out"] == 0


# ------------------------------------------------------------------ the committed record (DEFERRED-TO-REFIT)
def test_the_committed_record_holds_the_two_depths_on_the_same_kept_records_and_the_left_out_composition():
    """DEFERRED-TO-REFIT: written by the recorded pass. (Named for the 592 kept records of the 649-record primary
    until the recorded pass of 38cd750; the kept records are 581 of the 643, so the name no longer carries a count.)"""
    with io.open(os.path.join(HERE, "results", "check_cohort_depth_sensitivity_results.json"), encoding="utf-8") as fh:
        rec = json.load(fh)
    h2, h3 = rec["honest_backtest_t_minus_2_on_the_kept_records"], rec["honest_backtest_t_minus_3"]
    sb = rec["honest_t_minus_2_vs_t_minus_3"]
    assert h2["depth"] == "t_minus_2" and h3["depth"] == "t_minus_3" and h2["n"] == h3["n"] == sb["n"] == rec["n_kept"]
    assert h2["per_target"]["targets"] == h3["per_target"]["targets"]
    assert sb["size_quartile_edges_gbp_m"] == h2["size_quartiles"]["edges_gbp_m"] == h3["size_quartiles"]["edges_gbp_m"]
    assert all(f["diagnostics"]["divergences"] == 0 and f["diagnostics"]["max_rhat"] <= 1.01 for f in h2["honest"]["fits"])
    assert len(h2["honest"]["fits"]) == 10
    for src in ("honest_plug_in", "honest_posterior_draws"):
        for a in D.SIDE_LEVELS:
            blk = sb[src]["leave_out"][a]
            assert blk["total"]["t_minus_2"] == sum(h2["per_target"]["exceedance_flags"][src]["leave_out"][a])
            assert blk["total"]["t_minus_3"] == sum(h3["per_target"]["exceedance_flags"][src]["leave_out"][a])
            assert sum(blk["by_size_quartile"]["size_quartile_%d" % j]["t_minus_2"]["exceedances"] for j in (1, 2, 3, 4)) \
                == blk["total"]["t_minus_2"]
            assert len(blk["targets_whose_flag_differs"]) == sum(
                1 for x, y in zip(h2["per_target"]["exceedance_flags"][src]["leave_out"][a],
                                  h3["per_target"]["exceedance_flags"][src]["leave_out"][a]) if x != y)
    lo = rec["left_out_by_primary_size_quartile"]
    prim = SS.load_json(D.BACKTEST_RECORD)
    assert lo["edges_gbp_m"] == pytest.approx(prim["size_quartiles"]["edges_gbp_m"])
    assert sum(lo["n_primary_in_quartile"]) == rec["n_primary"] == prim["n"]
    assert sum(lo["size_quartile_%d" % j]["n_left_out"] for j in (1, 2, 3, 4)) == rec["n_left_out"]
    for j in (1, 2, 3, 4):
        q = lo["size_quartile_%d" % j]
        assert q["n_primary"] == lo["n_primary_in_quartile"][j - 1] and len(q["records"]) == q["n_left_out"]
        assert sum(q["by_reason"].values()) == q["n_left_out"]
    for r in D.REASONS:
        assert sum(lo["size_quartile_%d" % j]["by_reason"][r] for j in (1, 2, 3, 4)) == rec["left_out_by_reason"][r]
    assert sum(v["n_left_out"] for v in lo["by_syndicate"].values()) == rec["n_left_out"]
    assert [r["record"] for r in lo["syndicate_1991"]["records"]] == ["1991_2015", "1991_2018"]
    # the quartile of a record in the table is the one the primary's committed backtest gives it
    pq = {(s, y): q for s, y, q in zip(prim["per_target"]["targets"]["syndicate"], prim["per_target"]["targets"]["year"],
                                      prim["per_target"]["targets"]["size_quartile"])}
    for s, v in lo["by_syndicate"].items():
        for r in v["records"]:
            syn, yr = (int(x) for x in r["record"].split("_"))
            assert pq[(syn, yr)] == r["primary_size_quartile"], r


def test_the_docstring_states_the_left_out_composition_by_pointing_to_the_record_not_by_copying_it():
    """The script's docstring carries no count of the records left out (a count there drifts from the record at every
    regeneration, and the cohort-depth repair of 26 October 2026 moved them): it points to the record's tables and states
    the mechanisms. The record, once written, is internally consistent (the tests above)."""
    doc = " ".join(D.__doc__.split())
    for stale in (r"\d+ of its \d+ smallest books", r"\d+ of \d+ in quartile 2", r"\d+ have no figure on u <= t-3",
                  r"\d+ have a figure no stored grid reproduces", r"\d+ records left out are not a random",
                  r"Syndicate 382 has \w+", r"\w+-?\w* syndicates have a record left out", r"against 198/458/913",
                  r"on the 581 kept", r"carries six of the primary's eight exceedances"):
        assert not re.search(stale, doc), stale
    for needle in ("left_out_by_primary_size_quartile in the record", "partition_before_repair",
                   "OUTSIDE a test of that cell by construction", "not a test of the primary's quartile 1",
                   "An empty set is NEVER zero", "cohort-depth repair (26 October 2026", "derived 2012 cell".replace("derived", "DERIVED")):
        assert needle in doc, needle
    assert "1274/2016 uses the register's DERIVED 2012 cell at both depths" in doc
    assert "3334/2018 and 3500/2018 enter as single-cohort t-3 figures" in doc


def test_the_committed_record_holds_the_honest_backtest_on_the_kept_records():
    """DEFERRED-TO-REFIT: written by the recorded pass."""
    with io.open(os.path.join(HERE, "results", "check_cohort_depth_sensitivity_results.json"), encoding="utf-8") as fh:
        rec = json.load(fh)
    hb = rec["honest_backtest_t_minus_3"]
    assert hb["n"] == rec["n_kept"] == len(hb["per_target"]["targets"]["syndicate"])
    assert hb["honest"]["folds"] == 10 and len(hb["honest"]["fits"]) == 10
    assert all(f["diagnostics"]["divergences"] == 0 and f["diagnostics"]["max_rhat"] <= 1.01 for f in hb["honest"]["fits"])
    assert (hb["operator"], hb["operator_role"]) == ("size_only", "headline")
    for src in ("honest_plug_in", "honest_posterior_draws"):
        for a in ("0.99", "0.995"):
            tab = hb["per_target"]["by_size_quartile"][src]["leave_out"][a]
            flags = hb["per_target"]["exceedance_flags"][src]["leave_out"][a]
            assert sum(tab["size_quartile_%d" % j]["exceedances"] for j in (1, 2, 3, 4)) == sum(flags)
            assert sum(tab["size_quartile_%d" % j]["n_targets"] for j in (1, 2, 3, 4)) == rec["n_kept"]
    assert hb["against_the_primarys_backtest"]["depth_n"] == rec["n_kept"]
    assert "runtime_seconds" in hb
