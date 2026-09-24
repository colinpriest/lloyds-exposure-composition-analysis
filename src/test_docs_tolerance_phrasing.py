r"""No current document states a model-agreement tolerance the code does not apply, and any that uses the words
"material disagreement" says which measure it means (R222).

Two measures in this project share those words:

  * this repository's own summary count, over the records' stored model values, of the syndicate-years whose two
    PYD percentages differ by more than 0.5 percentage points (run_analysis's dual_model_stats, the paper pack's
    Table 32);
  * the extraction pipeline's field-by-field comparator, which flags a numeric field where the two readings differ
    by more than 0.5% of the larger AND by more than 0.05 absolute (check_tolerance with _is_numeric_near).

docs/appendix-data-audit.md described the second and printed the first's rule (frozen review of 24 September 2026,
D05); docs/paper-pack.md described the first and named neither, which a review of this round found. The documents
are read from the repository rather than listed here: the round's first sweep in the extraction repository missed a
third file because it named the two files the review had named.

Run:  python -m pytest src/test_docs_tolerance_phrasing.py -q
"""
import io
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Forms of the comparator's rule that no code applies. The pack's own 0.5pp count is not among them: it is a real
#: measure, and the second test is what keeps it from being read as the comparator's.
RETIRED = (re.compile(r"differ by >\s*0\.5\s*pp", re.I),
           re.compile(r"Within [+±]/?-? ?1\.0\s*pp", re.I),
           re.compile(r"Within [+±]/?-? ?2\.0m", re.I),
           re.compile(r"field tolerances [+±]?2\.0m", re.I),
           re.compile(r"[+±]5% reserves", re.I))

#: A statement of either measure must name which one it is.
FAMILY = re.compile(r"material disagreement", re.I)
#: A unit that gives a number with a unit is stating the rule, not naming the metric. The number and its unit may
#: be separated by LaTeX spacing ("$> 0.5$\,pp"), which is how the statement this test was written for was written.
THRESHOLD = re.compile(r"[0-9]+(?:\.[0-9]+)?[\s$\\,]*(?:pp\b|percentage points?|\\?%|absolute)", re.I)
NAMES_ONE = (re.compile(r"dual_model_stats|pack's own measure", re.I),
             re.compile(r"check_tolerance|_is_numeric_near|0\.5\\?% of the larger", re.I),
             re.compile(r"not the extraction pipeline's field", re.I))

HISTORICAL = re.compile(r"\b(superseded|withdrawn|before round \d+|round \d+ record|historic(al)?|no longer)\b", re.I)


def _docs():
    out = ["README.md"]
    for name in sorted(os.listdir(os.path.join(HERE, "docs"))):
        if name.endswith(".md"):
            out.append(os.path.join("docs", name))
    return out


def _blocks(rel):
    with io.open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        text = fh.read()
    for block in re.split(r"\n\s*\n", text):
        if block.strip():
            yield block


def test_no_document_prints_a_retired_tolerance_form():
    found = []
    for rel in _docs():
        for block in _blocks(rel):
            flat = " ".join(block.split())
            if HISTORICAL.search(flat):
                continue
            for pattern in RETIRED:
                m = pattern.search(flat)
                if m:
                    found.append("%s: %r in %s" % (rel, m.group(0), flat[:120]))
    assert not found, "a retired tolerance form is still printed:\n  " + "\n  ".join(found)


def _units(flat):
    """The cells of a table row, or the sentences of a paragraph: a statement must name its own measure, not rely on
    another cell of the same table naming the generator that writes it."""
    parts = [p for p in flat.split("|") if p.strip()] if "|" in flat else re.split(r"(?<=\.)\s+", flat)
    return [p.strip() for p in parts if p.strip()]


def test_every_material_disagreement_statement_says_which_measure_it_is():
    missing, seen = [], []
    for rel in _docs():
        for block in _blocks(rel):
            flat = " ".join(block.split())
            if not FAMILY.search(flat):
                continue
            seen.append(rel)
            if HISTORICAL.search(flat):
                continue
            for unit in _units(flat):
                # A bare metric name ("material disagreement count") defines nothing; a unit that gives a threshold
                # is making the statement, and that is the one that must say which measure it belongs to.
                if not (FAMILY.search(unit) and THRESHOLD.search(unit)):
                    continue
                if not any(p.search(unit) for p in NAMES_ONE):
                    missing.append("%s: %s" % (rel, unit[:160]))
    # The paper pack's own table is the statement this test was written for: if the sweep stops seeing it, the
    # sweep is broken, whatever it reports about the rest.
    assert os.path.join("docs", "paper-pack.md") in seen, "the sweep no longer sees the paper pack's own statement"
    assert not missing, ("a \"material disagreement\" is stated without saying which measure it is:\n  "
                         + "\n  ".join(missing))


def test_the_documents_are_read_from_the_repository():
    """The list is not a pair of file names somebody remembered."""
    docs = _docs()
    assert "README.md" in docs
    assert os.path.join("docs", "paper-pack.md") in docs
    assert os.path.join("docs", "appendix-data-audit.md") in docs
    assert len(docs) >= 8
