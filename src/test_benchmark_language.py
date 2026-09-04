"""The k = 1/2 benchmark is the FINITE-VARIANCE independent sqrt(N) rate.

Round 50 of the paper review found the public surfaces calling k = 1/2 "pure
independence", "independent sqrt-N" and "slower-than-independent" while the
manuscript defines the benchmark with its finite-variance condition and notes that
independent alpha-stable aggregation gives k > 1/2. Every sentence or label on these
surfaces that ties the exponent, benchmark or pooling rate to independence must
carry the condition.

Run:  python -m pytest src/test_benchmark_language.py -q
"""
import io
import os
import re

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SURFACES = ("README.md", "docs/current-results.md", "src/pooling_compare.py",
            "src/check_pooling_cv_extended.py", "src/build_current_results.py",
            "results/check_pooling_cv_extended_results.json",
            # round 51: the generated calibration table and its generator
            "paper_pack/table38_dispersion_calibration.tex")
FORBIDDEN_LABELS = ("=indep.", "= indep.", "(indep.)")

INDEPENDENCE = re.compile(r"independen", re.I)
RATE = re.compile(r"tfrac12|\b1/2\b|sqrt|\u221a|square-root|k\s*(?:=|fixed at)\s*0\.5", re.I)
NOUN = re.compile(r"exponent|benchmark|pooling|scal|\bk\b", re.I)
FINITE_VARIANCE = re.compile(r"finite[- ]variance", re.I)
FORBIDDEN = ("pure independence", "slower-than-independent", "[independent sqrt-N")


def _read(rel):
    return io.open(os.path.join(HERE, rel), encoding="utf-8", errors="replace").read()


def unqualified_benchmark_sentences(text):
    flat = " ".join(text.split())
    out = []
    for sent in re.split(r"(?<=[.!?])\s+|\s*\|\s*|\n", flat):
        if (INDEPENDENCE.search(sent) and RATE.search(sent) and NOUN.search(sent)
                and not FINITE_VARIANCE.search(sent)):
            out.append(sent.strip())
    return out


@pytest.mark.parametrize("rel", SURFACES)
def test_no_unqualified_independence_benchmark(rel):
    if not os.path.exists(os.path.join(HERE, rel)):
        pytest.skip(rel + " absent")
    text = _read(rel)
    for phrase in FORBIDDEN:
        assert phrase not in text, "%s: %r" % (rel, phrase)
    assert unqualified_benchmark_sentences(text) == [], rel


def test_the_historical_forms_fire():
    for bad in ("M2 - independent sqrt(N): as M1 but k fixed at 0.5 (pure independence)",
                "M2  k = 1/2 fixed + floor [independent sqrt-N pooling]",
                "the textbook independent sqrt N rate, k = 1/2"):
        assert unqualified_benchmark_sentences(bad), bad
    # the phrase form is a word, not a sentence about the rate: the FORBIDDEN list
    assert "slower-than-independent" in FORBIDDEN


def test_the_qualified_form_passes():
    good = ("whether pooling is slower than the finite-variance independent sqrt N "
            "benchmark -- independence alone does not give k = 1/2 under infinite-variance "
            "aggregation.")
    assert unqualified_benchmark_sentences(good) == []


def test_the_calibration_table_generator_carries_the_condition():
    """_gen_table38 wrote "1/2=indep." and a constrained-support P(k<1) row."""
    import ast
    src = _read("src/run_analysis.py")
    tree = ast.parse(src)
    gen = next(ast.get_source_segment(src, n) for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_gen_table38")
    for bad in FORBIDDEN_LABELS:
        assert bad not in gen, bad
    assert "finite-variance" in gen
    assert "k_lt_1" not in gen, "the constrained-support P(k<1) is not evidence"
    frag = _read("paper_pack/table38_dispersion_calibration.tex")
    for bad in FORBIDDEN_LABELS:
        assert bad not in frag, bad
    assert "P(k<1) = " not in frag and "P(k<1) = --" not in frag
