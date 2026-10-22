#!/usr/bin/env python3
"""The gamma options of adopted_model.scale_block, the wider supports of k, and the records built on them.

Since option B (the author's decision of 10 October 2026) the headline fixes gamma at 0 in the likelihood: scale_block's
default is gamma_prior="fixed_0", and gamma_prior="halfnormal" is the gamma-free fit, the concentration overlay's
source. check_gamma_free_fit.py (until then check_gamma0_refit.py, which fitted the gamma = 0 model as a sensitivity)
sets the gamma-free fit beside the headline without fitting anything; check_k_support.py refits the headline with k
on a wider support (k_prior="logistic_0.25" and "logistic_0"). These tests hold the options to what they claim
(test_model_variants.py pins both graphs) and the committed records to the form, sampling quality and arithmetic
they state:

  * scale_block: the default and fixed_0 create no gamma variable; halfnormal does, and at gamma = 0 gives the
    headline's scale; the wider supports put k at k_lo + (1 - k_lo) logistic(theta); an unknown option is refused;
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
import check_gamma_free_fit as G
import check_k_support as KS
import transfer_operator as TO

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")


def _json(rel):
    with io.open(os.path.join(HERE, rel), encoding="utf-8") as _fh:
        return json.load(_fh)


def _ref():
    with np.load(os.path.join(HERE, "tests_data", "adopted_block_reference.npz")) as _npz:
        return {key: _npz[key] for key in _npz.files}


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


def test_the_default_gamma_is_fixed_at_zero():
    """Option B: the headline (scale_block's default) has no gamma variable; the gamma-free fit asks for one."""
    m, b = _build()
    assert "gamma" not in [v.name for v in m.free_RVs] and b["gamma"] == 0.0
    m0, _b0 = _build(gamma_prior="fixed_0")
    assert [v.name for v in m0.free_RVs] == [v.name for v in m.free_RVs]
    m2, _b2 = _build(gamma_prior="halfnormal")
    assert "gamma" in [v.name for v in m2.free_RVs]
    import inspect
    assert inspect.signature(am.scale_block).parameters["gamma_prior"].default == "fixed_0"


def test_fixed_zero_gives_the_adopted_scale_at_gamma_zero():
    """The two graphs share every other term: at gamma ~ 0 the gamma-free sigma is the fixed-0 (headline) sigma."""
    ma, ba = _build(gamma_prior="halfnormal")
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
    with io.open(os.path.join(SRC, "check_k_support.py"), encoding="utf-8") as _fh:
        tree = ast.parse(_fh.read())
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


def test_the_size_ratio_is_the_small_book_over_the_large_book_at_the_gamma_given():
    """check_gamma_free_fit.size_ratio reads the scale law as given: both of its constructions have gamma = 0 (the
    headline fit's, and the retired construction's zeroed draws), so the ratio is the size law's alone."""
    means = {"k": 0.6, "gamma": 0.0, "sd_undiv": 0.03, "sd_div": 0.06}
    cfg = (500.0, 0.01, 1.0)

    def sigma(r):
        return np.sqrt(0.03 ** 2 + 0.06 ** 2 * (r / 500.0) ** (2 * (0.6 - 1.0)))      # gamma = 0: no H term

    assert G.size_ratio(means, cfg) == pytest.approx(sigma(100.0) / sigma(2000.0), rel=1e-12)
    assert G.size_ratio(means, cfg) > 1.0, "a small book is more dispersed than a large one"
    # a non-zero gamma enters at H = 0.4: the function does not zero it, the caller's construction does
    assert G.size_ratio(dict(means, gamma=0.9), cfg) != pytest.approx(G.size_ratio(means, cfg), rel=1e-6)


def test_the_fit_parameters_are_read_at_full_precision():
    cal = {"k": 0.58761234, "sd_undiv": 0.0337123, "params": {
        p: {"mean": 0.1, "sd": 0.01, "hdi_2.5": 0.0, "hdi_97.5": 0.2} for p in G.PARAMS + ("gamma",)}}
    out = G.fit_params(cal)
    assert out["k"]["mean"] == 0.58761234 and out["sd_undiv"]["mean"] == 0.0337123
    assert out["tau_s"]["mean"] == 0.1 and "gamma" in out
    del cal["params"]["gamma"]
    assert "gamma" not in G.fit_params(cal)


def test_the_retired_construction_is_declared_for_this_script_only():
    assert set(TO.RETIRED_ZEROING_DECLARED) == {"check_gamma_free_fit.py"}
    with io.open(os.path.join(SRC, "check_gamma_free_fit.py"), encoding="utf-8") as _fh:
        src = _fh.read()
    assert "retired_zeroing=True" in src


# ------------------------------------------------------------------ the records ------
def _sampling_ok(d):
    assert d["divergences"] == 0 and d["max_rhat"] <= 1.01 and d["min_ess_bulk"] >= 400, d


def _centres_equal_the_gamma0_record(block, mode, key="adopted"):
    assert block[key]["centre"] == _json("results/check_gamma0_vignette_results.json")[mode]["centre"]


def _moved(rc, names):
    return sorted(q for q in names if abs(rc[q]) >= 0.02)


@pytest.fixture(scope="module")
def g():
    """results/check_gamma_free_fit_results.json is written by the regeneration."""
    return _json("results/check_gamma_free_fit_results.json")


@pytest.fixture(scope="module")
def ks():
    return _json("results/check_k_support_results.json")


class TestTheGammaFreeFit:
    """The record check_gamma_free_fit.py writes from both committed calibrations."""

    def test_form_and_the_two_fits(self, g):
        # 649 (34 RITC-regime) since the regeneration of 23 October 2026 on the primary sample; 672 (38) before it
        assert (g["n"], g["n_ritc"]) == (649, 34) and g["fit_seed"] == 42
        assert set(g["headline_fit"]["params"]) == set(G.PARAMS) and "gamma" not in g["headline_fit"]["params"]
        assert set(g["gamma_free_fit"]["params"]) == set(G.PARAMS) | {"gamma"}
        for fit in ("headline_fit", "gamma_free_fit"):
            for p, v in g[fit]["params"].items():
                assert v["hdi_2.5"] < v["mean"] < v["hdi_97.5"], (fit, p)
            _sampling_ok(g[fit]["diagnostics"])
        gf = _json("model/dispersion_calibration_ritc_gamma_free.json")
        assert g["gamma_free_fit"]["posterior_prob"]["gamma_gt_0.05"] == gf["posterior_prob"]["gamma_gt_0.05"]
        assert g["gamma_free_fit"]["prior_prob"]["gamma_gt_0.05"] == gf["prior_prob"]["gamma_gt_0.05"]

    def test_the_sampler_is_the_headline_calibrations(self):
        import re
        with io.open(os.path.join(SRC, "calibrate_dispersion_ritc.py"), encoding="utf-8") as _fh:
            src = _fh.read()
        assert re.search(r"pm\.sample\(1500, tune=1500, chains=4,[^)]*target_accept=0\.98,\s*random_seed=SEED", src)
        assert re.search(r"^SEED = 42$", src, re.M)
        assert (KS.DRAWS, KS.TUNE, KS.CHAINS, KS.TARGET_ACCEPT, KS.FIT_SEED) == (1500, 1500, 4, 0.98, 42)

    def test_both_operators_are_like_for_like_with_check_gamma0(self, g):
        v = g["vignettes"]
        _centres_equal_the_gamma0_record(v, TO.HEADLINE, "headline")
        _centres_equal_the_gamma0_record(v, TO.OVERLAY, "overlay_sensitivity")

    def test_the_stamps_and_the_retired_construction(self, g):
        v = g["vignettes"]
        assert (v["headline"]["operator"], v["headline"]["operator_role"]) == ("size_only", "headline")
        assert (v["overlay_sensitivity"]["operator"], v["overlay_sensitivity"]["operator_role"]) == ("overlay",
                                                                                                  "sensitivity")
        # the retired construction is not an operator mode: it carries its own label, no operator in force (rev9, C5)
        assert v["retired_zeroing"]["operator"] == TO.RETIRED_ZEROING not in TO.MODES
        assert v["retired_zeroing"]["operator_role"] == TO.RETIRED_ROLE
        assert "retired" in v["retired_zeroing"]["construction"]
        # three constructions in one record: no operator stamp at its top level; each fit carries its own
        assert "operator" not in g
        assert (g["headline_fit"]["operator"], g["gamma_free_fit"]["operator"]) == (TO.HEADLINE, TO.OVERLAY)

    def test_the_guard_names_every_shared_parameter_and_is_recorded_not_enforced(self, g):
        hg = g["headline_guard"]
        assert hg["enforced"] is False
        assert sorted(r["param"] for r in hg["rows"]) == sorted(am.SHARED)
        assert hg["within_tolerance"] is all(r["gap_in_sd"] <= am.TOL_SD for r in hg["rows"])

    def test_relative_changes_and_the_moved_list_are_recomputed_from_the_stored_figures(self, g):
        rc, rr, v = g["relative_change_of_means"], g["retired_relative_to_headline"], g["vignettes"]
        for p in G.PARAMS:
            assert rc[p] == pytest.approx(g["gamma_free_fit"]["params"][p]["mean"] / g["headline_fit"]["params"][p]["mean"]
                                          - 1.0)
        for q in v["headline"]["centre"]:
            assert rr[q] == pytest.approx(v["retired_zeroing"]["centre"][q] / v["headline"]["centre"][q] - 1.0)
            assert v["retired_pct_change_from_headline"][q] == pytest.approx(100.0 * rr[q])
        assert g["headline_quantities_moved_by_2pct_or_more"] == _moved({**rr, **{p: rc[p] for p in G.PARAMS}},
                                                                        G.HEADLINE_QUANTITIES)
        assert g["relative_flag"] == 0.02

    def test_the_means_are_stored_at_full_precision(self, g):
        for fit, rel in (("headline_fit", "model/dispersion_calibration_ritc.json"),
                         ("gamma_free_fit", "model/dispersion_calibration_ritc_gamma_free.json")):
            full = _json(rel)
            for p in G.PARAMS:
                assert g[fit]["params"][p]["mean"] == (full[p] if p in full else full["params"][p]["mean"])

    def test_the_size_ratio_of_both_constructions(self, g):
        r, z = g["size_ratio_100_2000_size_only"], g["size_ratio_100_2000_retired_zeroing"]
        assert (r["operator"], z["operator"]) == (TO.HEADLINE, TO.RETIRED_ZEROING)
        assert "retired_zeroing" not in r, "the headline's block holds the headline's ratio only"
        assert r["headline"] > 1.0 and z["retired_zeroing"] > 1.0
        assert z["retired_pct_change"] == pytest.approx(100.0 * (z["retired_zeroing"] / r["headline"] - 1.0))


class TestTheGammaFreeCheckRefuses:
    """check_gamma_free_fit.py refuses to write when its comparison is not like for like (the review of 12 October
    2026, S2): a headline that is not the gamma = 0 fit (:87), a gamma-free fit with no gamma (:89), H bounds that
    differ (:93), headline or overlay vignettes that differ from check_gamma0_vignette.py's record, centre or
    intervals (:110: what makes the retired construction a bridge between like quantities), and fits on different
    samples (:147). Each case runs main() on the committed fits with a small B and a record written for that B, so
    the positive control passes and each refusal is the one perturbation's."""

    B = 6

    @pytest.fixture(scope="class")
    def small_record(self):
        """check_gamma0_vignette.py's record with each block's intervals recomputed at B, exactly as main() computes
        them (centres do not depend on B)."""
        from check_gamma0_vignette import operator_vignettes
        from vignette_uncertainty import load_pool, load_ritc, load_targets
        rec = _json("results/check_gamma0_vignette_results.json")
        pool = load_pool()
        ritc, targets = load_ritc(pool[3], pool[4]), load_targets()
        for mode in (TO.HEADLINE, TO.OVERLAY):
            draws, ref, hlo, hce = TO.load_draws(mode, keys=G.DRAW_PARAMS)
            blk = operator_vignettes(mode, pool, {p: draws[p] for p in TO.OPERATOR_KEYS}, (ref, hlo, hce), ritc,
                                     targets, b=self.B, seed=G.VIG_SEED)
            assert blk["centre"] == rec[mode]["centre"], mode
            rec[mode]["intervals"] = blk["intervals"]
        rec["B"] = self.B
        return rec

    def _run(self, monkeypatch, tmp_path, record, calibration=None, draws=None):
        path = tmp_path / "gamma0.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        out = tmp_path / "out.json"
        monkeypatch.setattr(G, "GAMMA0", path)
        monkeypatch.setattr(G, "OUT", out)
        monkeypatch.setattr(G, "B", self.B)
        if calibration:
            real = TO.load_calibration
            monkeypatch.setattr(TO, "load_calibration", lambda mode: calibration(mode, real(mode)))
        if draws:
            real_d = TO.load_draws
            monkeypatch.setattr(TO, "load_draws", lambda mode, keys=TO.OPERATOR_KEYS: draws(mode, real_d(mode, keys)))
        return out

    def test_the_unperturbed_comparison_writes(self, monkeypatch, tmp_path, small_record):
        out = self._run(monkeypatch, tmp_path, small_record)
        G.main()
        with io.open(str(out), encoding="utf-8") as _fh:
            rec = json.load(_fh)
        assert rec["vignettes"]["B"] == self.B
        assert rec["vignettes"]["headline"]["intervals"] == small_record[TO.HEADLINE]["intervals"]
        assert rec["vignettes"]["overlay_sensitivity"]["centre"] == small_record[TO.OVERLAY]["centre"]

    @pytest.mark.parametrize("change", [{"gamma_prior": "halfnormal"}, {"gamma": 0.1}])
    def test_a_headline_that_is_not_the_gamma0_fit_is_refused(self, monkeypatch, tmp_path, small_record, change):
        out = self._run(monkeypatch, tmp_path, small_record,
                        calibration=lambda mode, cal: {**cal, **change} if mode == TO.HEADLINE else cal)
        with pytest.raises(SystemExit, match="is not the gamma = 0 headline fit"):
            G.main()
        assert not out.exists()

    def test_a_gamma_free_fit_without_gamma_is_refused(self, monkeypatch, tmp_path, small_record):
        def drop(mode, cal):
            if mode != TO.OVERLAY:
                return cal
            return {**cal, "params": {p: v for p, v in cal["params"].items() if p != "gamma"}}
        out = self._run(monkeypatch, tmp_path, small_record, calibration=drop)
        with pytest.raises(SystemExit, match="carries no fitted gamma"):
            G.main()
        assert not out.exists()

    def test_different_h_bounds_are_refused(self, monkeypatch, tmp_path, small_record):
        out = self._run(monkeypatch, tmp_path, small_record,
                        draws=lambda mode, d: (d[0], d[1], d[2] + 1e-9, d[3]) if mode == TO.OVERLAY else d)
        with pytest.raises(SystemExit, match="reference size and H bounds differ"):
            G.main()
        assert not out.exists()

    @pytest.mark.parametrize("mode", [TO.HEADLINE, TO.OVERLAY])
    @pytest.mark.parametrize("part", ["centre", "intervals"])
    def test_vignettes_that_differ_from_the_gamma0_record_are_refused(self, monkeypatch, tmp_path, small_record,
                                                                     mode, part):
        rec = json.loads(json.dumps(small_record))
        if part == "centre":
            rec[mode]["centre"]["V1_v995"] += 1e-12
        else:
            rec[mode]["intervals"]["V2_d995"]["hi"] += 1e-12
        out = self._run(monkeypatch, tmp_path, rec)
        with pytest.raises(SystemExit, match="the %s vignettes differ from check_gamma0_vignette.py's record" % mode):
            G.main()
        assert not out.exists()

    def test_fits_on_different_samples_are_refused(self, monkeypatch, tmp_path, small_record):
        out = self._run(monkeypatch, tmp_path, small_record,
                        calibration=lambda mode, cal: {**cal, "n": cal["n"] + 1} if mode == TO.OVERLAY else cal)
        with pytest.raises(SystemExit, match="on different samples"):
            G.main()
        assert not out.exists()


class TestTheKSupport:
    def test_form_and_sampler(self, ks):
        """The regenerated record's fits carry no gamma (option B)."""
        assert (ks["n"], ks["n_ritc"]) == (649, 34)          # 649 since the regeneration of 23 October 2026 (primary)
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

    def test_the_headline_is_stamped_and_there_is_no_overlay_leg(self, ks):
        """Since option B the wider-support refits have gamma = 0, so there is no overlay leg."""
        v = ks["vignettes"]
        assert (v["operator"], v["operator_role"]) == ("size_only", "headline")
        assert "overlay_sensitivity" not in v and "full-sample gamma-free fit" in v["overlay_sensitivity_note"]

    def test_relative_changes_and_the_moved_lists_are_recomputed_from_the_stored_figures(self, ks):
        """The regenerated record's guard rows are adopted_model.SHARED's eight."""
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
