#!/usr/bin/env python3
"""The counts the manuscript quotes from the loader flow and the inferential partition, keyed and reconciled.

The review of 29 September 2026 (A-3k) found counts quoted that no output held: 133 basis exclusions against
the flow's 125, 15 records at the unusable-severity step, and the assumed-business regime's composition
(30 + 4 + 2 of 36 in the working sample; 60 across the scanned filings; 53 in the corpus). missingness_check
now writes each as a keyed count with the arithmetic that joins them, and asserts that arithmetic. These
tests hold the identities on the committed inputs, show the assertions refuse a planted inconsistency,
and pin the quoted values so a data change that moves them is seen.

Run:  python -m pytest src/test_missingness_reconciliation.py -q
"""
import copy
import csv
import io
import json
import os

import pytest

import assumed_business
import missingness_check as MC

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def inputs():
    rows = MC.add_size_proxies(MC.classify_filings())
    ledger = list(csv.DictReader(io.open(os.path.join(HERE, "results", "disposition_ledger.csv"), encoding="utf-8")))
    flow = json.load(io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8"))["disposition_flow"]
    return rows, ledger, flow


def test_the_basis_exclusions_reconcile_with_the_flow(inputs):
    rows, ledger, flow = inputs
    r = MC.basis_exclusions_reconciliation(rows, ledger, flow)
    tows = flow["to_working_sample"]
    assert r["flow_basis_step"] == tows["net_or_unstated_basis"]
    assert r["flow_basis_step_net"] + r["flow_basis_step_unstated"] == r["flow_basis_step"]
    assert r["flow_basis_step"] + r["basis_records_at_unusable_severity_step"] == r["inferential_basis_exclusions"]
    assert len(r["basis_records_at_unusable_severity_step_files"]) == r["basis_records_at_unusable_severity_step"]
    assert sum(r["unusable_severity_components"].values()) == r["flow_unusable_severity_step"] \
        == tows["unusable_severity"]


def test_the_quoted_counts(inputs):
    rows, ledger, flow = inputs
    r = MC.basis_exclusions_reconciliation(rows, ledger, flow)
    assert r["identity_basis"] == "125 + 8 = 133"
    assert (r["flow_basis_step_net"], r["flow_basis_step_unstated"]) == (100, 25)
    assert r["unusable_severity_components"] == {"gross_development_unavailable": 6,
                                                 "non_gross_or_unstated_development": 8,
                                                 "provision_movement_not_development": 1}
    g = MC.regime_composition(rows)
    assert g["working_sample"]["composition"] == {"ritc_flagged": 30, "confirmed_transfer_not_flagged": 4,
                                                  "takeon_only": 2}
    assert (g["working_sample"]["n_regime"], g["scanned_filings"]["n_regime"], g["corpus"]["n_regime"]) == (36, 60, 53)


def test_a_flow_that_disagrees_is_refused(inputs):
    rows, ledger, flow = inputs
    bad = copy.deepcopy(flow)
    bad["to_working_sample"]["net_or_unstated_basis"] += 1
    with pytest.raises(AssertionError):
        MC.basis_exclusions_reconciliation(rows, ledger, bad)
    bad = copy.deepcopy(flow)
    bad["to_working_sample"]["unusable_severity"] -= 1
    with pytest.raises(AssertionError):
        MC.basis_exclusions_reconciliation(rows, ledger, bad)


def test_each_regime_row_is_counted_once(inputs):
    rows, _ledger, _flow = inputs
    g = MC.regime_composition(rows)
    for name in ("scanned_filings", "corpus", "working_sample"):
        p = g[name]
        assert sum(p["composition"].values()) == p["n_regime"] <= p["n_rows"]
        assert p["confirmed_transfers_also_flagged"] <= min(p["confirmed_transfers"], p["composition"]["ritc_flagged"])
    assert g["working_sample"]["n_rows"] < g["corpus"]["n_rows"] < g["scanned_filings"]["n_rows"]


def test_a_regime_row_outside_the_scanned_filings_is_refused(inputs, monkeypatch):
    rows, _ledger, _flow = inputs
    real = assumed_business.sources()
    monkeypatch.setattr(assumed_business, "sources", lambda: dict(real, **{"9999_2099": ["transfer_takeon"]}))
    with pytest.raises(AssertionError):
        MC.regime_composition(rows)


def _classify(tmp_path, monkeypatch, ledger_rows):
    """classify_filings over a synthetic ledger of pre-corpus dispositions (no observations, no audit)."""
    for d in ("results", "model", "pdf_extraction"):
        (tmp_path / d).mkdir()
    (tmp_path / "results" / "disposition_ledger.csv").write_text(
        "file,disposition,status,reason,basis_source\n"
        + "".join("%s,%s,%s,,\n" % (f, d, d) for f, d in ledger_rows), encoding="utf-8")
    (tmp_path / "model" / "exposure_results.json").write_text(json.dumps({"observations": []}), encoding="utf-8")
    for f, _d in ledger_rows:
        (tmp_path / "pdf_extraction" / f).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(MC, "SD", tmp_path)
    monkeypatch.setattr(MC, "_structural_decisions", lambda: {})
    return {r["file"]: r for r in MC.classify_filings()}


def test_a_run_off_year_is_a_scientific_exclusion(tmp_path, monkeypatch):
    """Round 62: 2468/2022 is the first run-off year the loader has met (no gross premium written, so no
    premium-mix composition), and classify_filings, which had no branch for the loader's IN RUNOFF, stopped the
    regeneration pass. It is a design exclusion before the corpus, like a year without a positive reserve base."""
    rows = _classify(tmp_path, monkeypatch, [("syndicate_2468_2022.json", "IN RUNOFF"),
                                             ("syndicate_5183_2024.json", "NO_RESERVES")])
    run_off = rows["syndicate_2468_2022.json"]
    assert (run_off["category"], run_off["detail"]) == ("scientific_exclusion", "in_runoff_no_written_premium")
    assert run_off["economic_eligibility"] == "outside_written-premium_estimand"
    assert run_off["observation"] is None and (run_off["syndicate"], run_off["year"]) == (2468, 2022)
    no_reserves = rows["syndicate_5183_2024.json"]
    assert (no_reserves["category"], no_reserves["detail"]) == ("scientific_exclusion", "no_positive_reserve_base")


def test_a_pre_corpus_disposition_nobody_classified_still_stops_the_check(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match="unclassified pre-corpus disposition"):
        _classify(tmp_path, monkeypatch, [("syndicate_9999_2024.json", "SOMETHING_NEW")])


def test_the_recorded_result_carries_both_blocks(inputs):
    """DEFERRED-TO-REFIT: results/missingness_check_results.json is rewritten by the recorded pass."""
    rows, ledger, flow = inputs
    rec = json.load(io.open(os.path.join(HERE, "results", "missingness_check_results.json"), encoding="utf-8"))
    assert rec["basis_exclusions_reconciliation"] == MC.basis_exclusions_reconciliation(rows, ledger, flow)
    assert rec["assumed_business_regime"] == MC.regime_composition(rows)
