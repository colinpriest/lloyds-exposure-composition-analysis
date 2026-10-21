"""Every fitting script builds the adopted model from adopted_model.scale_block and
departs from it only in its declared dimension.

Round 51 of the paper review (T1): ten scripts carried their own copy of the
two-regime block, the mechanism by which an earlier refit diverged from the adopted
likelihood. The block is now defined once; this test enumerates every random
variable each script creates and fails on any that is not the script's declared
departure, so a copy of a shared term cannot come back. A graph test pins the
headline block itself.

Run:  python -m pytest src/test_model_variants.py -q
"""
import ast
import io
import os
import re

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")

# the random variables adopted_model.scale_block creates (under any k_prior)
SHARED = {"theta", "k", "gamma", "log_tot", "f", "sd_undiv", "sd_div", "tau_s", "z_s",
          "s_y", "nu_clean", "lambda_ritc", "nu_ritc", "beta_ritc"}

# script -> (random variables it may create itself, its declared departure)
VARIANTS = {
    "calibrate_dispersion_ritc.py": (set(), "the headline: no departure"),
    "check_fx_timing.py": (None, "not enumerated: a location script built before this test"),
    "check_mean_concentration_bayes.py": (None, "not enumerated: location variants"),
    "check_ritc_scale_term.py": (None, "not enumerated"),
    "fx_sensitivity.py": (None, "not enumerated"),
    "check_syndicate_random_effect.py": ({"tau_alpha", "z_alpha", "alpha"},
                                         "a syndicate random intercept in the location"),
    "check_maturity_denominator.py": (set(), "rebased inputs only"),
    "check_cohort_scope.py": (set(), "the adopted model on the observations whose cohort cutoff is enforced"),
    "check_margin_sensitivity.py": (set(), "the adopted model without the syndicates that state a management margin, "
                                           "and without size-matched random records as its control"),
    "check_skew_t.py": ({"delta"}, "one shared skewness index on the shock: a Jones-Faddy skew-t with "
                                   "a = (nu/2)e^delta, b = (nu/2)e^-delta, so delta = 0 is the adopted model"),
    "check_missingness_sensitivity.py": (set(), "observation weights on the likelihood"),
    "proxy_stress_bayes.py": (set(), "the gamma-free fit (gamma_prior='halfnormal', the overlay's source) on a "
                                   "perturbed concentration index"),
    "check_size_maturity.py": ({"delta_proxy"}, "an extra log-scale term"),
    "check_k_half_sensitivity.py": (set(), "k fixed at its theoretical bracket's lower end, via k_prior"),
    "check_k_support.py": (set(), "k on a wider support, k_lo + (1 - k_lo) logistic(theta), via k_prior"),
    "check_operator_backtest.py": (set(), "the adopted model on each fold's training syndicates: which observations "
                                          "are included is the only thing that changes"),
    "check_serial_sensitivity.py": (set(), "the adopted model on subsamples of the working sample: which "
                                          "observations are included is the only thing that changes"),
    "check_long_tail_share.py": ({"beta_LT"}, "a long-tail share term on the log-scale"),
    "check_currency_entanglement.py": ({"tau_m", "z_m", "m_y", "beta_share"},
                                       "a directional shock and a USD-share term in the location"),
    "calibrate_dispersion_sizeloaded.py": ({"tau_m", "z_m", "m_y", "psi"},
                                           "a size-loaded directional shock in the location"),
    "calibrate_dispersion_systemic.py": ({"tau_m", "z_m", "m_y"},
                                         "a directional shock in the location"),
    "calibrate_dispersion_hetscale.py": ({"psi_s"}, "a size loading on the scale shock"),
}

PM_RV = {"Normal", "HalfNormal", "Gamma", "Beta", "Uniform", "Deterministic", "StudentT",
         "Potential", "HalfCauchy", "Exponential", "LogNormal", "Dirichlet"}


def _rv_names(rel):
    with io.open(os.path.join(SRC, rel), encoding="utf-8") as _fh:
        tree = ast.parse(_fh.read())
    names, calls_block = set(), False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "scale_block":
                calls_block = True
            if (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                    and fn.value.id == "pm" and fn.attr in PM_RV and node.args
                    and isinstance(node.args[0], ast.Constant)):
                names.add(node.args[0].value)
    return names, calls_block


@pytest.mark.parametrize("rel", [r for r, (own, _) in VARIANTS.items() if own is not None])
def test_the_script_departs_only_in_its_declared_dimension(rel):
    names, calls_block = _rv_names(rel)
    assert calls_block, "%s does not build from adopted_model.scale_block" % rel
    own, why = VARIANTS[rel]
    copied = names & SHARED
    assert not copied, "%s recreates shared terms %s" % (rel, sorted(copied))
    extra = names - own - {"S_obs", "S_obs_w"}
    assert not extra, "%s creates undeclared variables %s (declared: %s)" % (rel, sorted(extra), why)


def test_no_script_that_fits_outside_the_shared_block_calls_its_model_adopted():
    """The review of 2 October 2026, A-4: check_pooling_cv_extended.py labelled a single-regime fit with no year shock
    "[adopted]", in its docstring and in the label its results carry. The adopted model is scale_block's; a fitting
    script that does not build from it may say it uses the adopted scale form, not that its model is the adopted
    one."""
    offenders = []
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".py") or fn.startswith("test_") or fn == "adopted_model.py":
            continue
        with io.open(os.path.join(SRC, fn), encoding="utf-8") as _fh:
            src = _fh.read()
        names, calls_block = _rv_names(fn)
        if calls_block or "StudentT" not in src:
            continue
        if re.search(r"\[adopted\]|\(adopted\)", src, re.I):
            offenders.append(fn)
    assert offenders == [], offenders


def test_no_fitting_script_retypes_the_shared_block():
    """Any script under src/ that creates 'nu_clean' or 'beta_ritc' itself is a copy."""
    offenders = []
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".py") or fn == "adopted_model.py":
            continue
        names, _ = _rv_names(fn)
        if names & {"nu_clean", "beta_ritc", "lambda_ritc"}:
            offenders.append(fn)
    assert offenders == [], offenders


def _reference_model(**kw):
    import pymc as pm
    import adopted_model as am
    with np.load(os.path.join(HERE, "tests_data", "adopted_block_reference.npz")) as _npz:
        ref = {key: _npz[key] for key in _npz.files}
    with pm.Model() as m:
        b = am.scale_block(ref["R"], ref["H"], ref["yr"], ref["ritc"], **kw)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=ref["S"])
    return m, ref


def test_the_gamma_free_graph_is_unchanged():
    """The block with gamma ~ HalfNormal(1) (the gamma-free fit, the headline before option B) is the model whose
    log-density on a fixed synthetic dataset was pinned before the block gained options."""
    m, ref = _reference_model(gamma_prior="halfnormal")
    lp = float(m.compile_logp()(m.initial_point()))
    assert abs(lp - float(ref["lp"])) < 1e-8, (lp, float(ref["lp"]))
    assert [v.name for v in m.free_RVs] == ["theta", "gamma", "log_tot", "f", "tau_s", "z_s",
                                            "nu_clean", "lambda_ritc", "beta_ritc"]


#: the headline block's log-density at its initial point on the reference dataset, pinned when gamma = 0 became the
#: headline (option B, 10 October 2026); test_the_headline_graph_is_unchanged also derives it from the gamma-free graph
HEADLINE_LP = 33.85902849667567


def test_the_headline_graph_is_unchanged():
    """The block called with (R, H, yr, ritc) is the headline, gamma = 0 in the likelihood: its log-density is the
    pinned value, it has no gamma variable, and it is the gamma-free graph's log-density at gamma -> 0 less that
    variable's prior and Jacobian terms (gamma = exp(-80) there: the scale is the same to machine precision), so
    the two graphs differ only in gamma."""
    m, _ref = _reference_model()
    p = m.initial_point()
    lp = float(m.compile_logp()(p))
    assert abs(lp - HEADLINE_LP) < 1e-8, (lp, HEADLINE_LP)
    assert [v.name for v in m.free_RVs] == ["theta", "log_tot", "f", "tau_s", "z_s",
                                            "nu_clean", "lambda_ritc", "beta_ritc"]
    mh, _ = _reference_model(gamma_prior="halfnormal")
    ph = dict(p, gamma_log__=np.array(-80.0))
    # log HalfNormal(1) density at g = exp(-80), plus the log-Jacobian of the log transform (-80)
    prior_and_jacobian = np.log(np.sqrt(2.0 / np.pi)) - 0.5 * np.exp(-160.0) - 80.0
    assert abs(float(mh.compile_logp()(ph)) - prior_and_jacobian - lp) < 1e-9


def test_the_options_are_the_declared_ones():
    import inspect
    import adopted_model as am
    params = list(inspect.signature(am.scale_block).parameters)
    assert params == ["R", "H", "yr", "ritc", "logR", "logH", "yidx", "n_y", "k_prior",
                      "gamma_prior", "record_shock", "shock_loading", "extra_log_scale"]


def test_the_shared_parameters_are_the_headlines_eight():
    """Option B: gamma is 0 in the headline's likelihood, so it is not a fitted parameter a refit is compared on;
    the gamma-free fit's guard (reference=GAMMA_FREE_JSON) compares it as well."""
    import adopted_model as am
    assert am.SHARED == ["k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s"]
    assert am.GAMMA_FREE_SHARED == am.SHARED[:1] + ["gamma"] + am.SHARED[1:]


def _fake_reference(tmp_path, params):
    import json
    p = tmp_path / "calibration.json"
    p.write_text(json.dumps({"params": params}), encoding="utf-8")
    return p


def test_the_guard_reads_the_reference_it_is_given(tmp_path, monkeypatch):
    import adopted_model as am
    row = {"mean": 1.0, "sd": 0.1, "hdi_2.5": 0.8, "hdi_97.5": 1.2}
    ref = _fake_reference(tmp_path, {p: dict(row) for p in am.GAMMA_FREE_SHARED})
    post = {p: np.full(10, 1.0) for p in am.GAMMA_FREE_SHARED}
    post["gamma"] = np.full(10, 1.2)                       # two SDs from the reference's gamma
    ok, rows = am.check_against_headline(post, reference=ref)
    assert ok and [r["param"] for r in rows] == am.SHARED, "against a headline-type reference gamma is not compared"
    monkeypatch.setattr(am, "GAMMA_FREE_JSON", ref)
    ok, rows = am.check_against_headline(post, reference=ref)
    assert not ok and [r["param"] for r in rows] == am.GAMMA_FREE_SHARED
    assert [r["gap_in_sd"] for r in rows if r["param"] == "gamma"] == [pytest.approx(2.0)]


def test_a_gap_from_a_zero_sd_reference_is_not_zero(tmp_path):
    """Until 10 October 2026 a reference parameter with posterior SD 0 gave any refit a gap of 0 SDs. A point-mass
    reference passes only a refit at that value exactly."""
    import adopted_model as am
    ref = _fake_reference(tmp_path, {"k": {"mean": 0.5, "sd": 0.0}})
    ok, rows = am.check_against_headline({"k": np.array([0.6])}, reference=ref)
    assert not ok and rows[0]["gap_in_sd"] == float("inf")
    ok, rows = am.check_against_headline({"k": np.array([0.5])}, reference=ref)
    assert ok and rows[0]["gap_in_sd"] == 0.0


def _guard_row_lists(node, path=""):
    """Every list of objects carrying param, refit, headline and gap_in_sd: the rows
    adopted_model.check_against_headline returns, wherever a record stores them."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _guard_row_lists(v, "%s/%s" % (path, k))
    elif isinstance(node, list):
        if node and all(isinstance(x, dict) and {"param", "refit", "headline", "gap_in_sd"} <= set(x)
                        for x in node):
            yield path, [x["param"] for x in node]
        else:
            for i, v in enumerate(node):
                yield from _guard_row_lists(v, "%s[%d]" % (path, i))


def test_every_headline_guard_compares_every_shared_parameter():
    """The A+/L1 review (B-02 (i)): three scripts gave the headline guard six or seven of
    adopted_model.SHARED's parameters, so a refit could move sd_div, lambda_ritc or
    tau_s by any amount and still pass. Every guard row list in the committed records must
    name all of them (eight since option B: gamma is 0 in the headline). The lists are found by their shape, so a
    new script's rows are held to the same rule without being listed here."""
    import json
    import adopted_model as am
    found, short = 0, []
    for d in ("results", "model"):
        for root, _, files in os.walk(os.path.join(HERE, d)):
            for fn in sorted(files):
                if not fn.endswith(".json"):
                    continue
                with io.open(os.path.join(root, fn), encoding="utf-8") as fh:
                    record = json.load(fh)
                for path, params in _guard_row_lists(record):
                    found += 1
                    missing = [p for p in am.SHARED if p not in params]
                    if missing:
                        short.append((os.path.relpath(os.path.join(root, fn), HERE), path, missing))
    assert found >= 9, "only %d guard row lists found: the scan is not reading the records" % found
    assert short == [], short
