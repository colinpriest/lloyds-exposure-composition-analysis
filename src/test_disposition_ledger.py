"""The disposition ledger and the flow derived from it (round 52, review finding M04).

The manuscript's reconciliation table once subtracted 134 'empty' files first and then
listed discard groups that overlapped that subtraction, so its running totals could not
be reproduced.  The loader's dispositions are sequential and mutually exclusive; the
ledger records one row per filing and the flow is derived from it, so the corpus and
working-sample totals are exact sums.
"""
import csv
import io
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

LEDGER = os.path.join(HERE, "results", "disposition_ledger.csv")
RESULTS = os.path.join(HERE, "model", "exposure_results.json")
TABLE = os.path.join(HERE, "paper_pack", "table39_reconciliation.tex")


def _flow():
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    fl = d.get("disposition_flow")
    if not fl:
        pytest.skip("exposure_results.json predates the disposition ledger (rerun pending)")
    return fl


def test_flow_sums_are_exact():
    fl = _flow()
    pre = fl["pre_corpus"]
    assert fl["files_retrieved"] - sum(pre.values()) == fl["corpus"]
    ws = fl["to_working_sample"]
    assert fl["corpus"] - sum(ws.values()) == fl["working_sample"]
    assert fl["corpus"] == fl["corpus_records_parsed"]
    assert fl["working_sample_equals_eligible_for_capital"] is True


def test_ledger_has_one_row_per_filing_and_matches_the_flow():
    fl = _flow()
    if not os.path.exists(LEDGER):
        pytest.skip("ledger not written yet (rerun pending)")
    rows = list(csv.DictReader(io.open(LEDGER, encoding="utf-8")))
    assert len(rows) == fl["files_retrieved"]
    assert len({r["file"] for r in rows}) == len(rows)
    by = {}
    for r in rows:
        by[r["disposition"]] = by.get(r["disposition"], 0) + 1
    pre = fl["pre_corpus"]
    assert by.get("EXCLUDED", 0) == pre["excluded"]
    assert by.get("SKIPPED", 0) == pre["skipped"]
    assert by.get("INCOMPLETE_PRE", 0) == pre["incomplete_no_development_record"]
    assert by.get("IN RUNOFF", 0) == pre["in_runoff"]
    assert by.get("NO_RESERVES", 0) == pre["no_reserves"]
    assert sum(v for k, v in by.items() if k.startswith("CORPUS:")) == fl["corpus"]


def test_generated_table_carries_the_flow_and_no_first_subtraction_of_empties():
    fl = _flow()
    if not os.path.exists(TABLE):
        pytest.skip("generated table not written yet (rerun pending)")
    tex = io.open(TABLE, encoding="utf-8").read()
    assert "tab:reconcile" in tex
    corpus = f"{fl['corpus']:,}".replace(",", "{,}")
    assert f"Corpus & -- & {corpus}" in tex
    assert f"\\textbf{{{fl['working_sample']}}}" in tex
    # the overlapping diagnostic is a note, never a flow step
    n_empty = fl["files_without_dual_model_record_overlapping_audit_count"]
    assert f"less: no usable dual-model extraction" not in tex
    assert f"{n_empty} of the" in tex


def test_builder_on_a_synthetic_log():
    import run_analysis as ra
    log = [
        {"file": "a.json", "status": "EXCLUDED", "no_models": True},
        {"file": "b.json", "status": "SKIPPED", "no_models": True},
        {"file": "c.json", "status": "INCOMPLETE", "reason": "no models"},
        {"file": "d.json", "status": "IN RUNOFF"},
        {"file": "e.json", "status": "NO_RESERVES"},
        {"file": "f.json", "status": "RELIABLE"},
        {"file": "g.json", "status": "NET_BASIS", "basis_source": "register"},
        {"file": "h.json", "status": "INCOMPLETE"},
    ]
    records = [
        {"data_quality_tag": "RELIABLE", "pyd_basis": "gross", "pyd_pct": 1.0,
         "opening_reserves_gbp_m": 10.0, "lob_severity_computed": True, "eligible_for_capital": True},
        {"data_quality_tag": "NET_BASIS", "pyd_basis": "net", "pyd_pct": 1.0,
         "opening_reserves_gbp_m": 10.0, "lob_severity_computed": True, "eligible_for_capital": False},
        {"data_quality_tag": "INCOMPLETE", "pyd_basis": "gross", "pyd_pct": None,
         "opening_reserves_gbp_m": 10.0, "lob_severity_computed": False, "eligible_for_capital": False},
    ]
    out = os.path.join(HERE, "results", "_ledger_test.csv")
    try:
        fl = ra.build_disposition_ledger(log, records, out)
    finally:
        if os.path.exists(out):
            os.unlink(out)
    assert fl["files_retrieved"] == 8 and fl["corpus"] == 3
    assert fl["pre_corpus"] == {"excluded": 1, "skipped": 1, "incomplete_no_development_record": 1,
                                "in_runoff": 1, "no_reserves": 1}
    assert fl["to_working_sample"] == {"net_or_unstated_basis": 1, "unusable_severity": 1,
                                       "missing_opening_reserves": 0, "missing_lob_weights": 0}
    assert fl["working_sample"] == 1 and fl["working_sample_equals_eligible_for_capital"]
    assert fl["files_without_dual_model_record_overlapping_audit_count"] == 2
