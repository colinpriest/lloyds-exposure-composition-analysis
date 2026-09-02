#!/usr/bin/env python3
"""The displayed model must be the fitted model: semantic checks, not phrase lists.

Round 42 of the paper review found the manuscript displaying a likelihood whose
scale had no RITC term while the fitted model (adopted_model.scale_block) carries
sigma_it = exp(s_t + beta_ritc*1[RITC]) * sqrt(...), and three public descriptions
here repeating the conflation: the README displayed the scale without beta_ritc and
said the term was "left out", current-results said it "is omitted" without limiting
that to the operator, and the calibrator docstring said the scale was "modelled as
unchanged" above code that fits the term.

Two different objects were being collapsed:

  1. the FITTED LIKELIHOOD, which includes exp(beta_ritc*1[RITC]) in the scale; and
  2. the TRANSFER OPERATOR, which standardises donors by the base sigma(R,H) law and
     deliberately omits the multiplier (a measured ~3% structural simplification).

These tests check the semantics on both sides rather than banning phrases:

  A. graph tests -- which terms actually enter scale_block's sigma and nu, verified
     on the pytensor graph and numerically (the RITC multiplier is exp(beta) on
     flagged rows and exactly 1 on clean rows; the year effect enters as exp(s_t));
  B. operator tests -- the operator's scale function carries NO beta term;
  C. documentation coherence -- every current-facing display of the model includes
     the multiplier, and every omission claim names the operator in the same
     sentence. scaling_analysis_writeup.md is a declared development archive and is
     deliberately out of scope.

Run:  python -m pytest src/test_model_semantics.py -q
"""
import ast
import io
import json
import os
import re

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")


def _read(rel):
    return io.open(os.path.join(HERE, rel), encoding="utf-8").read()


# --- A. which terms enter the fitted likelihood ------------------------------

@pytest.fixture(scope="module")
def block():
    import pymc as pm
    import adopted_model
    R = np.array([100.0, 500.0, 900.0, 300.0])
    H = np.array([0.2, 0.5, 0.9, 0.4])
    yr = np.array([2019, 2019, 2020, 2020])
    ritc = np.array([0.0, 1.0, 0.0, 1.0])
    with pm.Model() as m:
        b = adopted_model.scale_block(R, H, yr, ritc)
    return m, b, ritc


def _rvs(m):
    return {v.name: v for v in m.free_RVs}


def test_beta_ritc_is_an_ancestor_of_the_likelihood_scale(block):
    from pytensor.graph.basic import ancestors
    m, b, _ = block
    anc = set(ancestors([b["sigma"]]))
    assert _rvs(m)["beta_ritc"] in anc, (
        "the fitted scale does not depend on beta_ritc -- the adopted model has "
        "changed; every display of the likelihood must change with it")


def test_lambda_ritc_is_an_ancestor_of_nu_and_not_of_sigma(block):
    from pytensor.graph.basic import ancestors
    m, b, _ = block
    rvs = _rvs(m)
    assert rvs["lambda_ritc"] in set(ancestors([b["nu_obs"]]))
    assert rvs["lambda_ritc"] not in set(ancestors([b["sigma"]]))
    assert rvs["beta_ritc"] not in set(ancestors([b["nu_obs"]]))


def _fixed(m, overrides):
    """givens replacing every free RV with a constant, so graph outputs are numbers."""
    import pytensor.tensor as pt
    base = {"theta": 0.3, "gamma": 0.25, "log_tot": float(np.log(0.05)), "f": 0.4,
            "tau_s": 0.1, "z_s": np.array([0.2, -0.1]), "nu_clean": 2.4,
            "lambda_ritc": 0.5, "beta_ritc": 0.0}
    base.update(overrides)
    rvs = _rvs(m)
    return {rvs[k]: pt.constant(np.asarray(v, dtype="float64")) for k, v in base.items()}


def _eval(m, expr, overrides):
    import pytensor
    f = pytensor.function([], expr, givens=_fixed(m, overrides),
                          on_unused_input="ignore")
    return np.asarray(f())


def test_sigma_multiplies_by_exp_beta_on_flagged_rows_only(block):
    m, b, ritc = block
    s0 = _eval(m, b["sigma"], {"beta_ritc": 0.0})
    s1 = _eval(m, b["sigma"], {"beta_ritc": -0.5})
    expected = np.where(ritc == 1.0, np.exp(-0.5), 1.0)
    assert np.allclose(s1 / s0, expected), (
        "the RITC scale multiplier is not exp(beta_ritc) gated by the flag")


def test_nu_divides_by_exp_lambda_on_flagged_rows_only(block):
    m, b, ritc = block
    n0 = _eval(m, b["nu_obs"], {"lambda_ritc": 0.0})
    n1 = _eval(m, b["nu_obs"], {"lambda_ritc": 0.5})
    expected = np.where(ritc == 1.0, np.exp(-0.5), 1.0)
    assert np.allclose(n1 / n0, expected)


def test_year_effect_enters_the_scale_as_exp_s_t(block):
    m, b, _ = block
    s0 = _eval(m, b["sigma"], {"z_s": np.zeros(2)})
    s1 = _eval(m, b["sigma"], {"z_s": np.array([0.2, -0.1]), "tau_s": 0.1})
    yidx = np.array([0, 0, 1, 1])
    expected = np.exp(0.1 * np.array([0.2, -0.1])[yidx])
    assert np.allclose(s1 / s0, expected)


# --- B. the operator omits the multiplier ------------------------------------

def _function_source(rel, name):
    tree = ast.parse(_read(rel))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(_read(rel), node)
    raise AssertionError("%s not found in %s" % (name, rel))


def test_operator_scale_function_carries_no_beta_term():
    src = _function_source("src/vignette_uncertainty.py", "sigma_theta")
    assert "beta" not in src, (
        "sigma_theta gained a beta term: the operator no longer omits the RITC "
        "scale multiplier, so every 'the operator omits it' statement is stale")


def test_operator_transfer_uses_ritc_for_the_tail_map_not_the_scale():
    src = _function_source("src/vignette_uncertainty.py", "transfer")
    assert "beta_ritc" not in src
    # the flag must still drive the tail-regime quantile map
    assert "ritc" in src


# --- C. documentation coherence ----------------------------------------------

CURRENT_FACING = ("README.md", "docs/current-results.md",
                  "src/calibrate_dispersion_ritc.py", "src/adopted_model.py")

OMIT_WORDS = re.compile(r"omit|left out|leaves? .{0,24}out", re.I)
SCALE_WORDS = re.compile(r"scale (?:term|shift|multiplier)|beta[_ ]?\{?\\?(?:text\{)?ritc",
                         re.I)


def unscoped_omission_sentences(text):
    """Sentences claiming the RITC scale term is omitted without naming the operator.

    The fitted likelihood INCLUDES the term; only the transfer operator omits it, so
    any omission claim must carry 'operator' in the same sentence.
    """
    flat = " ".join(text.split())
    out = []
    for sent in re.split(r"(?<=[.!?])\s+|\s*\|\s*|\n", flat):
        if OMIT_WORDS.search(sent) and SCALE_WORDS.search(sent) \
                and "operator" not in sent.lower():
            out.append(sent.strip())
    return out


def shared_scale_claims(text):
    """Claims that the fitted scale is shared/unchanged across RITC regimes.

    False for the adopted model: sigma_it carries exp(beta_ritc*1[RITC]). A scoped
    statement about the BASE scale law being common is fine; these patterns catch
    the unscoped forms that stood in round 42.
    """
    flat = " ".join(text.split())
    pats = (r"scale is modelled as unchanged",
            r"keeping sigma\(R,\s*HHI?\) shared",
            r"scale[^.]{0,70}\bis shared across regimes")
    return [p for p in pats if re.search(p, flat, re.I)]


@pytest.mark.parametrize("rel", CURRENT_FACING)
def test_no_unscoped_omission_claims(rel):
    assert unscoped_omission_sentences(_read(rel)) == []


@pytest.mark.parametrize("rel", CURRENT_FACING)
def test_no_shared_scale_claims(rel):
    assert shared_scale_claims(_read(rel)) == []


def test_readme_displays_the_fitted_scale_with_the_multiplier():
    txt = _read("README.md")
    m = re.search(r"```\n(S_it ~ Student-t.*?)```", txt, re.S)
    assert m, "README no longer displays the model block"
    block_txt = m.group(1)
    sigma_line = re.search(r"sigma_it\s*=.*?(?=\nnu_it)", block_txt, re.S)
    assert sigma_line and "beta_RITC" in sigma_line.group(0), (
        "the README's displayed sigma omits the fitted RITC multiplier")
    assert "s_t" in sigma_line.group(0)


def test_calibrator_and_adopted_docstrings_display_the_multiplier():
    for rel in ("src/calibrate_dispersion_ritc.py", "src/adopted_model.py"):
        doc = ast.get_docstring(ast.parse(_read(rel))) or ""
        assert re.search(r"beta_ritc\s*\*\s*1\[RITC\]", doc), (
            "%s no longer displays the fitted scale with beta_ritc" % rel)


def test_committed_calibration_spec_records_the_multiplier():
    d = json.load(io.open(os.path.join(HERE, "model",
                                       "dispersion_calibration_ritc.json"),
                          encoding="utf-8"))
    assert "exp(beta_ritc*1[RITC])" in d["spec"]
    assert "beta_ritc" in d["params"]


def test_generated_audit_quotes_the_calibrated_beta():
    """The audit doc's beta_RITC sentence must round-match the committed calibration.

    The typed lower bound -0.41 survived three review rounds after the round-39
    recalibration moved it to -0.39, because generate_data_audit.py hardcoded the
    interval instead of reading it. The generator now formats it from the
    calibration; this pins the generated output to the same source.
    """
    cal = json.load(io.open(os.path.join(HERE, "model",
                                         "dispersion_calibration_ritc.json"),
                            encoding="utf-8"))
    beta = cal["params"]["beta_ritc"]
    doc = _read("docs/appendix-data-audit.md")
    m = re.search(r"\\beta_\{\\text\{RITC\}\}=(-?\d+\.\d+)\$ "
                  r"\[\$(-?\d+\.\d+)\$, \$\+?(-?\d+\.\d+)\$\] with "
                  r"\$P\(\|\\beta_\{\\text\{RITC\}\}\|>0\.1\)=(\d+\.\d+)\$", doc)
    assert m, "the audit doc no longer quotes the beta_RITC posterior"
    assert m.group(1) == "%.2f" % beta["mean"]
    assert m.group(2) == "%.2f" % beta["hdi_2.5"], (
        "the audit doc's lower HDI bound does not match the calibration")
    assert m.group(3) == "%.2f" % beta["hdi_97.5"]
    assert m.group(4) == "%.2f" % cal["posterior_prob"]["beta_ritc_gt_0.1_abs"]


# --- mutation guards: the helpers must fire on the round-42 defects ----------

ROUND42_DEFECTS = (
    # README, before the fix
    "external reinsurance-to-close is modelled as a heavier tail, with the scale "
    "term left out as a structural simplification rather than because it was "
    "shown to be zero",
    # current-results status cell, before the fix
    "| 0.672 | the RITC scale term is omitted, not shown to be zero |",
)


@pytest.mark.parametrize("bad", ROUND42_DEFECTS)
def test_helper_fires_on_the_actual_round42_omission_wordings(bad):
    assert unscoped_omission_sentences(bad), (
        "the coherence helper no longer detects the wording round 42 corrected")


def test_helper_fires_on_the_actual_round42_shared_claims():
    docstring_defect = ("The scale is modelled as unchanged, which is a structural "
                        "simplification ... while keeping sigma(R,HHI) shared:")
    manuscript_defect = ("while the scale $\\sigma_{i,t}$ (size, concentration and "
                         "floor) is shared across regimes.")
    assert shared_scale_claims(docstring_defect)
    assert shared_scale_claims(manuscript_defect)


def test_helper_accepts_operator_scoped_statements():
    good = ("beta_ritc is fitted here; the transfer operator omits the scale "
            "multiplier as a structural simplification.")
    assert unscoped_omission_sentences(good) == []


# --- D. the operator is not "the fitted model applied" -----------------------
# Round 43: with the likelihood display corrected (round 42), three descriptions
# still called the operator "the fitted model(,) applied" and its denominator the
# donor's "fitted scale" -- but the operator applies the fitted BASE scale law
# sigma(R,H) and the two tail indices, omitting the fitted RITC multiplier and
# dividing out no year effect. A reader implementing "divide by the fitted scale"
# literally would build a different transfer.

FULL_MODEL_CLAIM = re.compile(
    r"(?:is|:)?\s*the fitted (?:model|likelihood)(?:,?\s*applied)?|"
    r"whole fitted (?:law|model|likelihood)|discards nothing|"
    r"(?:by|to) (?:its|their) own fitted scale", re.I)
OPERATOR_SCOPE = re.compile(r"base|omit|tail ind|subject to", re.I)


def operator_full_model_claims(text):
    """Operator descriptions claiming the full fitted model/scale, unscoped.

    Window-bound rather than sentence-bound: a LaTeX table cell is one giant
    "sentence", and the round-43 defective fragment was excused by a scope word
    two clauses away when adjudicated sentence-wise.
    """
    flat = " ".join(text.split())
    out = []
    for m in FULL_MODEL_CLAIM.finditer(flat):
        win = flat[max(0, m.start() - 80):m.end() + 120]
        if "operator" in win.lower() and not OPERATOR_SCOPE.search(win):
            out.append(win.strip()[:160])
    return out


def test_generator_operator_label_is_base_law_plus_omission():
    src = _read("src/run_analysis.py")
    assert "the fitted model, applied" not in src
    # adjacent string literals split across source lines: join them first
    joined = re.sub(r'"\s*\n\s*"', "", src)
    assert "fitted base scale law and tail indices, applied" in joined
    assert "deliberately omitted" in joined


def test_generated_table20_carries_the_corrected_label():
    frag = _read("paper_pack/table20_combined_model.tex")
    assert operator_full_model_claims(frag) == []
    assert "fitted base scale law and tail indices" in frag
    assert "deliberately omitted" in frag


@pytest.mark.parametrize("rel", ("README.md", "docs/current-results.md",
                                 "paper_pack/table20_combined_model.tex"))
def test_no_current_facing_full_model_operator_claims(rel):
    assert operator_full_model_claims(_read(rel)) == []


ROUND43_OPERATOR_DEFECTS = (
    # the generated table cell, before the fix
    "Transfer operator (the fitted model, applied): $S$ ...",
    # the manuscript's opening sentence, before the fix
    "The operator is the fitted model applied, and it has three steps.",
    # the manuscript's step 1, before the fix
    "standardise the donor movement by its own fitted scale; the operator then",
    # the archived formula doc's strongest form
    "the operator uses the whole fitted law and discards nothing.",
)


@pytest.mark.parametrize("bad", ROUND43_OPERATOR_DEFECTS)
def test_helper_fires_on_the_round43_operator_wordings(bad):
    assert operator_full_model_claims(bad), bad


def test_helper_fires_on_the_real_round43_fragment():
    """The detector must fire on the ACTUAL defective artifact, not a paraphrase:
    the sentence-bound first draft was excused on the real table cell by a scope
    word two clauses away."""
    import subprocess
    p = subprocess.run(["git", "-C", HERE, "show",
                        "b5676b8:paper_pack/table20_combined_model.tex"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        pytest.skip("pre-fix commit not available")
    assert operator_full_model_claims(p.stdout), (
        "the detector passes the real round-43 defective fragment")


def test_helper_accepts_the_corrected_operator_wordings():
    good = ("The operator applies the fitted base scale law and the fitted tail "
            "indices. Transfer operator (the fitted base scale law and tail "
            "indices, applied; the fitted RITC scale multiplier is deliberately "
            "omitted): standardise the donor movement by the base transfer scale.")
    assert operator_full_model_claims(good) == []
