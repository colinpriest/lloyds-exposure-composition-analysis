"""The referee note does not turn a test's non-detection into absence (frozen review of 21 September 2026, D02).

docs/referee-checks.md said that no scale co-movement excess "exists to capture", on one posterior predictive check
that did not detect one, and that the persistent per-syndicate mean is "the only serial feature", on lag-1
diagnostics after de-meaning. src/build_current_results.py writes the note. Both conclusions now say what the test
detects and what it does not show; these tests hold the generator and the generated note to that.
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ABSENCE = re.compile(r"exists to capture|the only serial feature", re.I)
#: what each conclusion now says, as the generator writes it (one source line each) and as the note prints it
SCOPED = ("That is one test's non-detection", "dependence of a form a lag-1")
SCOPED_NOTE = ("That is one test's non-detection, not a demonstration that none exists",
               "dependence of a form a lag-1 statistic cannot see is not tested")


def _flat(*parts):
    return " ".join(io.open(os.path.join(ROOT, *parts), encoding="utf-8").read().split())


def test_the_generator_scopes_both_conclusions():
    src = io.open(os.path.join(HERE, "build_current_results.py"), encoding="utf-8").read()
    assert not ABSENCE.search(src)
    for phrase in SCOPED:
        assert phrase in src, phrase


def test_the_generated_note_scopes_both_conclusions():
    note = _flat("docs", "referee-checks.md")
    assert not ABSENCE.search(note), ABSENCE.search(note).group(0)
    for phrase in SCOPED_NOTE:
        assert phrase in note, phrase
