"""The register of page readings of premium by line of business (data/composition_page_readings.json; the PC page
readings of 5 October 2026).

D3-1 left a record out of scope when its extracted mix names no line of business. The PC read the filings:
  * twelve records print premium by line although every model's mix names none (6103's "Property reinsurance",
    6118/2015's and 6132/2020's divisions, 6118/2016's divisions, 6123/2017's regional table of one line, 2357/2017's
    property catastrophe and weather lines): the extraction lost the lines. The loader classes such a record
    composition_unavailable with the reason "extraction_lost_lines": it stays in the target and gets no weights, and no
    mix is rebuilt from the page (D3-1 chose against remapping);
  * one record prints none, whatever another model read (6107/2024: its only split by line is a percentage for the
    closed 2022 year): it is out of scope, with the entry's scope reason.
A page reading outranks the model readings in both directions (the decision of the Claude analysis session of 5 October
2026, reported to the owner), so readers_disagree remains only for a record no page has been read for, and is empty on
the current data. The rule: a book is out of scope only if its filing prints no premium amount by line; lines named in
words without amounts stay out of scope. The register is a hashed input of the run id.

Run:  python -m pytest src/test_composition_page_readings.py -q
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

TRUE = ["2357_2017", "6103_2016", "6103_2017", "6103_2018", "6103_2019", "6103_2021", "6103_2022", "6103_2024",
        "6118_2015", "6118_2016", "6123_2017", "6132_2020"]
FALSE = ["6107_2024"]


def _register():
    with open(ra.COMPOSITION_PAGE_READINGS, encoding="utf-8") as fh:
        return json.load(fh)


def _entries():
    return {k: v for k, v in _register().items() if not k.startswith("_")}


def mix(*pairs):
    return [{"line_of_business": label, "amount_gbp_m": amount} for label, amount in pairs]


def test_the_register_holds_twelve_filings_that_print_lines_and_one_that_prints_none():
    entries = _entries()
    assert sorted(entries) == sorted(TRUE + FALSE)
    assert ra.load_composition_page_readings() == entries
    assert not any(v.get("_to_complete") for v in entries.values())
    for key, v in entries.items():
        assert v["quote"].strip() and v["reading"].strip() and v["where"].strip(), key
        assert v["filing_prints_lines"] is (key in TRUE), key
        # only the HTML filings have no pages
        html = key in ("6103_2024", "6107_2024")
        assert bool(v["pages"]) == (not html), key
        assert v.get("html") is True or not html, key
        if v["filing_prints_lines"]:
            assert v["lines"] and all(x["amount_m"] > 0 and x["currency"] in ("GBP", "USD") for x in v["lines"]), key
        else:
            assert v["scope_reason"] in ra.COMPOSITION_REASONS_OUT_OF_SCOPE and "lines" not in v, key
    assert entries["6107_2024"]["scope_reason"] == "contract_form_only"


def test_each_entry_names_its_source_filing_and_its_hash():
    """The evidence standard: the filing the pages were read in, by name and by the SHA-256 of the file as downloaded."""
    for key, v in _entries().items():
        assert re.fullmatch(r"syndicate_reports/pdfs/syndicate_%s\.(pdf|html)" % key, v["source_file"]), key
        assert re.fullmatch(r"[0-9a-f]{64}", v["source_sha256"]), key
    entries = _entries()
    assert entries["6103_2024"]["source_file"].endswith(".html") and entries["6107_2024"]["source_file"].endswith(".html")
    # the hashes the PC page readings quoted (their first eight digits)
    for key, prefix in (("2357_2017", "7d9a7ed1"), ("6132_2020", "037b7640"), ("6107_2024", "4ce10912")):
        assert entries[key]["source_sha256"].startswith(prefix), key
    # eleven entries have a second reading (the stage-3 verifier's check of every quote and amount); 6118/2016 and
    # 6107/2024 have one reading each, and the status says so
    for key, v in entries.items():
        if key in ("6118_2016", "6107_2024"):
            assert "second_reading" not in v, key
        else:
            assert v["second_reading"].startswith("stage-3 verifier, 5 October 2026: quote and amounts found on the cited "
                                                  "page"), key
    status = _register()["_status"]
    assert "6118/2016 and 6107/2024 have one reading each" in status and "Eleven entries have two readings" in status


def test_each_entrys_lines_add_up_to_the_records_own_gross_premium_and_appear_in_its_quote():
    """The amounts are the filing's, in the report's currency: they add to the premium the record's models read, and
    each appears in the quote (as printed in thousands, or in millions)."""
    for key, v in _entries().items():
        if not v["filing_prints_lines"]:
            continue
        with open(os.path.join(str(ra.DATA_DIR), "syndicate_%s.json" % key), encoding="utf-8") as fh:
            models = json.load(fh)["models"]
        premiums = [m.get("gross_premiums_written_gbp_m") for m in models.values()
                    if m.get("gross_premiums_written_gbp_m")]
        assert premiums, key
        # a channel (2357/2017's MGA Insurance) and an amount the page states but the quote does not itemise
        # (6118/2016's 4.7m) are part of the premium but not an itemised line
        total = sum(x["amount_m"] for x in v["lines"] + v.get("channel_amounts", [])) + v.get("not_itemised_m", 0)
        assert any(abs(total - p) <= 0.02 * p for p in premiums), (key, total, premiums)
        for x in v["lines"]:
            printed = {"%g" % x["amount_m"], "{:,.0f}".format(round(x["amount_m"] * 1000)), "%.1f" % x["amount_m"]}
            assert any(p in v["quote"] for p in printed), (key, x["line"])
    quotes = {k: v["quote"] for k, v in _entries().items()}
    assert all("single line of business" in quotes[k] and "Property reinsurance" in quotes[k]
               for k in TRUE if k.startswith("6103_"))
    assert "Marine, Aviation and Transport (MAT)" in quotes["6118_2015"] and "47.5" in quotes["6118_2015"]
    assert "gross written premium of £28.4m" in quotes["6118_2016"] and "£27.2m" in quotes["6118_2016"]
    assert "Gulf Coast 2,615" in quotes["6123_2017"] and "17,666" in quotes["6123_2017"]
    assert "Gross written premium of £13.8m" in quotes["6132_2020"] and "£(0.1)m" in quotes["6132_2020"]
    assert "'Property Catastrophe Reinsurance 161,953'" in quotes["2357_2017"] and "'Weather 41,981'" in quotes["2357_2017"]
    # 6107/2024: no premium amount by line; the percentages and the single class row are the page's
    q = quotes["6107_2024"]
    assert "property (43%), digital (5%) and cyber (52%)" in q and "Reinsurance acceptances 63,311" in q
    assert "only wrote cyber reinsurance business" in q


@pytest.mark.parametrize("field,bad", [("pages", []), ("pages", [0]), ("quote", " "), ("reading", ""), ("where", None),
                                        ("source_file", ""), ("source_sha256", "abc"), ("source_sha256", None),
                                        ("filing_prints_lines", "yes"), ("filing_prints_lines", None),
                                        ("lines", []), ("lines", [{"line": "Property", "amount_m": 0,
                                                                   "currency": "GBP"}]),
                                        ("lines", [{"line": "Property", "amount_m": 1.0, "currency": "EUR"}]),
                                        ("lines", [{"amount_m": 1.0, "currency": "GBP"}])])
def test_an_entry_is_applied_only_with_its_evidence(tmp_path, field, bad):
    entry = dict(_entries()["6103_2016"])
    path = tmp_path / "register.json"
    path.write_text(json.dumps({"6103_2016": entry}), encoding="utf-8")
    assert ra.load_composition_page_readings(path) == {"6103_2016": entry}
    path.write_text(json.dumps({"6103_2016": dict(entry, **{field: bad})}), encoding="utf-8")
    with pytest.raises(ValueError, match="6103_2016"):
        ra.load_composition_page_readings(path)


def test_the_loader_message_names_the_evidence_each_register_needs(tmp_path):
    """The shared loader said every register needs 'two readings'; this one needs its page, quote and source, and the
    older registers still say two readings."""
    path = tmp_path / "register.json"
    path.write_text(json.dumps({"6103_2016": dict(_entries()["6103_2016"], quote="")}), encoding="utf-8")
    with pytest.raises(ValueError, match="source file and hash") as exc:
        ra.load_composition_page_readings(path)
    assert "two readings" not in str(exc.value)
    path.write_text(json.dumps({"1254_2022": {"kind": "first_year_nil_opening", "pages": [1], "quote": "q"}}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="two readings of the filing, the pages read and a quote"):
        ra.load_filing_eligibility(path)


def test_a_false_entry_needs_one_of_the_scope_reasons(tmp_path):
    entry = dict(_entries()["6107_2024"])
    path = tmp_path / "register.json"
    path.write_text(json.dumps({"6107_2024": entry}), encoding="utf-8")
    assert ra.load_composition_page_readings(path) == {"6107_2024": entry}
    for bad in (None, "readers_disagree", "extraction_lost_lines", "no_mix"):
        path.write_text(json.dumps({"6107_2024": dict(entry, scope_reason=bad)}), encoding="utf-8")
        with pytest.raises(ValueError, match="scope_reason"):
            ra.load_composition_page_readings(path)


@pytest.mark.parametrize("bad", [{"line": "MGA Insurance", "amount_m": 0, "currency": "USD"},
                                 {"line": "MGA Insurance", "amount_m": 1.0, "currency": "EUR"},
                                 {"amount_m": 1.0, "currency": "USD"}, "MGA Insurance"])
def test_channel_amounts_are_checked_when_given(tmp_path, bad):
    """2357/2017's MGA Insurance (a channel, not a line) is part of its premium and sits in channel_amounts."""
    entry = dict(_entries()["2357_2017"])
    path = tmp_path / "register.json"
    path.write_text(json.dumps({"2357_2017": entry}), encoding="utf-8")
    assert ra.load_composition_page_readings(path) == {"2357_2017": entry}
    path.write_text(json.dumps({"2357_2017": dict(entry, channel_amounts=[bad])}), encoding="utf-8")
    with pytest.raises(ValueError, match="channel_amounts"):
        ra.load_composition_page_readings(path)


def test_a_to_complete_entry_is_skipped_and_an_html_entry_may_have_no_pages(tmp_path):
    entry = dict(_entries()["6103_2024"])
    path = tmp_path / "register.json"
    path.write_text(json.dumps({"6103_2024": entry, "6103_2025": {"_to_complete": True, "lead": "to read"}}),
                    encoding="utf-8")
    assert sorted(ra.load_composition_page_readings(path)) == ["6103_2024"]
    path.write_text(json.dumps({"6103_2024": dict(entry, html=False)}), encoding="utf-8")
    with pytest.raises(ValueError):
        ra.load_composition_page_readings(path)


LOST = {"filing_prints_lines": True}


def none_printed(reason):
    return {"filing_prints_lines": False, "scope_reason": reason}


@pytest.mark.parametrize("gpm,scope", [
    (mix(("Reinsurance accepted", 4.871)), "contract_form_only"),
    (mix(("MGA Insurance", 1.0), ("Reinsurance", 3.0)), "channel_only"),
    (mix(("Long-term insurance business", 50.0)), "life"),
])
def test_a_would_be_scope_mix_with_a_true_entry_is_extraction_lost_lines(gpm, scope):
    assert ra.composition_unavailable_reason(gpm) == scope
    assert ra.composition_unavailable_reason(gpm, [], None) == scope
    assert ra.composition_unavailable_reason(gpm, [], LOST) == "extraction_lost_lines"
    assert ra.composition_unavailable_reason(gpm, [mix(("Reinsurance", 9.0))], LOST) == "extraction_lost_lines"


@pytest.mark.parametrize("gpm,scope", [
    (mix(("Reinsurance acceptances", 63.311)), "contract_form_only"),
    (mix(("MGA Insurance", 1.0), ("Reinsurance", 3.0)), "channel_only"),
    (mix(("Long-term insurance business", 50.0)), "life"),
])
def test_a_page_reading_outranks_another_models_lines_in_both_directions(gpm, scope):
    """Without an entry, another model's positive lines make the record readers_disagree. With an entry the page decides:
    a true entry gives extraction_lost_lines, a false one the scope reason (6107/2024: gpt-5-mini's mix was the 2022
    percentages applied to the 2024 premium; 6118/2016: gpt-5-mini's mix is the page's divisions)."""
    other = [mix(("Property", 27.2), ("Digital", 3.2), ("Cyber", 32.9))]
    assert ra.composition_unavailable_reason(gpm, other) == "readers_disagree"
    assert ra.composition_unavailable_reason(gpm, other, LOST) == "extraction_lost_lines"
    assert ra.composition_unavailable_reason(gpm, other, none_printed(scope)) == scope
    assert ra.composition_unavailable_reason(gpm, [], none_printed(scope)) == scope


@pytest.mark.parametrize("gpm,reason", [
    (mix(("Medical Malpractice", 14.8)), "line_not_in_taxonomy"),
    (mix(("UK", 33.0), ("US", 101.9), ("Other", 102.7)), "misparse_geographic"),
    (mix(("Reinsurance", 4.0), ("Other", 2.0)), "other_labels"),
    ([], "no_mix"),
])
def test_the_register_changes_a_scope_outcome_and_nothing_else(gpm, reason):
    assert ra.composition_unavailable_reason(gpm, [], LOST) == reason
    assert ra.composition_unavailable_reason(gpm, [], none_printed("contract_form_only")) == reason


def test_the_reason_is_in_the_ledger_as_composition_unavailable_in_the_target():
    assert "extraction_lost_lines" in ra.COMPOSITION_REASONS
    assert "extraction_lost_lines" not in ra.COMPOSITION_REASONS_OUT_OF_SCOPE
    assert set(MC.COMPOSITION_REASON_WORDS) == set(ra.COMPOSITION_REASONS)
    got = MC.composition_disposition({"hhi": None, "composition_unavailable_reason": "extraction_lost_lines"},
                                     "syndicate_6103_2016.json")
    assert (got[0], got[1]) == ("eligible_observed_composition_unavailable", "missing_lob_composition")
    assert "composition_page_readings.json" in got[5] and "lost the lines" in got[5]


@pytest.fixture(scope="module")
def loaded():
    records, counters, _log, _files = ra.load_and_classify()
    return records, counters


def test_on_the_committed_records_the_page_readings_decide_their_records(loaded):
    records, counters = loaded
    by_key = {"%s_%s" % (r["syndicate"], r["year"]): r for r in records}
    for key in TRUE:
        r = by_key[key]
        assert r["composition_unavailable_reason"] == "extraction_lost_lines", key
        assert r["weight_source"] == "none" and r["hhi"] is None, "no mix is rebuilt from the page: " + key
    assert sorted(k for k, r in by_key.items() if r["composition_unavailable_reason"] == "extraction_lost_lines") \
        == sorted(TRUE)
    assert counters["composition_unavailable_reasons"]["extraction_lost_lines"] == 12
    # 6107/2024 is out of scope on the page's word, though gpt-5-mini read lines; 6118/2016 is a lost-lines record
    assert by_key["6107_2024"]["composition_unavailable_reason"] == "contract_form_only"
    assert by_key["6107_2024"]["weight_source"] == "none"
    assert by_key["6118_2016"]["composition_unavailable_reason"] == "extraction_lost_lines"
    # every record has been page-read, so readers_disagree is empty on the current data, and the register leaves every
    # other reason as it was
    assert counters["composition_unavailable_reasons"].get("readers_disagree", 0) == 0
    assert by_key["6103_2015"]["weight_source"] == "premium_mix"


def test_no_real_register_entry_is_named_unused_on_the_committed_records(capsys):
    """Every one of the thirteen entries is used by its record: the loader's unused-entry log names none (so a loader
    that never fills its used set, and would name all thirteen, fails here)."""
    ra.load_and_classify()
    assert "applies to no record" not in capsys.readouterr().err


def test_an_entry_that_applies_to_no_record_is_named_in_the_run_log(monkeypatch, capsys):
    """A stale entry (a record whose figures changed) is named, not silently kept."""
    real = ra.load_composition_page_readings()
    monkeypatch.setattr(ra, "load_composition_page_readings",
                        lambda path=None: dict(real, **{"1200_2021": real["6103_2016"]}))
    ra.load_and_classify()
    assert "applies to no record whose extracted mix names no line of business now: 1200_2021" in capsys.readouterr().err


def test_the_register_is_a_hashed_input_of_the_run_id_and_pinned_raw():
    assert str(ra.COMPOSITION_PAGE_READINGS) in ra.source_files_for_hash([])
    with open(os.path.join(HERE, ".gitattributes"), encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh.read().splitlines()]
    assert "data/composition_page_readings.json -text" in lines
    assert "data/composition_lines_in_filing.json -text" not in lines
    assert not os.path.exists(os.path.join(HERE, "data", "composition_lines_in_filing.json"))
