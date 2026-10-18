#!/usr/bin/env python3
"""The operator backtest (check_operator_backtest.py): the scoring, the folds, the sqrt(R) figures and the record.

The backtest scores the headline operator, out of sample, against the raw pool and the simple sqrt(R) scaling. Its
claim is only as good as its parts, so each is held to a hand-computed case:

  * the fold assignment is oos_validation's own, extracted into one helper and pinned: the helper returns what the
    original expression returned (a literal mapping, and a digest of the real sample's syndicate-to-fold map taken
    from the original code before it was extracted), and oos_validation.main and the backtest both call it;
  * the scoring: the pinball loss, the size quartiles, the pool each target is scored against (its own syndicate or
    fold, and optionally its reporting year, never in it), the sqrt(R) rule, the operator's identity at an equal
    book and its independence of H at gamma = 0, the counts against the expected counts, the bootstrap rates;
  * the vignette figures: the sqrt(R) and operator VaRs from the same pool and var_q, the operator's equal to
    check_gamma0_vignette.py's record or nothing is written;
  * the committed record: form, clean sampling of the ten fold refits, the folds equal to oos_validation's, counts
    that add up, and exceedances that cannot rise with the level.

Run:  python -m pytest src/test_operator_backtest.py -q
"""
import ast
import hashlib
import io
import json
import os
import re

import numpy as np
import pytest

import adopted_model as am
import check_operator_backtest as BT
import oos_validation as OV
import transfer_operator as TO
from pool_quantile import var_q
from vignette_uncertainty import transfer

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")
CFG = (500.0, 0.01, 1.0)


def _json(rel):
    with io.open(os.path.join(HERE, rel), encoding="utf-8") as _fh:
        return json.load(_fh)


def _tree(script):
    with io.open(os.path.join(SRC, script), encoding="utf-8") as _fh:
        return ast.parse(_fh.read())


# ------------------------------------------------------------------ the folds ------
def test_the_helper_deals_the_sorted_syndicates_out_in_turn():
    syn = np.array([30, 10, 20, 10, 50, 40, 30, 60, 70])
    # sorted syndicates 10, 20, 30, 40, 50, 60, 70 go to folds 0, 1, 2, 0, 1, 2, 0
    want = {10: 0, 20: 1, 30: 2, 40: 0, 50: 1, 60: 2, 70: 0}
    assert OV.fold_assignment(syn, 3).tolist() == [want[s] for s in syn.tolist()]
    assert OV.fold_assignment(syn).tolist() == [{10: 0, 20: 1, 30: 2, 40: 3, 50: 4, 60: 0, 70: 1}[s] for s in syn.tolist()]
    assert OV.K == 5


def test_a_whole_syndicate_is_in_one_fold():
    syn = np.repeat(np.arange(20, 0, -1), 3)
    f = OV.fold_assignment(syn, 4)
    for s in set(syn.tolist()):
        assert len(set(f[syn == s].tolist())) == 1


def _digest(syn, k):
    uniq = sorted(set(syn.tolist()))
    f = OV.fold_assignment(syn, k)
    pairs = ",".join("%s:%d" % (s, f[syn == s][0]) for s in uniq)
    return hashlib.sha256(pairs.encode()).hexdigest()


def test_the_real_samples_folds_are_the_ones_oos_validation_used_before_the_extraction():
    """Digests of the syndicate-to-fold map of the 118 syndicates, taken from the original inline expression."""
    syn = am.load_sample()[4]
    assert len(set(syn.tolist())) == 118
    assert _digest(syn, 5) == "f44a6ca19dc52276cd42c8da78718d7f9d8b9af86385c7b3a7cd6bd9cbbd8885"
    assert _digest(syn, 10) == "7e9200380ac8a5305985ff3ee8a5969a5518d8192211b4fc7713bcde8628c31a"
    # and oos_validation's own loader gives the same syndicates as the model's sample
    assert OV.load()[3].tolist() == syn.tolist()


def test_oos_validation_and_the_backtest_both_call_the_helper():
    main = [n for n in _tree("oos_validation.py").body if isinstance(n, ast.FunctionDef) and n.name == "main"][0]
    assert any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == "fold_assignment" for c in ast.walk(main))
    assert not any(isinstance(n, ast.Name) and n.id == "fold_of" for n in ast.walk(main)), "the rule is retyped in main"
    assert BT.fold_assignment is OV.fold_assignment
    bt = _tree("check_operator_backtest.py")
    assert not any(isinstance(n, ast.Name) and n.id == "fold_of" for n in ast.walk(bt)), "the backtest retypes the rule"


# ------------------------------------------------------------------ the scoring ------
def test_the_pinball_loss():
    # S at or above the forecast costs a (S - q); below it costs (1 - a) (q - S)
    assert BT.pinball(1.0, 0.5, 0.9) == pytest.approx(0.45)
    assert BT.pinball(0.0, 0.5, 0.9) == pytest.approx(0.05)
    assert BT.pinball(0.5, 0.5, 0.9) == pytest.approx(0.0)
    assert BT.pinball(np.array([1.0, 0.0]), np.array([0.5, 0.5]), 0.5).tolist() == [0.25, 0.25]
    # a level-a quantile minimises it: the loss at the true 90% point of a uniform sample beats a shifted forecast
    x = np.linspace(0, 1, 1001)
    best = BT.pinball(x, 0.9, 0.9).mean()
    assert best < BT.pinball(x, 0.8, 0.9).mean() and best < BT.pinball(x, 0.99, 0.9).mean()


def test_the_size_quartiles():
    edges, idx = BT.size_quartiles(np.arange(1.0, 9.0))
    assert edges.tolist() == [2.75, 4.5, 6.25]
    assert idx.tolist() == [0, 0, 1, 1, 2, 2, 3, 3]
    _e, tied = BT.size_quartiles(np.array([1.0, 2.0, 2.0, 2.0, 3.0, 4.0, 5.0, 6.0]))
    assert set(tied.tolist()) <= {0, 1, 2, 3}


#: a gamma = 0 fit's means: since option B (10 October 2026) every fit here, the fold refits and the headline, has gamma
#: fixed at 0 in the likelihood
TH = {"k": 0.6, "gamma": 0.0, "sd_undiv": 0.03, "sd_div": 0.06, "nu_clean": 5.0, "nu_ritc": 7.0}


def _head(th=TH):
    return BT.operator_params(th)


def test_there_is_no_overlay_method_and_a_fitted_gamma_is_refused():
    """The fits have gamma = 0, so there is no fitted exponent for an overlay: no overlay method, and the operator's
    parameters refuse a fitted gamma rather than zero it (the retired construction)."""
    assert BT.METHODS == ("raw_pool", "sqrt_R", "operator_size_only")
    assert "gamma" not in BT.FIT_PARAMS and "gamma" in BT.OPERATOR_PARAMS
    with pytest.raises(ValueError):
        BT.operator_params(dict(TH, gamma=0.4))


def test_the_three_pools_for_one_target():
    Sp = np.array([0.02, -0.01, 0.05, 0.1])
    Rp = np.array([100.0, 400.0, 900.0, 2500.0])
    Hp = np.array([0.1, 0.2, 0.3, 0.4])
    rp = np.zeros(4, bool)
    head = _head()
    pools = BT.method_pools(Sp, Rp, Hp, rp, (400.0, 0.2), head, CFG)
    assert list(pools) == list(BT.METHODS)
    assert np.array_equal(pools["raw_pool"], Sp)
    assert np.allclose(pools["sqrt_R"], Sp * np.sqrt(Rp / 400.0), rtol=1e-14, atol=0)      # the stated rule
    assert np.allclose(pools["sqrt_R"], [0.02 * 0.5, -0.01, 0.05 * 1.5, 0.1 * 2.5])
    # the operator at an equal book and an equal concentration leaves the severity as it was
    assert pools["operator_size_only"][1] == pytest.approx(-0.01, rel=1e-12)
    # gamma = 0: the size-only pool does not depend on the target's H, and does on its R
    a = BT.method_pools(Sp, Rp, Hp, rp, (900.0, 0.05), head, CFG)
    b = BT.method_pools(Sp, Rp, Hp, rp, (900.0, 0.9), head, CFG)
    c = BT.method_pools(Sp, Rp, Hp, rp, (300.0, 0.05), head, CFG)
    assert np.array_equal(a["operator_size_only"], b["operator_size_only"])
    assert not np.allclose(a["operator_size_only"], c["operator_size_only"])


def test_the_operator_pool_is_the_published_transfer():
    Sp = np.array([0.02, -0.01, 0.05, 0.1, 0.3])
    Rp = np.array([100.0, 400.0, 900.0, 2500.0, 50.0])
    Hp = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    rp = np.array([False, False, False, False, True])
    head = _head()
    pools = BT.method_pools(Sp, Rp, Hp, rp, (700.0, 0.25), head, CFG)
    assert np.array_equal(pools["operator_size_only"], transfer(Sp, Rp, Hp, (700.0, 0.25), head, CFG, rp))
    plain = transfer(Sp, Rp, Hp, (700.0, 0.25), head, CFG, np.zeros(5, bool))
    assert plain[4] != pools["operator_size_only"][4], "the de-RITC map did not act on the RITC donor"


def _toy(n_syn=4, per=3):
    rng = np.random.default_rng(3)
    n = n_syn * per
    syn = np.repeat(np.arange(n_syn) + 100, per)
    yr = np.tile(np.arange(2015, 2015 + per), n_syn)
    S = rng.normal(0, 0.05, n)
    R = np.exp(rng.normal(np.log(300), 1.0, n))
    H = rng.uniform(0.05, 0.5, n)
    ritc = np.zeros(n, bool)
    ritc[[2, 7]] = True
    return S, R, H, ritc, syn, yr


def test_a_target_is_never_scored_against_its_own_syndicate_or_year():
    S, R, H, ritc, syn, yr = _toy()
    thetas = {s: _head() for s in set(syn.tolist())}
    for drop in (False, True):
        q = BT.leave_out_quantiles(S, R, H, ritc, syn, syn, yr, thetas, CFG, drop, (0.5, 0.9))
        for i in range(len(S)):
            keep = syn != syn[i]
            if drop:
                keep &= yr != yr[i]
            for a in (0.5, 0.9):
                assert q["raw_pool"][a][i] == var_q(S[keep], a), (drop, i, a)
                assert q["sqrt_R"][a][i] == var_q(S[keep] * np.sqrt(R[keep] / R[i]), a)
                want = var_q(transfer(S[keep], R[keep], H[keep], (R[i], H[i]), thetas[syn[i]], CFG, ritc[keep]), a)
                assert q["operator_size_only"][a][i] == want


def test_each_held_out_unit_uses_its_own_parameters():
    S, R, H, ritc, syn, yr = _toy()
    lo = dict(TH, k=0.55)
    hi = dict(TH, k=0.95)
    thetas = {100: _head(lo), 101: _head(hi), 102: _head(lo), 103: _head(hi)}
    q = BT.leave_out_quantiles(S, R, H, ritc, syn, syn, yr, thetas, CFG, False, (0.9,))
    for i in (0, 3, 6, 9):
        th = thetas[syn[i]]
        keep = syn != syn[i]
        assert q["operator_size_only"][0.9][i] == var_q(transfer(S[keep], R[keep], H[keep], (R[i], H[i]), th, CFG,
                                                                  ritc[keep]), 0.9)
    swapped = {s: thetas[{100: 101, 101: 100, 102: 103, 103: 102}[s]] for s in thetas}
    q2 = BT.leave_out_quantiles(S, R, H, ritc, syn, syn, yr, swapped, CFG, False, (0.9,))
    assert not np.array_equal(q["operator_size_only"][0.9], q2["operator_size_only"][0.9])


def test_a_fold_pool_excludes_the_whole_fold():
    S, R, H, ritc, syn, yr = _toy(n_syn=6, per=2)
    fold = OV.fold_assignment(syn, 3)
    thetas = {f: _head() for f in range(3)}
    q = BT.leave_out_quantiles(S, R, H, ritc, fold, syn, yr, thetas, CFG, False, (0.9,))
    for i in range(len(S)):
        assert q["raw_pool"][0.9][i] == var_q(S[fold != fold[i]], 0.9)


def test_the_bootstrap_weights_share_a_syndicates_weight_and_sum_to_one_over_syndicates():
    syn = np.array([5, 5, 5, 9, 9, 2])
    W = BT.bayes_bootstrap_weights(syn, reps=50, seed=1)
    assert W.shape == (50, 6)
    assert np.array_equal(W[:, 0], W[:, 1]) and np.array_equal(W[:, 1], W[:, 2]) and np.array_equal(W[:, 3], W[:, 4])
    assert np.allclose(W[:, 0] + W[:, 3] + W[:, 5], 1.0)
    assert np.array_equal(W, BT.bayes_bootstrap_weights(syn, reps=50, seed=1))


def test_the_rate_posterior_under_equal_weights_is_the_share():
    exc = np.array([True, False, False, True, False])
    W = np.ones((7, 5))
    r = BT.rate_posterior(exc, np.ones(5, bool), W, 0.1)
    assert (r["mean"], r["lo"], r["hi"]) == pytest.approx((0.4, 0.4, 0.4)) and r["share_above_nominal"] == 1.0
    sub = BT.rate_posterior(exc, np.array([True, True, True, False, False]), W, 0.5)
    assert sub["mean"] == pytest.approx(1 / 3) and sub["share_above_nominal"] == 0.0 and sub["nominal"] == 0.5
    # a syndicate carrying all the weight sets the rate
    W2 = np.zeros((3, 5))
    W2[:, 0] = 1.0
    assert BT.rate_posterior(exc, np.ones(5, bool), W2, 0.1)["mean"] == 1.0


def test_the_summary_counts_against_expectations_by_group():
    S = np.array([0.5, 0.1, 0.9, 0.2, 0.3, 0.8, 0.0, 0.4])
    q = {0.9: np.full(8, 0.45), 0.5: np.full(8, 0.25)}
    quart = np.array([0, 0, 1, 1, 2, 2, 3, 3])
    ritc = np.array([False, False, False, False, False, True, True, False])
    out = BT.summarise_method(S, q, quart, ritc, np.ones((3, 8)), levels=(0.9, 0.5))
    a = out["0.9"]
    assert a["exceedances"]["all"] == 3                                   # 0.5, 0.9, 0.8
    assert a["exceedances"]["clean"] == 2 and a["exceedances"]["ritc"] == 1
    assert [a["exceedances"]["size_quartile_%d" % j] for j in (1, 2, 3, 4)] == [1, 1, 1, 0]
    assert a["expected"]["all"] == pytest.approx(0.8) and a["expected"]["size_quartile_1"] == pytest.approx(0.2)
    assert a["expected"]["ritc"] == pytest.approx(0.2) and a["expected"]["clean"] == pytest.approx(0.6)
    loss = BT.pinball(S, q[0.9], 0.9)
    assert a["pinball_mean"]["all"] == pytest.approx(loss.mean())
    assert a["pinball_mean"]["ritc"] == pytest.approx(loss[ritc].mean())
    assert a["rate_bayes_bootstrap"]["all"]["mean"] == pytest.approx(3 / 8)
    assert out["0.5"]["exceedances"]["all"] == 5                          # 0.5, 0.9, 0.3, 0.8, 0.4
    # an outcome equal to the VaR is not an exceedance
    tie = BT.summarise_method(np.array([1.0, 2.0]), {0.9: np.array([1.0, 1.0])}, np.array([0, 1]),
                              np.zeros(2, bool), np.ones((2, 2)), levels=(0.9,))
    assert tie["0.9"]["exceedances"]["all"] == 1


# ------------------------------------------------------------------ the vignette figures ------
@pytest.fixture(scope="module")
def vig():
    """The headline draws and the vignette record are the regeneration's."""
    pool = BT.load_pool()
    ritc = BT.load_ritc(pool[3], pool[4])
    draws, ref, hlo, hce = BT.load_draws()
    targets = BT.load_targets()
    recorded = _json("results/check_gamma0_vignette_results.json")
    return pool, ritc, draws, (ref, hlo, hce), targets, recorded


def test_the_sqrt_r_figures_are_the_rule_applied_to_the_published_pool(vig):
    pool, ritc, draws, cfg, targets, recorded = vig
    out = BT.vignette_figures(pool, ritc, draws, cfg, targets, recorded)
    S, R = pool[0], pool[1]
    (r1, _h1), (r2o, _ho), (r2n, _hn) = targets
    assert out["sqrt_R"]["V1"]["v995"] == var_q(S * np.sqrt(R / r1), 0.995)
    assert out["sqrt_R"]["V1"]["v99"] == var_q(S * np.sqrt(R / r1), 0.99)
    assert out["sqrt_R"]["V2_new"]["v995"] == var_q(S * np.sqrt(R / r2n), 0.995)
    assert out["sqrt_R"]["V2_d995"] == var_q(S * np.sqrt(R / r2n), 0.995) - var_q(S * np.sqrt(R / r2o), 0.995)
    assert out["raw_pool"] == {"v99": var_q(S, 0.99), "v995": var_q(S, 0.995)}
    assert out["operator_size_only"]["V1"]["v995"] == recorded[TO.HEADLINE]["centre"]["V1_v995"]
    assert out["operator_size_only"]["V2_d995"] == recorded[TO.HEADLINE]["centre"]["V2_d995"]
    assert (out["operator"], out["operator_role"]) == ("size_only", "headline")
    # the three differ: the check can tell the sqrt(R) scaling from the operator and from the raw pool
    assert len({out["raw_pool"]["v995"], out["sqrt_R"]["V1"]["v995"], out["operator_size_only"]["V1"]["v995"]}) == 3
    assert out["sqrt_R_over_operator"]["V1_v995"] == out["sqrt_R"]["V1"]["v995"] / out["operator_size_only"]["V1"]["v995"]


def test_the_figures_are_refused_when_the_operator_departs_from_the_record(vig):
    pool, ritc, draws, cfg, targets, recorded = vig
    bad = json.loads(json.dumps(recorded))
    bad[TO.HEADLINE]["centre"]["V1_v995"] += 1e-9
    with pytest.raises(SystemExit):
        BT.vignette_figures(pool, ritc, draws, cfg, targets, bad)


# ------------------------------------------------------------------ one fold refit, small ------
def test_a_fold_refit_returns_its_posterior_means_and_diagnostics(monkeypatch):
    monkeypatch.setattr(BT, "DRAWS", 40)
    monkeypatch.setattr(BT, "TUNE", 40)
    monkeypatch.setattr(BT, "CHAINS", 2)
    r = BT.fit_training(3)
    S, R, H, yr, syn, ritc = am.load_sample()
    held = OV.fold_assignment(syn, BT.K_HONEST) == 3
    assert (r["n_train"], r["n_held_out"]) == (int((~held).sum()), int(held.sum())) and r["n_train"] + r["n_held_out"] == 672
    assert r["n_held_out_syndicates"] == len(set(syn[held].tolist()))
    assert r["n_train_syndicates"] + r["n_held_out_syndicates"] == 118
    assert set(r["means"]) == set(BT.OPERATOR_PARAMS) and 0.5 < r["means"]["k"] < 1.0
    assert set(r["diagnostics"]) == {"max_rhat", "min_ess_bulk", "divergences"} and r["seconds"] > 0


# ------------------------------------------------------------------ the whole computation, small ------
@pytest.fixture(scope="module")
def small_run():
    """compute() with the fold refits replaced by the full-sample means and a short bootstrap: it exercises everything
    but the sampler. The full-sample means are the regenerated (gamma = 0) headline's."""
    import check_operator_backtest as m
    draws, *_ = BT.load_draws()
    means = {p: float(np.mean(draws[p])) for p in BT.OPERATOR_PARAMS}
    folds = [{"fold": f, "means": means, "n_train": 0, "n_held_out": 0, "n_train_syndicates": 0,
              "n_held_out_syndicates": 0, "params": {}, "seconds": 0.0,
              "diagnostics": {"max_rhat": 1.0, "min_ess_bulk": 1000.0, "divergences": 0}} for f in range(BT.K_HONEST)]
    real = m.bayes_bootstrap_weights
    m.bayes_bootstrap_weights = lambda syn, reps=100, seed=BT.BB_SEED: real(syn, reps, seed)
    try:
        return m.compute(workers=1, folds=folds)
    finally:
        m.bayes_bootstrap_weights = real


def test_the_record_has_both_versions_all_methods_and_both_pool_rules(small_run):
    o = small_run
    # 672 since the regeneration of 13 October 2026 (465f99a, outputs e627b77: four repairs, 1218/2015 net, 4020/2017 excluded)
    assert (o["n"], o["n_syndicates"], o["n_ritc"]) == (672, 118, 38)
    for ver in ("honest", "cheap"):
        assert set(o[ver]["pool_rules"]) == set(BT.POOL_RULES)
        for rule in BT.POOL_RULES:
            assert set(BT.METHODS) <= set(o[ver]["pool_rules"][rule])
    assert o["honest"]["folds"] == 10 and o["cheap"]["folds"] == 118
    assert o["honest"]["leaks_held_out_syndicate_into_scale_law"] is False
    assert o["cheap"]["leaks_held_out_syndicate_into_scale_law"] is True


# ------------------------------------------------------------------ the committed record ------
@pytest.fixture(scope="module")
def rec():
    return _json("results/check_operator_backtest_results.json")


def _methods_block(rec):
    for ver in ("honest", "cheap"):
        for rule in BT.POOL_RULES:
            yield ver, rule, rec[ver]["pool_rules"][rule]


def test_the_record_stamps_the_headline_and_says_why_there_is_no_overlay(rec):
    """The regenerated record has no overlay method (option B)."""
    assert (rec["operator"], rec["operator_role"]) == ("size_only", "headline")
    assert "overlay_sensitivity" not in rec and "full-sample gamma-free fit" in rec["overlay_sensitivity_note"]
    assert rec["vignette_figures"]["operator"] == "size_only"
    assert rec["methods"] == list(BT.METHODS) and rec["levels"] == list(BT.LEVELS)


def test_the_honest_folds_are_oos_validations_and_every_refit_sampled_cleanly(rec):
    """The regenerated fold refits have gamma = 0, so FIT_PARAMS carries no gamma."""
    syn = am.load_sample()[4]
    fold = OV.fold_assignment(syn, 10)
    fits = rec["honest"]["fits"]
    assert [f["fold"] for f in fits] == list(range(10)) and rec["honest"]["folds"] == 10
    for f in fits:
        held = fold == f["fold"]
        assert f["n_held_out"] == int(held.sum()) and f["n_train"] == int((~held).sum())
        assert f["n_held_out_syndicates"] == len(set(syn[held].tolist()))
        d = f["diagnostics"]
        assert d["divergences"] == 0 and d["max_rhat"] <= 1.01 and d["min_ess_bulk"] >= 400, (f["fold"], d)
        assert set(f["params"]) == set(BT.FIT_PARAMS) and 0.5 < f["params"]["k"]["mean"] < 1.0
    assert sum(f["n_held_out"] for f in fits) == 672 and sum(f["n_held_out_syndicates"] for f in fits) == 118
    assert rec["sampler"] == {"draws": 1500, "tune": 1500, "chains": 4, "target_accept": 0.98, "seed": 42}


def test_the_counts_add_up_and_match_the_expected_counts(rec):
    counts = rec["size_quartiles"]["counts"]
    assert sum(counts) == 672 and len(counts) == 4
    for ver, rule, blk in _methods_block(rec):
        for m in BT.METHODS:
            for a in BT.LEVELS:
                row = blk[m]["%g" % a]
                e, x = row["expected"], row["exceedances"]
                assert x["clean"] + x["ritc"] == x["all"], (ver, rule, m, a)
                assert sum(x["size_quartile_%d" % j] for j in (1, 2, 3, 4)) == x["all"], (ver, rule, m, a)
                assert e["all"] == pytest.approx(672 * (1 - a)) and e["ritc"] == pytest.approx(38 * (1 - a))
                assert [e["size_quartile_%d" % (j + 1)] for j in range(4)] == pytest.approx([c * (1 - a) for c in counts])
                for g, rate in row["rate_bayes_bootstrap"].items():
                    assert rate["lo"] <= rate["mean"] <= rate["hi"] and rate["nominal"] == pytest.approx(1 - a)
                assert all(v >= 0 for v in row["pinball_mean"].values())


#: a count the record's prose names: "the 672 targets", "the published 672-donor pool"
NAMED_COUNT = re.compile(r"\b(\d+)(?:-donor| donors?\b| targets?\b| records?\b| syndicate-years?\b)")


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def test_every_count_the_record_names_is_the_samples(rec):
    """The labels read "the 674 targets" and "the published 674-donor pool" against a 672 sample and pool (the final
    review of 14 October 2026, P19); the script now writes the count it has. Every count the record's strings name is
    the sample's, and the two labels that carried the stale one are among those read."""
    pool_n = len(BT.load_pool()[0])
    assert rec["n"] == 672 == sum(rec["size_quartiles"]["counts"]) == pool_n
    named = [(s, int(m.group(1))) for s in _strings(rec) for m in NAMED_COUNT.finditer(s)]
    assert [(s, n) for s, n in named if n != rec["n"]] == []
    assert rec["size_quartiles"]["of"] == "R of the 672 targets"
    assert rec["vignette_figures"]["pool"] == "the published 672-donor pool, full sample (no donor held out)"
    assert {s for s, _n in named} >= {rec["size_quartiles"]["of"], rec["vignette_figures"]["pool"]}


def test_exceedances_cannot_rise_with_the_level(rec):
    for ver, rule, blk in _methods_block(rec):
        for m in BT.METHODS:
            for g in ("all", "clean", "ritc", "size_quartile_1", "size_quartile_4"):
                xs = [blk[m]["%g" % a]["exceedances"][g] for a in BT.LEVELS]
                assert xs == sorted(xs, reverse=True), (ver, rule, m, g, xs)


def test_the_record_scores_every_target_once(rec):
    # at 90% the three methods are scored on the same 672 targets: the cheapest sanity that none was dropped
    for _ver, _rule, blk in _methods_block(rec):
        for m in BT.METHODS:
            assert blk[m]["0.9"]["expected"]["all"] == pytest.approx(67.2)


def test_the_vignette_figures_are_the_published_operators_and_the_sqrt_r_rule(rec):
    """The pin is the headline's V1 VaR99.5 on the regeneration at 0912834 (option B, committed as 5693622):
    0.29515908143283026 from the gamma = 0 fit, 0.2952 to four places. It was 0.2954 under the retired construction
    (the gamma-free fit with gamma zeroed), which check_gamma_free_fit_results.json now records as the bridge.
    Re-pinned on the regeneration of 13 October 2026 (465f99a, outputs e627b77: four repairs, 1218/2015 net, 4020/2017 excluded):
    0.29505437438720905, 0.2951 to four places."""
    vf = rec["vignette_figures"]
    cen = _json("results/check_gamma0_vignette_results.json")[TO.HEADLINE]["centre"]
    assert vf["operator_size_only"]["V1"]["v995"] == cen["V1_v995"] and vf["operator_size_only"]["V1"]["v99"] == cen["V1_v99"]
    assert vf["operator_size_only"]["V2_d995"] == cen["V2_d995"]
    pool = BT.load_pool()
    S, R = pool[0], pool[1]
    assert vf["sqrt_R"]["V1"]["v995"] == var_q(S * np.sqrt(R / 500.0), 0.995)
    assert vf["sqrt_R"]["V1"]["v99"] == var_q(S * np.sqrt(R / 500.0), 0.99)
    assert vf["raw_pool"]["v995"] == var_q(S, 0.995)
    assert vf["targets"]["V1"] == [500.0, 0.17]
    assert round(vf["operator_size_only"]["V1"]["v995"], 4) == 0.2951


def test_the_run_time_sits_under_the_key_the_verifier_strips(rec):
    import reproduce
    assert "runtime_seconds" in reproduce.VOLATILE
    rt = rec["runtime_seconds"]
    assert rt["workers"] >= 1 and rt["fold_fits_wall"] > 0 and len(rt["fits_seconds"]) == 10
    # nothing run-dependent (a worker count, a wall time) is left outside it
    stripped = reproduce._strip_volatile(rec)
    assert "runtime_seconds" not in stripped and "workers" not in json.dumps(stripped)
