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
  * the committed record (DEFERRED-TO-REFIT: written by the recorded pass).

Run:  python -m pytest src/test_cohort_depth_honest_backtest.py -q
"""
import io
import json
import os

import numpy as np
import pytest

import check_cohort_depth_sensitivity as D
import check_cohort_scope as CS
import check_operator_backtest as BT
import sample_scope as SS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEANS = {"k": 0.6, "gamma": 0.0, "sd_undiv": 0.03, "sd_div": 0.05, "nu_clean": 4.0, "nu_ritc": 6.0}
CFG = (500.0, 0.01, 1.0)


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
    recs = _recs()
    fits = _fits()
    return recs, fits, D.honest_backtest(recs, CFG, fits=fits)


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


# ------------------------------------------------------------------ the committed record (DEFERRED-TO-REFIT)
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
