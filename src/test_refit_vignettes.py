"""The stresses under a refit's own posterior (refit_vignettes.py), and the two records that carry them.

The author's decision of 14 October 2026 added Vignette 1's VaR99 and VaR99.5 and Vignette 2's change at 99.5% to two
sensitivities: the cohort-enforced subset's fit on its own donors (check_cohort_scope.py) and each selection-weighted
fit (check_missingness_sensitivity.py). The helpers are tested on synthetic inputs where they can be (convergence,
the relative change, the weighted centre, the pool checks, the top donors, the refusal of an unconverged fit); the
records are tested for the keys and for what can be recomputed from committed inputs without a refit (the headline
block, the relative changes, the pool-only leg, the top donors and their cohort scope).

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
def test_the_top_donor_scope_counts_the_donors_the_subset_drops():
    import check_cohort_scope as CS
    top = [{"donor": k, "transferred_severity": v} for k, v in (("a", 3.0), ("b", 2.0), ("c", 1.0))]
    out = CS.top_donor_scope(top, {"a": "mature-enforced", "b": "disclosed-prior-year", "c": "mature-enforced"})
    assert out["n"] == 3 and out["n_leaving"] == 1 and out["leaving"] == ["b"]
    assert [r["rank"] for r in out["donors"]] == [1, 2, 3]
    assert out["donors"][1]["pyd_cohort_scope"] == "disclosed-prior-year"


@pytest.fixture(scope="module")
def cohort():
    return _json("results/check_cohort_scope_results.json")


@pytest.fixture(scope="module")
def scopes():
    obs = _json("model/exposure_results.json")["observations"]
    return {"%s_%s" % (o["syndicate"], o["year"]): o.get("pyd_cohort_scope") for o in obs
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None
            and o.get("pyd_basis") == "gross"}


class TestTheCohortRecord:
    def test_the_vignette_block_is_present_and_stamped_headline(self, cohort):
        v = cohort["vignettes"]
        for key in ("seed", "B", "estimator", "pool", "headline", "triangle_only", "relative_to_headline",
                    "centre_decomposition", "order_statistics", "v1_top_donors_headline"):
            assert key in v, key
        n_full = len(RV.pool_for()[2])
        for q, a in (("V1_v99", 0.99), ("V1_v995", 0.995)):
            assert v["order_statistics"][q] == {"headline_pool": RV.rank_from_top(n_full, a),
                                                "subset_pool": RV.rank_from_top(v["pool"]["n_donors"], a)}
        assert v["triangle_only"]["operator"] == TO.HEADLINE and v["headline"]["operator"] == TO.HEADLINE
        for q in ("V1_v99", "V1_v995", "V2_d995"):
            assert q in v["triangle_only"]["centre"] and q in v["triangle_only"]["intervals"]

    def test_the_fit_converged(self, cohort):
        d = cohort["enforced_subset_fit_convergence"]
        assert RV.converged(d) and d["min_ess_bulk"] > 400 and d["parameters"] == list(RV.DIAG_VARS)

    def test_the_headline_is_the_vignette_record_and_the_seed_and_b_are_its(self, cohort):
        rec = _json("results/check_gamma0_vignette_results.json")
        v = cohort["vignettes"]
        head = {k: x for k, x in v["headline"].items() if k != "source"}
        assert head == rec[TO.HEADLINE]
        assert (v["seed"], v["B"]) == (rec["seed"], rec["B"])

    def test_the_pool_is_the_cohort_enforced_records(self, cohort, scopes):
        v = cohort["vignettes"]
        n_enforced = sum(s == "mature-enforced" for s in scopes.values())
        assert v["pool"]["n_donors"] == cohort["n_mature_enforced"] == n_enforced
        assert cohort["n_disclosed_prior_year"] == len(scopes) - n_enforced
        _p, _r, keys = RV.pool_for([k for k, s in scopes.items() if s == "mature-enforced"])
        assert len(keys) == v["pool"]["n_donors"]

    def test_the_relative_changes_are_computed_as_stated(self, cohort):
        v = cohort["vignettes"]
        h = v["headline"]["centre"]
        for q in QUANTITIES:
            assert v["relative_to_headline"][q] == pytest.approx(v["triangle_only"]["centre"][q] / h[q] - 1.0,
                                                                 rel=1e-12)
            d = v["centre_decomposition"]
            assert d["headline_fit_on_subset_pool_relative_to_headline"][q] == pytest.approx(
                d["headline_fit_on_subset_pool"][q] / h[q] - 1.0, rel=1e-12)
            assert d["subset_fit_on_full_pool_relative_to_headline"][q] == pytest.approx(
                d["subset_fit_on_full_pool"][q] / h[q] - 1.0, rel=1e-12)

    def test_the_pool_only_leg_is_the_headline_fit_on_the_subsets_donors(self, cohort, scopes):
        draws, ref, hlo, hce = TO.load_draws(TO.HEADLINE)
        pool, ritc, _k = RV.pool_for([k for k, s in scopes.items() if s == "mature-enforced"])
        assert RV.centre_only(draws, pool, ritc, (ref, hlo, hce)) == \
            cohort["vignettes"]["centre_decomposition"]["headline_fit_on_subset_pool"]

    def test_the_top_donors_are_the_headlines_and_their_scope_is_the_records(self, cohort, scopes):
        t = cohort["vignettes"]["v1_top_donors_headline"]
        draws, ref, hlo, hce = TO.load_draws(TO.HEADLINE)
        pool, ritc, keys = RV.pool_for()
        top = RV.v1_top_donors(draws, pool, ritc, keys, (ref, hlo, hce), n=RV.TOP_N)
        assert [r["donor"] for r in t["donors"]] == [r["donor"] for r in top] and t["n"] == RV.TOP_N
        assert all(r["pyd_cohort_scope"] == scopes[r["donor"]] for r in t["donors"])
        leaving = [r["donor"] for r in top if scopes[r["donor"]] != "mature-enforced"]
        assert t["leaving"] == leaving and t["n_leaving"] == len(leaving)


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
