"""The generated documents name their tests and decide on the paper's criterion (the review of 2 October 2026, A-2,
A-7).

docs/current-results.md printed an unnamed "p=0.0000" (the Mann-Whitney p is 1.5e-32) beside a LaTeX pound macro
left in Markdown, and docs/referee-checks.md decided the pooling comparison "within two standard errors", a z-type
reading the paper disclaims, guarded by |d|/se. The size contrast now names its rank test, and the decision and its
guard rest on the Bayesian-bootstrap interval the manuscript uses.

Run:  python -m pytest src/test_generated_doc_language.py -q
"""
import glob
import io
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import build_current_results as bcr  # noqa: E402


@pytest.mark.parametrize("p,text", [(1.5e-32, "Mann-Whitney p < 0.001"), (0.0009, "Mann-Whitney p < 0.001"),
                                    (0.001, "Mann-Whitney p = 0.001"), (0.2345, "Mann-Whitney p = 0.234")])
def test_the_size_contrast_names_its_rank_test(p, text):
    assert bcr.rank_test_text(p) == text


def test_no_markdown_document_carries_a_latex_pound_macro_or_a_zero_p():
    found = []
    for path in sorted(glob.glob(os.path.join(HERE, "docs", "*.md"))) + [os.path.join(HERE, "README.md")]:
        text = io.open(path, encoding="utf-8").read()
        for bad in ("\\pounds", "p=0.0000", "p = 0.0000"):
            if bad in text:
                found.append((os.path.basename(path), bad))
    assert found == []


PCV = {"delta_ELPD_M1_minus_M2": -0.32, "delta_SE": 0.1, "folds": 5, "n": 674, "n_syndicates": 118,
       "pct_held_out_M1_higher_density": 48.0}


def _cse(lo, hi, p=0.42):
    return {"contrasts": {"composition__vs__k0.5": {"delta_ELPD": -0.32, "bb_2.5": lo, "bb_97.5": hi,
                                                     "P_first_better": p}}}


def test_the_decision_rests_on_the_bayesian_bootstrap_not_on_standard_errors():
    """|d| is 3.2 standard errors here, which the old guard refused; the interval includes zero, so the decision
    stands, and its words carry the interval's P, not a multiple of the standard error."""
    text = bcr.referee_section_3(PCV, _cse(-3.4, 2.6))
    decision = text[text.index("**Decision.**"):text.index("→ State this.")]
    assert "standard error" not in decision
    assert "Bayesian-bootstrap interval for the difference" in decision and "= 0.42$" in decision


def test_the_decision_is_refused_without_the_bootstrap_or_when_it_excludes_zero():
    with pytest.raises(SystemExit, match="no Bayesian-bootstrap record"):
        bcr.referee_section_3(PCV, {})
    with pytest.raises(SystemExit, match="excludes zero"):
        bcr.referee_section_3(PCV, _cse(0.5, 4.0))
