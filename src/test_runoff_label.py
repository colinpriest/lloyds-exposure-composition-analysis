r"""The run-off class's words (the author's decision D1, 30 September 2026; FIX3 A2).

The class was labelled "gross written premium =0, no mix". "No mix" was false for every record the class could hold:
each of the nine records with a development figure and a premium at or below zero lists a premium mix. D1 also
widened the class to a negative premium where the syndicate's own filing states that it is in run-off. The
reconciliation table and the data-audit appendix now state the rule. The table keeps the words "in run-off": the
manuscript's gate BB finds the row by them.

Run:  python -m pytest src/test_runoff_label.py -q
"""
import copy
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import generate_data_audit as gda  # noqa: E402
import run_analysis as ra  # noqa: E402

RULE_TEX = "in run-off (gross written premium $=0$, or $<0$ where the filing states run-off)"
RULE_MD = "In run-off (GPW = 0, or GPW < 0 where the filing states run-off)"
RETRACTED = ("no mix", "no premium mix")


def _table39(monkeypatch, in_runoff):
    written = {}
    monkeypatch.setattr(ra, "_write_tex", lambda fname, content: written.__setitem__(fname, content))
    corpus = 20 - 2 - 3 - 1 - in_runoff - 1
    flow = {"files_retrieved": 20,
            "pre_corpus": {"excluded": 2, "skipped": 3, "incomplete_no_development_record": 1,
                           "in_runoff": in_runoff, "no_reserves": 1},
            "corpus": corpus, "corpus_records_parsed": corpus,
            "to_working_sample": {"net_or_unstated_basis": 1, "takeon_not_development": 0,
                                  "unusable_severity": 0, "missing_opening_reserves": 0,
                                  "missing_lob_weights": 1},
            "working_sample": corpus - 2, "working_sample_equals_eligible_for_capital": True,
            "files_without_any_model_record_overlapping_audit_count": 4,
            "files_without_dual_model_record_overlapping_audit_count": 4,
            "ledger_csv": "results/disposition_ledger.csv"}
    ra._gen_table39({"disposition_flow": flow})
    return written["table39_reconciliation.tex"]


@pytest.mark.parametrize("n", [1, 7])
def test_the_reconciliation_row_states_the_rule(monkeypatch, n):
    tex = _table39(monkeypatch, n)
    # 20 retrieved, less 2 excluded, 3 skipped and 1 without a development record: 14 before the run-off step
    assert "\\quad less: %s & $-%d$ & %d \\\\" % (RULE_TEX, n, 14 - n) in tex
    assert not any(word in tex for word in RETRACTED)


def test_the_manuscripts_gate_finds_the_row_by_its_words(monkeypatch):
    rows = [line for line in _table39(monkeypatch, 7).splitlines() if "in run-off" in line]
    assert len(rows) == 1 and "$-7$" in rows[0]


@pytest.fixture(scope="module")
def audit_inputs():
    return gda.compute(), gda.mine_raw()


@pytest.mark.parametrize("n, count", [(1, "(1 record)"), (7, "(7 records)")])
def test_the_data_audit_states_the_rule_and_counts_its_records(audit_inputs, n, count):
    c, r = audit_inputs
    c = copy.deepcopy(c)
    c["disc"]["in_runoff"] = n
    text = gda.md(c, r)
    assert "| — %s | | %d |" % (RULE_MD, n) in text
    assert "*run-off* years leave before the corpus %s" % count in text
    assert "pdf_extraction/audit/runoff_register.json" in text
    assert not any(word in text for word in RETRACTED)
