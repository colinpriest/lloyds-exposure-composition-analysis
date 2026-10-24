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
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: the repository root, for `import reproduce` (as the sibling test files put it on sys.path): the file runs alone
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "src"))

import adopted_model as am  # noqa: E402
import check_operator_backtest as BT  # noqa: E402
import oos_validation as OV  # noqa: E402
import transfer_operator as TO  # noqa: E402
from pool_quantile import var_q  # noqa: E402
from vignette_uncertainty import transfer  # noqa: E402

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
    """Digests of the syndicate-to-fold map of the 118 syndicates, taken from the original inline expression (the sorted
    syndicates dealt out in turn, syndicate i to fold i mod k). The primary sample (the regeneration of 23 October 2026)
    has syndicate 6107 in and 1994 out of the 672 construction's 118, which moves the folds of the syndicates between
    them; the pins are the digests of the same inline rule on the primary's syndicates (they were
    f44a6ca19dc52276cd42c8da78718d7f9d8b9af86385c7b3a7cd6bd9cbbd8885 and
    7e9200380ac8a5305985ff3ee8a5969a5518d8192211b4fc7713bcde8628c31a)."""
    syn = am.load_sample()[4]
    assert len(set(syn.tolist())) == 118
    assert _digest(syn, 5) == "49eb3843c9cefd6b178a31ede741a3ac76ecf0ffcfece41be2f247ec054ab1b2"
    assert _digest(syn, 10) == "88c78d42a8862e914d531c7ba3685f266881e36ef367e8b2b96fd674c1b6f595"
    # and the inline rule itself, retyped here so the pin does not rest on the helper alone
    uniq = sorted(set(syn.tolist()))
    for k in (5, 10):
        inline = ",".join("%s:%d" % (u, i % k) for i, u in enumerate(uniq))
        assert hashlib.sha256(inline.encode()).hexdigest() == _digest(syn, k)
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


def test_a_group_with_no_targets_has_no_mean_loss_and_no_rate_and_raises_no_warning():
    """The tie set above has empty RITC and size-quartile groups. Their mean loss and exceedance rate are null (the mean of
    nothing, and a 0/0 ratio of weights), not nan, and neither calculation warns; the populated groups are as before."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = BT.summarise_method(np.array([1.0, 2.0]), {0.9: np.array([1.0, 1.0])}, np.array([0, 1]),
                                  np.zeros(2, bool), np.ones((2, 2)), levels=(0.9,))["0.9"]
    assert out["pinball_mean"]["ritc"] is None and out["pinball_mean"]["size_quartile_3"] is None
    assert out["rate_bayes_bootstrap"]["ritc"] == {"mean": None, "lo": None, "hi": None, "nominal": pytest.approx(0.1),
                                                   "share_above_nominal": None}
    assert out["exceedances"]["ritc"] == 0 and out["expected"]["ritc"] == 0.0
    assert out["pinball_mean"]["all"] == pytest.approx(0.45) and out["pinball_mean"]["size_quartile_1"] == 0.0
    assert out["rate_bayes_bootstrap"]["all"]["mean"] == pytest.approx(0.5)
    assert json.dumps(out)           # strict json: no nan
    assert "NaN" not in json.dumps(out)


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


# ------------------------------------------------------------------ the operator over the fold fits' draws ------
def test_the_mixtures_var_is_var_q_at_equal_weights():
    """mixture_var reads the inverse-CDF VaR from one sort; it must be pool_quantile.var_q's value, ties included."""
    rng = np.random.default_rng(11)
    for n in (1, 7, 200, 1999, 6000):
        a = np.round(rng.standard_t(4, n), 2)          # rounding makes ties
        got = BT.mixture_var(a, BT.LEVELS + (0.5, 1.0))
        for lv in BT.LEVELS + (0.5, 1.0):
            assert got[lv] == var_q(a, lv), (n, lv)


def _draws3(th=TH):
    return {"k": np.array([0.55, 0.62, 0.7]), "gamma": np.zeros(3), "sd_undiv": np.array([0.02, 0.03, 0.04]),
            "sd_div": np.array([0.05, 0.06, 0.07]), "nu_clean": np.array([4.0, 5.0, 6.0]),
            "nu_ritc": np.array([3.0, 7.0, 9.0])}


@pytest.mark.parametrize("drop_year", [False, True])
def test_the_draw_based_var_is_the_mixture_of_the_published_transfer_under_each_draw(drop_year):
    S, R, H, ritc, syn, yr = _toy()
    held = syn % 2                                      # two units
    draws = {0: _draws3(), 1: {p: v[::-1].copy() for p, v in _draws3().items()}}
    q = BT.draw_quantiles(S, R, H, ritc, held, yr, draws, CFG, drop_year)
    for i in range(len(S)):
        keep = held != held[i]
        if drop_year:
            keep &= yr != yr[i]
        d = draws[held[i]]
        mix = np.concatenate([transfer(S[keep], R[keep], H[keep], (R[i], H[i]),
                                       {p: float(d[p][j]) for p in d}, CFG, ritc[keep]) for j in range(3)])
        for a in BT.LEVELS:
            assert q[a][i] == pytest.approx(var_q(mix, a), rel=1e-12, abs=1e-15), (i, a)


def test_draws_all_at_the_means_give_the_plug_in_exactly():
    S, R, H, ritc, syn, yr = _toy()
    held = syn % 2
    th = _head()
    plug = BT.leave_out_quantiles(S, R, H, ritc, held, syn, yr, {0: th, 1: th}, CFG, False)["operator_size_only"]
    same = {p: np.full(4, TH[p]) for p in TH}
    q = BT.draw_quantiles(S, R, H, ritc, held, yr, {0: same, 1: same}, CFG, False)
    for a in BT.LEVELS:
        assert np.array_equal(q[a], plug[a]), a


def test_a_fitted_gamma_in_the_draws_is_refused():
    S, R, H, ritc, syn, yr = _toy()
    bad = dict(_draws3(), gamma=np.array([0.0, 0.3, 0.0]))
    with pytest.raises(ValueError):
        BT.draw_quantiles(S, R, H, ritc, syn % 2, yr, {0: bad, 1: bad}, CFG, False)


# ------------------------------------------------------------------ one fold refit, small ------
def test_a_fold_refit_returns_its_posterior_means_and_diagnostics(monkeypatch):
    monkeypatch.setattr(BT, "DRAWS", 40)
    monkeypatch.setattr(BT, "TUNE", 40)
    monkeypatch.setattr(BT, "CHAINS", 2)
    r = BT.fit_training(3)
    S, R, H, yr, syn, ritc = am.load_sample()
    held = OV.fold_assignment(syn, BT.K_HONEST) == 3
    assert (r["n_train"], r["n_held_out"]) == (int((~held).sum()), int(held.sum())) and r["n_train"] + r["n_held_out"] == 643  # 649 until the pass of 38cd750
    assert r["n_held_out_syndicates"] == len(set(syn[held].tolist()))
    assert r["n_train_syndicates"] + r["n_held_out_syndicates"] == 118
    assert set(r["means"]) == set(BT.OPERATOR_PARAMS) and 0.5 < r["means"]["k"] < 1.0
    assert set(r["diagnostics"]) == {"max_rhat", "min_ess_bulk", "divergences"} and r["seconds"] > 0
    # the draws the parameter-uncertainty version mixes: evenly spaced through the 80 (2 chains x 40), gamma exactly 0
    assert set(r["draws"]) == set(BT.OPERATOR_PARAMS) and all(len(v) == 80 for v in r["draws"].values())
    assert r["draws"]["gamma"] == [0.0] * 80 and np.mean(r["draws"]["k"]) == pytest.approx(r["means"]["k"])


# ------------------------------------------------------------------ the whole computation, small ------
@pytest.fixture(scope="module")
def small_run():
    """compute() with the fold refits replaced by the full-sample means and a short bootstrap: it exercises everything
    but the sampler. The full-sample means are the regenerated (gamma = 0) headline's."""
    import check_operator_backtest as m
    draws, *_ = BT.load_draws()
    means = {p: float(np.mean(draws[p])) for p in BT.OPERATOR_PARAMS}
    folds = [{"fold": f, "means": means, "draws": {p: [means[p]] * 3 for p in BT.OPERATOR_PARAMS},
              "n_train": 0, "n_held_out": 0, "n_train_syndicates": 0,
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
    # 649 (118 syndicates, 34 RITC-regime) since the regeneration of 23 October 2026 on the primary sample; it was 672
    # (118, 38) from the regeneration of 13 October 2026 (465f99a, outputs e627b77: four repairs, 1218/2015 net, 4020/2017
    # excluded)
    # 643 (118 syndicates, 33 RITC-regime) since the recorded pass of 24 October 2026 at 38cd750 (the round-5
    # adjudication and review 8's decisions took six records out of the primary, one of them RITC-regime; no syndicate
    # left, so the syndicates stay 118)
    assert (o["n"], o["n_syndicates"], o["n_ritc"]) == (643, 118, 33)
    for ver in ("honest", "cheap"):
        assert set(o[ver]["pool_rules"]) == set(BT.POOL_RULES)
        for rule in BT.POOL_RULES:
            assert set(BT.METHODS) <= set(o[ver]["pool_rules"][rule])
    assert o["honest"]["folds"] == 10 and o["cheap"]["folds"] == 118
    assert o["honest"]["leaks_held_out_syndicate_into_scale_law"] is False
    assert o["cheap"]["leaks_held_out_syndicate_into_scale_law"] is True


def test_with_every_draw_at_the_means_the_draw_based_block_is_the_plug_in(small_run):
    """small_run's fold draws are three copies of the means: the mixture is the plug-in pool three times, so every
    figure of the draw-based block equals the honest version's operator figures exactly."""
    d = small_run["honest_posterior_draws"]
    assert (d["operator"], d["operator_role"]) == ("size_only", "headline") and d["method_scored"] == "operator_size_only"
    for rule in BT.POOL_RULES:
        assert d["pool_rules"][rule]["operator_size_only"] == small_run["honest"]["pool_rules"][rule]["operator_size_only"]
        for a in BT.LEVELS:
            row = d["against_posterior_mean_plug_in"][rule]["%g" % a]
            assert row["exceedances_all"]["posterior_draws"] == row["exceedances_all"]["posterior_mean_plug_in"]
            assert row["pinball_mean_all"]["posterior_draws"] == row["pinball_mean_all"]["posterior_mean_plug_in"]


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
    assert sum(f["n_held_out"] for f in fits) == 643 and sum(f["n_held_out_syndicates"] for f in fits) == 118
    assert rec["sampler"] == {"draws": 1500, "tune": 1500, "chains": 4, "target_accept": 0.98, "seed": 42}


def test_the_counts_add_up_and_match_the_expected_counts(rec):
    counts = rec["size_quartiles"]["counts"]
    assert sum(counts) == 643 and len(counts) == 4   # 643 (33 RITC-regime) at 38cd750; 649 (34) before it
    for ver, rule, blk in _methods_block(rec):
        for m in BT.METHODS:
            for a in BT.LEVELS:
                row = blk[m]["%g" % a]
                e, x = row["expected"], row["exceedances"]
                assert x["clean"] + x["ritc"] == x["all"], (ver, rule, m, a)
                assert sum(x["size_quartile_%d" % j] for j in (1, 2, 3, 4)) == x["all"], (ver, rule, m, a)
                assert e["all"] == pytest.approx(643 * (1 - a)) and e["ritc"] == pytest.approx(33 * (1 - a))
                assert [e["size_quartile_%d" % (j + 1)] for j in range(4)] == pytest.approx([c * (1 - a) for c in counts])
                for g, rate in row["rate_bayes_bootstrap"].items():
                    assert rate["lo"] <= rate["mean"] <= rate["hi"] and rate["nominal"] == pytest.approx(1 - a)
                assert all(v >= 0 for v in row["pinball_mean"].values())


#: a count the record's prose names: "the 643 targets", "the published 643-donor pool"
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
    """The labels read "the 674 targets" and "the published 674-donor pool" against a 672 sample and pool, then 649 and now 643 (the
    final review of 14 October 2026, P19; 643 at the recorded pass of 38cd750); the script now writes the count it has.
    Every count the record's strings name is the sample's, and the two labels that carried the stale one are among
    those read."""
    pool_n = len(BT.load_pool()[0])
    assert rec["n"] == 643 == sum(rec["size_quartiles"]["counts"]) == pool_n
    named = [(s, int(m.group(1))) for s in _strings(rec) for m in NAMED_COUNT.finditer(s)]
    assert [(s, n) for s, n in named if n != rec["n"]] == []
    assert rec["size_quartiles"]["of"] == "R of the 643 targets"
    assert rec["vignette_figures"]["pool"] == "the published 643-donor pool, full sample (no donor held out)"
    assert {s for s, _n in named} >= {rec["size_quartiles"]["of"], rec["vignette_figures"]["pool"]}


def test_exceedances_cannot_rise_with_the_level(rec):
    for ver, rule, blk in _methods_block(rec):
        for m in BT.METHODS:
            for g in ("all", "clean", "ritc", "size_quartile_1", "size_quartile_4"):
                xs = [blk[m]["%g" % a]["exceedances"][g] for a in BT.LEVELS]
                assert xs == sorted(xs, reverse=True), (ver, rule, m, g, xs)


def test_the_record_scores_every_target_once(rec):
    # at 90% the three methods are scored on the same 643 targets: the cheapest sanity that none was dropped
    # (64.3 = 643 x 0.1 at the recorded pass of 38cd750; 64.9 on the 649)
    for _ver, _rule, blk in _methods_block(rec):
        for m in BT.METHODS:
            assert blk[m]["0.9"]["expected"]["all"] == pytest.approx(64.3)


def test_the_vignette_figures_are_the_published_operators_and_the_sqrt_r_rule(rec):
    """The pin is the headline's V1 VaR99.5 on the regeneration at 0912834 (option B, committed as 5693622):
    0.29515908143283026 from the gamma = 0 fit, 0.2952 to four places. It was 0.2954 under the retired construction
    (the gamma-free fit with gamma zeroed), which check_gamma_free_fit_results.json now records as the bridge.
    Re-pinned on the regeneration of 13 October 2026 (465f99a, outputs e627b77: four repairs, 1218/2015 net, 4020/2017 excluded):
    0.29505437438720905, 0.2951 to four places.
    Re-pinned on the regeneration of 23 October 2026 on the primary sample (649 donors): 0.3303768219054808, 0.3304 to
    four places.
    Re-pinned on 23 October 2026 to the recorded 0.33048897717077363, 0.3305 to four places: the primary moved when
    1945/2022's figure was repaired, and the record's V1 follows the primary (the paper prints $0.3305$).
    Re-pinned on 24 October 2026 to the recorded 0.33403593971572976, 0.3340 to four places, at the recorded pass of
    38cd750 on the 643-record primary (the round-5 adjudication and review 8's decisions took six records out of the
    donor pool); the rest of the test, which ties the record to check_gamma0_vignette_results.json and to the pool, is
    unchanged.
    Re-pinned on 24 October 2026 to the recorded 0.33432015847442714, 0.3343 to four places, at the recorded pass of
    c733f9f (152468b): the round-8 readings swapped 780/2016 into the donor pool and 2232/2017 out of it."""
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
    assert round(vf["operator_size_only"]["V1"]["v995"], 4) == 0.3343


def test_the_draw_based_block_is_beside_the_plug_in_and_reads_the_same_targets(rec):
    """DEFERRED-TO-REFIT: the parameter-uncertainty version (22 October 2026) is in the record beside the honest one,
    stamped with the headline operator, with both pool rules, and its plug-in figures are the honest version's."""
    d = rec["honest_posterior_draws"]
    assert (d["operator"], d["operator_role"]) == ("size_only", "headline")
    assert d["draws_per_fold"] == BT.N_PRED_DRAWS and set(d["pool_rules"]) == set(BT.POOL_RULES)
    for rule in BT.POOL_RULES:
        blk = d["pool_rules"][rule]["operator_size_only"]
        honest = rec["honest"]["pool_rules"][rule]["operator_size_only"]
        for a in BT.LEVELS:
            key = "%g" % a
            row = d["against_posterior_mean_plug_in"][rule][key]
            assert row["exceedances_all"]["posterior_mean_plug_in"] == honest[key]["exceedances"]["all"]
            assert row["pinball_mean_all"]["posterior_mean_plug_in"] == honest[key]["pinball_mean"]["all"]
            assert row["exceedances_all"]["posterior_draws"] == blk[key]["exceedances"]["all"]
            assert blk[key]["expected"] == honest[key]["expected"]
            x = blk[key]["exceedances"]
            assert x["clean"] + x["ritc"] == x["all"] == sum(x["size_quartile_%d" % j] for j in (1, 2, 3, 4))
        xs = [blk["%g" % a]["exceedances"]["all"] for a in BT.LEVELS]
        assert xs == sorted(xs, reverse=True)


def test_the_run_time_sits_under_the_key_the_verifier_strips(rec):
    import reproduce
    assert "runtime_seconds" in reproduce.VOLATILE
    rt = rec["runtime_seconds"]
    assert rt["workers"] >= 1 and rt["fold_fits_wall"] > 0 and len(rt["fits_seconds"]) == 10
    # nothing run-dependent (a worker count, a wall time) is left outside it
    stripped = reproduce._strip_volatile(rec)
    assert "runtime_seconds" not in stripped and "workers" not in json.dumps(stripped)


# ------------------------------------------------------------------ exceedances by size quartile (per_target) ------
def _quartile_case():
    """Eight targets, two per size quartile (R 1..8), four syndicates (a syndicate in two quartiles), known flags."""
    R = np.arange(1.0, 9.0)
    syn = np.array([10, 10, 20, 30, 30, 30, 40, 40])
    _edges, quart = BT.size_quartiles(R)
    flags = {0.9: np.array([1, 1, 0, 1, 1, 0, 0, 0], bool), 0.99: np.array([1, 0, 0, 0, 0, 0, 0, 0], bool)}
    return R, syn, quart, flags


def test_the_quartile_table_counts_flags_by_quartile_and_by_distinct_syndicate():
    R, syn, quart, flags = _quartile_case()
    W = np.ones((5, 8))
    tab = BT.quartile_table(flags, quart, syn, W, levels=(0.9, 0.99))
    q1, q2 = tab["0.9"]["size_quartile_1"], tab["0.9"]["size_quartile_2"]
    # quartile 1 = targets 0, 1 (syndicate 10 twice): two exceedances, one syndicate carrying both
    assert (q1["n_targets"], q1["n_syndicates"], q1["exceedances"], q1["n_syndicates_with_exceedances"]) == (2, 1, 2, 1)
    assert q1["exceedances_by_syndicate"] == [[10, 2]]
    assert q1["expected"] == pytest.approx(0.2)
    # quartile 2 = targets 2, 3 (syndicates 20, 30): one exceedance, from syndicate 30
    assert (q2["exceedances"], q2["n_syndicates_with_exceedances"], q2["exceedances_by_syndicate"]) == (1, 1, [[30, 1]])
    # quartile 3 = targets 4, 5 (syndicate 30): one; quartile 4 = targets 6, 7 (syndicate 40): none
    assert tab["0.9"]["size_quartile_3"]["exceedances"] == 1
    q4 = tab["0.9"]["size_quartile_4"]
    assert q4["exceedances"] == 0 and q4["n_syndicates_with_exceedances"] == 0 and q4["exceedances_by_syndicate"] == []
    # at equal weights the rate posterior is the share; the posterior probability of exceeding the nominal 0.1 is 1 or 0
    assert q1["rate_mean"] == pytest.approx(1.0) and q1["rate_credible_interval_95"] == pytest.approx([1.0, 1.0])
    assert q1["p_rate_above_nominal"] == 1.0 and q4["p_rate_above_nominal"] == 0.0 and q4["nominal_rate"] == pytest.approx(0.1)
    # the 99% level reads its own flags
    assert tab["0.99"]["size_quartile_1"]["exceedances"] == 1
    assert sum(tab["0.99"]["size_quartile_%d" % j]["exceedances"] for j in (1, 2, 3, 4)) == 1


def test_the_quartile_table_uses_the_bootstrap_weights_by_syndicate():
    """Only targets 0 and 1 carry weight (3 and 1): the quartile-1 rate is the weighted share of exceedances, so a flag
    on the heavier target moves it by 3/4; the table's rate is rate_posterior's, not a count over targets."""
    R, syn, quart, flags = _quartile_case()
    W = np.zeros((4, 8))
    W[:, 0] = 3.0
    W[:, 1] = 1.0
    W[:, 2:] = 1.0
    t = BT.quartile_table({0.9: flags[0.9]}, quart, syn, W, levels=(0.9,))["0.9"]["size_quartile_1"]
    assert t["rate_mean"] == pytest.approx(1.0)
    flags2 = flags[0.9].copy()
    flags2[0] = False                                 # the weight-3 target is no longer an exceedance
    t2 = BT.quartile_table({0.9: flags2}, quart, syn, W, levels=(0.9,))["0.9"]["size_quartile_1"]
    assert t2["rate_mean"] == pytest.approx(0.25) and t2["exceedances"] == 1


def test_the_quartile_of_a_book_follows_the_targets_rule_at_the_edges():
    edges = [172.4, 418.9, 830.4]
    got = [BT.quartile_of(r, edges) for r in (1.0, 172.3, 172.4, 418.8, 418.9, 830.3, 830.4, 9000.0)]
    assert got == [1, 1, 2, 2, 3, 3, 4, 4]
    R = np.array([1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0])
    e, quart = BT.size_quartiles(R)
    assert [BT.quartile_of(r, e) - 1 for r in R] == quart.tolist()


def _per_target_toy():
    S, R, H, ritc, syn, yr = _toy(n_syn=4, per=3)
    q = {a: np.full(len(S), v) for a, v in ((0.9, 0.04), (0.99, 0.09))}
    qd = {a: np.full(len(S), v - 0.04) for a, v in ((0.9, 0.04), (0.99, 0.09))}
    plug = {rule: q for rule in BT.POOL_RULES}
    draw = {rule: qd for rule in BT.POOL_RULES}
    return S, R, ritc, syn, yr, plug, draw


def test_the_per_target_block_keeps_every_flag_with_its_syndicate_year_and_size():
    S, R, ritc, syn, yr, plug, draw = _per_target_toy()
    W = np.ones((3, len(S)))
    vig = {"V1": (float(np.median(R)) + 1e-6, 0.2), "V2_old": (float(R.max()) + 1.0, 0.2),
           "V2_new": (float(R.min()) - 1.0, 0.2)}
    blk = BT.per_target_block(S, R, ritc, syn, yr, W, plug, draw, vig, levels=(0.9, 0.99))
    t = blk["targets"]
    assert t["syndicate"] == syn.tolist() and t["year"] == yr.tolist() and t["R_gbp_m"] == R.tolist()
    assert t["ritc"] == ritc.astype(int).tolist() and len(t["size_quartile"]) == len(S)
    _e, quart = BT.size_quartiles(R)
    assert t["size_quartile"] == (quart + 1).tolist()
    for rule in BT.POOL_RULES:
        assert blk["exceedance_flags"]["honest_plug_in"][rule]["0.9"] == (S > 0.04).astype(int).tolist()
        assert blk["exceedance_flags"]["honest_posterior_draws"][rule]["0.99"] == (S > 0.05).astype(int).tolist()
        # the table is built from the flags it sits beside: counts add up
        for src in ("honest_plug_in", "honest_posterior_draws"):
            for a in ("0.9", "0.99"):
                tab = blk["by_size_quartile"][src][rule][a]
                assert (sum(tab["size_quartile_%d" % j]["exceedances"] for j in (1, 2, 3, 4))
                        == sum(blk["exceedance_flags"][src][rule][a]))
    # a different VaR gives different flags: the two sources are not the same table
    assert blk["exceedance_flags"]["honest_plug_in"]["leave_out"]["0.9"] != \
        blk["exceedance_flags"]["honest_posterior_draws"]["leave_out"]["0.9"]
    # the vignettes' quartiles come from the targets' edges
    assert blk["vignette_size_quartiles"]["V2_old"] == {"R_gbp_m": float(R.max()) + 1.0, "size_quartile": 4}
    assert blk["vignette_size_quartiles"]["V2_new"]["size_quartile"] == 1
    edges = blk["by_size_quartile"]["edges_gbp_m"]
    assert blk["vignette_size_quartiles"]["V1"]["size_quartile"] == BT.quartile_of(vig["V1"][0], edges)


def test_the_backtest_hands_back_the_operators_vars():
    S, R, H, ritc, syn, yr = _toy(n_syn=6, per=2)
    fold = OV.fold_assignment(syn, 3)
    thetas = {f: _head() for f in range(3)}
    cap = {}
    W = np.ones((2, len(S)))
    out = BT.backtest(S, R, H, ritc, syn, yr, fold, thetas, CFG, False, W, levels=(0.9,), capture=cap)
    q = BT.leave_out_quantiles(S, R, H, ritc, fold, syn, yr, thetas, CFG, False, (0.9,))
    assert np.array_equal(cap["operator"][0.9], q["operator_size_only"][0.9])
    # the captured VaRs are the ones the counts were made from
    assert out["operator_size_only"]["0.9"]["exceedances"]["all"] == int((S > cap["operator"][0.9]).sum())
    assert BT.backtest(S, R, H, ritc, syn, yr, fold, thetas, CFG, False, W, levels=(0.9,)) == out


def test_the_per_target_block_in_the_small_run_reproduces_the_blocks_counts(small_run):
    """The flags, the table and the record's own exceedance counts are three routes to one number; with the draws at the
    means the draw block's flags are the plug-in's."""
    pt = small_run["per_target"]
    assert len(pt["targets"]["syndicate"]) == 643   # 649 until the recorded pass of 38cd750
    for src, rule_blocks in (("honest_plug_in", small_run["honest"]["pool_rules"]),
                             ("honest_posterior_draws", small_run["honest_posterior_draws"]["pool_rules"])):
        for rule in BT.POOL_RULES:
            for a in BT.LEVELS:
                key = "%g" % a
                x = rule_blocks[rule]["operator_size_only"][key]["exceedances"]
                tab = pt["by_size_quartile"][src][rule][key]
                assert sum(pt["exceedance_flags"][src][rule][key]) == x["all"]
                for j in (1, 2, 3, 4):
                    assert tab["size_quartile_%d" % j]["exceedances"] == x["size_quartile_%d" % j]
    for rule in BT.POOL_RULES:
        assert pt["exceedance_flags"]["honest_plug_in"][rule] == pt["exceedance_flags"]["honest_posterior_draws"][rule]


def test_the_record_keeps_the_flags_and_the_quartile_table_and_they_agree_with_the_counts(rec):
    pt = rec["per_target"]
    S, R, H, yr, syn, ritc = am.load_sample()
    assert pt["targets"]["syndicate"] == syn.tolist() and pt["targets"]["year"] == yr.tolist()
    assert pt["targets"]["R_gbp_m"] == R.tolist() and pt["targets"]["ritc"] == ritc.astype(int).tolist()
    edges, quart = BT.size_quartiles(R)
    assert pt["targets"]["size_quartile"] == (quart + 1).tolist()
    assert pt["by_size_quartile"]["edges_gbp_m"] == edges.tolist() == rec["size_quartiles"]["edges_gbp_m"]
    plug = rec["honest"]["pool_rules"]
    draw = rec["honest_posterior_draws"]["pool_rules"]
    for src, blocks in (("honest_plug_in", plug), ("honest_posterior_draws", draw)):
        for rule in BT.POOL_RULES:
            for a in BT.LEVELS:
                key = "%g" % a
                flags = np.array(pt["exceedance_flags"][src][rule][key])
                assert len(flags) == 643 and set(flags.tolist()) <= {0, 1}
                x = blocks[rule]["operator_size_only"][key]["exceedances"]
                assert int(flags.sum()) == x["all"]
                tab = pt["by_size_quartile"][src][rule][key]
                for j in (1, 2, 3, 4):
                    row = tab["size_quartile_%d" % j]
                    assert row["exceedances"] == x["size_quartile_%d" % j] == int(flags[quart == j - 1].sum())
                    assert row["n_targets"] == int((quart == j - 1).sum()) == rec["size_quartiles"]["counts"][j - 1]
                    assert row["expected"] == pytest.approx(row["n_targets"] * (1 - a))
                    assert sum(c for _s, c in row["exceedances_by_syndicate"]) == row["exceedances"]
                    assert row["n_syndicates_with_exceedances"] == len(row["exceedances_by_syndicate"])
                    assert row["n_syndicates_with_exceedances"] == len(set(syn[(quart == j - 1) & (flags == 1)].tolist()))
                    assert row["n_syndicates_with_exceedances"] <= row["exceedances"]
                    lo, hi = row["rate_credible_interval_95"]
                    assert lo <= row["rate_mean"] <= hi and 0.0 <= row["p_rate_above_nominal"] <= 1.0
                    assert row["nominal_rate"] == pytest.approx(1 - a)
                    # the bootstrap posterior is the one summarise_method recorded for the same group
                    old = blocks[rule]["operator_size_only"][key]["rate_bayes_bootstrap"]["size_quartile_%d" % j]
                    assert (row["rate_mean"], lo, hi, row["p_rate_above_nominal"]) == (
                        old["mean"], old["lo"], old["hi"], old["share_above_nominal"])


def test_the_vignettes_size_quartiles_are_read_from_the_vignette_config_and_the_targets_edges(rec):
    v = rec["per_target"]["vignette_size_quartiles"]
    v1, v2o, v2n = BT.load_targets()
    edges = rec["size_quartiles"]["edges_gbp_m"]
    for tag, tgt in (("V1", v1), ("V2_old", v2o), ("V2_new", v2n)):
        assert v[tag]["R_gbp_m"] == tgt[0]
        assert v[tag]["size_quartile"] == int(np.searchsorted(edges, tgt[0], side="right")) + 1
    assert [v[t]["R_gbp_m"] for t in ("V1", "V2_old", "V2_new")] == [500.0, 800.0, 650.0]
    assert set(v) == {"V1", "V2_old", "V2_new"} and all(1 <= x["size_quartile"] <= 4 for x in v.values())


def test_an_outcome_equal_to_the_var_is_not_flagged_in_the_per_target_block():
    """The flag is S > VaR, strictly, as the counts are (summarise_method): a tie is not an exceedance."""
    S = np.array([0.04, 0.05, 0.03, 0.04])
    R = np.array([1.0, 2.0, 3.0, 4.0])
    syn = np.array([1, 2, 3, 4])
    yr = np.array([2015, 2015, 2016, 2016])
    q = {rule: {0.9: np.full(4, 0.04)} for rule in BT.POOL_RULES}
    blk = BT.per_target_block(S, R, np.zeros(4, bool), syn, yr, np.ones((2, 4)), q, q,
                              {"V1": (2.5, 0.1), "V2_old": (2.5, 0.1), "V2_new": (2.5, 0.1)}, levels=(0.9,))
    assert blk["exceedance_flags"]["honest_plug_in"]["leave_out"]["0.9"] == [0, 1, 0, 0]
    assert blk["exceedance_flags"]["honest_posterior_draws"]["leave_out_and_target_year"]["0.9"] == [0, 1, 0, 0]
    tab = blk["by_size_quartile"]["honest_plug_in"]["leave_out"]["0.9"]
    assert [tab["size_quartile_%d" % j]["exceedances"] for j in (1, 2, 3, 4)] == [0, 1, 0, 0]
