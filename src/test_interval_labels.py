#!/usr/bin/env python3
"""Posterior outputs must be labelled credible, never CI.

Round 41 of the paper review found four scripts that summarise posterior draws
printing or documenting "95% CI": donor_review, worked_example_donor,
vignette1_diagnostics and vignette_uncertainty. Those intervals are equal-tailed
posterior credible intervals -- not frequentist confidence intervals, and not
HDIs either (so a global CI -> HDI replace would have been a second mislabel).
The genuine cluster-bootstrap and permutation scripts keep "CI".

The rule keys on what a script LOADS, not on a name list: any non-test script
that touches the posterior draws must carry no CI-labelled string literal, and
the four corrected scripts must say "credible" or "CrI" where they label their
intervals.

Run:  python -m pytest src/test_interval_labels.py -q
"""
import ast
import io
import os
import re

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")

POSTERIOR_MARKERS = ("dispersion_posterior_draws", "load_draws", "posterior_draw(")
CI_LABEL = re.compile(r"95%\s*CI\b|\bconfidence interval", re.I)

CORRECTED = ("donor_review.py", "worked_example_donor.py",
             "vignette1_diagnostics.py", "vignette_uncertainty.py")


def _posterior_scripts():
    out = []
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".py") or fn.startswith("test_"):
            continue
        t = io.open(os.path.join(SRC, fn), encoding="utf-8",
                    errors="replace").read()
        if any(m in t for m in POSTERIOR_MARKERS):
            out.append((fn, t))
    return out


def test_no_posterior_script_labels_an_interval_ci():
    bad = []
    for fn, t in _posterior_scripts():
        try:
            tree = ast.parse(t)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and CI_LABEL.search(node.value)
                    and "credible" not in node.value.lower()):
                bad.append((fn, node.value[:50]))
    assert bad == [], bad


def test_the_corrected_scripts_say_credible():
    """Not merely CI-free: the labels must positively say what the intervals
    are, and must not have been 'fixed' by calling percentile intervals HDIs."""
    for fn in CORRECTED:
        t = io.open(os.path.join(SRC, fn), encoding="utf-8",
                    errors="replace").read()
        assert re.search(r"credible|CrI", t), fn
        for node in ast.walk(ast.parse(t)):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and re.search(r"95%\s*HDI", node.value)
                    and "hdi_prob" not in node.value):
                pytest.fail("%s labels a percentile interval an HDI: %r"
                            % (fn, node.value[:50]))


def test_the_bootstrap_scripts_keep_their_confidence_labels():
    """The mirror mistake would be renaming genuine frequentist intervals: the
    cluster-bootstrap shape checks legitimately report CIs."""
    for fn in ("ritc_tail_shape.py", "check_pyd_temporal_correlation.py"):
        p = os.path.join(SRC, fn)
        if not os.path.exists(p):
            continue
        t = io.open(p, encoding="utf-8", errors="replace").read()
        assert "95% CI" in t, "%s no longer labels its bootstrap CI" % fn
        assert not any(m in t for m in POSTERIOR_MARKERS), \
            "%s now loads the posterior; reclassify its labels" % fn
