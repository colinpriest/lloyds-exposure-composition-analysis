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


def test_the_scientific_exclusions_are_printed_by_detail_with_the_scope_rule():
    """The scope exclusions (D3-1) are not lumped in with the other scientific exclusions (the stage-3 review,
    finding 4): the audit prints each detail with its count, in the extracted-mix wording, and the counts add up."""
    inf = {"categories": {"scientific_exclusion": 7},
           "scientific_details": {"in_runoff": 2, "mix_names_no_line_of_business": 3, "life_book": 1,
                                  "a_new_detail": 1},
           "composition_reasons": {"readers_disagree": 2, "extraction_lost_lines": 11, "no_mix": 4}}
    text = "\n".join(gda.scientific_exclusion_lines(inf))
    # the emitted detail labels state the filing criterion, not the extracted mix (a page reading decided these records)
    assert "| scope: the filing prints no premium amount for any non-life line of business" in text and "| 3 |" in text
    assert "| scope: life business | 1 |" in text
    assert "extracted premium mix" not in text
    assert "| a_new_detail | 1 |" in text, "a detail the words do not list is printed, not dropped"
    assert "the book" not in text
    # the scope rule (the filing criterion, decided by a page reading) and the two kinds of extraction loss
    assert "only if its filing prints no premium amount for any non-life line of business" in text
    assert "life books are out of scope as life business" in text
    assert "outranks the models' readings in both directions" in text
    assert "`extraction_lost_lines`, 11 records" in text and "`readers_disagree`, 2 records" in text
    assert "composition_page_readings.json" in text and "gets no weights" in text
    assert "no other model's reading names a line of business:" not in text, "the old, partial rule"
    import pytest
    with pytest.raises(ValueError):
        gda.scientific_exclusion_lines({"categories": {"scientific_exclusion": 8},
                                        "scientific_details": inf["scientific_details"]})


def test_the_audit_counts_the_loaders_composition_reasons_from_the_ledger(tmp_path, monkeypatch):
    import csv
    cols = ["category", "detail", "economic_eligibility", "disclosure_availability", "extraction_status",
            "in_supported_target_population", "in_broader_potential_target", "in_model_sample",
            "composition_unavailable_reason"]
    cats = ["structural_no_eligible_outcome", "eligibility_unresolved", "scientific_exclusion",
            "eligible_outcome_unavailable", "eligible_observed_composition_unavailable", "working_sample"]
    rows = [(c, "x", "", "", "", "False", "False", "False", "") for c in cats]
    rows += [("scientific_exclusion", "mix_names_no_line_of_business", "", "", "", "False", "False", "False",
              "contract_form_only"),
             ("eligible_observed_composition_unavailable", "missing_lob_composition", "", "", "", "True", "True",
              "False", "extraction_lost_lines"),
             ("eligible_observed_composition_unavailable", "missing_lob_composition", "", "", "", "True", "True",
              "False", "extraction_lost_lines"),
             ("eligible_observed_composition_unavailable", "missing_lob_composition", "", "", "", "True", "True",
              "False", "readers_disagree")]
    path = tmp_path / "ledger.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        w.writerows(rows)
    monkeypatch.setattr(gda, "INFERENTIAL_LEDGER", path)
    reasons = gda.inferential_ledger()["composition_reasons"]
    assert (reasons["extraction_lost_lines"], reasons["readers_disagree"], reasons["contract_form_only"]) == (2, 1, 1)
    # a ledger from before the column has none
    cols2 = cols[:-1]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols2)
        w.writerows([r[:-1] for r in rows])
    assert gda.inferential_ledger()["composition_reasons"].get("extraction_lost_lines", 0) == 0


def test_the_rendered_audit_prints_every_scientific_exclusion_detail_with_its_count():
    """The generator calls the by-detail table, not only defines it: the rendered appendix lists each detail of the
    ledger it reads, with its count."""
    text = gda.md(gda.compute(), gda.mine_raw())
    assert "The scientific exclusions by detail:" in text and "| Scientific exclusion | Records |" in text
    inf = gda.inferential_ledger()
    assert inf["scientific_details"]
    for detail, n in inf["scientific_details"].items():
        assert "| %s | %d |" % (gda.SCIENTIFIC_DETAIL_WORDS.get(detail, detail), n) in text, detail


def test_the_audit_describes_the_run_off_rule_with_or_without_a_development_figure():
    """The whole-year run-off rule reaches a record the extraction left unread (1400/2014, 3210/2018), so every
    description of it says 'with or without a development figure': the waterfall row, the paragraph below it, and the
    paper pack's table row."""
    src = " ".join(open(gda.__file__, encoding="utf-8").read().split())
    # the waterfall row (split over two string literals in the source) and the paragraph below it
    assert "with or without a development figure, outside " in src and "the RITC regime; or GPW = 0" in src
    assert "was in run-off for the whole year, with or without a development figure (a record the extraction left" in src
    # (the rendered paragraph is checked whole in test_runoff_label)
    import run_analysis
    ra_src = " ".join(open(run_analysis.__file__, encoding="utf-8").read().split())
    assert "states run-off for the whole year, with or without a development " in ra_src  # (the table row, split in two)
    # no description of the rule is left without it
    for text in (src, ra_src):
        assert "states run-off for the whole year, outside the RITC regime" not in text


def test_every_scientific_exclusion_detail_in_the_committed_ledger_has_its_words():
    inf = gda.inferential_ledger()
    assert sum(inf["scientific_details"].values()) == inf["categories"]["scientific_exclusion"]
    assert set(inf["scientific_details"]) <= set(gda.SCIENTIFIC_DETAIL_WORDS), (
        set(inf["scientific_details"]) - set(gda.SCIENTIFIC_DETAIL_WORDS))


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
