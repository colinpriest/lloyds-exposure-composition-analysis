"""What a filing shows about a record whose models read no usable figure (the review of 2 October 2026, P-10).

Two of the twelve "eligible outcome unavailable" records are first-year reports with nil openings (1254/2022,
6118/2014), labelled eligible by processing status; 435/2014 states its prior-year movement as a "net release",
which the settled net-basis rule excludes. data/eligibility_from_filing.json records each from its filing. The page
readings are the PC's, so the committed entries are marked "_to_complete" and the loader applies none of them; these
tests hold the mechanism: the evidence rule, the loader's two effects and the ledger's classification.

Run:  python -m pytest src/test_filing_eligibility.py -q
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

READINGS = ["first reading (test)", "second reading (test)"]
FIRST_YEAR = {"kind": "first_year_nil_opening", "pages": [6, 17], "quote": "The Syndicate was set up on 1 January 2022",
              "readings": READINGS}
NET = {"kind": "stated_basis_excluded", "basis": "net", "pages": [22],
       "quote": "In total there was a net release of GBP98,556,000", "readings": READINGS}


def _write(tmp_path, reg):
    p = tmp_path / "eligibility_from_filing.json"
    p.write_text(json.dumps(dict({"_purpose": "test"}, **reg)), encoding="utf-8")
    return p


def test_the_committed_entries_are_complete_and_applied():
    """The stage-3 PC page check (5 October 2026) completed the three entries: each carries its pages, quote, file
    hash and two readings, none is marked _to_complete, and the loader applies all three."""
    with open(ra.FILING_ELIGIBILITY_REGISTER, encoding="utf-8") as fh:
        raw = fh.read()
    reg = json.loads(raw)
    entries = {k: v for k, v in reg.items() if not k.startswith("_")}
    assert sorted(entries) == ["1254_2022", "435_2014", "6118_2014"]
    assert not any(v.get("_to_complete") for v in entries.values())
    assert "PENDING" not in raw and "_to_complete" not in json.dumps(entries)
    assert ra.load_filing_eligibility() == entries
    for key, v in entries.items():
        assert len([r for r in v["readings"] if r.strip()]) >= 2 and v["quote"].strip(), key
        assert re.fullmatch(r"[0-9a-f]{64}", v["source_sha256"]), key
        assert v["source_file"] == "syndicate_reports/pdfs/syndicate_%s.pdf" % key, key
    assert (entries["6118_2014"]["kind"], entries["6118_2014"]["pages"]) == ("first_year_nil_opening", [6, 15, 20])
    # 435/2014's stated basis is unknown, not net: the note never says gross or net of reinsurance
    assert (entries["435_2014"]["kind"], entries["435_2014"]["basis"]) == ("stated_basis_excluded", "unknown")
    assert "42,433" in entries["435_2014"]["quote"] and "98,556" in entries["435_2014"]["quote"]


def test_1254_2022_is_kept_as_a_first_year_nil_opening_by_the_analysis_sessions_decision():
    """Option A of the page check: the opening is nil (p41), the reserves came by an inwards RITC of 2689's 2017-2019
    years, and the only printed development (-28.229 on p30) is the cedant's estimate, which conflicts with the
    syndicate's own 4.7m release (p7)."""
    with open(ra.FILING_ELIGIBILITY_REGISTER, encoding="utf-8") as fh:
        e = json.load(fh)["1254_2022"]
    assert e["kind"] == "first_year_nil_opening" and e["pages"] == [6, 7, 21, 41, 30]
    # a decision of the Claude analysis session, reported to the owner: not the owner's own
    assert e["decision"].startswith("decision of the Claude analysis session, 5 October 2026, reported to the owner")
    assert "option A" in e["decision"] and "owner's decision" not in e["decision"]
    with open(ra.FILING_ELIGIBILITY_REGISTER, encoding="utf-8") as fh:
        assert "owner's decision of 5 October" not in fh.read()
    for words in ("2689", "-28.229", "p30", "4.7m", "p7"):
        assert words in e["reason"] or words in e["decision"], words
    for words in ("At 1 January 2022 -", "Inwards RITC of liabilities 75,257", "-28,229"):
        assert words in e["quote"], words


def test_an_entry_is_applied_only_with_its_evidence(tmp_path):
    assert ra.load_filing_eligibility(_write(tmp_path, {"1254_2022": FIRST_YEAR})) == {"1254_2022": FIRST_YEAR}
    for bad, words in ((dict(FIRST_YEAR, readings=READINGS[:1]), "two readings"),
                       (dict(FIRST_YEAR, quote=""), "a quote"),
                       (dict(FIRST_YEAR, pages=[]), "the pages read"),
                       (dict(FIRST_YEAR, kind="other"), "a kind"),
                       (dict(NET, basis="gross"), "the stated basis")):
        with pytest.raises(ValueError, match=words):
            ra.load_filing_eligibility(_write(tmp_path, {"1254_2022": bad}))


def _load(monkeypatch, tmp_path, reg):
    monkeypatch.setattr(ra, "FILING_ELIGIBILITY_REGISTER", _write(tmp_path, reg))
    records, counters, log, _files = ra.load_and_classify()
    return records, counters, {e["file"]: e for e in log}


def test_completed_entries_move_the_three_records(monkeypatch, tmp_path):
    records, counters, log = _load(monkeypatch, tmp_path, {"1254_2022": FIRST_YEAR, "6118_2014": FIRST_YEAR,
                                                             "435_2014": NET})
    for name in ("syndicate_1254_2022.json", "syndicate_6118_2014.json"):
        assert (log[name]["status"], log[name]["reason"]) == ("SKIPPED", ra.FIRST_YEAR_FROM_FILING_REASON)
    assert counters["first_year_from_filing_skipped"] == 2
    rec = next(r for r in records if (r["syndicate"], r["year"]) == (435, 2014))
    assert (rec["pyd_basis"], rec["pyd_basis_source"]) == ("net", "filing-register:stated-basis")
    assert counters["stated_basis_from_filing"] == 1


def test_without_entries_the_records_stay_where_processing_status_put_them(monkeypatch, tmp_path):
    records, counters, log = _load(monkeypatch, tmp_path, {})
    assert log["syndicate_1254_2022.json"]["status"] == "INCOMPLETE"
    assert log["syndicate_6118_2014.json"]["status"] == "INCOMPLETE"
    rec = next(r for r in records if (r["syndicate"], r["year"]) == (435, 2014))
    assert rec["pyd_basis_source"] != "filing-register:stated-basis"
    assert counters["first_year_from_filing_skipped"] == counters["stated_basis_from_filing"] == 0


def test_a_stated_basis_entry_on_a_record_with_a_figure_stops_the_run(monkeypatch, tmp_path):
    """A figure's basis belongs in the basis register; this register is for records no model read a figure for."""
    with pytest.raises(ValueError, match="carries a figure"):
        _load(monkeypatch, tmp_path, {"1084_2014": NET})


def test_the_ledger_classifies_a_first_year_report_as_structural():
    got = MC.first_year_disposition(FIRST_YEAR, "syndicate_1254_2022.json")
    assert (got[0], got[1], got[2]) == ("structural_no_eligible_outcome", "first_year_nil_opening", "ineligible")
    assert got[5] == ('first-year report with nil opening reserves; the filing (pages 6, 17): '
                      '"The Syndicate was set up on 1 January 2022"')
    for held in (None, NET):
        with pytest.raises(AssertionError, match="first-year report"):
            MC.first_year_disposition(held, "syndicate_1254_2022.json")
