"""The corpus test and its step are worded as the loader applies them (the review of 2 October 2026, P-9).

The paper defined the corpus as filings that carry "a prior-year development figure" and labelled the step before
it "incomplete (no model carries a development figure)". The loader's test is on the extraction's validation flag
and the percentage: a validated record takes its first model whatever that model read, and an unvalidated one
needs a model with a development percentage. So six corpus records carry no figure in any model (all validated),
and three of the step's six carry an amount but no percentage. The repair chosen is the wording (the corpus stays
902): the step's label and reason state the test, and these tests replay the loader to hold both sides of it.

Run:  python -m pytest src/test_corpus_test_wording.py -q
"""
import io
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import run_analysis as ra  # noqa: E402

PRE = {"EXCLUDED", "SKIPPED", "IN RUNOFF", "NO_RESERVES"}


def _record(name):
    with io.open(os.path.join(HERE, "pdf_extraction", name), encoding="utf-8") as fh:
        return json.load(fh)


def _has(models, field):
    return any((m or {}).get(field) is not None for m in models.values())


@pytest.fixture(scope="module")
def log():
    _records, _counters, log, _files = ra.load_and_classify()
    return log


def test_the_steps_records_failed_validation_and_carry_no_percentage(log):
    step = [e["file"] for e in log if e["status"] == "INCOMPLETE" and e.get("reason") == ra.INCOMPLETE_PRE_REASON]
    # six until the PC's completion of data/eligibility_from_filing.json (5 October 2026) counted 1254/2022 and 6118/2014
    # with the first-year reports the extraction skips, from their filings (P-10)
    assert len(step) == 4
    with_amount = []
    for name in step:
        rec = _record(name)
        models = rec.get("models") or {}
        assert (rec.get("validation") or {}).get("passed") is not True, name
        assert not _has(models, "prior_year_development_pct"), name
        if _has(models, "prior_year_development_gbp_m"):
            with_amount.append(name)
    # the review's three, less 1254/2022 (now a first-year report from its filing): an amount, no percentage
    assert with_amount == ["syndicate_6107_2017.json", "syndicate_6107_2021.json"]


def test_a_corpus_record_with_no_figure_in_any_model_is_a_validated_one(log):
    # the ledger's rule (build_disposition_ledger): an INCOMPLETE entry with a reason stopped before the corpus
    corpus = [e["file"] for e in log
              if e["status"] not in PRE and not (e["status"] == "INCOMPLETE" and e.get("reason"))]
    no_figure = []
    for name in corpus:
        rec = _record(name)
        models = rec.get("models") or {}
        if not _has(models, "prior_year_development_pct") and not _has(models, "prior_year_development_gbp_m"):
            assert (rec.get("validation") or {}).get("passed") is True, name
            no_figure.append(name[len("syndicate_"):-len(".json")])
    assert len(corpus) > 850
    assert sorted(no_figure) == sorted(["3622_2015", "435_2014", "4711_2014", "5623_2020", "6050_2017", "6107_2019"])


def test_the_reconciliation_row_states_the_test(monkeypatch):
    flow = {"files_retrieved": 10, "corpus": 4, "working_sample": 4,
            "files_without_dual_model_record_overlapping_audit_count": 0,
            "pre_corpus": {"excluded": 0, "skipped": 0, "incomplete_no_development_record": 6, "in_runoff": 0,
                           "no_reserves": 0},
            "to_working_sample": {"net_or_unstated_basis": 0, "takeon_not_development": 0, "unusable_severity": 0,
                                  "missing_opening_reserves": 0, "missing_lob_weights": 0}}
    written = {}
    monkeypatch.setattr(ra, "_write_tex", lambda name, tex: written.update({name: tex}))
    ra._gen_table39({"disposition_flow": flow})
    tex = written["table39_reconciliation.tex"]
    assert "\\quad less: %s & $-6$" % ra.INCOMPLETE_PRE_LABEL in tex
    assert "no model carries a development figure" not in tex
    assert "validation failed" in ra.INCOMPLETE_PRE_LABEL and "percentage" in ra.INCOMPLETE_PRE_LABEL
