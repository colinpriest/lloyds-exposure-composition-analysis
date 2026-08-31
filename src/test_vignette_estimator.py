#!/usr/bin/env python3
"""Tests for the vignette estimator: it must BE what the manuscript calls it.

Review found the vignette intervals reported as credible intervals and their sign
frequencies as posterior probabilities, while the code ran a multinomial cluster
bootstrap and drew one posterior sample per replicate. Every existing test passed:
the JSON keys were neutral, the script imported a posterior, and nothing asserted
anything about the ESTIMATOR.

So these tests are about the estimator and its declaration:

  * the results file says what estimator produced it, and what the estimand is --
    the manuscript's audit reads that declaration and checks the vocabulary against it;
  * the weighted quantile reduces EXACTLY to the unweighted convention at equal
    weights, so an interval surrounds its point estimate instead of sitting above it;
  * the Dirichlet weights are a by-syndicate Bayesian bootstrap, not a by-row one;
  * the relabelling did not move the science: the frequentist sensitivity agrees.

Run:  python -m pytest src/test_vignette_estimator.py -q
"""
import importlib.util
import io
import json
import os
import re

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(HERE, "results", "vignette_uncertainty_results.json")
SIGN = os.path.join(HERE, "results", "check_vignette2_sign_results.json")


def _module(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vu():
    return _module("vignette_uncertainty_mod", "src/vignette_uncertainty.py")


@pytest.fixture(scope="module")
def results():
    if not os.path.exists(RESULTS):
        pytest.skip("vignette results not present")
    return json.load(io.open(RESULTS, encoding="utf-8"))


class TestDeclaration:
    """The file must say what produced it; the manuscript's gate AA reads this."""

    def test_estimator_is_declared_and_bayesian(self, results):
        est = results["meta"].get("estimator", "")
        assert est, "no estimator declared"
        assert "bayes" in est.lower(), est

    def test_the_estimand_is_stated(self, results):
        estimand = results["meta"].get("estimand", "")
        assert "posterior" in estimand.lower()
        assert "dirichlet" in estimand.lower()

    def test_frequentist_variants_are_labelled_as_sensitivities(self, results):
        rob = results["robustness"]
        assert "estimator_note" in rob
        for key in ("V1_adj_var995_CI_by_clustering", "V2_change995_CI_by_clustering"):
            names = set(rob[key])
            assert "bayesian_bootstrap_primary" in names
            assert any(n.endswith("_freq") for n in names), names


class TestWeightedQuantile:
    """The weighted rule must generalise the unweighted one, not replace it."""

    def test_equal_weights_reproduce_the_point_convention(self, vu):
        rng = np.random.default_rng(0)
        for n in (5, 50, 789):
            x = rng.normal(size=n)
            w = np.ones(n)
            for a in (0.5, 0.9, 0.99, 0.995):
                assert abs(vu.var_q(x, a) - vu.var_q(x, a, w)) < 1e-9, (n, a)

    def test_a_half_weight_rule_would_not_have(self, vu):
        """Why the generalisation was chosen: the type-5 plotting position sits
        visibly above type-7 in the tail, which would have shifted every interval."""
        rng = np.random.default_rng(0)
        x = rng.normal(size=789)
        w = np.ones(789)
        cw = np.cumsum(np.sort(w))
        p5 = (cw - 0.5 * w) / cw[-1]
        type5 = float(np.interp(0.995, p5, np.sort(x)))
        assert abs(type5 - vu.var_q(x, 0.995)) > 0.01

    def test_scaling_is_exact(self, vu):
        """VaR(c*x) = c*VaR(x): the identity Vignette 2's direction rests on."""
        rng = np.random.default_rng(1)
        x = rng.normal(size=200)
        w = rng.dirichlet(np.ones(200))
        for c in (0.5, 1.084, 3.0):
            assert abs(vu.var_q(c * x, 0.995, w) - c * vu.var_q(x, 0.995, w)) < 1e-12

    def test_weighted_quantile_moves_with_the_weights(self, vu):
        x = np.arange(100.0)
        w = np.ones(100)
        base = vu.var_q(x, 0.95, w)
        w2 = w.copy()
        w2[-10:] = 50.0                      # pile weight on the top decile
        assert vu.var_q(x, 0.95, w2) > base


class TestBayesianBootstrapWeights:
    """Dirichlet weights at the SYNDICATE level, matching the cluster bootstrap."""

    def test_weights_are_per_syndicate_and_sum_to_one(self, vu):
        synd = np.array([1, 1, 1, 2, 3, 3])
        year = np.array([2014, 2015, 2016, 2014, 2015, 2016])
        draw = vu.build_resampler(synd, year, "bayes")
        rng = np.random.default_rng(7)
        for _ in range(20):
            idx, w = draw(rng)
            assert idx.tolist() == list(range(6)), "the whole pool is kept"
            assert abs(w.sum() - 1.0) < 1e-12
            totals = {s: w[synd == s].sum() for s in (1, 2, 3)}
            assert all(t > 0 for t in totals.values())
            # a syndicate's observations share its weight equally
            assert np.allclose(w[synd == 1], w[synd == 1][0])

    def test_expected_weight_is_the_pooled_row_share(self, vu):
        """The replaced test required the OPPOSITE -- equal mass per syndicate -- which
        made the interval describe a different population from the point it surrounds.
        The unit is the syndicate-year, so a syndicate with four of five years must
        carry four-fifths of the expected mass."""
        synd = np.array([1, 1, 1, 1, 2])
        year = np.array([2014, 2015, 2016, 2017, 2014])
        draw = vu.build_resampler(synd, year, "bayes")
        rng = np.random.default_rng(3)
        tot1 = np.mean([draw(rng)[1][synd == 1].sum() for _ in range(4000)])
        assert abs(tot1 - 0.8) < 0.02, tot1

    def test_prior_mean_weights_reproduce_the_unweighted_statistic(self, vu):
        """The identity that keeps the interval and its centre on one estimand: at the
        Dirichlet prior mean every ROW carries 1/N, so a weighted statistic equals the
        unweighted one exactly."""
        rng = np.random.default_rng(11)
        synd = np.repeat(np.arange(20), rng.integers(1, 8, 20))
        n = len(synd)
        year = np.arange(n)
        keys, counts = np.unique(synd, return_counts=True)
        alpha = len(keys) * counts / counts.sum()
        sidx = np.searchsorted(keys, synd)
        wbar = (alpha / alpha.sum())[sidx] / counts[sidx]
        x = rng.normal(size=n)
        for a in (0.5, 0.9, 0.995):
            assert abs(vu.var_q(x, a, wbar) - vu.var_q(x, a)) < 1e-12, a

    def test_the_concentration_keeps_variability_at_cluster_scale(self, vu):
        """Total concentration S, not N: an equal-alpha or row-level Dirichlet would
        give a materially tighter weight distribution than the cluster bootstrap."""
        rng = np.random.default_rng(5)
        synd = np.repeat(np.arange(30), 4)
        draw = vu.build_resampler(synd, np.arange(len(synd)), "bayes")
        tot = np.array([draw(rng)[1][synd == 0].sum() for _ in range(3000)])
        # Var of a Dirichlet share with sum(alpha)=S: p(1-p)/(S+1), p = 1/30
        expect = (1 / 30) * (1 - 1 / 30) / 31
        assert 0.5 < tot.var() / expect < 2.0, (tot.var(), expect)

    def test_multinomial_schemes_still_return_no_weights(self, vu):
        synd = np.array([1, 1, 2, 3])
        year = np.array([2014, 2015, 2014, 2015])
        for scheme in ("cluster", "year", "iid"):
            idx, w = vu.build_resampler(synd, year, scheme)(np.random.default_rng(0))
            assert w is None and len(idx) > 0


class TestScienceUnchangedByRelabelling:
    """The point of the change is honesty, not a different answer."""

    def test_the_two_estimators_agree_on_the_sign_probabilities(self, results):
        p = results["robustness"]["P_sign_by_estimator"]
        assert abs(p["V1_fall_bayesian_bootstrap"]
                   - p["V1_fall_cluster_bootstrap_freq"]) < 0.03
        assert p["V2_rise_bayesian_bootstrap"] == p["V2_rise_cluster_bootstrap_freq"]

    def test_the_point_estimates_are_untouched(self, results):
        """These are the pooled scenario quantiles, and the Dirichlet prior mean now
        reproduces them -- so locking them no longer pins a second estimand."""
        c = results["centres_full_pool_posterior_mean"]
        assert abs(c["V1_adj"]["v995"] - 0.393) < 0.001
        assert abs(c["V2_old"]["v995"] - 0.343) < 0.001
        assert abs(c["V2_new"]["v995"] - 0.373) < 0.001

    def test_the_results_declare_the_unit_and_the_prior_mean_identity(self, results):
        meta = results["meta"]
        assert "syndicate-year" in meta["inferential_unit"]
        assert meta["prior_mean_weights_reproduce_point"] is True
        assert "one index per replicate" in meta["posterior_draw"]

    def test_the_sensitivities_are_conditional_not_hybrid(self, results):
        rob = results["robustness"]
        assert "posterior-mean parameters" in rob["frequentist_sensitivity_construction"]
        src = io.open(os.path.join(HERE, "src", "vignette_uncertainty.py"),
                      encoding="utf-8").read()
        for scheme in ('combined("cluster"', 'combined("year"', 'combined("iid"'):
            i = src.index(scheme)
            call = src[i:src.index(")", i)]
            assert "param_uncertainty=False" in call, call

    def test_vignette1_interval_still_admits_an_increase(self, results):
        """The manuscript must not be able to claim a resolved fall: this is the
        finding, not an accident of the estimator."""
        pct = results["vignette1"]["change_raw_to_adjusted"]["pct_995"]
        assert pct["lo"] < 0 < pct["hi"], pct


class TestVignette2SignIsStructural:
    """Finding 2: the direction is imposed by the support, and the file says so."""

    @pytest.fixture(scope="class")
    def sign(self):
        if not os.path.exists(SIGN):
            pytest.skip("sign check not run")
        return json.load(io.open(SIGN, encoding="utf-8"))

    def test_every_draw_raises_the_scale(self, sign):
        assert sign["scale_ratio_new_over_old"]["frac_draws_above_one"] == 1.0
        assert sign["constraints"]["frac_draws_k_le_1"] == 1.0
        assert sign["constraints"]["frac_draws_gamma_ge_0"] == 1.0

    def test_the_reversing_exponent_is_the_bracket_endpoint(self, sign):
        assert abs(sign["reversal"]["k_at_which_direction_reverses"] - 1.0) < 1e-6

    def test_the_file_states_the_identity_rather_than_a_frequency(self, sign):
        assert "sigma(new)/sigma(old)" in sign["identity"]
        assert "magnitude" in sign["answer"].lower()

    def test_the_magnitude_range_matches_the_manuscript(self, sign):
        r = sign["scale_ratio_new_over_old"]
        assert abs(r["min"] - 1.04) < 0.01 and abs(r["max"] - 1.17) < 0.01




class TestJointPosteriorDraws:
    """Finding 1: one index per replicate, not one per parameter.

    A per-parameter index silently replaces the fitted joint posterior with the product
    of its marginals. Array lengths and marginal distributions are unaffected, which is
    why nothing downstream could see it -- so the test is an exact RELATION between
    parameters, which only survives aligned indexing."""

    def test_an_exact_relation_between_parameters_survives_every_draw(self, vu):
        n = 500
        base = np.linspace(0.5, 1.0, n)
        draws = {"k": base, "sd_div": 3.0 * base, "sd_undiv": 1.0 - base,
                 "gamma": np.sqrt(base)}
        rng = np.random.default_rng(2)
        for _ in range(2000):
            th = vu.posterior_draw(draws, rng, n)
            assert abs(th["sd_div"] - 3.0 * th["k"]) < 1e-12
            assert abs(th["sd_undiv"] - (1.0 - th["k"])) < 1e-12
            assert abs(th["gamma"] - np.sqrt(th["k"])) < 1e-12

    def test_it_visits_the_whole_posterior(self, vu):
        """Aligned indexing must not collapse to one draw."""
        n = 200
        draws = {"k": np.arange(n, dtype=float)}
        rng = np.random.default_rng(3)
        seen = {vu.posterior_draw(draws, rng, n)["k"] for _ in range(4000)}
        assert len(seen) > n * 0.9

    def test_the_independent_version_would_fail_this_test(self, vu):
        """The defect, written out: sampling each parameter separately breaks the
        relation almost always."""
        n = 500
        base = np.linspace(0.5, 1.0, n)
        draws = {"k": base, "sd_div": 3.0 * base}
        rng = np.random.default_rng(4)
        broken = [{p: draws[p][rng.integers(0, n)] for p in draws} for _ in range(200)]
        bad = sum(1 for th in broken if abs(th["sd_div"] - 3.0 * th["k"]) > 1e-12)
        assert bad > 190, bad

    def test_every_parameter_path_uses_the_helper(self):
        """Fixing the primary loop and leaving the parameter-only decomposition was
        named as an incomplete solution; nothing may build a parameter dict by
        indexing draws directly."""
        src = io.open(os.path.join(HERE, "src", "vignette_uncertainty.py"),
                      encoding="utf-8").read()
        assert "rng.integers(0, ndraw)] for p in draws" not in src
        assert src.count("posterior_draw(draws, rng, ndraw)") >= 2


class TestGpdBandSmoke:
    """The GPD script broke silently when the resampler's return type changed.

    It runs only in a full manifest pass, so nothing exercised it for a round. A tiny
    end-to-end call is enough to catch an interface break."""

    def test_analyse_runs_and_returns_finite_numbers(self):
        gpd = _module("gpd_mod", "src/gpd_var_uncertainty.py")
        S, R, H, synd, year = gpd.load_pool()
        draws, ref, hlo, hce = gpd.load_draws()
        ritc = gpd.load_ritc(synd, year)
        thbar = {p: float(draws[p].mean()) for p in draws}
        v1, _o, _n = gpd.load_targets()
        gpd.B = 5
        r = gpd.analyse("smoke", v1, S, R, H,
                        gpd.build_resampler(synd, year, "cluster"), draws, thbar,
                        (ref, hlo, hce), len(draws["k"]), np.random.default_rng(0), ritc)
        for key in ("point_var995", "band_lo_2.5", "band_hi_97.5"):
            assert np.isfinite(r[key]), (key, r[key])
        assert r["band_lo_2.5"] <= r["band_median"] <= r["band_hi_97.5"]

    def test_the_band_is_conditional_on_fixed_parameters(self):
        src = io.open(os.path.join(HERE, "src", "gpd_var_uncertainty.py"),
                      encoding="utf-8").read()
        assert "thbar, cfg, ritc[idx]" in src
        assert "rng.integers(0, ndraw)] for p in draws" not in src




class TestDocumentationMatchesTheEstimator:
    """Finding: the opening description said Dirichlet(1) a commit after the code
    stopped using it. The JSON, the inline comment and the manuscript had all moved.

    These tests tie the three surfaces together: the JSON meta must equal the module's
    declared spec, the docstring must carry each structural claim, and the CONCENTRATION
    FORMULA parsed out of the docstring must match what the sampler actually does."""

    def test_the_json_meta_is_the_module_spec(self, vu, results):
        for key, value in vu.ESTIMATOR_SPEC.items():
            assert results["meta"].get(key) == value, key

    def test_the_docstring_carries_every_structural_claim(self, vu):
        for claim in vu.DOC_INVARIANTS:
            assert claim in vu.__doc__, claim

    def test_the_docstring_does_not_describe_the_superseded_weights(self, vu):
        """It may NAME the superseded concentration to contrast with it -- a
        correction has to be allowed to say what it corrects -- but not assert it."""
        doc = vu.__doc__
        i = doc.find("Dirichlet(1)")
        if i != -1:
            assert "not Dirichlet(1)" in doc[max(0, i - 40):i + 20], doc[i - 60:i + 60]
        assert "same total weight regardless" not in doc

    def _documented_alpha(self, vu, S, n_s, N):
        """Evaluate the concentration formula AS WRITTEN in the docstring."""
        # stop at the gloss: the docstring writes "alpha_s = S * n_s / N   (S syndicates,
        # n_s years ...)", and swallowing the parenthetical makes the formula unparseable
        m = re.search(r"alpha_s\s*=\s*([A-Za-z0-9_ */+.-]+?)(?:\s{2,}|\(|\n|$)",
                      vu.__doc__)
        assert m, "the docstring states no concentration formula"
        expr = m.group(1).strip()
        return eval(expr, {"__builtins__": {}}, {"S": S, "n_s": n_s, "N": N})

    def test_the_documented_formula_reproduces_the_sampler_mean(self, vu):
        rng = np.random.default_rng(19)
        counts = np.array([1, 2, 3, 5, 9])
        synd = np.repeat(np.arange(len(counts)), counts)
        N, S = len(synd), len(counts)
        draw = vu.build_resampler(synd, np.arange(N), "bayes")
        W = np.array([draw(rng)[1] for _ in range(6000)])
        alpha = np.array([self._documented_alpha(vu, S, c, N) for c in counts])
        expected = alpha / alpha.sum()
        got = np.array([W[:, synd == i].sum(axis=1).mean() for i in range(S)])
        assert np.allclose(got, expected, atol=0.01), (got, expected)

    def test_the_documented_formula_reproduces_the_sampler_variance(self, vu):
        """The mean alone cannot distinguish alpha from 10*alpha; the variance fixes
        the total concentration, so the pair pins the documented formula."""
        rng = np.random.default_rng(23)
        counts = np.array([2, 2, 3, 3, 4, 4, 6, 6])
        synd = np.repeat(np.arange(len(counts)), counts)
        N, S = len(synd), len(counts)
        draw = vu.build_resampler(synd, np.arange(N), "bayes")
        W = np.array([draw(rng)[1] for _ in range(8000)])
        alpha = np.array([self._documented_alpha(vu, S, c, N) for c in counts])
        a0 = alpha.sum()
        p = alpha / a0
        expected_var = p * (1 - p) / (a0 + 1)
        got_var = np.array([W[:, synd == i].sum(axis=1).var() for i in range(S)])
        assert np.allclose(got_var, expected_var, rtol=0.25), (got_var, expected_var)

    def test_a_dirichlet_one_description_would_fail_that_check(self, vu):
        """The defect, written out: the superseded formula does not describe this
        sampler, and the numerical check is what says so."""
        counts = np.array([1, 2, 3, 5, 9])
        S, N = len(counts), int(counts.sum())
        alpha_wrong = np.ones(S)
        alpha_right = np.array([self._documented_alpha(vu, S, c, N) for c in counts])
        assert not np.allclose(alpha_wrong / alpha_wrong.sum(),
                               alpha_right / alpha_right.sum(), atol=0.01)




class TestAppendixCGeneratorMatchesItsSources:
    """Finding: the generator kept writing "cluster bootstrap x posterior draws" for two
    rows long after the analysis stopped doing that, and typed an exceedance count the
    sources contradicted. Manuscript prose had been corrected by hand, so only the next
    run would have shown it.

    Every assertion here compares the GENERATED artefact with the metadata of the files
    it reads, which is the only version of this check that cannot go stale."""

    ART = os.path.join(HERE, "figures", "appendix_c_tail_comparison.tex")

    def _mod(self):
        return _module("appendix_c_mod", "src/appendix_c_tail_comparison.py")

    def _artefact(self):
        if not os.path.exists(self.ART):
            pytest.skip("appendix C artefact not generated")
        return io.open(self.ART, encoding="utf-8").read()

    def test_the_note_is_the_one_the_sources_imply(self):
        mod = self._mod()
        rows, meta = mod.load()
        assert mod.method_note(meta) in " ".join(self._artefact().split())

    def test_the_withdrawn_hybrid_description_is_gone(self):
        flat = " ".join(self._artefact().split())
        assert "bootstrap $\\times$ posterior draws" not in flat
        assert "empirical and frequentist-POT from a cluster" not in flat

    def test_each_row_matches_its_source_file(self):
        mod = self._mod()
        rows, _meta = mod.load()
        flat = " ".join(self._artefact().split())
        for vign in rows:
            for method in ("Empirical", "EVT - frequentist POT", "EVT - Bayesian POT"):
                pt, lo, hi = rows[vign][method]
                assert "%.3f [%.3f, %.3f]" % (pt, lo, hi) in flat, (vign, method)

    def test_the_exceedance_count_is_read_not_typed(self):
        mod = self._mod()
        _rows, meta = mod.load()
        assert "N_u\\approx%.0f" % meta["nu_median"] in self._artefact()
        assert "approx49" not in self._artefact(), "the typed count is back"

    def test_the_guard_refuses_a_source_that_contradicts_the_label(self):
        """check_labels is the generator's own fail-closed check: a source declaring the
        withdrawn hybrid must stop the table being written at all."""
        mod = self._mod()
        _rows, meta = mod.load()
        hybrid = dict(meta, gp_estimator="cluster bootstrap x posterior draws of theta")
        with pytest.raises(SystemExit) as exc:
            mod.check_labels(hybrid)
        assert "frequentist-POT" in str(exc.value)

    def test_the_guard_refuses_a_non_bayesian_empirical_source(self):
        mod = self._mod()
        _rows, meta = mod.load()
        wrong = dict(meta, vu_estimator="multinomial_cluster_bootstrap")
        with pytest.raises(SystemExit):
            mod.check_labels(wrong)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
