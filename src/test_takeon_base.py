r"""Opening reserves adjusted for a take-on the adopted development covers (PLAN R213; error-rate protocol, ninth
amendment).

Severity is the development figure over the opening reserves. The study's eighth census found records whose adopted
development covers business taken into the syndicate in the report year while their opening reserves, the gross claims
outstanding at 1 January before the transfer, do not. 1884/2021's triangle carries the 2018 years of Syndicates 1861
and 1955, taken on at 1 January 2021 (839.787m gross), on both diagonals of its step: its -20.1m is development on about
913m of reserves, and the loader divided it by 73.709m.

The loader adds the transferred amount (data/opening_reserves_takeon_base.json) to the opening reserves of the
registered records only, after the confirmed opening reserves and before the FX conversion, recomputes the percentage,
says so in the record's notes, and leaves the development figure and its route as they are. It refuses an entry whose
1 January figure is not the block's within 2%: that entry describes other reserves.

Run:  python -m pytest src/test_takeon_base.py -q
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

EVIDENCE = {"pages": [24, 32, 33],
            "quote": "p24 note 3: 'At 1 January 2021 (73,709)'; 'Reinsurance to close accepted (839,787)'",
            "readings": ["first reading: the triangle carries the RITCs on both diagonals", "second reading: the same"],
            "source": "test"}
ENTRY = dict(EVIDENCE, opening_reserves_m=73.709, takeon_m=839.787)
DROP = object()


def _entry(change):
    out = dict(ENTRY)
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


# --- the register ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("change", [{"readings": DROP}, {"readings": ["one reading"]}, {"pages": []}, {"pages": ["p24"]},
                                    {"quote": "   "}, {"opening_reserves_m": None}, {"opening_reserves_m": 0},
                                    {"opening_reserves_m": "73.709"}, {"opening_reserves_m": DROP}, {"takeon_m": None},
                                    {"takeon_m": 0}, {"takeon_m": -5.0}, {"takeon_m": "839.787"}, {"takeon_m": DROP}],
                         ids=["no-readings", "one-reading", "no-pages", "page-text", "blank-quote", "opening-null",
                              "opening-zero", "opening-text", "opening-missing", "takeon-null", "takeon-zero",
                              "takeon-negative", "takeon-text", "takeon-missing"])
def test_the_register_refuses_an_entry_without_its_evidence_or_its_amounts(tmp_path, change):
    reg = {"_purpose": "test", "9999_2021": _entry(change)}
    with pytest.raises(ValueError, match="9999_2021"):
        ra.load_takeon_base(_register(tmp_path, reg))


def test_the_register_skips_its_notes_and_the_entries_still_to_complete(tmp_path):
    reg = {"_purpose": "test", "9999_2021": ENTRY, "9999_2022": {"_to_complete": True, "takeon_m": 1.0}}
    assert set(ra.load_takeon_base(_register(tmp_path, reg))) == {"9999_2021"}


# --- apply_takeon_base ------------------------------------------------------------------------------------------------

def test_apply_takeon_base_adds_the_take_on_and_recomputes_the_percentage_on_a_copy():
    cm = {"prior_year_development_gbp_m": -20.1, "prior_year_development_pct": -27.27,
          "opening_reserves_gbp_m": 73.709, "data_quality_notes": "earlier notes",
          "_pyd_route": {"source": "rag_triangle", "value": -20.1}}
    out = ra.apply_takeon_base(cm, ENTRY)
    assert out["opening_reserves_gbp_m"] == pytest.approx(913.496)
    assert out["prior_year_development_pct"] == pytest.approx(100.0 * -20.1 / 913.496)
    assert out["prior_year_development_gbp_m"] == -20.1
    assert out["_pyd_route"] == {"source": "rag_triangle", "value": -20.1}
    assert out["data_quality_notes"].startswith("earlier notes ")
    assert ("[OPENING RESERVES ADJUSTED FOR A TAKE-ON: 913.496m, the 73.709m at 1 January plus 839.787m of gross "
            "claims reserves taken on in the year, register data/opening_reserves_takeon_base.json]") in out["data_quality_notes"]
    assert cm["opening_reserves_gbp_m"] == 73.709 and cm["prior_year_development_pct"] == -27.27
    assert cm["data_quality_notes"] == "earlier notes"


@pytest.mark.parametrize("block_opening", [70.0, 77.5, 1659.705, None])
def test_apply_takeon_base_refuses_an_entry_whose_1_january_figure_is_not_the_blocks(block_opening):
    cm = {"prior_year_development_gbp_m": -20.1, "opening_reserves_gbp_m": block_opening}
    with pytest.raises(ValueError, match="1 January"):
        ra.apply_takeon_base(cm, ENTRY)


def test_apply_takeon_base_adds_to_the_blocks_figure_within_2_percent_of_the_entrys():
    cm = {"prior_year_development_gbp_m": -20.1, "opening_reserves_gbp_m": 73.709 * 1.019}
    out = ra.apply_takeon_base(cm, ENTRY)
    assert out["opening_reserves_gbp_m"] == pytest.approx(73.709 * 1.019 + 839.787)


# --- the loader, on the real records ------------------------------------------------------------------------------------

RECORDS = ("1884_2021", "3500_2021", "2003_2018", "457_2016")
OPENING_2003 = dict(EVIDENCE, opening_reserves_m=5344.064)


def _load(factory, base, openings):
    d = factory.mktemp("records")
    for key in RECORDS:
        shutil.copy(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), str(d))
    reg = factory.mktemp("registers")
    paths = {name: reg / ("%s.json" % name) for name in ("confirmed", "takeons", "openings", "base")}
    paths["confirmed"].write_text(json.dumps({"_purpose": "empty"}), encoding="utf-8")
    paths["takeons"].write_text(json.dumps({"_purpose": "empty"}), encoding="utf-8")
    paths["openings"].write_text(json.dumps(openings), encoding="utf-8")
    paths["base"].write_text(json.dumps(base), encoding="utf-8")
    mp = pytest.MonkeyPatch()
    try:
        # inside the try: a setattr that raises must not leave the registers patched for later tests
        mp.setattr(ra, "DATA_DIR", d)
        mp.setattr(ra, "PYD_CONFIRMED_FIGURES", paths["confirmed"])
        mp.setattr(ra, "TAKEON_REGISTER", paths["takeons"])
        mp.setattr(ra, "OPENING_RESERVES_CONFIRMED", paths["openings"])
        mp.setattr(ra, "TAKEON_BASE_REGISTER", paths["base"])
        records, counters, log, files = ra.load_and_classify()
    finally:
        mp.undo()
    assert len(files) == len(RECORDS)
    return {"by_key": {"%s_%s" % (r["syndicate"], r["year"]): r for r in records}, "counters": counters}


@pytest.fixture(scope="module")
def adjusted(tmp_path_factory):
    return _load(tmp_path_factory,
                 {"_purpose": "test", "1884_2021": ENTRY,
                  "3500_2021": dict(EVIDENCE, opening_reserves_m=770.428, takeon_m=2425.117),
                  # on the confirmed opening reserves: applies only if the take-on follows them
                  "2003_2018": dict(EVIDENCE, opening_reserves_m=5344.064, takeon_m=532.922)},
                 {"_purpose": "test", "2003_2018": OPENING_2003})


@pytest.fixture(scope="module")
def unadjusted(tmp_path_factory):
    return _load(tmp_path_factory, {"_purpose": "empty"}, {"_purpose": "test", "2003_2018": OPENING_2003})


def test_the_loader_adds_the_take_on_for_the_registered_records_only(adjusted, unadjusted):
    was, now = unadjusted["by_key"]["1884_2021"], adjusted["by_key"]["1884_2021"]
    assert now["fx_applied"] is False
    assert was["opening_reserves_gbp_m"] == pytest.approx(73.709)
    assert now["opening_reserves_gbp_m"] == pytest.approx(73.709 + 839.787)
    assert now["pyd_gbp_m"] == pytest.approx(was["pyd_gbp_m"])
    assert now["pyd_pct"] == pytest.approx(100.0 * -20.1 / 913.496)
    assert (now["pyd_basis"], now["data_quality_tag"]) == (was["pyd_basis"], was["data_quality_tag"])
    other_was, other_now = unadjusted["by_key"]["457_2016"], adjusted["by_key"]["457_2016"]
    assert other_now["opening_reserves_gbp_m"] == other_was["opening_reserves_gbp_m"]
    assert other_now["pyd_pct"] == other_was["pyd_pct"]
    assert adjusted["counters"]["takeon_base_applied"] == 3
    assert unadjusted["counters"]["takeon_base_applied"] == 0


def test_the_take_on_is_added_in_the_reports_currency_before_the_fx_conversion(adjusted, unadjusted):
    was, now = unadjusted["by_key"]["3500_2021"], adjusted["by_key"]["3500_2021"]
    assert now["fx_applied"] is True
    rate = now["fx_rate_usd_per_gbp"]
    assert was["opening_reserves_gbp_m"] == pytest.approx(770.428 / rate)
    assert now["opening_reserves_gbp_m"] == pytest.approx((770.428 + 2425.117) / rate)
    assert now["pyd_pct"] == pytest.approx(100.0 * 109.086 / (770.428 + 2425.117))


def test_the_take_on_follows_the_confirmed_opening_reserves(adjusted, unadjusted):
    # 2003/2018's extraction holds the reinsurers' share, 1,659.705m; the confirmed register gives 5,344.064m. The entry
    # names the confirmed figure, so the loader must add the take-on after the confirmed opening reserves.
    was, now = unadjusted["by_key"]["2003_2018"], adjusted["by_key"]["2003_2018"]
    rate = now["fx_rate_usd_per_gbp"]
    assert was["opening_reserves_gbp_m"] == pytest.approx(5344.064 / rate)
    assert now["opening_reserves_gbp_m"] == pytest.approx((5344.064 + 532.922) / rate)


def test_the_committed_register_names_existing_records_and_carries_its_evidence():
    reg = json.load(io.open(str(ra.TAKEON_BASE_REGISTER), encoding="utf-8"))
    assert reg.get("_purpose")
    keys = [k for k in reg if not k.startswith("_")]
    for key in keys:
        assert os.path.exists(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key)), key
    pending = {k for k in keys if reg[k].get("_to_complete")}
    assert set(ra.load_takeon_base()) == set(keys) - pending
