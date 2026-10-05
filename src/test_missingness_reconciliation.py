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
    # the author's decision D1 (30 September 2026): 1206/2019 and 1400/2014, net-basis years at the unusable-severity
    # step whose filings state run-off, leave before the corpus (125 + 8 = 133 -> 125 + 6 = 131; that step 15 -> 13);
    # the decision of 1 October 2026: 2243/2014, a net-basis whole-year run-off year, leaves too (-> 124 + 6 = 130),
    # and the same day's extension of rule M01 counts four basis exclusions with the first-year reports: 1947/2019 and
    # 6133/2019 (net), 1729/2015 and 6134/2019 (unstated) (-> 120 + 6 = 126); the import of the extraction at
    # 57b4b14d (4 October 2026) adds one unstated-basis record at the basis step (-> 121 + 6 = 127: 97 net and 24
    # unstated, measured from the loader on the imported records); the PC's completion of 435/2014 (a stated "net release"
    # that is unstated-basis: basis exclusion at the unusable-severity step, where it was a gross development unavailable)
    # makes the step's basis records 7 and its gross-unavailable ones 5 (-> 121 + 7 = 128)
    assert r["identity_basis"] == "121 + 7 = 128"
    assert (r["flow_basis_step_net"], r["flow_basis_step_unstated"]) == (97, 24)
    assert r["unusable_severity_components"] == {"gross_development_unavailable": 5,
                                                 "non_gross_or_unstated_development": 7,
                                                 "provision_movement_not_development": 1}
    g = MC.regime_composition(rows)
    # round 62 (the records at extraction d9f2bdee): the working sample's regime rows 30 + 4 + 2 of 36 -> 31 + 5 + 2
    # of 38 and the corpus's 53 -> 55; the scanned filings' 60 and the basis identities above are unchanged
    assert g["working_sample"]["composition"] == {"ritc_flagged": 31, "confirmed_transfer_not_flagged": 5,
                                                  "takeon_only": 2}
    assert (g["working_sample"]["n_regime"], g["scanned_filings"]["n_regime"], g["corpus"]["n_regime"]) == (38, 60, 55)


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


def _classify(tmp_path, monkeypatch, ledger_rows, sources=None, structural=None, observations=None):
    """classify_filings over a synthetic ledger of pre-corpus dispositions (no observations); a row is
    (file, disposition) or (file, disposition, the loader's reason); `sources` gives a record's JSON where the test
    needs one, and `structural` the filing-page audit's decisions by file (none by default)."""
    for d in ("results", "model", "pdf_extraction"):
        (tmp_path / d).mkdir()
    rows = [tuple(r) + ("",) * (3 - len(r)) for r in ledger_rows]
    with io.open(tmp_path / "results" / "disposition_ledger.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["file", "disposition", "status", "reason", "basis_source"])
        writer.writerows([f, d, d, reason, ""] for f, d, reason in rows)
    (tmp_path / "model" / "exposure_results.json").write_text(json.dumps({"observations": observations or []}),
                                                              encoding="utf-8")
    for f, _d, _reason in rows:
        (tmp_path / "pdf_extraction" / f).write_text(json.dumps((sources or {}).get(f, {})), encoding="utf-8")
    monkeypatch.setattr(MC, "SD", tmp_path)
    monkeypatch.setattr(MC, "_structural_decisions", lambda: dict(structural or {}))
    return {r["file"]: r for r in MC.classify_filings()}


RUNOFF_BY_STATEMENT = ('gross written premium -2.19m and the filing states the syndicate is in run-off (page 7): '
                       '"The syndicate ceased underwriting, and is in run-off."')


#: the loader's reason for a positive opening base at or below its floor (run_analysis.no_reserves_reason; P-6)
BELOW_FLOOR = "opening reserves of GBP 0.0799m, positive but at or below the floor of GBP 0.1m (after the FX conversion)"


def test_a_run_off_year_is_a_scientific_exclusion(tmp_path, monkeypatch):
    """Round 62: 2468/2022 is the first run-off year the loader has met (gross written premium 0), and
    classify_filings, which had no branch for the loader's IN RUNOFF, stopped the regeneration pass. It is a design
    exclusion before the corpus, like a year without a positive reserve base. The author's decision D1 (30 September
    2026) adds a negative-premium year whose filing states that the syndicate is in run-off; the evidence is the
    loader's reason, with the filing's words, and the detail no longer says "no written premium"."""
    rows = _classify(tmp_path, monkeypatch, [("syndicate_2468_2022.json", "IN RUNOFF", "gross written premium 0"),
                                             ("syndicate_2468_2021.json", "IN RUNOFF", RUNOFF_BY_STATEMENT),
                                             ("syndicate_5183_2024.json", "NO_RESERVES", BELOW_FLOOR)])
    for name, reason in (("syndicate_2468_2022.json", "gross written premium 0"),
                         ("syndicate_2468_2021.json", RUNOFF_BY_STATEMENT)):
        run_off = rows[name]
        assert (run_off["category"], run_off["detail"]) == ("scientific_exclusion", "in_runoff"), name
        assert run_off["economic_eligibility"] == "outside_written-premium_estimand"
        assert run_off["classification_evidence"] == "run-off year: " + reason
        assert run_off["observation"] is None
    assert (rows["syndicate_2468_2022.json"]["syndicate"], rows["syndicate_2468_2022.json"]["year"]) == (2468, 2022)
    no_reserves = rows["syndicate_5183_2024.json"]
    assert (no_reserves["category"], no_reserves["detail"]) == ("scientific_exclusion", "no_positive_reserve_base")
    # the loader's reason, which tells a positive base below the floor from a nil one (P-6)
    assert no_reserves["classification_evidence"] == "no opening-reserve base above the floor: " + BELOW_FLOOR


def test_a_run_off_row_without_the_loaders_reason_is_refused(tmp_path, monkeypatch):
    """A ledger from before the rule carries no reason: the partition would state a run-off year with no evidence."""
    with pytest.raises(AssertionError, match="without the loader's reason"):
        _classify(tmp_path, monkeypatch, [("syndicate_2468_2022.json", "IN RUNOFF")])


def test_an_unread_record_carries_the_extractions_status_and_nothing_about_its_filing(tmp_path, monkeypatch):
    """Round 62's verification (MAT-2 residual): the 45 records the extraction did not read were classified as
    "no_development_disclosure_found", a claim about filings nobody read. Their status is no_deterministic_reading:
    the parsers found no prior-year figure and the models were not run. The detail is that status, the evidence is the
    record's own reason, and an EXCLUDED record with any other status is refused, not relabelled."""
    reason = ("No deterministic reading: the table, page-text and narrative parsers found no prior-year figure. "
              "This describes the parsers, not the filing.")
    rows = _classify(tmp_path, monkeypatch, [("syndicate_1221_2014.json", "EXCLUDED")],
                     {"syndicate_1221_2014.json": {"status": "no_deterministic_reading", "exclusion_reason": reason,
                                                   "models_run": False}})
    row = rows["syndicate_1221_2014.json"]
    assert (row["category"], row["detail"]) == ("eligibility_unresolved", "no_deterministic_reading")
    assert row["economic_eligibility"] == "unresolved"
    assert row["classification_evidence"] == reason
    assert "disclosure" not in row["detail"] and "found" not in row["disclosure_availability"]


def test_an_excluded_record_of_another_status_is_refused(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match="not no_deterministic_reading"):
        _classify(tmp_path, monkeypatch, [("syndicate_9_2014.json", "EXCLUDED")],
                  {"syndicate_9_2014.json": {"status": "manually_excluded"}})


def test_a_pre_corpus_disposition_nobody_classified_still_stops_the_check(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match="unclassified pre-corpus disposition"):
        _classify(tmp_path, monkeypatch, [("syndicate_9999_2024.json", "SOMETHING_NEW")])


def _observation(syndicate, year, reason, opening=10.0):
    return {"syndicate": syndicate, "year": year, "pyd_pct": 0.1, "pyd_basis": "gross", "hhi": None,
            "opening_reserves_gbp_m": opening, "composition_unavailable_reason": reason}


@pytest.mark.parametrize("reason,category,detail", [
    ("contract_form_only", "scientific_exclusion", "mix_names_no_line_of_business"),
    ("channel_only", "scientific_exclusion", "mix_names_no_line_of_business"),
    ("life", "scientific_exclusion", "life_book"),
    ("readers_disagree", "eligible_observed_composition_unavailable", "missing_lob_composition"),
    ("other_labels", "eligible_observed_composition_unavailable", "missing_lob_composition"),
])
def test_an_observed_record_without_a_composition_is_classified_by_the_loaders_reason(tmp_path, monkeypatch,
                                                                                        reason, category, detail):
    rows = _classify(tmp_path, monkeypatch, [("syndicate_9_2020.json", "CORPUS:INCOMPLETE")],
                     observations=[_observation(9, 2020, reason)])
    row = rows["syndicate_9_2020.json"]
    assert (row["category"], row["detail"]) == (category, detail)
    assert row["classification_evidence"].endswith(MC.COMPOSITION_REASON_WORDS[reason])


def test_an_observed_record_with_no_opening_base_carries_the_label_the_no_reserves_rule_uses(tmp_path, monkeypatch):
    """The current loader removes such a record at NO_RESERVES (P-6), so the branch for an observation without one is
    reached only with older loader output; it carried the label "outside_positive-reserve_estimand", which the
    NO_RESERVES rule does not use (the stage-3 review, finding 4)."""
    rows = _classify(tmp_path, monkeypatch, [("syndicate_9_2020.json", "CORPUS:INCOMPLETE")],
                     observations=[_observation(9, 2020, "life", opening=0)])
    row = rows["syndicate_9_2020.json"]
    assert (row["category"], row["detail"]) == ("scientific_exclusion", "no_positive_reserve_base")
    assert row["economic_eligibility"] == MC.no_reserves_disposition(
        {"file": "x", "reason": "r"})[2] == "outside_reserve-base_estimand"
    with io.open(os.path.join(HERE, "src", "missingness_check.py"), encoding="utf-8") as fh:
        # the comment on the branch names the old label; it is not a label the code assigns
        lines = [ln for ln in fh.read().splitlines() if "outside_positive-reserve_estimand" in ln]
        assert lines and all(ln.strip().startswith("#") for ln in lines)


def test_the_exclusion_counts_give_the_scope_exclusions_by_detail_and_the_reasons():
    def row(category, detail, reason=None):
        return {"category": category, "detail": detail,
                "observation": None if reason is None else {"composition_unavailable_reason": reason}}

    rows = [row("scientific_exclusion", "mix_names_no_line_of_business", "contract_form_only"),
            row("scientific_exclusion", "mix_names_no_line_of_business", "channel_only"),
            row("scientific_exclusion", "life_book", "life"),
            row("scientific_exclusion", "in_runoff"),
            row("eligible_observed_composition_unavailable", "missing_lob_composition", "readers_disagree"),
            row("eligible_observed_composition_unavailable", "missing_lob_composition", "no_mix"),
            row("working_sample", "observed_eligible_complete")]
    got = MC.exclusion_counts(rows)
    assert got["scientific_exclusion_detail_counts"] == {"in_runoff": 1, "life_book": 1,
                                                         "mix_names_no_line_of_business": 2}
    assert got["composition_scope_exclusion_counts"] == {"life_book": 1, "mix_names_no_line_of_business": 2}
    assert got["composition_unavailable_reason_counts"] == {"channel_only": 1, "contract_form_only": 1, "life": 1,
                                                            "no_mix": 1, "readers_disagree": 1}


def test_the_definition_says_what_the_scope_rule_is():
    src = io.open(os.path.join(HERE, "src", "missingness_check.py"), encoding="utf-8").read()
    start = src.index('"supported_disclosure_defined_target"')
    definition = " ".join(src[start:src.index('"broader_potential_target"')].split())
    definition = definition.replace('" "', "")
    assert "extracted premium mix names no line of business" in definition
    assert "life record" in definition and "another model's reading" in definition
    assert "the book" not in definition


def test_the_current_results_print_the_scientific_exclusions_by_detail():
    import build_current_results as bcr
    miss = {"scientific_exclusion_detail_counts": {"in_runoff": 5, "life_book": 22, "mix_names_no_line_of_business": 50,
                                                   "a_new_detail": 1},
            "composition_scope_exclusion_counts": {"life_book": 22, "mix_names_no_line_of_business": 50},
            "composition_unavailable_reason_counts": {"readers_disagree": 4, "no_mix": 4}}
    text = bcr.scientific_exclusion_sentence(miss)
    assert text.startswith("- The 78 scientific exclusions are, by detail: 50 the extracted premium mix names no line")
    assert "22 the extracted premium mix is life business (scope)" in text and "1 a_new_detail" in text
    assert "72 of them are scope exclusions" in text and "a further 4 records stay in the target" in text
    assert "the book" not in text


# ---- the author's decision D2 (30 September 2026): unread records the filing-page audit confirms as first-year
# stubs are restated as stubs; the loader skips them and the partition classifies them by the audit's decision

STUB = "syndicate_1609_2021.json"


def _decision(name, eligibility="ineligible"):
    return {"file": name, "economic_eligibility": eligibility, "review_note": None,
            "mature_cohort_calculation": "no underwriting year u <= 2019; reviewed years are [2021]"}


def test_an_audited_first_year_stub_is_structural_with_its_audit_decision(tmp_path, monkeypatch):
    rows = _classify(tmp_path, monkeypatch, [(STUB, "SKIPPED")], structural={STUB: _decision(STUB)})
    row = rows[STUB]
    assert (row["category"], row["detail"], row["economic_eligibility"]) == (
        "structural_no_eligible_outcome", "no_mature_cohort", "ineligible")
    assert row["classification_evidence"] == _decision(STUB)["mature_cohort_calculation"]


def test_a_skipped_filing_without_an_audit_decision_is_refused(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match="lacks an independent source-page eligibility decision"):
        _classify(tmp_path, monkeypatch, [(STUB, "SKIPPED")])


def test_a_skipped_filing_the_audit_found_eligible_is_refused(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match="eligible audited filing is still SKIPPED"):
        _classify(tmp_path, monkeypatch, [(STUB, "SKIPPED")], structural={STUB: _decision(STUB, "eligible")})


@pytest.mark.parametrize("ledger_rows, eligibility, shown", [
    ([(STUB, "EXCLUDED")], "ineligible", "EXCLUDED"),
    ([(STUB, "EXCLUDED")], "unresolved", "EXCLUDED"),
    ([("syndicate_1686_2014.json", "EXCLUDED")], "ineligible", "no ledger row"),
], ids=["still unread", "unresolved and still unread", "no such filing"])
def test_an_audit_decision_the_loader_did_not_skip_is_refused(tmp_path, monkeypatch, ledger_rows, eligibility,
                                                              shown):
    """An audit decision whose restatement did not reach the record leaves the loader reading it as unread: the
    partition would count it unresolved beside the audit's own decision."""
    unread = {name: {"status": "no_deterministic_reading"} for name, _d in ledger_rows}
    with pytest.raises(AssertionError, match=r"decides filings the loader did not skip.*%s" % shown):
        _classify(tmp_path, monkeypatch, ledger_rows, unread, structural={STUB: _decision(STUB, eligibility)})


def test_the_audit_is_one_decision_per_reviewed_filing(tmp_path, monkeypatch):
    path = tmp_path / "structural_eligibility_audit.json"
    records = [_decision(STUB), _decision("syndicate_1686_2014.json")]
    path.write_text(json.dumps({"counts": {"reviewed": 2}, "records": records}), encoding="utf-8")
    monkeypatch.setattr(MC, "STRUCTURAL_AUDIT", path)
    assert sorted(MC._structural_decisions()) == ["syndicate_1609_2021.json", "syndicate_1686_2014.json"]
    path.write_text(json.dumps({"counts": {"reviewed": 3}, "records": records}), encoding="utf-8")
    with pytest.raises(ValueError, match="one decision per reviewed filing"):
        MC._structural_decisions()


# ---- the decision of 1 October 2026: rule M01 holds whatever the figure's route; a filing it skips is structural
# with its entry in data/no_mature_cohort_records.json, and every entry is a filing the loader so skipped

YOUNG = "syndicate_3902_2018.json"
YOUNG_RECORD = {"models": {"gpt-5-mini": {"_claims_triangle": {"underwriting_years": [2018, 2017]}}}}
YOUNG_ENTRY = {"syndicate": 3902, "year": 2018, "triangle_years": [2017, 2018], "mature_cutoff": 2016,
               "start_statements": [{"page": 6, "page_printed": "4",
                                     "quote": "The Syndicate began underwriting on the 2017 YOA, replacing the "
                                              "Incidental Syndicate that previously operated within Syndicate 4020."}]}


def _m01(tmp_path, monkeypatch, entries, ledger_rows=None):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "no_mature_cohort_records.json").write_text(
        json.dumps(dict({"_purpose": "test"}, **entries)), encoding="utf-8")
    return _classify(tmp_path, monkeypatch, ledger_rows or [(YOUNG, "SKIPPED", MC.NO_MATURE_COHORT_REASON)],
                     {YOUNG: YOUNG_RECORD})


def test_a_filing_skipped_under_m01_is_structural_with_its_entry(tmp_path, monkeypatch):
    row = _m01(tmp_path, monkeypatch, {"3902_2018": YOUNG_ENTRY})[YOUNG]
    assert (row["category"], row["detail"], row["economic_eligibility"]) == (
        "structural_no_eligible_outcome", "no_mature_cohort", "ineligible")
    assert row["extraction_status"] == "parsed_then_loader_rule_m01"
    assert row["classification_evidence"] == (
        "no underwriting year up to 2016: the record's triangles hold 2017, 2018; the filing (page 6): \"The "
        "Syndicate began underwriting on the 2017 YOA, replacing the Incidental Syndicate that previously operated "
        "within Syndicate 4020.\"")


def test_a_filing_skipped_under_m01_without_an_entry_is_refused(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match="skipped under M01 has no entry"):
        _m01(tmp_path, monkeypatch, {})


def test_an_entry_whose_triangle_years_are_not_the_records_is_refused(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match=r"triangle years \[2017, 2018\] are not the register's \[2016, 2017\]"):
        _m01(tmp_path, monkeypatch, {"3902_2018": dict(YOUNG_ENTRY, triangle_years=[2016, 2017])})


def test_an_entry_for_a_filing_the_loader_did_not_skip_under_m01_is_refused(tmp_path, monkeypatch):
    """A stale entry would cite evidence for a decision the run did not make: here the loader kept the filing."""
    with pytest.raises(AssertionError, match="did not skip under M01: syndicate_3902_2018.json"):
        _m01(tmp_path, monkeypatch, {"3902_2018": YOUNG_ENTRY}, [(YOUNG, "NO_RESERVES", BELOW_FLOOR)])


def test_the_recorded_result_carries_both_blocks(inputs):
    """DEFERRED-TO-REFIT: results/missingness_check_results.json is rewritten by the recorded pass."""
    rows, ledger, flow = inputs
    rec = json.load(io.open(os.path.join(HERE, "results", "missingness_check_results.json"), encoding="utf-8"))
    assert rec["basis_exclusions_reconciliation"] == MC.basis_exclusions_reconciliation(rows, ledger, flow)
    assert rec["assumed_business_regime"] == MC.regime_composition(rows)
