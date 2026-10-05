"""The register of compositions the filings print although every model's extracted mix names none
(data/composition_lines_in_filing.json; the PC page readings of 5 October 2026, item 4).

D3-1 left a record out of scope when its extracted mix names no line of business. The PC read the filings and found
eleven such records whose filing prints premium by line of business (6103's "Property reinsurance", 6118/2015's and
6132/2020's divisions, 6123/2017's regional table of one line, 2357/2017's property catastrophe and weather lines): the
extraction lost the lines. The rule (decision of 5 October 2026): a book is out of scope only if its filing prints no
premium amount by line; lines named in words without amounts stay out of scope. The loader classes such a record
composition_unavailable with the reason "extraction_lost_lines": it stays in the target and gets no weights, and no
mix is rebuilt from the page (D3-1 chose against remapping). The register is a hashed input of the run id.

Run:  python -m pytest src/test_composition_lines_in_filing.py -q
"""
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import missingness_check as MC  # noqa: E402
import run_analysis as ra  # noqa: E402

STEMS = ["2357_2017", "6103_2016", "6103_2017", "6103_2018", "6103_2019", "6103_2021", "6103_2022", "6103_2024",
         "6118_2015", "6123_2017", "6132_2020"]


def _register():
    with open(ra.COMPOSITION_LINES_REGISTER, encoding="utf-8") as fh:
        return json.load(fh)


def _entries():
    return {k: v for k, v in _register().items() if not k.startswith("_")}


def mix(*pairs):
    return [{"line_of_business": label, "amount_gbp_m": amount} for label, amount in pairs]


def test_the_register_holds_the_eleven_records_whose_filings_print_premium_by_line():
    entries = _entries()
    assert sorted(entries) == STEMS
    assert "6118_2016" not in entries, "6118/2016 is readers_disagree: another model read its lines"
    assert ra.load_composition_lines_in_filing() == entries
    assert not any(v.get("_to_complete") for v in entries.values())
    for key, v in entries.items():
        assert v["quote"].strip() and v["reading"].strip() and v["where"].strip(), key
        assert v["lines"] and all(x["amount_m"] > 0 and x["currency"] in ("GBP", "USD") for x in v["lines"]), key
        # only the HTML filing has no pages
        assert bool(v["pages"]) == (key != "6103_2024"), key
        assert v.get("html") is True or key != "6103_2024"


def test_each_entrys_lines_add_up_to_the_records_own_gross_premium_and_appear_in_its_quote():
    """The amounts are the filing's, in the report's currency: they add to the premium the record's models read, and
    each appears in the quote (as printed in thousands, or in millions)."""
    for key, v in _entries().items():
        with open(os.path.join(str(ra.DATA_DIR), "syndicate_%s.json" % key), encoding="utf-8") as fh:
            models = json.load(fh)["models"]
        premiums = [m.get("gross_premiums_written_gbp_m") for m in models.values()
                    if m.get("gross_premiums_written_gbp_m")]
        assert premiums, key
        # a channel (2357/2017's MGA Insurance) is part of the premium but not a line
        total = sum(x["amount_m"] for x in v["lines"] + v.get("channel_amounts", []))
        assert any(abs(total - p) <= 0.02 * p for p in premiums), (key, total, premiums)
        for x in v["lines"]:
            printed = {"%g" % x["amount_m"], "{:,.0f}".format(round(x["amount_m"] * 1000)), "%.1f" % x["amount_m"]}
            assert any(p in v["quote"] for p in printed), (key, x["line"])
    quotes = {k: v["quote"] for k, v in _entries().items()}
    assert all("single line of business" in quotes[k] and "Property reinsurance" in quotes[k]
               for k in STEMS if k.startswith("6103_"))
    assert "Marine, Aviation and Transport (MAT)" in quotes["6118_2015"] and "47.5" in quotes["6118_2015"]
    assert "Gulf Coast 2,615" in quotes["6123_2017"] and "17,666" in quotes["6123_2017"]
    assert "Gross written premium of £13.8m" in quotes["6132_2020"] and "£(0.1)m" in quotes["6132_2020"]
    assert "'Property Catastrophe Reinsurance 161,953'" in quotes["2357_2017"] and "'Weather 41,981'" in quotes["2357_2017"]


@pytest.mark.parametrize("field,bad", [("pages", []), ("pages", [0]), ("quote", " "), ("reading", ""), ("where", None),
                                        ("lines", []), ("lines", [{"line": "Property", "amount_m": 0,
                                                                   "currency": "GBP"}]),
                                        ("lines", [{"line": "Property", "amount_m": 1.0, "currency": "EUR"}]),
                                        ("lines", [{"amount_m": 1.0, "currency": "GBP"}])])
def test_an_entry_is_applied_only_with_its_evidence(tmp_path, field, bad):
    entry = dict(_entries()["6103_2016"])
    path = tmp_path / "register.json"
    path.write_text(json.dumps({"6103_2016": entry}), encoding="utf-8")
    assert ra.load_composition_lines_in_filing(path) == {"6103_2016": entry}
    path.write_text(json.dumps({"6103_2016": dict(entry, **{field: bad})}), encoding="utf-8")
    with pytest.raises(ValueError, match="6103_2016"):
        ra.load_composition_lines_in_filing(path)


@pytest.mark.parametrize("bad", [{"line": "MGA Insurance", "amount_m": 0, "currency": "USD"},
                                 {"line": "MGA Insurance", "amount_m": 1.0, "currency": "EUR"},
                                 {"amount_m": 1.0, "currency": "USD"}, "MGA Insurance"])
def test_channel_amounts_are_checked_when_given(tmp_path, bad):
    """2357/2017's MGA Insurance (a channel, not a line) is part of its premium and sits in channel_amounts."""
    entry = dict(_entries()["2357_2017"])
    path = tmp_path / "register.json"
    path.write_text(json.dumps({"2357_2017": entry}), encoding="utf-8")
    assert ra.load_composition_lines_in_filing(path) == {"2357_2017": entry}
    path.write_text(json.dumps({"2357_2017": dict(entry, channel_amounts=[bad])}), encoding="utf-8")
    with pytest.raises(ValueError, match="channel_amounts"):
        ra.load_composition_lines_in_filing(path)


def test_a_to_complete_entry_is_skipped_and_an_html_entry_may_have_no_pages(tmp_path):
    entry = dict(_entries()["6103_2024"])
    path = tmp_path / "register.json"
    path.write_text(json.dumps({"6103_2024": entry, "6103_2025": {"_to_complete": True, "lead": "to read"}}),
                    encoding="utf-8")
    assert sorted(ra.load_composition_lines_in_filing(path)) == ["6103_2024"]
    path.write_text(json.dumps({"6103_2024": dict(entry, html=False)}), encoding="utf-8")
    with pytest.raises(ValueError):
        ra.load_composition_lines_in_filing(path)


@pytest.mark.parametrize("gpm,scope", [
    (mix(("Reinsurance accepted", 4.871)), "contract_form_only"),
    (mix(("MGA Insurance", 1.0), ("Reinsurance", 3.0)), "channel_only"),
    (mix(("Long-term insurance business", 50.0)), "life"),
])
def test_a_would_be_scope_mix_of_a_registered_record_is_extraction_lost_lines(gpm, scope):
    assert ra.composition_unavailable_reason(gpm) == scope
    assert ra.composition_unavailable_reason(gpm, [], False) == scope
    assert ra.composition_unavailable_reason(gpm, [], True) == "extraction_lost_lines"
    assert ra.composition_unavailable_reason(gpm, [mix(("Reinsurance", 9.0))], True) == "extraction_lost_lines"
    # another model that reads a line is a disagreement, whatever the register says
    assert ra.composition_unavailable_reason(gpm, [mix(("Marine", 2.0))], True) == "readers_disagree"


@pytest.mark.parametrize("gpm,reason", [
    (mix(("Medical Malpractice", 14.8)), "line_not_in_taxonomy"),
    (mix(("UK", 33.0), ("US", 101.9), ("Other", 102.7)), "misparse_geographic"),
    (mix(("Reinsurance", 4.0), ("Other", 2.0)), "other_labels"),
    ([], "no_mix"),
])
def test_the_register_changes_a_scope_outcome_and_nothing_else(gpm, reason):
    assert ra.composition_unavailable_reason(gpm, [], True) == reason


def test_the_reason_is_in_the_ledger_as_composition_unavailable_in_the_target():
    assert "extraction_lost_lines" in ra.COMPOSITION_REASONS
    assert "extraction_lost_lines" not in ra.COMPOSITION_REASONS_OUT_OF_SCOPE
    assert set(MC.COMPOSITION_REASON_WORDS) == set(ra.COMPOSITION_REASONS)
    got = MC.composition_disposition({"hhi": None, "composition_unavailable_reason": "extraction_lost_lines"},
                                     "syndicate_6103_2016.json")
    assert (got[0], got[1]) == ("eligible_observed_composition_unavailable", "missing_lob_composition")
    assert "composition_lines_in_filing.json" in got[5] and "lost the lines" in got[5]


@pytest.fixture(scope="module")
def loaded():
    records, counters, _log, _files = ra.load_and_classify()
    return records, counters


def test_on_the_committed_records_the_eleven_are_extraction_lost_lines_and_have_no_weights(loaded):
    records, counters = loaded
    by_key = {"%s_%s" % (r["syndicate"], r["year"]): r for r in records}
    for key in STEMS:
        r = by_key[key]
        assert r["composition_unavailable_reason"] == "extraction_lost_lines", key
        assert r["weight_source"] == "none" and r["hhi"] is None, "no mix is rebuilt from the page: " + key
    others = sorted(k for k, r in by_key.items() if r["composition_unavailable_reason"] == "extraction_lost_lines")
    assert others == sorted(STEMS)
    assert counters["composition_unavailable_reasons"]["extraction_lost_lines"] == 11
    # 6118/2016 stays a disagreement, and the register leaves every other reason as it was
    assert by_key["6118_2016"]["composition_unavailable_reason"] == "readers_disagree"
    assert by_key["6103_2015"]["weight_source"] == "premium_mix"


def test_an_entry_that_applies_to_no_record_is_named_in_the_run_log(monkeypatch, capsys):
    """A stale entry (a record whose figures changed) is named, not silently kept."""
    real = ra.load_composition_lines_in_filing()
    monkeypatch.setattr(ra, "load_composition_lines_in_filing",
                        lambda path=None: dict(real, **{"1200_2021": real["6103_2016"]}))
    ra.load_and_classify()
    assert "applies to no record without a composition now: 1200_2021" in capsys.readouterr().err


def test_the_register_is_a_hashed_input_of_the_run_id_and_pinned_raw():
    assert str(ra.COMPOSITION_LINES_REGISTER) in ra.source_files_for_hash([])
    with open(os.path.join(HERE, ".gitattributes"), encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh.read().splitlines()]
    assert "data/composition_lines_in_filing.json -text" in lines
