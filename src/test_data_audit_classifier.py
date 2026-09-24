r"""The data audit describes the taxonomy the analysis fits, so it holds no classifier of its own (frozen review of
24 September 2026, D03).

generate_data_audit.py kept a copy of the keyword rules from before R221, without the two steps run_analysis had
added: an Energy-headed label is Energy, and "non-marine" is removed before the keywords are tried. The copy
therefore sent every Energy sub-line to Marine. On the audit's own census of 296 distinct labels and 5,591 label
instances that was 21 labels and 202 instances, and the appendix printed Marine at 6% and Energy at 1% where the
fitted taxonomy gives 3% and 5%.

These tests fail if a second classifier comes back, if the two disagree on the labels the difference turned on, or
if the committed appendix files a label under a category its classifier does not give.

Run:  python -m pytest src/test_data_audit_classifier.py -q
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, HERE)
import generate_data_audit as gda  # noqa: E402
import run_analysis as ra  # noqa: E402

APPENDIX = os.path.join(HERE, "docs", "appendix-data-audit.md")

#: The labels the two classifiers disagreed about, and the categories the analysis gives them.
TURNING_LABELS = {
    "Energy - Marine": "Energy",
    "Energy - Non Marine": "Energy",
    "Energy-non marine": "Energy",
    "Direct insurance: Energy - Marine": "Energy",
    "non-marine treaty reinsurance": "Aggregate",
    "Marine": "Marine",
    "Marine, aviation and transport": "Aviation",
    "Motor (third party liability)": "Casualty",
}


def labels_in(cell):
    """The labels a B.3 table cell lists, each with its frequency in parentheses.

    A label carries its own commas: Lloyd's composite Solvency II classes read "Marine, aviation and transport".
    Splitting the cell on commas therefore keeps only the tail of such a label, and the tail can classify elsewhere
    ("and transport" is Aggregate where the label is Aviation), so the check would be made against a string the
    corpus does not contain. Each label instead runs up to the count in parentheses that ends it.
    """
    return [m.group(1).strip() for m in re.finditer(r"(?:^|, )([^|]+?) \(\d+\)(?=, |$)", cell)]


def test_a_label_carrying_its_own_commas_is_read_whole():
    """The class the appendix's first keyword-ordering bullet is about is the class that breaks a comma split."""
    cell = "Marine, aviation and transport (268), Marine aviation and transport (146), Aviation (118)"
    assert labels_in(cell) == ["Marine, aviation and transport", "Marine aviation and transport", "Aviation"]
    assert gda.LOB_NAMES[ra.classify_lob("Marine, aviation and transport")] == "Aviation"
    assert gda.LOB_NAMES[ra.classify_lob("and transport")] != "Aviation"      # what a comma split would have read


def test_the_audit_holds_no_classifier_of_its_own():
    assert not hasattr(gda, "RULES"), "the audit has its own keyword table again"
    assert gda.LOB_NAMES is ra.LOB_NAMES, "the audit's category names are not the analysis's own list"


def test_the_audit_classifies_every_turning_label_as_the_analysis_does():
    for label, category in TURNING_LABELS.items():
        assert gda.classify(label) == ra.classify_lob(label), label
        assert gda.LOB_NAMES[gda.classify(label)] == category, label


def test_the_committed_appendix_files_each_label_under_the_category_the_analysis_gives_it():
    """The table's rows carry their own labels, so a stale document fails here without re-mining the corpus."""
    with io.open(APPENDIX, encoding="utf-8") as fh:
        text = fh.read()
    section = text.split("## B.3 Line-of-business taxonomy", 1)[1].split("## B.4", 1)[0]
    rows = re.findall(r"^\| ([^|]+?) \| +\d+% \| (.+?) \|$", section, re.M)
    assert len(rows) >= 10, "the taxonomy table is not where it was"
    checked = 0
    for category, labels in rows:
        for label in labels_in(labels):
            name = label.replace("–", "-")
            assert gda.LOB_NAMES[ra.classify_lob(name)] == category.strip(), \
                "%r is filed under %s; the analysis gives %s" % (name, category.strip(),
                                                                 gda.LOB_NAMES[ra.classify_lob(name)])
            checked += 1
    assert checked >= 30, "only %d labels were checked" % checked


def test_the_appendix_states_the_classifier_it_uses():
    with io.open(APPENDIX, encoding="utf-8") as fh:
        text = " ".join(fh.read().split())
    assert "`classify_lob` in `src/run_analysis.py`" in text
    assert "an Energy-headed label is Energy" in text
    assert "*non-marine* is removed before the keywords are tried" in text
