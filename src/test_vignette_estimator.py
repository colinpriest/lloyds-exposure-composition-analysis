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

    def test_the_syndicate_weights_are_rubins_uniform_dirichlet(self, vu):
        """The construction, not a matched moment. On a BALANCED panel the exposure
        step is the identity, so the syndicate masses must be exactly a uniform
        Dirichlet: mean 1/S and variance (1/S)(1-1/S)/(S+1)."""
        S, per = 25, 4
        synd = np.repeat(np.arange(S), per)
        draw = vu.build_resampler(synd, np.arange(len(synd)), "bayes")
        rng = np.random.default_rng(5)
        tot = np.array([draw(rng)[1][synd == 0].sum() for _ in range(6000)])
        assert abs(tot.mean() - 1.0 / S) < 0.002, tot.mean()
        expect = (1.0 / S) * (1 - 1.0 / S) / (S + 1)
        assert 0.75 < tot.var() / expect < 1.35, (tot.var(), expect)

    def test_exposure_enters_the_mixture_not_the_concentration(self, vu):
        """n_s must act through the predictive mixture. Two syndicates, one with four
        times the exposure, must carry about four times the scenario mass -- while the
        SYNDICATE-level weights behind them stay uniform."""
        # with only two syndicates the Dirichlet's own shrinkage dominates; the design
        # is visible on a panel of realistic width
        counts = np.array([2] * 19 + [8])
        synd = np.repeat(np.arange(len(counts)), counts)
        draw = vu.build_resampler(synd, np.arange(len(synd)), "bayes")
        rng = np.random.default_rng(9)
        mass = np.array([[draw(rng)[1][synd == i].sum() for i in (0, len(counts) - 1)]
                         for _ in range(6000)])
        ratio = mass[:, 1].mean() / mass[:, 0].mean()
        assert 3.2 < ratio < 4.8, ratio

    def test_the_posterior_mean_is_not_forced_onto_the_point(self, vu):
        """Review's non-solution list: forcing the mean weights to reproduce the
        displayed point is a substitute for defining a population. On an unbalanced
        panel the exposure-weighted mean is CLOSE to the pooled shares but not equal,
        and nothing in the code arranges otherwise."""
        counts = np.array([1, 2, 3, 5, 9])
        synd = np.repeat(np.arange(len(counts)), counts)
        N = len(synd)
        draw = vu.build_resampler(synd, np.arange(N), "bayes")
        rng = np.random.default_rng(4)
        mass = np.array([[draw(rng)[1][synd == i].sum() for i in range(len(counts))]
                         for _ in range(6000)]).mean(axis=0)
        pooled = counts / N
        assert np.max(np.abs(mass - pooled)) > 1e-3, "the identity is being engineered"
        assert np.max(np.abs(mass - pooled)) < 0.08, (mass, pooled)

    def test_the_alternative_population_models_exist_and_differ(self, vu):
        """equal_cluster and row are reported as sensitivities, and they are genuinely
        different populations -- otherwise the sensitivity says nothing."""
        counts = np.array([1, 2, 3, 5, 9])
        synd = np.repeat(np.arange(len(counts)), counts)
        N = len(synd)
        rng = np.random.default_rng(6)
        got = {}
        for scheme in ("bayes", "equal_cluster", "row"):
            draw = vu.build_resampler(synd, np.arange(N), scheme)
            got[scheme] = np.array([[draw(rng)[1][synd == i].sum()
                                     for i in range(len(counts))]
                                    for _ in range(4000)]).mean(axis=0)
        assert abs(got["equal_cluster"][0] - 0.2) < 0.02, got["equal_cluster"]
        assert abs(got["row"][0] - counts[0] / N) < 0.01, got["row"]
        assert abs(got["bayes"][0] - got["equal_cluster"][0]) > 0.05

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

    def test_the_results_declare_the_population_model(self, results):
        """The removed declaration was that prior-mean weights reproduce the point --
        an engineered identity. What must be declared is the POPULATION."""
        meta = results["meta"]
        assert "syndicate-year" in meta["inferential_unit"]
        assert "prior_mean_weights_reproduce_point" not in meta
        model = meta["population_model"].lower()
        assert "exposure" in model and "uniformly" in model
        assert "Dirichlet(1" in meta["concentration"]
        assert "equal_cluster" in meta["sensitivity_population_models"]
        assert "one index per replicate" in meta["posterior_draw"]

    def test_the_population_sensitivity_is_reported_for_every_headline(self, results):
        ps = results["robustness"]["population_model_sensitivity"]
        for key in ("V1_adj_v995", "V1_change_pct_995", "V2_change_pct_995",
                    "P_fall_995"):
            assert set(ps[key]) == {"exposure_weighted_cluster", "equal_cluster",
                                    "row"}, key

    def test_the_population_choice_does_not_carry_the_conclusion(self, results):
        """If the three models disagreed materially the adopted one would be doing the
        work; they do not, and that is worth asserting."""
        p = results["robustness"]["population_model_sensitivity"]["P_fall_995"]
        assert max(p.values()) - min(p.values()) < 0.05, p

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
        # flattened: a claim that wraps across two lines is still stated, and the first
        # version of this check failed on exactly that -- the project's oldest lesson
        flat = " ".join(vu.__doc__.split())
        for claim in vu.DOC_INVARIANTS:
            assert " ".join(claim.split()) in flat, claim

    def test_the_docstring_states_the_population_model(self, vu):
        """The docstring must carry the DESIGN, since that is what makes the output a
        posterior; the previous version documented a tuned concentration instead."""
        doc = " ".join(vu.__doc__.split()).lower()
        assert "exposure" in doc
        assert "posterior predictive mixture" in doc
        assert "w ~ dirichlet(1, ..., 1)" in doc

    def test_the_withdrawn_concentration_is_named_only_as_withdrawn(self, vu):
        doc = " ".join(vu.__doc__.split())
        i = doc.find("alpha_s = S*n_s/N")
        if i != -1:
            window = doc[max(0, i - 200):i + 240].lower()
            assert "earlier version" in window and "withdrawn" in window, window

    def test_the_json_estimand_describes_the_same_construction(self, results):
        """The machine-readable field is a description too: it kept the withdrawn
        concentration for a commit after the docstring moved."""
        estimand = results["meta"]["estimand"].lower()
        assert "exposure" in estimand
        assert "dirichlet(1,...,1)" in estimand.replace(" ", "")
        assert "alpha_s = s*n_s/n" not in estimand


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




class TestDeclaredPdfsAreDeterministic:
    """R1: matplotlib stamps a CreationDate, so a declared PDF output could never be
    byte-verified. Two runs a second apart agreed on the .tex and .png and differed on
    the .pdf -- and the manifest verifies non-JSON outputs byte for byte."""

    def _declared_pdfs(self):
        rp = _module("rp34", "reproduce.py")
        return sorted({rel for outs in rp.OUTPUTS.values() for rel in outs
                       if rel.endswith(".pdf")})

    def test_the_manifest_declares_pdfs(self):
        assert self._declared_pdfs(), "no declared PDFs; this test has lost its subject"

    def test_every_pdf_writer_omits_the_creation_date(self):
        """Source-level, so a new figure script cannot reintroduce it."""
        import ast as _ast
        bad = []
        src = os.path.join(HERE, "src")
        for fn in sorted(os.listdir(src)):
            if not fn.endswith(".py") or fn.startswith("test_"):
                continue
            tree = _ast.parse(io.open(os.path.join(src, fn), encoding="utf-8",
                                      errors="replace").read())
            for node in _ast.walk(tree):
                if not (isinstance(node, _ast.Call)
                        and isinstance(node.func, _ast.Attribute)
                        and node.func.attr == "savefig"):
                    continue
                target = _ast.dump(node.args[0]) if node.args else ""
                if "pdf" not in target.lower():
                    continue
                if not any(kw.arg == "metadata" for kw in node.keywords):
                    bad.append("%s:%d" % (fn, node.lineno))
        assert bad == [], bad

    def test_regenerating_a_declared_pdf_twice_gives_identical_bytes(self):
        """The reviewer's own bullet: run the generator twice and show the hashes."""
        import hashlib
        import subprocess
        import sys
        import time
        rel = "figures/appendix_c_tail_comparison.pdf"
        path = os.path.join(HERE, rel)
        if not os.path.exists(path):
            pytest.skip("declared PDF not generated in this checkout")
        first = hashlib.sha256(io.open(path, "rb").read()).digest()
        t = time.time()
        while time.time() - t < 1.2:          # cross a second boundary: the old defect
            pass
        r = subprocess.run([sys.executable,
                            os.path.join(HERE, "src",
                                         "appendix_c_tail_comparison.py")],
                           cwd=HERE, capture_output=True)
        assert r.returncode == 0, r.stderr[-400:]
        second = hashlib.sha256(io.open(path, "rb").read()).digest()
        assert first == second, "the declared PDF is not byte-reproducible"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


class TestThreePlayerShapley:
    """Round 36, M1: shapley_v1 standardised every coalition on the de-RITC'd
    residual, so its 'size' and 'concentration' were a two-player split CONDITIONAL
    on the tail map, and the manuscript called the leftover an 'order-averaged
    (Shapley) contribution' when it was numerically the map applied first. The
    decomposition must own the tail regime as a third player over all 8 coalitions."""

    TH = {"k": 0.606, "gamma": 0.243, "sd_undiv": 0.0207, "sd_div": 0.058,
          "nu_clean": 2.43, "nu_ritc": 1.55}
    CFG = (500.0, 0.01, 1.0)
    TGT = (500.0, 0.17)

    def _pool(self):
        rng = np.random.default_rng(7)
        n = 60
        R = rng.uniform(30, 2000, n)
        H = rng.uniform(0.12, 0.6, n)
        ritc = np.zeros(n, bool)
        ritc[::4] = True
        S = rng.standard_t(3, n) * 0.08
        # the quantile map only moves VaR99.5 when RITC donors occupy the extreme
        # tail, so put the two largest severities in the RITC regime
        ritc[np.argsort(S)[-2:]] = True
        return S, R, H, ritc

    def _sig(self, vu, Rx, Hx):
        th = self.TH
        return vu.sigma_theta(Rx, Hx, th["k"], th["gamma"], th["sd_undiv"],
                              th["sd_div"], *self.CFG)

    def _coalition_values(self, vu, S, R, H, ritc):
        base = self._sig(vu, R, H)
        z_raw = S / base
        z_map = vu.deritc_resid(z_raw, self.TH, ritc)
        Rq, Hq = self.TGT
        v = {}
        for mask in range(8):
            z = z_map if (mask & 1) else z_raw
            Rx = np.full_like(R, Rq) if (mask & 2) else R
            Hx = np.full_like(H, Hq) if (mask & 4) else H
            v[mask] = vu.var_q(z * self._sig(vu, Rx, Hx), 0.995)
        return v

    def test_the_components_bridge_raw_to_adjusted_exactly(self, vu):
        """Efficiency against quantities computed OUTSIDE the function: the raw pool
        VaR and the transferred pool VaR."""
        S, R, H, ritc = self._pool()
        idx = np.arange(len(S))
        te, se, ce = vu.shapley_v1(S, R, H, idx, self.TGT, self.TH, self.CFG, ritc)
        raw = vu.var_q(S, 0.995)
        adj = vu.var_q(vu.transfer(S, R, H, self.TGT, self.TH, self.CFG, ritc), 0.995)
        assert abs((te + se + ce) - (adj - raw)) < 1e-12

    def test_it_matches_a_permutation_average_reference(self, vu):
        """The Shapley weighting itself, against an independent enumeration of the
        six orderings over independently rebuilt coalition values."""
        from itertools import permutations
        S, R, H, ritc = self._pool()
        idx = np.arange(len(S))
        v = self._coalition_values(vu, S, R, H, ritc)
        totals = {1: 0.0, 2: 0.0, 4: 0.0}
        for order in permutations((1, 2, 4)):
            mask = 0
            for f in order:
                totals[f] += v[mask | f] - v[mask]
                mask |= f
        want = (totals[1] / 6.0, totals[2] / 6.0, totals[4] / 6.0)
        got = vu.shapley_v1(S, R, H, idx, self.TGT, self.TH, self.CFG, ritc)
        for g, w in zip(got, want):
            assert abs(g - w) < 1e-12, (got, want)

    def test_the_tail_player_vanishes_when_no_regime_changes(self, vu):
        """The reduction the manuscript is allowed to state: with no RITC donor the
        map is the identity, the tail player is exactly zero, and size plus
        concentration carry the whole change."""
        S, R, H, _ = self._pool()
        idx = np.arange(len(S))
        none = np.zeros(len(S), bool)
        te, se, ce = vu.shapley_v1(S, R, H, idx, self.TGT, self.TH, self.CFG, none)
        assert te == 0.0
        raw = vu.var_q(S, 0.995)
        adj = vu.var_q(vu.transfer(S, R, H, self.TGT, self.TH, self.CFG, none), 0.995)
        assert abs((se + ce) - (adj - raw)) < 1e-12

    def test_the_conditional_two_player_split_is_gone(self, vu):
        """The old behaviour summed size+conc to (adjusted minus DE-RITC'D raw); the
        genuine three-player size+conc must NOT reproduce that conditional bridge
        while a tail effect exists."""
        S, R, H, ritc = self._pool()
        idx = np.arange(len(S))
        te, se, ce = vu.shapley_v1(S, R, H, idx, self.TGT, self.TH, self.CFG, ritc)
        assert te != 0.0
        base = self._sig(vu, R, H)
        z0 = vu.deritc_resid(S / base, self.TH, ritc)
        adj = vu.var_q(vu.transfer(S, R, H, self.TGT, self.TH, self.CFG, ritc), 0.995)
        old_bridge = adj - vu.var_q(z0 * base, 0.995)
        assert abs((se + ce) - old_bridge) > 1e-6, \
            "size+conc still equals the tail-conditional bridge"

    def test_the_json_components_sum_to_the_reported_total(self, results):
        s = results["vignette1"]["shapley_995"]
        assert s.get("n_coalitions") == 8
        assert {"tail_regime", "size", "concentration"} <= set(s)
        total = results["vignette1"]["change_raw_to_adjusted"]["abs_995"]["mean"]
        comp = (s["tail_regime"]["mean"] + s["size"]["mean"]
                + s["concentration"]["mean"])
        assert abs(comp - total) < 1e-9, (comp, total)

    def test_v2_declares_why_two_players_are_complete(self, results, vu):
        """Two players for the paired vignette is a theorem about the design, and
        both the output and the code must state it rather than leave it implicit."""
        s2 = results["vignette2"]["shapley_995"]
        assert "identically zero" in s2.get("note", "")
        assert "size_change" in s2 and "concentration_change" in s2
        assert "complete decomposition" in (vu.shapley_v2.__doc__ or "").lower()


class TestPointDecompositionBlock:
    """Round 37, M2: the manuscript compared the posterior-mean tail component with
    the full-pool point added-last step and blamed the whole gap on ordering. The
    like-for-like partner (the point Shapley tail) must be computed, persisted, and
    internally exact -- the sequential steps are marginal contributions of the SAME
    coalition system (added-first = v1-v0, added-last = v7-v6)."""

    def test_the_point_block_is_internally_exact(self, results):
        p = results["vignette1"]["shapley_995_point_full_pool"]
        cv = {int(k): float(v) for k, v in p["coalition_var995"].items()}
        assert set(cv) == set(range(8))
        assert abs(p["tail_regime"] + p["size"] + p["concentration"]
                   - p["total"]) < 1e-9
        assert abs(p["total"] - (cv[7] - cv[0])) < 1e-12
        assert abs(p["added_last_tail_step"] - (cv[7] - cv[6])) < 1e-12
        assert abs(p["added_first_tail_step"] - (cv[1] - cv[0])) < 1e-12

    def test_the_point_total_is_the_centres_point_change(self, results):
        p = results["vignette1"]["shapley_995_point_full_pool"]
        centre = results["centres_full_pool_posterior_mean"]["V1_d995"]
        assert abs(p["total"] - centre) < 1e-12

    def test_the_point_and_posterior_summaries_are_distinct(self, results):
        """The two summaries must not silently collapse into one: the point tail is
        the like-for-like partner of the added-last step, and the posterior mean is
        a different functional of a different distribution."""
        p = results["vignette1"]["shapley_995_point_full_pool"]
        s = results["vignette1"]["shapley_995"]
        assert abs(p["tail_regime"] - s["tail_regime"]["mean"]) > 1e-4
        # ordering moderates the sequential step: added-last is the extreme order
        assert abs(p["added_last_tail_step"]) > abs(p["tail_regime"])
        assert abs(p["added_first_tail_step"]) < abs(p["tail_regime"])

    def test_the_coalition_view_agrees_with_the_players(self, vu):
        rng = np.random.default_rng(11)
        n = 50
        R = rng.uniform(30, 2000, n)
        H = rng.uniform(0.12, 0.6, n)
        S = rng.standard_t(3, n) * 0.08
        ritc = np.zeros(n, bool)
        ritc[np.argsort(S)[-2:]] = True
        th = {"k": 0.606, "gamma": 0.243, "sd_undiv": 0.0207, "sd_div": 0.058,
              "nu_clean": 2.43, "nu_ritc": 1.55}
        cfg = (500.0, 0.01, 1.0)
        idx = np.arange(n)
        a = vu.shapley_v1(S, R, H, idx, (500.0, 0.17), th, cfg, ritc)
        te, se, ce, v = vu.shapley_v1_coalitions(S, R, H, idx, (500.0, 0.17),
                                                 th, cfg, ritc)
        assert a == (te, se, ce)
        assert set(v) == set(range(8))
        assert abs(v[0] - vu.var_q(S, 0.995)) < 1e-12
        adj = vu.transfer(S, R, H, (500.0, 0.17), th, cfg, ritc)
        assert abs(v[7] - vu.var_q(adj, 0.995)) < 1e-12
