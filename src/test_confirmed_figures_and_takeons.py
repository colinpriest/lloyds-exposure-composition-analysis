r"""Figures two readings of the filing confirmed, and take-ons that are not development (PLAN R213).

The extraction error-rate study read each sampled filing twice. Two kinds of confirmed error
need a repair the pipeline cannot make for itself.

A wrong figure whose correct value no extraction route produces. 4444/2022 adopted +435.491m
from a stored grid misaligned by one column: it counts the 2021 year's first development and
drops 2013. The printed gross triangle gives +34.9m. The loader adopts the figure the two
readings confirmed (data/pyd_confirmed_figures.json), for the registered records only, says so
in the record's notes and route, and keeps the record in the sample.

A figure that is not development at all. 2008/2021's +383.9m is the whole 2021 gross claims
charge, the first-year recognition of the reserves the Hiscox loss portfolio transfer brought
in. The record stays in the corpus and leaves the working sample, the way a net-basis record
does (data/takeon_not_development.json), and the reconciliation gives it a step of its own.

Both registers refuse an entry that does not carry its evidence: two readings, the pages and a
quote. An entry marked "_to_complete" is skipped until it does, so the committed-register test
checks the evidence of the complete entries only.

A confirmed figure the extraction itself produces is repaired there, not here. 2010/2019's
deterministic triangle gives the confirmed -18.659m, which the sign veto refused because both
models read a transposed note line (+132.679m); the extraction's own register of confirmed
triangle figures lifts the veto for it (R213), and its record carries the figure. The loader
tests below still use 2010/2019 as the loader read it before that repair, because it is the one
confirmed error whose sign and currency both differ from the record's.

Run:  python -m pytest src/test_confirmed_figures_and_takeons.py -q
"""
import ast
import csv
import io
import json
import os
import re
import shutil
import sys
from collections import Counter

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, HERE)
import run_analysis as ra  # noqa: E402
import build_current_results as bcr  # noqa: E402
import generate_data_audit as gda  # noqa: E402

TAKEON = "TAKEON_NOT_DEVELOPMENT"
TAKEON_REASON = "take-on, not development (data/takeon_not_development.json)"

EVIDENCE = {"pages": [22, 23], "quote": "total +34,900 (GBP000)",
            "readings": ["first reading: error", "second reading: error"], "source": "test"}
CONFIRMED_ENTRY = dict(EVIDENCE, figure_m=34.9, figure_kind="triangle", basis="gross")
TAKEON_ENTRY = dict(EVIDENCE, takeon_amount_m=384.7)
DROP = object()

#: each way an entry can lack the evidence the study recorded
EVIDENCE_GAPS = {
    "no readings key": {"readings": DROP},
    "no readings": {"readings": []},
    "one reading": {"readings": ["first reading: error"]},
    "a blank second reading": {"readings": ["first reading: error", "  "]},
    "no pages key": {"pages": DROP},
    "no pages": {"pages": []},
    "pages that are not page numbers": {"pages": ["p22"]},
    "no quote key": {"quote": DROP},
    "a blank quote": {"quote": "   "},
}


def _entry(base, change):
    out = dict(base)
    for k, v in change.items():
        if v is DROP:
            out.pop(k, None)
        else:
            out[k] = v
    return out


def _register(tmp_path, reg, name="register.json"):
    p = tmp_path / name
    p.write_text(json.dumps(reg), encoding="utf-8")
    return p


# --- the registers refuse an entry without its evidence ----------------------------------

@pytest.mark.parametrize("gap", sorted(EVIDENCE_GAPS))
def test_the_confirmed_figure_register_refuses_an_entry_without_its_evidence(tmp_path, gap):
    reg = {"_purpose": "test", "9999_2020": _entry(CONFIRMED_ENTRY, EVIDENCE_GAPS[gap])}
    with pytest.raises(ValueError, match="9999_2020"):
        ra.load_pyd_confirmed_figures(_register(tmp_path, reg))


@pytest.mark.parametrize("gap", sorted(EVIDENCE_GAPS))
def test_the_takeon_register_refuses_an_entry_without_its_evidence(tmp_path, gap):
    reg = {"_purpose": "test", "9999_2021": _entry(TAKEON_ENTRY, EVIDENCE_GAPS[gap])}
    with pytest.raises(ValueError, match="9999_2021"):
        ra.load_takeon_register(_register(tmp_path, reg))


@pytest.mark.parametrize("change", [{"figure_kind": "Triangle"}, {"basis": "Gross"},
                                    {"figure_m": "34.9"}, {"figure_m": None}, {"figure_m": DROP}],
                         ids=["kind", "basis", "figure-text", "figure-null", "figure-missing"])
def test_the_confirmed_figure_register_refuses_a_figure_the_loader_cannot_read(tmp_path, change):
    """pyd_cohort_scope and pyd_basis act on figure_kind and basis as written: a "Triangle"
    would read as a stated figure and a "Gross" as an unknown basis, and nothing would say so."""
    reg = {"9999_2020": _entry(CONFIRMED_ENTRY, change)}
    with pytest.raises(ValueError, match="9999_2020"):
        ra.load_pyd_confirmed_figures(_register(tmp_path, reg))


def test_the_takeon_register_refuses_an_amount_it_cannot_read(tmp_path):
    reg = {"9999_2021": _entry(TAKEON_ENTRY, {"takeon_amount_m": "384.7"})}
    with pytest.raises(ValueError, match="9999_2021"):
        ra.load_takeon_register(_register(tmp_path, reg))


def test_the_registers_skip_their_notes_and_the_entries_still_to_complete(tmp_path):
    pending = {"_to_complete": True, "figure_m": -18.659, "figure_kind": "stated", "basis": "gross",
               "pages": [], "quote": "", "readings": []}
    reg = {"_purpose": "test", "9999_2019": pending, "9999_2020": CONFIRMED_ENTRY}
    assert set(ra.load_pyd_confirmed_figures(_register(tmp_path, reg, "c.json"))) == {"9999_2020"}
    reg = {"_purpose": "test", "9999_2021": TAKEON_ENTRY,
           "9999_2019": {"_to_complete": True, "takeon_amount_m": 1.0, "pages": [], "quote": "",
                         "readings": []}}
    assert set(ra.load_takeon_register(_register(tmp_path, reg, "t.json"))) == {"9999_2021"}


# --- the confirmed figure replaces the adopted one, on a copy ------------------------------

def _canonical(key):
    """The model block the loader adopts for a record (load_and_classify's resolution)."""
    d = json.load(io.open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key),
                          encoding="utf-8"))
    models = d["models"]
    if (d.get("validation") or {}).get("passed") is True:
        return models[sorted(models)[0]]
    cands = [(mk, m.get("prior_year_movement_confidence", 0) or 0)
             for mk, m in sorted(models.items()) if m.get("prior_year_development_pct") is not None]
    return models[max(cands, key=lambda x: x[1])[0]]


def test_the_recorded_percentage_is_a_percent_of_opening_reserves():
    """The unit apply_confirmed_figure writes in: 4444/2022 records 21.99 for +435.491m on
    1,980.61m of opening reserves, a percent and not a fraction."""
    cm = _canonical("4444_2022")
    assert cm["prior_year_development_pct"] == pytest.approx(
        100.0 * cm["prior_year_development_gbp_m"] / cm["opening_reserves_gbp_m"], abs=0.01)


BLOCK = {"syndicate": 4444, "year": 2022, "prior_year_development_gbp_m": 435.491,
         "prior_year_development_pct": 21.99, "opening_reserves_gbp_m": 1980.61,
         "direction": "strengthening",
         "data_quality_notes": ("[CODE OVERRIDE: Model said PYD=1947.812, but code computed 435.491 "
                                "from triangle (OVERRIDE from gemini-2.5-flash triangle). Using code value.]"),
         "_claims_triangle": {"type": "gross", "cells": [[1.0, 2.0]]},
         "gross_premium_mix": [{"line_of_business": "Property", "amount_gbp_m": 100.0}]}
NOTE_4444 = ("[PYD CONFIRMED BY TWO READINGS OF THE FILING: +34.9m replaces +435.491m, "
             "register data/pyd_confirmed_figures.json]")


def test_apply_confirmed_figure_writes_the_figure_percent_route_and_note_on_a_copy():
    cm = json.loads(json.dumps(BLOCK))
    before = json.dumps(cm, sort_keys=True)
    out = ra.apply_confirmed_figure(cm, CONFIRMED_ENTRY)
    assert out["prior_year_development_gbp_m"] == 34.9
    assert out["prior_year_development_pct"] == pytest.approx(100.0 * 34.9 / 1980.61)
    assert out["_pyd_route"] == {"source": "confirmed_figure", "value": 34.9, "figure_kind": "triangle",
                                 "basis": "gross", "register": "data/pyd_confirmed_figures.json"}
    assert out["data_quality_notes"].startswith(BLOCK["data_quality_notes"])
    assert out["data_quality_notes"].endswith(NOTE_4444)
    assert out["direction"] == "strengthening"
    # the original is untouched, nested objects included: the loader's FX conversion rewrites
    # the adopted block's *_gbp_m fields in place, and it must rewrite the copy only
    assert json.dumps(cm, sort_keys=True) == before
    out["gross_premium_mix"][0]["amount_gbp_m"] = 1.0
    assert cm["gross_premium_mix"][0]["amount_gbp_m"] == 100.0


def test_a_confirmed_figure_of_the_other_sign_carries_its_own_direction():
    """2010/2019: the models read +132.679m, strengthening; the figure to confirm is -18.659m.
    Left as it was, the direction would make the loader's sign correction turn -18.659m back
    into +18.659m."""
    cm = dict(BLOCK, prior_year_development_gbp_m=132.679, prior_year_development_pct=27.34,
              opening_reserves_gbp_m=485.327, data_quality_notes="")
    out = ra.apply_confirmed_figure(cm, dict(CONFIRMED_ENTRY, figure_m=-18.659, figure_kind="stated"))
    assert out["prior_year_development_pct"] == pytest.approx(100.0 * -18.659 / 485.327)
    assert out["direction"] == "release" and cm["direction"] == "strengthening"
    assert ("[PYD CONFIRMED BY TWO READINGS OF THE FILING: -18.659m replaces +132.679m, "
            "register data/pyd_confirmed_figures.json]") in out["data_quality_notes"]
    assert "release replaces strengthening" in out["data_quality_notes"]


def test_a_confirmed_figure_on_no_reserves_carries_no_percentage():
    out = ra.apply_confirmed_figure(dict(BLOCK, opening_reserves_gbp_m=None), CONFIRMED_ENTRY)
    assert out["prior_year_development_pct"] is None


# --- the route decides the basis and the cohort scope --------------------------------------

def test_a_confirmed_route_carries_the_basis_its_readings_recorded():
    """The confirmed figure is read before every other step: here a net claims triangle, a
    register entry calling the record net and a stale override annotation all say otherwise."""
    cm = ra.apply_confirmed_figure(dict(BLOCK, _claims_triangle={"type": "net"}), CONFIRMED_ENTRY)
    register = {"4444_2022": {"basis": "net", "source": "test"}}
    assert ra.pyd_basis(cm, "4444_2022", register, {"m": cm}) == ("gross", "confirmed-figure:register", "")
    net = ra.apply_confirmed_figure(dict(BLOCK), dict(CONFIRMED_ENTRY, basis="net"))
    assert ra.pyd_basis(net, "4444_2022", {}) == ("net", "confirmed-figure:register", "")


def test_a_confirmed_triangle_figure_enforces_the_cohort_cutoff():
    """No override annotation to read: without the route the figure would be disclosed."""
    cm = ra.apply_confirmed_figure(dict(BLOCK, data_quality_notes=""), CONFIRMED_ENTRY)
    assert ra.pyd_cohort_scope(cm) == (ra.COHORT_ENFORCED, "triangle")


def test_a_confirmed_stated_figure_is_disclosed_whatever_the_annotation_says():
    """An override annotation computing the same figure would otherwise read as a triangle's."""
    notes = ("[CODE OVERRIDE: Model said PYD=1947.812, but code computed 34.9 from triangle "
             "(OVERRIDE from gemini-2.5-flash triangle). Using code value.]")
    cm = ra.apply_confirmed_figure(dict(BLOCK, data_quality_notes=notes),
                                   dict(CONFIRMED_ENTRY, figure_kind="stated"))
    assert ra.pyd_cohort_scope(cm) == (ra.COHORT_DISCLOSED, "disclosed")


# --- the take-on step: eligibility, ledger and reconciliation table -------------------------

def _parsed(tag, basis="gross", pct=1.0, opening=10.0, lob=True, eligible=False):
    return {"data_quality_tag": tag, "pyd_basis": basis, "pyd_pct": pct,
            "opening_reserves_gbp_m": opening, "lob_severity_computed": lob,
            "eligible_for_capital": eligible}


def test_a_takeon_is_not_eligible_for_capital():
    base = {"pyd_pct": 1.0, "opening_reserves_gbp_m": 10.0, "lob_severity_computed": True,
            "pyd_basis": "gross", "weight_source": "premium_mix"}
    kept, takeon = dict(base, data_quality_tag="RELIABLE"), dict(base, data_quality_tag=TAKEON)
    counts = ra.compute_eligibility([kept, takeon], {"DENSE": [kept, takeon], "FULL": [kept, takeon]})
    assert kept["eligible_for_capital"] is True
    assert takeon["eligible_for_capital"] is False
    assert counts["eligible_for_capital"] == 1


def test_the_ledger_places_a_takeon_in_its_own_step_and_the_totals_close(tmp_path):
    log = [
        {"file": "a.json", "status": "EXCLUDED", "no_models": True},
        {"file": "f.json", "status": "RELIABLE"},
        {"file": "g.json", "status": "NET_BASIS", "basis_source": "register"},
        {"file": "t.json", "status": TAKEON, "reason": TAKEON_REASON},
        {"file": "h.json", "status": "INCOMPLETE"},
        {"file": "w.json", "status": "RELIABLE"},
    ]
    records = [
        _parsed("RELIABLE", eligible=True),
        _parsed("NET_BASIS", basis="net"),
        # gross, with a percentage, reserves and weights: only the take-on step can hold it
        _parsed(TAKEON),
        _parsed("INCOMPLETE", pct=None, lob=False),
        _parsed("RELIABLE", lob=False),
    ]
    out = tmp_path / "ledger.csv"
    fl = ra.build_disposition_ledger(log, records, str(out))
    ws = fl["to_working_sample"]
    assert list(ws) == ["net_or_unstated_basis", "takeon_not_development", "unusable_severity",
                        "missing_opening_reserves", "missing_lob_weights"]
    assert ws == {"net_or_unstated_basis": 1, "takeon_not_development": 1, "unusable_severity": 1,
                  "missing_opening_reserves": 0, "missing_lob_weights": 1}
    assert fl["corpus"] == fl["corpus_records_parsed"] == len(records)
    assert fl["corpus"] - sum(ws.values()) == fl["working_sample"] == 1
    assert fl["working_sample_equals_eligible_for_capital"] is True
    rows = {r["file"]: r for r in csv.DictReader(io.open(str(out), encoding="utf-8"))}
    assert rows["t.json"]["disposition"] == "CORPUS:" + TAKEON
    assert rows["t.json"]["reason"] == TAKEON_REASON


NEW_NOTE = ("Syndicate-years in the RITC regime (an accepted RITC or a confirmed inward transfer) are "
            "retained and modelled as a separate tail regime, not excluded; a record whose filing shows "
            "its adopted figure to be the take-on itself is not development and leaves the working sample.")


def test_table39_prints_the_takeon_step_and_its_running_totals_close(monkeypatch):
    written = {}
    monkeypatch.setattr(ra, "_write_tex", lambda fname, content: written.__setitem__(fname, content))
    flow = {"files_retrieved": 20,
            "pre_corpus": {"excluded": 2, "skipped": 3, "incomplete_no_development_record": 1,
                           "in_runoff": 1, "no_reserves": 1},
            "corpus": 12, "corpus_records_parsed": 12,
            "to_working_sample": {"net_or_unstated_basis": 2, "takeon_not_development": 1,
                                  "unusable_severity": 1, "missing_opening_reserves": 0,
                                  "missing_lob_weights": 2},
            "working_sample": 6, "working_sample_equals_eligible_for_capital": True,
            "files_without_dual_model_record_overlapping_audit_count": 4,
            "ledger_csv": "results/disposition_ledger.csv"}
    ra._gen_table39({"disposition_flow": flow})
    tex = written["table39_reconciliation.tex"]
    rows = ["\\quad less: development on a net or unstated basis & $-2$ & 10 \\\\",
            "\\quad less: take-on, not development & $-1$ & 9 \\\\",
            "\\quad less: unusable severity & $-1$ & 8 \\\\",
            "\\quad less: missing opening reserves & $-0$ & 8 \\\\",
            "\\quad less: missing line-of-business weights & $-2$ & 6 \\\\"]
    at = [tex.index(r) for r in rows]
    assert at == sorted(at)
    assert "\\textbf{Working sample} & -- & \\textbf{6}" in tex
    assert NEW_NOTE in tex
    assert "RITC-flagged syndicate-years are retained" not in tex


# --- the loader, on the real records ---------------------------------------------------------

RECORDS = ("4444_2022", "2010_2019", "2008_2021", "457_2016")
TEST_CONFIRMED = {
    "_purpose": "test",
    "4444_2022": dict(EVIDENCE, figure_m=34.9, figure_kind="triangle", basis="gross"),
    # stand-in evidence: 2010/2019 is repaired in the extraction (R213), not in this register
    "2010_2019": dict(EVIDENCE, figure_m=-18.659, figure_kind="stated", basis="gross", pages=[1]),
}
TEST_TAKEONS = {"_purpose": "test", "2008_2021": dict(TAKEON_ENTRY, pages=[54, 44, 6, 7])}
# the figure, percentage, direction and route of 2010/2019's model blocks as the loader read them before the
# extraction's R213 repair (extraction commit 40eb31aa): both models +132.679m, strengthening, no route
BEFORE_REPAIR = {"2010_2019": {"prior_year_development_gbp_m": 132.679, "prior_year_development_pct": 27.34,
                               "direction": "strengthening", "_pyd_route": None}}


def _copy_record(key, d):
    src = os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key)
    if key not in BEFORE_REPAIR:
        shutil.copy(src, str(d))
        return
    rec = json.load(io.open(src, encoding="utf-8"))
    for block in rec["models"].values():
        for field, value in BEFORE_REPAIR[key].items():
            if value is None:
                block.pop(field, None)
            else:
                block[field] = value
    (d / ("syndicate_%s.json" % key)).write_text(json.dumps(rec), encoding="utf-8")


def _load(factory, confirmed, takeons):
    d = factory.mktemp("records")
    for key in RECORDS:
        _copy_record(key, d)
    reg = factory.mktemp("registers")
    cpath, tpath, opath = reg / "confirmed.json", reg / "takeons.json", reg / "openings.json"
    cpath.write_text(json.dumps(confirmed), encoding="utf-8")
    tpath.write_text(json.dumps(takeons), encoding="utf-8")
    # the opening-reserves registers are not what these tests measure: empty in both the repaired and the control run
    opath.write_text(json.dumps({"_purpose": "empty"}), encoding="utf-8")
    bpath = reg / "takeon_base.json"
    bpath.write_text(json.dumps({"_purpose": "empty"}), encoding="utf-8")
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(ra, "DATA_DIR", d)
        mp.setattr(ra, "PYD_CONFIRMED_FIGURES", cpath)
        mp.setattr(ra, "TAKEON_REGISTER", tpath)
        mp.setattr(ra, "OPENING_RESERVES_CONFIRMED", opath)
        mp.setattr(ra, "TAKEON_BASE_REGISTER", bpath)
        records, counters, log, files = ra.load_and_classify()
    finally:
        mp.undo()
    assert len(files) == len(RECORDS)
    return {"by_key": {"%s_%s" % (r["syndicate"], r["year"]): r for r in records},
            "records": records, "counters": counters, "log": log}


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    return _load(tmp_path_factory, TEST_CONFIRMED, TEST_TAKEONS)


@pytest.fixture(scope="module")
def unrepaired(tmp_path_factory):
    """The same records with both registers empty: the control the repairs are measured against."""
    return _load(tmp_path_factory, {"_purpose": "empty"}, {"_purpose": "empty"})


def test_the_loader_adopts_the_confirmed_figure_for_the_registered_records_only(loaded, unrepaired):
    was, now = unrepaired["by_key"]["4444_2022"], loaded["by_key"]["4444_2022"]
    assert was["pyd_gbp_m"] == pytest.approx(435.491)
    assert now["pyd_gbp_m"] == pytest.approx(34.9)
    assert now["pyd_pct"] == pytest.approx(100.0 * 34.9 / 1980.61)
    assert now["s_raw_a"] == pytest.approx(34.9 / 1980.61)
    assert now["data_quality_tag"] == "RELIABLE"
    assert (now["pyd_basis"], now["pyd_basis_source"]) == ("gross", "confirmed-figure:register")
    assert (now["pyd_cohort_scope"], now["pyd_cohort_route"]) == (ra.COHORT_ENFORCED, "triangle")
    assert loaded["counters"]["confirmed_figures_applied"] == 2
    assert unrepaired["counters"]["confirmed_figures_applied"] == 0
    for key in ("2008_2021", "457_2016"):
        assert loaded["by_key"][key]["pyd_gbp_m"] == unrepaired["by_key"][key]["pyd_gbp_m"], key
        assert loaded["by_key"][key]["pyd_basis_source"] == unrepaired["by_key"][key]["pyd_basis_source"], key


def test_a_confirmed_figure_survives_the_sign_correction_and_the_fx_conversion(loaded, unrepaired):
    was, now = unrepaired["by_key"]["2010_2019"], loaded["by_key"]["2010_2019"]
    assert was["direction"] == "strengthening" and was["pyd_gbp_m"] > 0
    assert now["fx_applied"] is True
    assert now["pyd_gbp_m"] == pytest.approx(-18.659 / now["fx_rate_usd_per_gbp"])
    assert now["pyd_pct"] == pytest.approx(100.0 * -18.659 / 485.327)
    assert now["sign_flipped"] is False and now["direction"] == "release"
    assert now["s_raw_a"] == pytest.approx(-18.659 / 485.327)
    assert (now["pyd_cohort_scope"], now["pyd_cohort_route"]) == (ra.COHORT_DISCLOSED, "disclosed")


def test_a_takeon_stays_in_the_corpus_and_leaves_the_working_sample(loaded, unrepaired, tmp_path):
    was, now = unrepaired["by_key"]["2008_2021"], loaded["by_key"]["2008_2021"]
    _meta, subsets = ra.build_subsets(unrepaired["records"])
    ra.compute_eligibility(unrepaired["records"], subsets)
    assert was["data_quality_tag"] == "RELIABLE" and was["s_raw_a"] is not None
    assert was["eligible_for_capital"] is True
    assert now["data_quality_tag"] == TAKEON
    assert now["s_raw_a"] is None and now["s_raw_b"] is None
    assert now["pyd_gbp_m"] == pytest.approx(383.9)
    entries = [e for e in loaded["log"] if e["file"] == "syndicate_2008_2021.json"]
    assert entries == [{"file": "syndicate_2008_2021.json", "status": TAKEON, "reason": TAKEON_REASON}]
    assert loaded["counters"]["takeon_excluded"] == 1
    assert unrepaired["counters"]["takeon_excluded"] == 0
    _meta, subsets = ra.build_subsets(loaded["records"])
    ra.compute_eligibility(loaded["records"], subsets)
    assert now["eligible_for_capital"] is False
    flow = ra.build_disposition_ledger(loaded["log"], loaded["records"], str(tmp_path / "ledger.csv"))
    assert flow["to_working_sample"]["takeon_not_development"] == 1
    assert flow["corpus"] - sum(flow["to_working_sample"].values()) == flow["working_sample"]
    assert flow["working_sample_equals_eligible_for_capital"] is True


# --- the committed registers and the reported counters ---------------------------------------

def test_the_committed_registers_name_existing_records_and_carry_their_evidence():
    """Every key names a record the loader reads, and every complete entry carries its evidence
    (the loaders raise otherwise). An entry marked "_to_complete" is skipped, not applied: this
    test does not require the register to be complete."""
    raw = {}
    for path in (ra.PYD_CONFIRMED_FIGURES, ra.TAKEON_REGISTER):
        reg = json.load(io.open(str(path), encoding="utf-8"))
        keys = [k for k in reg if not k.startswith("_")]
        assert keys, str(path)
        for key in keys:
            assert os.path.exists(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key)), (
                str(path), key)
        raw[path.name] = keys, reg
    confirmed = ra.load_pyd_confirmed_figures()
    takeons = ra.load_takeon_register()
    ckeys, creg = raw[ra.PYD_CONFIRMED_FIGURES.name]
    pending = {k for k in ckeys if creg[k].get("_to_complete")}
    assert set(confirmed) == set(ckeys) - pending
    assert confirmed["4444_2022"]["figure_m"] == 34.9
    assert confirmed["2008_2019"]["figure_m"] == 14.053
    assert "2008_2021" in takeons
    assert not set(ckeys) & set(raw[ra.TAKEON_REGISTER.name][0]), (
        "a record cannot be both corrected and excluded as a take-on")
    # a figure the extraction repairs through its own register is not corrected a second time here
    upstream = json.load(io.open(os.path.join(HERE, "pdf_extraction", "audit",
                                              "triangle_figures_confirmed_by_hand.json"), encoding="utf-8"))
    repaired_upstream = {r["stem"].replace("syndicate_", "") for r in upstream["records"]}
    assert {"3624_2015", "1225_2022", "2010_2019"} <= repaired_upstream
    assert not set(ckeys) & repaired_upstream, sorted(set(ckeys) & repaired_upstream)


def test_the_results_report_both_counters_beside_the_basis_exclusions():
    """Wherever run_analysis.py reports net_basis_excluded (the loader's counters and the
    results' meta block), it reports the confirmed figures applied and the take-ons excluded."""
    tree = ast.parse(io.open(os.path.join(HERE, "src", "run_analysis.py"), encoding="utf-8").read())
    blocks = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
            if "net_basis_excluded" in keys:
                blocks.append(keys)
    assert len(blocks) >= 2
    for keys in blocks:
        assert {"confirmed_figures_applied", "takeon_excluded", "confirmed_openings_applied", "takeon_base_applied"} <= keys, sorted(keys)


def test_the_data_audit_appendix_is_regenerated_by_the_manifest():
    """The committed appendix quotes a beta_RITC mean the refit calibration no longer holds
    (test_model_semantics), because no manifest step regenerated it. It reads the loader's
    output and the published calibration, so it runs after build_current_results.py."""
    import reproduce
    order = [sc for sc, _stage, _minutes in reproduce.STEPS]
    assert order.index("generate_data_audit.py") > order.index("build_current_results.py")
    assert reproduce.OUTPUTS["generate_data_audit.py"] == ("docs/appendix-data-audit.md",)


# --- the generated public documents print the step ------------------------------------------

WATERFALL_TOWS = {"net_or_unstated_basis": 2, "takeon_not_development": 1, "unusable_severity": 1,
                  "missing_opening_reserves": 0, "missing_lob_weights": 2}
EQUATION = re.compile(
    r"(\d+) - (\d+) net or unstated basis \([^)]*\)(?: - (\d+) take-on, not development \([^)]*\))?"
    r" - (\d+) unusable severity - (\d+) missing opening reserves - (\d+) without premium weights = (\d+)")


def _exposure(tows, takeons_logged=None):
    corpus = 12
    byr = {"NET_BASIS": {"2020": 1}, "UNKNOWN_BASIS": {"2021": 1}}
    if "takeon_not_development" in tows:
        byr[TAKEON] = {"2021": tows["takeon_not_development"] if takeons_logged is None else takeons_logged}
    return {"disposition_flow": {
                "files_retrieved": 20,
                "pre_corpus": {"excluded": 2, "skipped": 3, "incomplete_no_development_record": 1,
                               "in_runoff": 1, "no_reserves": 1},
                "corpus": corpus, "to_working_sample": dict(tows),
                "working_sample": corpus - sum(tows.values()),
                "files_without_dual_model_record_overlapping_audit_count": 4},
            "classification_summary": {"by_reason_year": byr},
            "dual_model_stats": {"single_model_files": 4}}


def _printed_equation(lines):
    start = lines.index("  from the corpus to the working sample, also disjoint:")
    text = " ".join(" ".join(lines[start + 1:]).split())
    m = EQUATION.search(text)
    assert m, text
    return m.groups()


def test_the_provenance_waterfall_prints_the_takeon_step_and_adds_up():
    corpus, net, takeon, sev, res, wt, ws = _printed_equation(bcr.waterfall_lines(_exposure(WATERFALL_TOWS)))
    assert takeon == "1"
    assert int(corpus) - sum(int(x) for x in (net, takeon, sev, res, wt)) == int(ws) == 6


def test_a_flow_from_before_the_takeon_step_prints_as_it_did():
    tows = {k: v for k, v in WATERFALL_TOWS.items() if k != "takeon_not_development"}
    lines = bcr.waterfall_lines(_exposure(tows))
    corpus, net, takeon, sev, res, wt, ws = _printed_equation(lines)
    assert takeon is None and not any("take-on" in line for line in lines)
    assert int(corpus) - sum(int(x) for x in (net, sev, res, wt)) == int(ws)


def test_the_provenance_waterfall_refuses_a_step_it_cannot_print_or_a_count_it_cannot_confirm():
    """The flow's own sum passes in both cases; the printed equation would not add up."""
    with pytest.raises(SystemExit):
        bcr.waterfall_lines(_exposure(dict(WATERFALL_TOWS, a_later_step=1)))
    with pytest.raises(SystemExit):
        bcr.waterfall_lines(_exposure(WATERFALL_TOWS, takeons_logged=2))


def _audit_counts(tmp_path, monkeypatch):
    def obs(syn, tag, s=0.1, hhi=0.5, opening=10.0):
        return {"syndicate": syn, "year": 2021, "data_quality_tag": tag, "s_raw_a": s, "hhi": hhi,
                "opening_reserves_gbp_m": opening}
    ex = {"meta": {"discarded": {"reasons": {"excluded": 1, "skipped": 0,
                                             "incomplete_no_development_record": 0, "in_runoff": 0,
                                             "no_reserves": 0}},
                   "yearly_observations": {"2021": 5}, "total_files": 6, "unique_syndicates": 5},
          "observations": [obs(1, "RELIABLE"), obs(2, "NET_BASIS", s=None), obs(3, TAKEON, s=None),
                           obs(4, "INCOMPLETE", s=None, hhi=None), obs(5, "RELIABLE", hhi=None)],
          "data_quality": {"mix_unreconciled": 0},
          "analysis_config": {"lob_weight_floor": 0.01, "lob_severity_cap": 5.0}}
    p = tmp_path / "exposure_results.json"
    p.write_text(json.dumps(ex), encoding="utf-8")
    monkeypatch.setattr(gda, "RESULTS", p)
    return gda.compute()


def test_the_data_audit_waterfall_gives_a_takeon_its_own_stage(tmp_path, monkeypatch):
    """Without its own stage a take-on, which carries no severity, would be counted as an
    unusable severity: the totals would still close and the label would be wrong."""
    c = _audit_counts(tmp_path, monkeypatch)
    assert (c["basis"], c["takeon"], c["sev"], c["res"], c["wt"], c["sample"]) == (1, 1, 1, 0, 1, 1)
    assert c["corpus"] - c["excl"] == c["sample"]


def test_the_data_audit_prints_the_takeon_stage(tmp_path, monkeypatch):
    c = _audit_counts(tmp_path, monkeypatch)
    r = {"has_g": 5, "cap": Counter({"gross claims": 5}), "gross": 5, "net": 0, "tri": 5, "gpm": 5,
         "labels": Counter({"Property": 3, "Miscellaneous": 2}), "neither": 1,
         "raw_year": Counter({2021: 6}), "empty_year": Counter({2021: 1}), "ritc": 0, "ritc_sy": set()}
    text = gda.md(c, r)
    assert "| — Take-on, not development (`data/takeon_not_development.json`) | | 1 |" in text
    assert "| **Working sample** | **1** | 4 excluded |" in text
