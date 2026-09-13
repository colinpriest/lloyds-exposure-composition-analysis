r"""Opening reserves two readings of the filing confirmed, and a basis two readings established without a figure
(PLAN R213; error-rate protocol, eighth amendment).

Two confirmed errors of the study's third sample need a repair the existing registers cannot make.

Opening reserves read from the wrong line. 2003/2018 adopted 1,659.705m, the reinsurers' share of claims outstanding
at 1 January 2018; the filing's gross claims outstanding is 5,344.064m (p44). Severity is development over opening
reserves, so the record's severity was about 3.2 times too large. The loader adopts the confirmed opening reserves
(data/opening_reserves_confirmed.json) for the registered records only, before the FX conversion, recomputes the
percentage on them, says so in the record's notes, and leaves the development figure and its route as they were.

A figure that is not a gross amount, with nothing to replace it. 623/2014's -17.3 is a sum of loss-ratio points that a
model stored as millions; 1880/2014's -13.6m is the recomputation of a table the filing heads "after reinsurance
recoveries". A confirmed-figure entry may carry the basis the readings established without a figure (623/2014: unknown)
or with the net figure (1880/2014: net). The loader keeps the adopted figure, takes the basis from the entry, and the
record is recorded and excluded like any net or unknown-basis record. A gross basis without a figure is refused: it
would change nothing and claim a confirmation.

Run:  python -m pytest src/test_confirmed_openings_and_bases.py -q
"""
import io
import json
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, HERE)
import run_analysis as ra  # noqa: E402

EVIDENCE = {"pages": [44], "quote": "Gross Technical Provisions As at 1 January 2018 1,545,443 5,344,064",
            "readings": ["first reading: the adopted opening is the reinsurers' share", "second reading: the same"],
            "source": "test"}
OPENING_ENTRY = dict(EVIDENCE, opening_reserves_m=5344.064)
UNKNOWN_BASIS_ENTRY = dict(EVIDENCE, figure_m=None, figure_kind=None, basis="unknown")
NET_ENTRY = dict(EVIDENCE, figure_m=-13.6, figure_kind="triangle", basis="net")
DROP = object()
EVIDENCE_GAPS = {
    "no readings key": {"readings": DROP},
    "one reading": {"readings": ["first reading"]},
    "no pages": {"pages": []},
    "pages that are not page numbers": {"pages": ["p44"]},
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


# --- the opening-reserves register ------------------------------------------------------------

@pytest.mark.parametrize("gap", sorted(EVIDENCE_GAPS))
def test_the_opening_register_refuses_an_entry_without_its_evidence(tmp_path, gap):
    reg = {"_purpose": "test", "9999_2018": _entry(OPENING_ENTRY, EVIDENCE_GAPS[gap])}
    with pytest.raises(ValueError, match="9999_2018"):
        ra.load_opening_reserves_confirmed(_register(tmp_path, reg))


@pytest.mark.parametrize("change", [{"opening_reserves_m": "5344.064"}, {"opening_reserves_m": None},
                                    {"opening_reserves_m": DROP}, {"opening_reserves_m": 0},
                                    {"opening_reserves_m": -1.0}],
                         ids=["text", "null", "missing", "zero", "negative"])
def test_the_opening_register_refuses_reserves_the_loader_cannot_use(tmp_path, change):
    reg = {"9999_2018": _entry(OPENING_ENTRY, change)}
    with pytest.raises(ValueError, match="9999_2018"):
        ra.load_opening_reserves_confirmed(_register(tmp_path, reg))


def test_the_opening_register_skips_its_notes_and_the_entries_still_to_complete(tmp_path):
    reg = {"_purpose": "test", "9999_2018": OPENING_ENTRY,
           "9999_2019": {"_to_complete": True, "opening_reserves_m": 1.0, "pages": [], "quote": "", "readings": []}}
    assert set(ra.load_opening_reserves_confirmed(_register(tmp_path, reg))) == {"9999_2018"}


def test_apply_confirmed_opening_replaces_the_reserves_and_the_percentage_on_a_copy():
    cm = {"prior_year_development_gbp_m": 419.0, "prior_year_development_pct": 25.25,
          "opening_reserves_gbp_m": 1659.705, "data_quality_notes": "earlier notes",
          "_pyd_route": {"source": "rag_triangle", "value": 419.0}}
    out = ra.apply_confirmed_opening(cm, OPENING_ENTRY)
    assert out["opening_reserves_gbp_m"] == 5344.064
    assert out["prior_year_development_pct"] == pytest.approx(100.0 * 419.0 / 5344.064)
    assert out["prior_year_development_gbp_m"] == 419.0
    assert out["_pyd_route"] == {"source": "rag_triangle", "value": 419.0}
    assert out["data_quality_notes"].startswith("earlier notes ")
    assert ("[OPENING RESERVES CONFIRMED BY TWO READINGS OF THE FILING: 5,344.064m replaces 1,659.705m, "
            "register data/opening_reserves_confirmed.json]") in out["data_quality_notes"]
    assert cm["opening_reserves_gbp_m"] == 1659.705 and cm["prior_year_development_pct"] == 25.25


# --- a basis the readings established, with or without a figure ---------------------------------

def test_the_confirmed_figure_register_accepts_a_net_or_unknown_basis_without_a_figure(tmp_path):
    reg = {"9999_2014": UNKNOWN_BASIS_ENTRY, "9998_2014": dict(UNKNOWN_BASIS_ENTRY, basis="net"),
           "9997_2014": NET_ENTRY}
    assert set(ra.load_pyd_confirmed_figures(_register(tmp_path, reg))) == {"9999_2014", "9998_2014", "9997_2014"}


@pytest.mark.parametrize("change", [{"basis": "gross"}, {"figure_kind": "triangle"}, {"basis": DROP}],
                         ids=["gross-without-figure", "kind-without-figure", "no-basis"])
def test_the_confirmed_figure_register_refuses_an_entry_without_a_figure_that_changes_nothing(tmp_path, change):
    reg = {"9999_2014": _entry(UNKNOWN_BASIS_ENTRY, change)}
    with pytest.raises(ValueError, match="9999_2014"):
        ra.load_pyd_confirmed_figures(_register(tmp_path, reg))


def test_a_basis_without_a_figure_keeps_the_figure_and_sets_the_basis_on_a_copy():
    cm = {"prior_year_development_gbp_m": -17.3, "prior_year_development_pct": -2.33,
          "opening_reserves_gbp_m": 741.5, "direction": "release", "data_quality_notes": "earlier notes"}
    out = ra.apply_confirmed_figure(cm, UNKNOWN_BASIS_ENTRY)
    assert out["prior_year_development_gbp_m"] == -17.3 and out["prior_year_development_pct"] == -2.33
    assert out["direction"] == "release"
    assert out["_pyd_route"] == {"source": ra.CONFIRMED_FIGURE_SOURCE, "value": None, "figure_kind": None,
                                 "basis": "unknown", "register": "data/pyd_confirmed_figures.json"}
    assert ra.pyd_basis(out, "623_2014", {}, {}) == ("unknown", "confirmed-figure:register", "")
    assert ("[PYD BASIS ESTABLISHED BY TWO READINGS OF THE FILING: unknown, with no figure to adopt; -17.3m kept, "
            "register data/pyd_confirmed_figures.json]") in out["data_quality_notes"]
    assert "_pyd_route" not in cm


# --- the loader, on the real records ------------------------------------------------------------

RECORDS = ("2003_2018", "623_2014", "1880_2014", "457_2016")


def _load(factory, confirmed, openings):
    d = factory.mktemp("records")
    for key in RECORDS:
        shutil.copy(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), str(d))
    reg = factory.mktemp("registers")
    cpath, tpath, opath = reg / "confirmed.json", reg / "takeons.json", reg / "openings.json"
    cpath.write_text(json.dumps(confirmed), encoding="utf-8")
    tpath.write_text(json.dumps({"_purpose": "empty"}), encoding="utf-8")
    opath.write_text(json.dumps(openings), encoding="utf-8")
    mp = pytest.MonkeyPatch()
    try:
        # inside the try: a setattr that raises must not leave the registers patched for later tests
        mp.setattr(ra, "DATA_DIR", d)
        mp.setattr(ra, "PYD_CONFIRMED_FIGURES", cpath)
        mp.setattr(ra, "TAKEON_REGISTER", tpath)
        mp.setattr(ra, "OPENING_RESERVES_CONFIRMED", opath)
        records, counters, log, files = ra.load_and_classify()
    finally:
        mp.undo()
    assert len(files) == len(RECORDS)
    return {"by_key": {"%s_%s" % (r["syndicate"], r["year"]): r for r in records}, "counters": counters, "log": log}


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    return _load(tmp_path_factory, {"_purpose": "test", "623_2014": UNKNOWN_BASIS_ENTRY, "1880_2014": NET_ENTRY},
                 {"_purpose": "test", "2003_2018": OPENING_ENTRY})


@pytest.fixture(scope="module")
def unrepaired(tmp_path_factory):
    return _load(tmp_path_factory, {"_purpose": "empty"}, {"_purpose": "empty"})


def test_the_loader_adopts_the_confirmed_opening_reserves_for_the_registered_record_only(loaded, unrepaired):
    was, now = unrepaired["by_key"]["2003_2018"], loaded["by_key"]["2003_2018"]
    assert was["data_quality_tag"] == now["data_quality_tag"] == "RELIABLE"
    assert now["fx_applied"] is True
    rate = now["fx_rate_usd_per_gbp"]
    assert was["opening_reserves_gbp_m"] == pytest.approx(1659.705 / rate)
    assert now["opening_reserves_gbp_m"] == pytest.approx(5344.064 / rate)
    assert now["pyd_gbp_m"] == pytest.approx(was["pyd_gbp_m"])
    assert now["pyd_pct"] == pytest.approx(100.0 * 419.0 / 5344.064)
    assert now["s_raw_a"] == pytest.approx(419.0 / 5344.064)
    assert (now["pyd_basis"], now["pyd_basis_source"]) == (was["pyd_basis"], was["pyd_basis_source"])
    assert loaded["counters"]["confirmed_openings_applied"] == 1
    assert unrepaired["counters"]["confirmed_openings_applied"] == 0
    other_was, other_now = unrepaired["by_key"]["457_2016"], loaded["by_key"]["457_2016"]
    assert other_now["opening_reserves_gbp_m"] == other_was["opening_reserves_gbp_m"]
    assert other_now["pyd_gbp_m"] == other_was["pyd_gbp_m"]


@pytest.mark.parametrize("key, tag", [("623_2014", "UNKNOWN_BASIS"), ("1880_2014", "NET_BASIS")])
def test_a_basis_the_readings_established_records_and_excludes_the_record(loaded, unrepaired, key, tag):
    was, now = unrepaired["by_key"][key], loaded["by_key"][key]
    assert was["data_quality_tag"] == "RELIABLE"
    assert now["data_quality_tag"] == tag
    assert now["pyd_basis_source"] == "confirmed-figure:register"
    assert now["pyd_gbp_m"] == pytest.approx(was["pyd_gbp_m"])
    assert [e["status"] for e in loaded["log"] if e["file"] == "syndicate_%s.json" % key] == [tag]


def test_the_committed_opening_register_names_existing_records_and_carries_its_evidence():
    reg = json.load(io.open(str(ra.OPENING_RESERVES_CONFIRMED), encoding="utf-8"))
    keys = [k for k in reg if not k.startswith("_")]
    assert keys
    for key in keys:
        assert os.path.exists(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key)), key
    openings = ra.load_opening_reserves_confirmed()
    pending = {k for k in keys if reg[k].get("_to_complete")}
    assert set(openings) == set(keys) - pending
    assert openings["2003_2018"]["opening_reserves_m"] == 5344.064
