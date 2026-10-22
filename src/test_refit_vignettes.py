"""The stresses under a refit's own posterior (refit_vignettes.py), and the two records that carry them.

The author's decision of 14 October 2026 added Vignette 1's VaR99 and VaR99.5 and Vignette 2's change at 99.5% to two
sensitivities: the 672 construction's fit on its own donors beside the primary (check_cohort_scope.py, since the
owner's decision of 22 October 2026; until then the cohort-enforced subset's) and each selection-weighted fit
(check_missingness_sensitivity.py). The helpers are tested on synthetic inputs where they can be (convergence,
the relative change, the weighted centre, the pool checks, the top donors, the refusal of an unconverged fit); the
records are tested for the keys and for what can be recomputed from committed inputs without a refit (the headline
block, the relative changes, the pool-only leg, the top donors and their cohort scope).

The smooth-tail check (Vignette 1's GPD VaR99.5 on both pools, under the smooth-tail rule of 14 October 2026, written
by the Claude analysis session on the author's instruction before the check was run) is
tested the same way: on synthetic pools with a stand-in for the Bayesian GPD fit (the headline GPD's functions, the
exact reproduction check and its refusal, the refusal of an unconverged fit, the legs and the relative changes), and
on the record (the keys, the full pool equal to both headline GPD records, the POT points under the headline fit).

Run:  python -m pytest src/test_refit_vignettes.py -q
"""
import copy
import io
import json
import os

import numpy as np
import pytest

import refit_vignettes as RV
import transfer_operator as TO
from check_gamma0_vignette import QUANTITIES

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _json(rel):
    with io.open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ synthetic inputs
def _idata(diverging=0, shift_chain=0.0, seed=3):
    import arviz as az
    rng = np.random.default_rng(seed)
    post = {n: rng.normal(1.0, 0.1, size=(4, 400)) for n in RV.DIAG_VARS}
    post["k"][0] += shift_chain                      # one chain away from the others: R-hat well above 1
    div = np.zeros((4, 400), bool)
    div.flat[:diverging] = True
    return az.from_dict(posterior=post, sample_stats={"diverging": div})


def _draws(n=200, seed=5):
    rng = np.random.default_rng(seed)
    return {"k": rng.uniform(0.55, 0.65, n), "gamma": np.zeros(n), "sd_undiv": rng.uniform(0.02, 0.04, n),
            "sd_div": rng.uniform(0.04, 0.06, n), "nu_clean": rng.uniform(4, 6, n), "nu_ritc": rng.uniform(5, 9, n)}


def _pool(n=60, seed=11):
    rng = np.random.default_rng(seed)
    S = rng.standard_t(5, n) * 0.05
    R = rng.uniform(50, 3000, n)
    H = rng.uniform(0.1, 0.9, n)
    synd = np.repeat(np.arange(n // 3), 3)
    year = np.tile([2015, 2016, 2017], n // 3)
    ritc = np.zeros(n, bool)
    ritc[::7] = True
    return (S, R, H, synd, year), ritc


CFG = (500.0, 0.01, 1.0)


class TestConvergence:
    def test_counts_divergences_and_reads_rhat_and_ess_unrounded(self):
        import arviz as az
        idata = _idata(diverging=3, shift_chain=0.5)
        d = RV.convergence(idata)
        assert d["divergences"] == 3
        rhat = az.rhat(idata, var_names=list(RV.DIAG_VARS))
        assert d["max_rhat"] == pytest.approx(max(float(rhat[n]) for n in RV.DIAG_VARS), abs=0)
        assert d["max_rhat"] == pytest.approx(float(rhat["k"]), abs=0) and d["max_rhat"] > 1.5
        bulk = az.ess(idata, var_names=list(RV.DIAG_VARS), method="bulk")
        tail = az.ess(idata, var_names=list(RV.DIAG_VARS), method="tail")
        assert d["min_ess_bulk"] == pytest.approx(min(float(bulk[n]) for n in RV.DIAG_VARS), abs=0)
        assert d["min_ess_tail"] == pytest.approx(min(float(tail[n]) for n in RV.DIAG_VARS), abs=0)
        assert d["parameters"] == list(RV.DIAG_VARS)

    def test_a_fit_converges_only_with_no_divergence_and_rhat_at_most_1_01(self):
        assert RV.converged({"divergences": 0, "max_rhat": 1.01})
        assert RV.converged({"divergences": 0, "max_rhat": 1.0003})
        assert not RV.converged({"divergences": 0, "max_rhat": 1.0101})
        assert not RV.converged({"divergences": 1, "max_rhat": 1.0})
        assert RV.converged(RV.convergence(_idata()))
        assert not RV.converged(RV.convergence(_idata(shift_chain=0.5)))
        assert not RV.converged(RV.convergence(_idata(diverging=1)))


def test_the_operator_draws_are_the_fits_own_with_gamma_exactly_zero():
    import arviz as az
    rng = np.random.default_rng(1)
    post = {n: rng.normal(1.0, 0.1, size=(2, 50)) for n in ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc",
                                                           "lambda_ritc")}
    d = RV.operator_draws(az.from_dict(posterior=post))
    assert sorted(d) == sorted(TO.OPERATOR_KEYS)
    assert np.all(d["gamma"] == 0.0) and d["gamma"].size == 100
    for n in ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc"):
        assert np.array_equal(d[n], post[n].ravel())
    TO.params(d, TO.HEADLINE)                     # the size-only operator takes them as they are


def test_relative_is_centre_over_headline_minus_one():
    head = {"V1_v99": 0.2, "V1_v995": 0.25, "V2_d995": 0.01, "V2_old_v995": 9.0}
    other = {"V1_v99": 0.22, "V1_v995": 0.2, "V2_d995": 0.015, "V2_old_v995": 1.0}
    rel = RV.relative(other, head)
    assert set(rel) == set(QUANTITIES)
    assert rel["V1_v99"] == pytest.approx(0.1) and rel["V1_v995"] == pytest.approx(-0.2)
    assert rel["V2_d995"] == pytest.approx(0.5)


class TestWeightedCentre:
    def test_unit_weights_give_the_headline_estimators_centre(self):
        pool, ritc = _pool()
        draws = _draws()
        assert RV.centre_only(draws, pool, ritc, CFG, weights=np.ones(len(ritc))) == RV.centre_only(
            draws, pool, ritc, CFG)

    def test_zero_weights_remove_donors_and_other_weights_rescale(self):
        pool, ritc = _pool()
        draws = _draws()
        w = np.ones(len(ritc))
        w[:12] = 0.0
        keep = np.arange(len(ritc)) >= 12
        sub = tuple(a[keep] for a in pool)
        assert RV.centre_only(draws, pool, ritc, CFG, weights=w) == RV.centre_only(draws, sub, ritc[keep], CFG)
        assert RV.centre_only(draws, pool, ritc, CFG, weights=3.7 * w) == RV.centre_only(draws, sub, ritc[keep], CFG)

    def test_weights_move_the_quantile(self):
        pool, ritc = _pool()
        draws = _draws()
        plain = RV.centre_only(draws, pool, ritc, CFG)
        th = TO.params(draws, TO.HEADLINE)
        thbar = {p: float(th[p].mean()) for p in th}
        from vignette_uncertainty import load_targets, transfer
        a1 = transfer(pool[0], pool[1], pool[2], load_targets()[0], thbar, CFG, ritc)
        # 60 donors: VaR99 is the largest; with almost no mass on the three most adverse it is the fourth largest
        assert plain["V1_v99"] == np.sort(a1)[-1]
        w = np.where(a1 >= np.sort(a1)[-3], 0.01, 1.0)
        assert RV.centre_only(draws, pool, ritc, CFG, weights=w)["V1_v99"] == np.sort(a1)[-4]


class TestPoolChecks:
    def test_the_tools_rounding_passes_and_more_does_not(self):
        pool, _ritc = _pool(n=6)
        keys = np.array(["%d_%d" % (s, y) for s, y in zip(pool[3], pool[4])])
        S, R = pool[0].copy(), pool[1].copy()
        RV.check_pool_is_the_fit_sample(pool, keys, keys[::-1], S[::-1], R[::-1])     # order does not matter
        RV.check_pool_is_the_fit_sample(pool, keys, keys, S + 4.9e-9, R - 0.0049)
        with pytest.raises(SystemExit, match="1 donors"):
            S2 = S.copy(); S2[2] += 2e-8
            RV.check_pool_is_the_fit_sample(pool, keys, keys, S2, R)
        with pytest.raises(SystemExit, match="1 donors"):
            R2 = R.copy(); R2[4] += 0.02
            RV.check_pool_is_the_fit_sample(pool, keys, keys, S, R2)
        with pytest.raises(SystemExit, match="is not the fit's sample"):
            RV.check_pool_is_the_fit_sample(pool, keys, keys[:-1], S[:-1], R[:-1])

    def test_a_key_outside_the_pool_is_an_error_not_a_smaller_pool(self):
        _pool_all, _r, keys = RV.pool_for()
        with pytest.raises(SystemExit, match="not in the vignette donor pool"):
            RV.pool_for(list(keys[:5]) + ["99999_2099"])
        pool, ritc, sub = RV.pool_for(list(keys[10:20])[::-1])
        assert list(sub) == list(keys[10:20])            # the tool's order, whatever order the keys come in
        assert len(ritc) == 10 and len(pool[0]) == 10


@pytest.mark.parametrize("n", [5, 100, 200, 571, 600, 672, 1000])
@pytest.mark.parametrize("alpha", [0.99, 0.995, 0.5])
def test_the_rank_from_top_is_the_order_statistic_var_q_reads(n, alpha):
    from pool_quantile import var_q
    x = np.random.default_rng(n).permutation(np.arange(n, dtype=float))
    v = var_q(x, alpha)
    assert v == np.sort(x)[::-1][RV.rank_from_top(n, alpha) - 1]


def test_the_vignette_ranks_of_the_two_pool_sizes():
    """672 donors put VaR99.5 at the 4th largest and VaR99 at the 7th; 571 put them at the 3rd and the 6th."""
    assert (RV.rank_from_top(672, 0.995), RV.rank_from_top(672, 0.99)) == (4, 7)
    assert (RV.rank_from_top(571, 0.995), RV.rank_from_top(571, 0.99)) == (3, 6)


def test_the_top_donors_are_the_largest_transferred_severities_in_order():
    pool, ritc = _pool()
    draws = _draws()
    keys = np.array(["d%d" % i for i in range(len(ritc))])
    top = RV.v1_top_donors(draws, pool, ritc, keys, CFG, n=7)
    th = TO.params(draws, TO.HEADLINE)
    thbar = {p: float(th[p].mean()) for p in th}
    from vignette_uncertainty import load_targets, transfer
    a1 = transfer(pool[0], pool[1], pool[2], load_targets()[0], thbar, CFG, ritc)
    expect = np.argsort(-a1)[:7]
    assert [r["donor"] for r in top] == ["d%d" % i for i in expect]
    assert [r["transferred_severity"] for r in top] == [float(a1[i]) for i in expect]


def test_the_headline_block_is_refused_when_its_centre_is_not_recomputed_exactly():
    rec = RV.headline_record()
    head, _draws_h, cfg = RV.headline_block(rec)
    assert head == rec[TO.HEADLINE] and cfg == (500.0, 0.01, 1.0)
    bad = copy.deepcopy(rec)
    bad[TO.HEADLINE]["centre"]["V1_v995"] += 1e-12
    with pytest.raises(SystemExit, match="differ from check_gamma0_vignette.py's record"):
        RV.headline_block(bad)


def test_the_headline_record_must_name_the_size_only_operator(tmp_path, monkeypatch):
    rec = RV.headline_record()
    rec["headline_operator"] = TO.OVERLAY
    p = tmp_path / "g0.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    monkeypatch.setattr(RV, "GAMMA0", p)
    with pytest.raises(SystemExit, match="does not name size_only"):
        RV.headline_record()


# ------------------------------------------------------------------ check_cohort_scope.py
# Since the owner's decision of 22 October 2026 the record sets the primary (the headline, every figure the
# mature-cohort movement) beside the 672 construction (the extraction's precedence rules), loaded in memory by
# run_analysis.load_and_classify("precedence_672"), refitted and transferred from its own donors.
def _obs(key, s, scope="mature-enforced"):
    synd, year = (int(x) for x in key.split("_"))
    return {"syndicate": synd, "year": year, "s_raw_a": s, "opening_reserves_gbp_m": 100.0, "hhi": 0.3,
            "pyd_basis": "gross", "pyd_cohort_scope": scope}


def test_the_top_donor_place_counts_the_donors_absent_or_changed_in_the_sensitivity():
    import check_cohort_scope as CS
    top = [{"donor": k, "transferred_severity": v} for k, v in (("1_2020", 3.0), ("2_2020", 2.0), ("3_2020", 1.0))]
    primary = [_obs("1_2020", 0.3), _obs("2_2020", 0.2), _obs("3_2020", 0.1)]
    sensitivity = [_obs("1_2020", 0.3), _obs("2_2020", -0.05, "disclosed-prior-year")]
    out = CS.top_donor_place(top, primary, sensitivity)
    assert out["n"] == 3 and [r["rank"] for r in out["donors"]] == [1, 2, 3]
    assert out["absent_from_sensitivity"] == ["3_2020"] and out["n_absent_from_sensitivity"] == 1
    assert out["other_severity_in_sensitivity"] == ["2_2020"] and out["n_other_severity_in_sensitivity"] == 1
    assert [r["in_sensitivity"] for r in out["donors"]] == [True, True, False]


def test_the_coverage_and_the_membership_are_counted_as_stated():
    import check_cohort_scope as CS
    primary = [_obs("1_2020", 0.3), _obs("2_2020", 0.2), _obs("4_2021", 0.1)]
    sensitivity = [_obs("1_2020", 0.3), _obs("2_2020", -0.05, "disclosed-prior-year"), _obs("3_2019", 0.4,
                                                                                         "disclosed-prior-year")]
    c = CS.coverage(sensitivity)
    assert (c["n_gross_sample"], c["n_mature_enforced"], c["n_disclosed_prior_year"]) == (3, 1, 2)
    assert c["share_enforced"] == round(1 / 3, 6) and c["n_syndicates_enforced"] == 1 and c["years"] == [2019, 2020]
    m = CS.membership(primary, sensitivity)
    assert m["n_both_same_severity"] == 1 and m["both_other_severity"] == ["2_2020"]
    assert m["primary_only"] == ["4_2021"] and m["sensitivity_only"] == ["3_2019"]


def test_the_sensitivity_is_the_672_construction_and_its_donors_are_its_working_sample():
    """Recomputed from the committed records and registers (the loader in memory), not from a written output."""
    import check_cohort_scope as CS
    records, sens = CS.load_sensitivity()
    c = CS.coverage(sens)
    assert (c["n_gross_sample"], c["n_mature_enforced"], c["n_disclosed_prior_year"]) == (672, 571, 101)
    pool, ritc, keys = CS.donor_pool(records)
    assert sorted(keys.tolist()) == sorted(CS.key_of(o) for o in sens) and len(pool[0]) == 672
    by = {CS.key_of(o): o for o in sens}
    for k, s, r, h in zip(keys, pool[0], pool[1], pool[2]):
        assert s == round(by[k]["s_raw_a"], 8) and r == round(by[k]["opening_reserves_gbp_m"], 2)
        assert h == round(by[k]["hhi"], 6)


def test_a_move_either_way_reaches_the_line():
    import check_cohort_scope as CS
    for p, b, at in ((-0.06, 0.01, (True, False)), (0.049, -0.05, (False, True)), (0.05, -0.0499, (True, False))):
        out = CS.line_comparison({"point_var995": p, "bayesian_var995_median": b})
        assert (out["point_var995_at_or_above_line"], out["bayesian_var995_median_at_or_above_line"]) == at
        assert (out["point_var995"], out["bayesian_var995_median"]) == (p, b)


# the fitted tail (Vignette 1's GPD VaR99.5), on synthetic pools with a stand-in for the Bayesian GPD fit
def _stub_bayes(calls=None, bad_n=None):
    """bayesian_gpd.fit_one's signature and keys; a fit on `bad_n` donors reports one divergence."""
    def fit(name, exc, N, Nu, u, emp, mode):
        if calls is not None:
            calls.append({"name": name, "n_exc": len(exc), "N": N, "Nu": Nu, "u": u, "emp": emp, "mode": mode})
        m = float(np.mean(exc))
        return {"threshold_u": float(u), "N": int(N), "Nu": int(Nu), "var995_median": u + 3 * m,
                "var995_2.5": u + 2 * m, "var995_97.5": u + 5 * m, "xi_median": 0.1, "xi_2.5": -0.1, "xi_97.5": 0.3,
                "sigma_median": m, "sigma_2.5": 0.5 * m, "sigma_97.5": 1.5 * m, "max_rhat": 1.0,
                "divergences": int(N == bad_n), "tail_shape": "not resolved", "empirical": emp, "freq_point": None}
    return fit


def _gpd_recs(full):
    """Headline GPD records that `full` reproduces, in the two scripts' layouts."""
    import check_cohort_scope as CS
    stamp = {"operator": TO.HEADLINE}
    rule = "%.0fth percentile of the signed transferred-severity sample" % CS.GPD_U_Q
    freq = {"point_var995": full["point_var995"], "point_threshold_u": full["threshold_u"], "point_Nu": full["Nu"],
            "point_xi": full["point_xi"], "point_sigma": full["point_sigma"], "empirical": full["empirical_var995"]}
    return {"frequentist": {**stamp, "meta": {"n_donors": full["N"], "threshold_rule": rule},
                            "distributions": {CS.GPD_TARGET: freq}},
            "bayesian": {**stamp, "meta": {"threshold_rule": rule},
                         "distributions": {CS.GPD_TARGET: dict(full["bayesian"])}}}


def _v1_sample(draws, pool, ritc):
    from vignette_uncertainty import load_targets, transfer
    th = TO.params(draws, TO.HEADLINE)
    thbar = {p: float(th[p].mean()) for p in th}
    return transfer(pool[0], pool[1], pool[2], load_targets()[0], thbar, CFG, ritc)


class TestTheGpdTail:
    def test_the_tail_is_the_headline_gpds_own_functions_on_the_pool(self):
        import check_cohort_scope as CS
        import gpd_var_uncertainty as GV
        from pool_quantile import var_q
        pool, ritc = _pool(n=210)
        draws = _draws()
        calls = []
        out = CS.v1_gpd_tail(draws, pool, ritc, CFG, bayes_fit=_stub_bayes(calls))
        a1 = _v1_sample(draws, pool, ritc)
        u = float(np.percentile(a1, 90.0, method="linear"))
        assert out["threshold_u"] == u and out["Nu"] == int((a1 > u).sum()) == 21 and out["N"] == 210
        v, xi, sc, nu, uu = GV.gpd_var995(a1, 90.0)
        assert (out["point_var995"], out["point_xi"], out["point_sigma"], out["Nu"], out["threshold_u"]) == (
            v, xi, sc, nu, uu)
        assert out["empirical_var995"] == var_q(a1, 0.995)
        assert calls == [{"name": "V1_adjusted", "n_exc": 21, "N": 210, "Nu": 21, "u": u, "emp": var_q(a1, 0.995),
                          "mode": TO.HEADLINE}]
        assert set(out) == {"N", "threshold_u", "Nu", "point_var995", "point_xi", "point_sigma", "empirical_var995",
                            "bayesian"}
        assert tuple(out["bayesian"]) == CS.GPD_BAYES_KEYS

    def test_the_settings_are_the_headline_gpds(self):
        import bayesian_gpd
        import check_cohort_scope as CS
        assert CS.GPD_U_Q == 90.0 and CS.GPD_TARGET == "V1_adjusted" and CS.GPD_RULE_LINE == 0.05
        assert set(CS.GPD_BAYES_KEYS) <= set(_stub_bayes()("V1_adjusted", np.ones(3), 30, 3, 0.0, 0.0, TO.HEADLINE))
        assert bayesian_gpd.U_Q == 90.0             # its own default, imported under this test runner's arguments

    def test_the_reproduction_check_passes_on_equal_figures_and_refuses_any_difference(self):
        import check_cohort_scope as CS
        pool, ritc = _pool(n=210)
        full = CS.v1_gpd_tail(_draws(), pool, ritc, CFG, bayes_fit=_stub_bayes())
        CS.check_gpd_reproduces(full, _gpd_recs(full))
        for where, key in (("frequentist", "point_var995"), ("frequentist", "point_threshold_u"),
                           ("frequentist", "point_xi"), ("frequentist", "point_sigma"), ("frequentist", "empirical"),
                           ("bayesian", "var995_median"), ("bayesian", "var995_2.5"), ("bayesian", "var995_97.5"),
                           ("bayesian", "xi_median"), ("bayesian", "threshold_u")):
            recs = _gpd_recs(full)
            d = recs[where]["distributions"][CS.GPD_TARGET]
            d[key] = float(np.nextafter(d[key], np.inf))        # one unit in the last place
            with pytest.raises(SystemExit, match="does not reproduce the headline's recorded GPD figures"):
                CS.check_gpd_reproduces(full, recs)
        for where, key in (("frequentist", "point_Nu"), ("bayesian", "Nu"), ("bayesian", "N")):
            recs = _gpd_recs(full)
            recs[where]["distributions"][CS.GPD_TARGET][key] += 1
            with pytest.raises(SystemExit, match="does not reproduce"):
                CS.check_gpd_reproduces(full, recs)
        recs = _gpd_recs(full)
        recs["frequentist"]["meta"]["n_donors"] -= 1
        with pytest.raises(SystemExit, match="does not reproduce"):
            CS.check_gpd_reproduces(full, recs)

    def test_the_records_must_be_the_headline_operators_at_the_90th_percentile(self, tmp_path, monkeypatch):
        import check_cohort_scope as CS
        pool, ritc = _pool(n=210)
        recs = _gpd_recs(CS.v1_gpd_tail(_draws(), pool, ritc, CFG, bayes_fit=_stub_bayes()))
        paths = {k: tmp_path / ("%s.json" % k) for k in recs}

        def write(r):
            for k, p in paths.items():
                p.write_text(json.dumps(r[k]), encoding="utf-8")
        monkeypatch.setattr(CS, "GPD_RECORDS", paths)
        write(recs)
        assert CS.gpd_records() == recs
        bad = copy.deepcopy(recs)
        bad["bayesian"]["operator"] = TO.OVERLAY
        write(bad)
        with pytest.raises(SystemExit, match="does not record the size_only operator"):
            CS.gpd_records()
        bad = copy.deepcopy(recs)
        bad["frequentist"]["meta"]["threshold_rule"] = "95th percentile of the signed transferred-severity sample"
        write(bad)
        with pytest.raises(SystemExit, match="threshold is not the 90th percentile"):
            CS.gpd_records()

    def _block(self, recs=None, bad_n=None, calls=None):
        import check_cohort_scope as CS
        full_pool, full_ritc = _pool(n=210)
        keep = np.arange(210) % 7 != 3                              # 180 donors
        pool, ritc = tuple(a[keep] for a in full_pool), full_ritc[keep]
        head, other = _draws(seed=5), _draws(seed=9)
        stub = _stub_bayes(calls, bad_n)
        if recs is None:
            recs = _gpd_recs(CS.v1_gpd_tail(head, full_pool, full_ritc, CFG, bayes_fit=_stub_bayes(None, bad_n)))
        block = CS.gpd_tail_block(head, other, pool, ritc, full_pool, full_ritc, CFG, bayes_fit=stub, recs=recs)
        return block, (head, other, pool, ritc, full_pool, full_ritc)

    def test_the_block_carries_both_pools_both_single_change_legs_and_the_line(self):
        import check_cohort_scope as CS
        block, (head, other, pool, ritc, full_pool, full_ritc) = self._block()
        for key in ("operator", "question", "rule", "rule_line", "estimator", "reproduced", "full_pool_headline_fit",
                    "relative_to_full_pool_headline_fit", "rule_comparison") + CS.GPD_LEGS:
            assert key in block, key
        assert block["operator"] == TO.HEADLINE and block["rule_line"] == 0.05
        stub = _stub_bayes()
        expect = {"full_pool_headline_fit": CS.v1_gpd_tail(head, full_pool, full_ritc, CFG, bayes_fit=stub),
                  "sensitivity_672_fit": CS.v1_gpd_tail(other, pool, ritc, CFG, bayes_fit=stub),
                  "headline_fit_on_sensitivity_pool": CS.v1_gpd_tail(head, pool, ritc, CFG, bayes_fit=stub),
                  "sensitivity_fit_on_headline_pool": CS.v1_gpd_tail(other, full_pool, full_ritc, CFG, bayes_fit=stub)}
        for leg, e in expect.items():
            assert block[leg] == e, leg
        assert block["full_pool_headline_fit"]["N"] == 210 and block["sensitivity_672_fit"]["N"] == 180
        full = block["full_pool_headline_fit"]
        for leg, rel in block["relative_to_full_pool_headline_fit"].items():
            assert rel["point_var995"] == block[leg]["point_var995"] / full["point_var995"] - 1.0
            assert rel["bayesian_var995_median"] == (block[leg]["bayesian"]["var995_median"]
                                                     / full["bayesian"]["var995_median"] - 1.0)
        assert set(block["relative_to_full_pool_headline_fit"]) == set(CS.GPD_LEGS)
        rc, r2 = block["rule_comparison"], block["relative_to_full_pool_headline_fit"]["sensitivity_672_fit"]
        assert rc["point_var995"] == r2["point_var995"]
        assert rc["point_var995_at_or_above_line"] == (abs(r2["point_var995"]) >= 0.05)
        assert rc["bayesian_var995_median"] == r2["bayesian_var995_median"]
        assert rc["bayesian_var995_median_at_or_above_line"] == (abs(r2["bayesian_var995_median"]) >= 0.05)

    def test_a_record_that_does_not_reproduce_stops_the_block_before_any_other_leg(self):
        import check_cohort_scope as CS
        full_pool, full_ritc = _pool(n=210)
        recs = _gpd_recs(CS.v1_gpd_tail(_draws(seed=5), full_pool, full_ritc, CFG, bayes_fit=_stub_bayes()))
        recs["frequentist"]["distributions"][CS.GPD_TARGET]["point_var995"] *= 1.0 + 1e-9
        calls = []
        with pytest.raises(SystemExit, match="does not reproduce"):
            self._block(recs=recs, calls=calls)
        assert len(calls) == 1 and calls[0]["N"] == 210

    def test_an_unconverged_bayesian_gpd_fit_writes_nothing(self):
        with pytest.raises(SystemExit, match="Bayesian GPD fit of sensitivity_672_fit has not converged"):
            self._block(bad_n=180)
        with pytest.raises(SystemExit, match="Bayesian GPD fit of full_pool_headline_fit has not converged"):
            self._block(bad_n=210)


@pytest.fixture(scope="module")
def cohort():
    return _json("results/check_cohort_scope_results.json")


@pytest.fixture(scope="module")
def primary():
    import check_cohort_scope as CS
    return CS.load()


@pytest.fixture(scope="module")
def sensitivity():
    import check_cohort_scope as CS
    return CS.load_sensitivity()


class TestTheCohortRecord:
    def test_the_headline_is_the_primary_and_every_figure_is_mature_enforced(self, cohort, primary):
        assert primary and all(o.get("pyd_cohort_scope") == "mature-enforced" for o in primary)
        assert cohort["primary"]["n_gross_sample"] == cohort["primary"]["n_mature_enforced"] == len(primary)
        assert cohort["primary"]["n_disclosed_prior_year"] == 0

    def test_the_top_level_counts_are_the_672_constructions(self, cohort, sensitivity):
        import check_cohort_scope as CS
        _records, sens = sensitivity
        c = CS.coverage(sens)
        for k in ("n_gross_sample", "n_mature_enforced", "n_disclosed_prior_year", "share_enforced",
                  "n_syndicates_enforced"):
            assert cohort[k] == c[k] == cohort["sensitivity_672"][k], k

    def test_the_membership_is_the_two_samples(self, cohort, primary, sensitivity):
        import check_cohort_scope as CS
        assert cohort["membership"] == CS.membership(primary, sensitivity[1])

    def test_the_vignette_block_is_present_and_stamped_headline(self, cohort):
        v = cohort["vignettes"]
        for key in ("seed", "B", "estimator", "pool", "headline", "precedence_672", "relative_to_headline",
                    "centre_decomposition", "order_statistics", "v1_top_donors_headline", "v1_top_donors_sensitivity"):
            assert key in v, key
        n_full = len(RV.pool_for()[2])
        for q, a in (("V1_v99", 0.99), ("V1_v995", 0.995)):
            assert v["order_statistics"][q] == {"headline_pool": RV.rank_from_top(n_full, a),
                                                "sensitivity_pool": RV.rank_from_top(v["pool"]["n_donors"], a)}
        assert v["precedence_672"]["operator"] == TO.HEADLINE and v["headline"]["operator"] == TO.HEADLINE
        for q in ("V1_v99", "V1_v995", "V2_d995"):
            assert q in v["precedence_672"]["centre"] and q in v["precedence_672"]["intervals"]

    def test_the_fit_converged(self, cohort):
        d = cohort["sensitivity_672_fit_convergence"]
        assert RV.converged(d) and d["min_ess_bulk"] > 400 and d["parameters"] == list(RV.DIAG_VARS)

    def test_the_headline_is_the_vignette_record_and_the_seed_and_b_are_its(self, cohort):
        rec = _json("results/check_gamma0_vignette_results.json")
        v = cohort["vignettes"]
        head = {k: x for k, x in v["headline"].items() if k != "source"}
        assert head == rec[TO.HEADLINE]
        assert (v["seed"], v["B"]) == (rec["seed"], rec["B"])

    def test_the_pool_is_the_672_constructions_donors(self, cohort, sensitivity):
        import check_cohort_scope as CS
        _pool, _ritc, keys = CS.donor_pool(sensitivity[0])
        assert cohort["vignettes"]["pool"]["n_donors"] == len(keys) == cohort["n_gross_sample"]

    def test_the_relative_changes_are_computed_as_stated(self, cohort):
        v = cohort["vignettes"]
        h = v["headline"]["centre"]
        for q in QUANTITIES:
            assert v["relative_to_headline"][q] == pytest.approx(v["precedence_672"]["centre"][q] / h[q] - 1.0,
                                                                 rel=1e-12)
            d = v["centre_decomposition"]
            assert d["headline_fit_on_sensitivity_pool_relative_to_headline"][q] == pytest.approx(
                d["headline_fit_on_sensitivity_pool"][q] / h[q] - 1.0, rel=1e-12)
            assert d["sensitivity_fit_on_headline_pool_relative_to_headline"][q] == pytest.approx(
                d["sensitivity_fit_on_headline_pool"][q] / h[q] - 1.0, rel=1e-12)

    def test_the_pool_only_leg_is_the_headline_fit_on_the_672_donors(self, cohort, sensitivity):
        import check_cohort_scope as CS
        draws, ref, hlo, hce = TO.load_draws(TO.HEADLINE)
        pool, ritc, _k = CS.donor_pool(sensitivity[0])
        assert RV.centre_only(draws, pool, ritc, (ref, hlo, hce)) == \
            cohort["vignettes"]["centre_decomposition"]["headline_fit_on_sensitivity_pool"]

    def test_the_top_donors_are_the_headlines_with_their_place_in_the_672(self, cohort, primary, sensitivity):
        import check_cohort_scope as CS
        t = cohort["vignettes"]["v1_top_donors_headline"]
        draws, ref, hlo, hce = TO.load_draws(TO.HEADLINE)
        pool, ritc, keys = RV.pool_for()
        top = RV.v1_top_donors(draws, pool, ritc, keys, (ref, hlo, hce), n=RV.TOP_N)
        assert t == CS.top_donor_place(top, primary, sensitivity[1]) and t["n"] == RV.TOP_N

    def test_the_gpd_tail_block_is_present_for_both_pools_and_both_legs(self, cohort):
        import check_cohort_scope as CS
        g = cohort["vignettes"]["v1_gpd_tail"]
        n_full, n_sub = len(RV.pool_for()[2]), cohort["vignettes"]["pool"]["n_donors"]
        assert g["operator"] == TO.HEADLINE and g["rule_line"] == CS.GPD_RULE_LINE
        for leg, n in (("full_pool_headline_fit", n_full), ("sensitivity_672_fit", n_sub),
                       ("headline_fit_on_sensitivity_pool", n_sub), ("sensitivity_fit_on_headline_pool", n_full)):
            r = g[leg]
            for key in ("N", "threshold_u", "Nu", "point_var995", "point_xi", "point_sigma", "empirical_var995"):
                assert key in r, (leg, key)
            assert r["N"] == n and r["bayesian"]["N"] == n and r["bayesian"]["Nu"] == r["Nu"]
            assert r["bayesian"]["threshold_u"] == r["threshold_u"] and tuple(r["bayesian"]) == CS.GPD_BAYES_KEYS
            assert RV.converged(r["bayesian"])
            assert r["bayesian"]["var995_2.5"] <= r["bayesian"]["var995_median"] <= r["bayesian"]["var995_97.5"]

    def test_the_full_pool_gpd_tail_is_the_headlines_recorded_gpd(self, cohort):
        import check_cohort_scope as CS
        g = cohort["vignettes"]["v1_gpd_tail"]
        CS.check_gpd_reproduces(g["full_pool_headline_fit"], CS.gpd_records())
        f = _json("results/gpd_var_uncertainty_results.json")["distributions"]["V1_adjusted"]
        b = _json("results/bayesian_gpd_results.json")["distributions"]["V1_adjusted"]
        assert g["full_pool_headline_fit"]["point_var995"] == f["point_var995"]
        assert g["full_pool_headline_fit"]["bayesian"]["var995_median"] == b["var995_median"]

    def test_the_empirical_figures_are_the_vignette_centres(self, cohort):
        v = cohort["vignettes"]
        g = v["v1_gpd_tail"]
        assert g["full_pool_headline_fit"]["empirical_var995"] == v["headline"]["centre"]["V1_v995"]
        assert g["sensitivity_672_fit"]["empirical_var995"] == v["precedence_672"]["centre"]["V1_v995"]
        d = v["centre_decomposition"]
        assert g["headline_fit_on_sensitivity_pool"]["empirical_var995"] == d["headline_fit_on_sensitivity_pool"][
            "V1_v995"]
        assert g["sensitivity_fit_on_headline_pool"]["empirical_var995"] == d["sensitivity_fit_on_headline_pool"][
            "V1_v995"]

    def test_the_gpd_relative_changes_and_the_line_comparison_are_computed_as_stated(self, cohort):
        g = cohort["vignettes"]["v1_gpd_tail"]
        full = g["full_pool_headline_fit"]
        for leg, rel in g["relative_to_full_pool_headline_fit"].items():
            assert rel["point_var995"] == pytest.approx(g[leg]["point_var995"] / full["point_var995"] - 1.0, rel=1e-12)
            assert rel["bayesian_var995_median"] == pytest.approx(
                g[leg]["bayesian"]["var995_median"] / full["bayesian"]["var995_median"] - 1.0, rel=1e-12)
        rc = g["rule_comparison"]
        r2 = g["relative_to_full_pool_headline_fit"]["sensitivity_672_fit"]
        assert rc["point_var995"] == r2["point_var995"]
        assert rc["bayesian_var995_median"] == r2["bayesian_var995_median"]
        assert rc["point_var995_at_or_above_line"] is (abs(r2["point_var995"]) >= 0.05)
        assert rc["bayesian_var995_median_at_or_above_line"] is (abs(r2["bayesian_var995_median"]) >= 0.05)

    def test_the_headline_fits_pot_points_recompute_from_committed_inputs(self, cohort, sensitivity):
        """The two legs under the headline fit, recomputed without a refit (the Bayesian fits stand in)."""
        import check_cohort_scope as CS
        g = cohort["vignettes"]["v1_gpd_tail"]
        draws, ref, hlo, hce = TO.load_draws(TO.HEADLINE)
        cfg = (ref, hlo, hce)
        sub_pool, sub_ritc, _k = CS.donor_pool(sensitivity[0])
        full_pool, full_ritc, _k = RV.pool_for()
        for leg, pool, ritc in (("full_pool_headline_fit", full_pool, full_ritc),
                                ("headline_fit_on_sensitivity_pool", sub_pool, sub_ritc)):
            r = CS.v1_gpd_tail(draws, pool, ritc, cfg, bayes_fit=_stub_bayes())
            r.pop("bayesian")
            assert r == {k: x for k, x in g[leg].items() if k != "bayesian"}, leg


# ------------------------------------------------------------------ check_missingness_sensitivity.py
def test_the_weighted_stresses_refuse_an_unconverged_fit():
    import check_missingness_sensitivity as cms
    ok = {"divergences": 0, "max_rhat": 1.001}
    kept = {tag: {"draws": None, "convergence": dict(ok)} for tag in cms.WEIGHTED_STRESS_FITS}
    kept["ipw_cap_0.15"]["convergence"] = {"divergences": 2, "max_rhat": 1.001}
    with pytest.raises(SystemExit, match="ipw_cap_0.15 fit has not converged"):
        cms.stress_under_weights(kept, [], None, None, {})
    kept["ipw_cap_0.15"]["convergence"] = dict(ok)
    kept["unweighted"]["convergence"] = {"divergences": 0, "max_rhat": 1.02}
    with pytest.raises(SystemExit, match="unweighted fit has not converged"):
        cms.stress_under_weights(kept, [], None, None, {})


@pytest.fixture(scope="module")
def missing():
    return _json("results/check_missingness_sensitivity_results.json")


class TestTheMissingnessRecord:
    def test_every_weighting_the_script_fits_has_its_stresses(self, missing):
        import check_missingness_sensitivity as cms
        s = missing["stress_under_selection_weights"]
        assert list(s["by_fit"]) == list(cms.WEIGHTED_STRESS_FITS)
        assert set(cms.WEIGHTED_STRESS_FITS) - {"unweighted"} == {
            k for k in missing["fits"] if k.startswith("ipw_cap_")}
        for tag, e in s["by_fit"].items():
            assert e["operator"] == TO.HEADLINE and e["fit"] == tag
            assert RV.converged(e["convergence"]) and e["convergence"]["min_ess_bulk"] > 400
            for q in QUANTITIES:
                assert e["relative_to_headline"][q] == pytest.approx(
                    e["centre"][q] / s["headline"]["centre"][q] - 1.0, rel=1e-12)
            if tag == "unweighted":
                assert e["probability_floor"] is None and "centre_pool_weighted" not in e
            else:
                assert e["probability_floor"] == float(tag.rsplit("_", 1)[1])
                for q in QUANTITIES:
                    assert e["centre_pool_weighted_relative_to_headline"][q] == pytest.approx(
                        e["centre_pool_weighted"][q] / s["headline"]["centre"][q] - 1.0, rel=1e-12)

    def test_the_headline_and_pool_are_the_records(self, missing):
        s = missing["stress_under_selection_weights"]
        rec = _json("results/check_gamma0_vignette_results.json")
        assert {k: x for k, x in s["headline"].items() if k != "source"} == rec[TO.HEADLINE]
        assert (s["seed"], s["B"]) == (rec["seed"], rec["B"])
        assert s["pool"]["n_donors"] == missing["n_model_sample"]

    def test_the_fit_diagnostics_agree_with_the_fits_own(self, missing):
        s = missing["stress_under_selection_weights"]["by_fit"]
        for tag, e in s.items():
            assert e["convergence"]["divergences"] == missing["fits"][tag]["_diag"]["divergences"]
            # the stress block reads R-hat over eight parameters, the fit summary over six of them
            assert e["convergence"]["max_rhat"] >= missing["fits"][tag]["_diag"]["max_rhat"] - 1e-12
