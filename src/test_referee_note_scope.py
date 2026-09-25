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
#: What each conclusion must still say, as the generator writes it (one source line each) and as the
#: note prints it. Patterns, not exact strings: the commitment is that the scope is stated, and round
#: 60 rewrote the sentences around the second one for M01 without weakening it. An exact-match
#: register failed there on a capital letter and an inserted "still", which is not what it is for.
SCOPED = (re.compile(r"That is one test's non-detection"),
          re.compile(r"dependence of a form a lag-1", re.I))
SCOPED_NOTE = (re.compile(r"That is one test's non-detection, not a demonstration that none exists"),
               re.compile(r"dependence of a form a lag-1 statistic cannot see is (still )?not tested",
                          re.I))


def _flat(*parts):
    return " ".join(io.open(os.path.join(ROOT, *parts), encoding="utf-8").read().split())


def test_the_generator_scopes_both_conclusions():
    src = io.open(os.path.join(HERE, "build_current_results.py"), encoding="utf-8").read()
    assert not ABSENCE.search(src)
    for pattern in SCOPED:
        assert pattern.search(src), pattern.pattern


def test_the_generated_note_scopes_both_conclusions():
    note = _flat("docs", "referee-checks.md")
    assert not ABSENCE.search(note), ABSENCE.search(note).group(0)
    for pattern in SCOPED_NOTE:
        assert pattern.search(note), pattern.pattern
