#!/usr/bin/env python3
"""The two new departures of adopted_model.scale_block and the sensitivity records built on them.

check_gamma0_refit.py refits the adopted model with gamma the constant 0 in the likelihood (gamma_prior="fixed_0");
check_k_support.py refits it with k on a wider support (k_prior="logistic_0.25" and "logistic_0"). Both are
sensitivity records: the adopted fit stays the headline. These tests hold the options to what they claim (the
default path is unchanged, which test_model_variants.py pins on the graph; the new paths differ only where declared)
and the committed records to the form, sampling quality and arithmetic they state:

  * scale_block: fixed_0 creates no gamma variable and gives the adopted scale at gamma = 0; the wider supports put
    k at k_lo + (1 - k_lo) logistic(theta); an unknown option is refused;
  * the prior mass of k below 1/2 on each support: exact, against draws from the prior, and not borrowed from
    check_prior_masses.prior_masses, which states P(k > 1/2) as one;
  * each record: clean sampling, the published fit's centres equal to check_gamma0_vignette.py's record, the stored
    relative changes and the list of those moved by 2% or more recomputed from the stored centres and means.

Run:  python -m pytest src/test_k_gamma_departures.py -q
"""
import ast
import io
import json
import os

import numpy as np
import pytest
from scipy import stats

import pymc as pm
import pytensor

import adopted_model as am
import check_gamma0_refit as G
import check_k_support as KS
import transfer_operator as TO

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")


def _json(rel):
    return json.load(io.open(os.path.join(HERE, rel), encoding="utf-8"))


def _ref():
    return np.load(os.path.join(HERE, "tests_data", "adopted_block_reference.npz"))


def _eval(m, expr, point):
    """`expr` (a function of the model's random variables) at a point of value-variable values."""
    ins = list(m.value_vars)
    f = pytensor.function(ins, m.replace_rvs_by_values([expr])[0], on_unused_input="ignore")
    return f(*[point[v.name] for v in ins])


def _build(**kw):
    ref = _ref()
    with pm.Model() as m:
        b = am.scale_block(ref["R"], ref["H"], ref["yr"], ref["ritc"], **kw)
    return m, b


# ------------------------------------------------------------------ gamma_prior ------
def test_gamma_fixed_at_zero_creates_no_gamma_variable():
    m, b = _build(gamma_prior="fixed_0")
    names = [v.name for v in m.free_RVs]
    assert "gamma" not in names and "gamma" not in [v.name for v in m.deterministics]
    assert b["gamma"] == 0.0
    assert names == ["theta", "log_tot", "f", "tau_s", "z_s", "nu_clean", "lambda_ritc", "beta_ritc"]


def test_the_default_gamma_is_still_the_halfnormal():
    m, _b = _build()
    assert "gamma" in [v.name for v in m.free_RVs]
    m2, _b2 = _build(gamma_prior="halfnormal")
    assert [v.name for v in m2.free_RVs] == [v.name for v in m.free_RVs]


def test_fixed_zero_gives_the_adopted_scale_at_gamma_zero():
    """The two graphs share every other term: at gamma ~ 0 the adopted sigma is the fixed-0 sigma."""
    ma, ba = _build()
    mb, bb = _build(gamma_prior="fixed_0")
    pa = ma.initial_point()
    pa["theta"] = np.array(0.3)
    pa["gamma_log__"] = np.array(-80.0)          # gamma = exp(-80): zero to machine precision
    pb = {k: v for k, v in pa.items() if k != "gamma_log__"}
    sa = _eval(ma, ba["sigma"], pa)
    sb = _eval(mb, bb["sigma"], pb)
    assert np.allclose(sa, sb, rtol=1e-12, atol=0)
    pa["gamma_log__"] = np.array(0.0)            # gamma = 1: the concentration term now matters
    assert not np.allclose(_eval(ma, ba["sigma"], pa), sb, rtol=1e-3), "the check cannot tell gamma 1 from 0"


@pytest.mark.parametrize("kw", [{"gamma_prior": "free"}, {"gamma_prior": None}, {"k_prior": "logistic_0.1"}, {"k_prior": "x"}])
def test_an_unknown_option_is_refused(kw):
    with pytest.raises(ValueError):
        _build(**kw)


# ------------------------------------------------------------------ the support of k ------
@pytest.mark.parametrize("k_prior,k_lo", [("logistic", 0.5), ("logistic_0.25", 0.25), ("logistic_0", 0.0)])
def test_k_is_the_logistic_on_its_support(k_prior, k_lo):
    assert am.K_LOWER[k_prior] == k_lo and k_prior in am.K_PRIORS
    m, b = _build(k_prior=k_prior)
    for theta in (-40.0, -1.0, 0.0, 2.5, 40.0):
        p = m.initial_point()
        p["theta"] = np.array(theta)
        want = k_lo + (1.0 - k_lo) / (1.0 + np.exp(-theta))
        assert float(_eval(m, b["k"], p)) == pytest.approx(want, abs=1e-12), (k_prior, theta)
    assert [v.name for v in m.free_RVs][0] == "theta"           # the same free variable, the same prior
    from check_prior_masses import prior_of
    assert prior_of(m, "theta") == ("NormalRV", [0.0, 1.5])


def test_the_fixed_lower_end_and_the_wider_supports_are_the_only_k_priors():
    assert am.K_PRIORS == ("logistic", "fixed_0.5", "logistic_0.25", "logistic_0")


# ------------------------------------------------------------------ the prior mass of k below 1/2 ------
def test_the_prior_mass_below_half_in_closed_form():
    assert KS.k_cdf_prior(0.25, 0.5, 0.0, 1.5) == pytest.approx(stats.norm.cdf(np.log(0.5) / 1.5), abs=1e-14)
    assert KS.k_cdf_prior(0.0, 0.5, 0.0, 1.5) == pytest.approx(0.5, abs=1e-14)       # the median of k is 1/2
    assert KS.k_cdf_prior(0.5, 0.5, 0.0, 1.5) == 0.0                                  # the bracket: nothing below 1/2
    assert KS.k_cdf_prior(0.25, 0.2, 0.0, 1.5) == 0.0 and KS.k_cdf_prior(0.25, 1.0, 0.0, 1.5) == 1.0
    # strictly increasing in c, and monotone in the lower end: a wider support puts more prior below 1/2
    cs = np.linspace(0.3, 0.95, 14)
    assert np.all(np.diff([KS.k_cdf_prior(0.25, c, 0.0, 1.5) for c in cs]) > 0)
    assert KS.k_cdf_prior(0.0, 0.5, 0.0, 1.5) > KS.k_cdf_prior(0.25, 0.5, 0.0, 1.5) > KS.k_cdf_prior(0.5, 0.5, 0.0, 1.5)


@pytest.mark.parametrize("k_lo", [0.25, 0.0])
def test_the_closed_form_agrees_with_draws_from_the_prior(k_lo):
    theta = np.random.default_rng(7).normal(0.0, 1.5, 400000)
    k = k_lo + (1.0 - k_lo) / (1.0 + np.exp(-theta))
    for c in (0.4, 0.5, 0.6):
        p = KS.k_cdf_prior(k_lo, c, 0.0, 1.5)
        assert abs((k < c).mean() - p) < 4.5 * np.sqrt(p * (1 - p) / k.size) + 1e-4, (k_lo, c)


@pytest.mark.parametrize("k_prior,want", [("logistic_0", 0.5), ("logistic_0.25", 0.3220054790252)])
def test_the_script_reads_the_prior_off_the_graph(k_prior, want):
    out = KS.prior_masses(k_prior)
    assert out["theta_prior"] == {"family": "NormalRV", "mu": 0.0, "sd": 1.5}
    assert out["closed_form"]["k_lt_0.5"] == pytest.approx(want, abs=1e-9)
    for key, p in out["closed_form"].items():
        assert abs(out["monte_carlo"][key] - p) < 5 * np.sqrt(p * (1 - p) / out["monte_carlo_draws"]) + 1e-3


def test_the_prior_mass_does_not_come_from_check_prior_masses():
    """check_prior_masses.prior_masses states P(k > 1/2) as one, true only on the bracketed support."""
    tree = ast.parse(io.open(os.path.join(SRC, "check_k_support.py"), encoding="utf-8").read())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "check_prior_masses"
                for a in n.names}
    assert "prior_masses" not in imported and "monte_carlo_masses" not in imported, imported


def test_the_posterior_summary_on_a_known_sample():
    k = np.linspace(0.25, 1.0, 751)                  # step 0.001
    s = KS.k_posterior(k, 0.25)
    assert s["k_lt_0.5"] == pytest.approx(250 / 751)             # 0.250 ... 0.499
    assert s["k_lt_0.55"] == pytest.approx(300 / 751)
    assert s["k_in_lower_edge"] == pytest.approx(38 / 751)       # below 0.25 + 0.05 * 0.75
    assert s["k_in_upper_edge"] == pytest.approx(38 / 751)
    assert s["min"] == 0.25 and s["max"] == 1.0
    assert s["mean"] == pytest.approx(0.625) and s["quantiles"]["0.5"] == pytest.approx(0.625)
    assert s["quantiles"]["0.005"] == pytest.approx(0.25 + 0.005 * 0.75, abs=2e-3)
    assert s["hdi_97.5"] - s["hdi_2.5"] == pytest.approx(0.95 * 0.75, abs=3e-3)      # the shortest 95% interval


# ------------------------------------------------------------------ the arithmetic of the two scripts ------
def test_relative_change_is_new_over_old_minus_one():
    for mod in (G, KS):
        assert mod.relative(1.1, 1.0) == pytest.approx(0.1) and mod.relative(0.5, 2.0) == pytest.approx(-0.75)


def test_the_size_ratio_is_the_small_book_over_the_large_book_at_the_operators_gamma():
    means = {"k": 0.6, "gamma": 0.4, "sd_undiv": 0.03, "sd_div": 0.06}
    cfg = (500.0, 0.01, 1.0)

    def sigma(r):
        return np.sqrt(0.03 ** 2 + 0.06 ** 2 * (r / 500.0) ** (2 * (0.6 - 1.0)))      # gamma zeroed: no H term

    assert G.size_ratio(means, cfg) == pytest.approx(sigma(100.0) / sigma(2000.0), rel=1e-12)
    assert G.size_ratio(means, cfg) > 1.0, "a small book is more dispersed than a large one"
    assert G.size_ratio(dict(means, gamma=0.9), cfg) == G.size_ratio(means, cfg)     # the operator zeroes gamma


# ------------------------------------------------------------------ the records ------
def _sampling_ok(d):
    assert d["divergences"] == 0 and d["max_rhat"] <= 1.01 and d["min_ess_bulk"] >= 400, d


def _centres_equal_the_gamma0_record(block, mode):
    assert block["adopted"]["centre"] == _json("results/check_gamma0_vignette_results.json")[mode]["centre"]


def _moved(rc, names):
    return sorted(q for q in names if abs(rc[q]) >= 0.02)


@pytest.fixture(scope="module")
def g():
    return _json("results/check_gamma0_refit_results.json")


@pytest.fixture(scope="module")
def ks():
    return _json("results/check_k_support_results.json")


class TestTheGamma0Refit:
    def test_form_and_sampler(self, g):
        assert (g["n"], g["n_ritc"]) == (674, 38)
        assert (g["draws"], g["tune"], g["chains"], g["target_accept"], g["fit_seed"]) == (1500, 1500, 4, 0.98, 42)
        assert set(g["gamma0_fit"]["params"]) == set(G.PARAMS) and "gamma" not in g["gamma0_fit"]["params"]
        for p, v in g["gamma0_fit"]["params"].items():
            assert v["hdi_2.5"] < v["mean"] < v["hdi_97.5"], p
        _sampling_ok(g["gamma0_fit"]["diagnostics"])

    def test_the_sampler_is_the_headline_calibrations(self):
        import re
        src = io.open(os.path.join(SRC, "calibrate_dispersion_ritc.py"), encoding="utf-8").read()
        assert re.search(r"pm\.sample\(1500, tune=1500, chains=4,[^)]*target_accept=0\.98,\s*random_seed=SEED", src)
        assert re.search(r"^SEED = 42$", src, re.M)
        for mod in (G, KS):
            assert (mod.DRAWS, mod.TUNE, mod.CHAINS, mod.TARGET_ACCEPT, mod.FIT_SEED) == (1500, 1500, 4, 0.98, 42)

    def test_the_published_fit_is_like_for_like_with_check_gamma0(self, g):
        _centres_equal_the_gamma0_record(g["vignettes"], TO.HEADLINE)

    def test_the_headline_operator_and_no_overlay_leg(self, g):
        v = g["vignettes"]
        assert (v["operator"], v["operator_role"]) == ("size_only", "headline")
        assert "overlay" not in json.dumps(v["adopted"]) and "overlay_sensitivity" not in v

    def test_the_guard_names_every_shared_parameter_and_is_recorded_not_enforced(self, g):
        hg = g["headline_guard"]
        assert hg["enforced"] is False
        assert sorted(r["param"] for r in hg["rows"]) == sorted(am.SHARED)
        gamma = [r for r in hg["rows"] if r["param"] == "gamma"][0]
        assert gamma["refit"] == 0.0 and gamma["gap_in_sd"] > am.TOL_SD         # 0 by construction
        assert hg["within_tolerance"] is all(r["gap_in_sd"] <= am.TOL_SD for r in hg["rows"])

    def test_relative_changes_and_the_moved_list_are_recomputed_from_the_stored_figures(self, g):
        rc, v = g["relative_change_of_means"], g["vignettes"]
        for p in G.PARAMS:
            assert rc[p] == pytest.approx(g["gamma0_fit"]["params"][p]["mean"] / g["adopted_params"][p]["mean"] - 1.0)
        for q in v["adopted"]["centre"]:
            assert rc[q] == pytest.approx(v["gamma0_refit"]["centre"][q] / v["adopted"]["centre"][q] - 1.0)
            assert v["centre_pct_change"][q] == pytest.approx(100.0 * rc[q])
        assert g["headline_quantities_moved_by_2pct_or_more"] == _moved(rc, G.HEADLINE_QUANTITIES)
        assert g["relative_flag"] == 0.02

    def test_the_adopted_means_are_stored_at_full_precision(self, g):
        full = _json("model/dispersion_calibration_ritc.json")
        for p in G.PARAMS:
            assert g["adopted_params"][p]["mean"] == (full[p] if p in full else full["params"][p]["mean"])
        assert g["adopted_params"]["sd_undiv"]["mean"] != round(full["sd_undiv"], 3), "the floor was rounded"

    def test_the_fit_has_no_gamma_to_apply(self, g):
        # a refit without gamma: the size-only scale ratio is the same law at every H, as the operator makes it
        r = g["size_ratio_100_2000_size_only"]
        assert r["adopted"] > 1.0 and r["gamma0_refit"] > 1.0
        assert r["pct_change"] == pytest.approx(100.0 * (r["gamma0_refit"] / r["adopted"] - 1.0))


class TestTheKSupport:
    def test_form_and_sampler(self, ks):
        assert (ks["n"], ks["n_ritc"]) == (674, 38)
        assert (ks["draws"], ks["tune"], ks["chains"], ks["target_accept"], ks["fit_seed"]) == (1500, 1500, 4, 0.98, 42)
        assert ks["supports"] == ["logistic_0.25", "logistic_0"] == list(KS.SUPPORTS)
        for name, f in ks["fits"].items():
            _sampling_ok(f["diagnostics"])
            assert set(f["params"]) == set(KS.PARAMS)
            kp = f["k_posterior"]
            lo = am.K_LOWER[name]
            assert lo <= kp["min"] <= kp["quantiles"]["0.005"] <= kp["quantiles"]["0.025"] <= kp["quantiles"]["0.5"] \
                <= kp["quantiles"]["0.975"] <= kp["max"] <= 1.0
            assert lo <= kp["hdi_2.5"] < kp["mean"] < kp["hdi_97.5"] <= 1.0

    def test_the_prior_masses_are_the_closed_forms_and_beside_the_posterior(self, ks):
        for name, want in (("logistic_0.25", float(stats.norm.cdf(np.log(0.5) / 1.5))), ("logistic_0", 0.5)):
            f = ks["fits"][name]
            assert ks["prior_masses"][name]["closed_form"]["k_lt_0.5"] == pytest.approx(want, abs=1e-12)
            assert f["mass_below_half"]["prior"] == pytest.approx(want, abs=1e-12)
            assert f["mass_below_half"]["posterior"] == f["k_posterior"]["k_lt_0.5"]
            mc = ks["prior_masses"][name]
            for key, p in mc["closed_form"].items():
                assert abs(mc["monte_carlo"][key] - p) < 5 * np.sqrt(p * (1 - p) / mc["monte_carlo_draws"]) + 1e-3
        a = ks["adopted"]
        assert a["mass_below_half"] == {"posterior": 0.0, "prior": 0.0} and a["k_posterior"]["min"] >= 0.5

    def test_the_adopted_k_is_the_published_posterior(self, ks):
        assert ks["adopted"]["k_posterior"]["mean"] == pytest.approx(_json("model/dispersion_calibration_ritc.json")["k"],
                                                                   abs=1e-9)

    def test_the_published_fit_is_like_for_like_with_check_gamma0(self, ks):
        _centres_equal_the_gamma0_record(ks["vignettes"], TO.HEADLINE)
        _centres_equal_the_gamma0_record(ks["vignettes"]["overlay_sensitivity"], TO.SENSITIVITY)

    def test_both_operators_are_stamped(self, ks):
        v = ks["vignettes"]
        assert (v["operator"], v["operator_role"]) == ("size_only", "headline")
        o = v["overlay_sensitivity"]
        assert (o["operator"], o["operator_role"]) == ("overlay", "sensitivity")

    def test_relative_changes_and_the_moved_lists_are_recomputed_from_the_stored_figures(self, ks):
        head = ks["vignettes"]
        for name in ks["supports"]:
            rc = ks["relative_change_of_means"][name]
            for p in KS.PARAMS:
                assert rc[p] == pytest.approx(ks["fits"][name]["params"][p]["mean"] / ks["adopted"]["params"][p]["mean"] - 1)
            for q in head["adopted"]["centre"]:
                assert rc[q] == pytest.approx(head[name]["centre"][q] / head["adopted"]["centre"][q] - 1.0)
                assert head[name]["centre_pct_change"][q] == pytest.approx(100.0 * rc[q])
            assert ks["headline_quantities_moved_by_2pct_or_more"][name] == _moved(rc, KS.HEADLINE_QUANTITIES)
            assert [r["param"] for r in ks["headline_guard"]["fits"][name]["rows"]] == am.SHARED

    def test_the_prior_mass_note_says_why_check_prior_masses_is_not_used(self, ks):
        assert "check_prior_masses.prior_masses" in ks["prior_masses_note"] and "as one" in ks["prior_masses_note"]
