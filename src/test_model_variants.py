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
    "check_missingness_sensitivity.py": (set(), "observation weights on the likelihood"),
    "proxy_stress_bayes.py": (set(), "a perturbed concentration index only"),
    "check_size_maturity.py": ({"delta_proxy"}, "an extra log-scale term"),
    "check_k_unconstrained.py": (set(), "the support of k, via k_prior"),
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
    tree = ast.parse(io.open(os.path.join(SRC, rel), encoding="utf-8").read())
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


def test_the_headline_graph_is_unchanged():
    """The block called with (R, H, yr, ritc) is the adopted model: its log-density on a
    fixed synthetic dataset equals the value pinned before the block gained options."""
    import pymc as pm
    import adopted_model as am
    ref = np.load(os.path.join(HERE, "tests_data", "adopted_block_reference.npz"))
    with pm.Model() as m:
        b = am.scale_block(ref["R"], ref["H"], ref["yr"], ref["ritc"])
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=ref["S"])
    lp = float(m.compile_logp()(m.initial_point()))
    assert abs(lp - float(ref["lp"])) < 1e-8, (lp, float(ref["lp"]))
    assert [v.name for v in m.free_RVs] == ["theta", "gamma", "log_tot", "f", "tau_s", "z_s",
                                            "nu_clean", "lambda_ritc", "beta_ritc"]


def test_the_options_are_the_declared_ones():
    import inspect
    import adopted_model as am
    params = list(inspect.signature(am.scale_block).parameters)
    assert params == ["R", "H", "yr", "ritc", "logR", "logH", "yidx", "n_y", "k_prior",
                      "record_shock", "shock_loading", "extra_log_scale"]
