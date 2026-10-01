r"""The run-off rule (the author's decision D1, 30 September 2026) and the register it reads.

A record whose development figure is kept and whose adopted gross written premium is at or below zero is a run-off
year, a scientific exclusion, when its own filing states that the syndicate is in run-off in that year. Premium
exactly zero stays run-off without the register. A negative premium alone is not run-off: 3623/2018 is a live
syndicate whose premium is negative through a return premium. The statements are the extraction's run-off register
(pdf_extraction/audit/runoff_register.json), one entry per record with a development figure and a premium at or
below zero, each with the page, the file's hash and the filing's words.

These tests build registers in a temporary directory and run three committed records through the loader there:
2468/2021 (premium -2.19m), 3623/2018 (premium -33.4m) and 2468/2022 (premium 0), with 457/2016 as a control
that writes business. The loader's reading of every committed record is the regeneration's run, which stops at
any record the register does not decide; the last test holds the committed ledger's run-off years to the imported
register's.

Run:  python -m pytest src/test_runoff_register.py -q
"""
import json
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import run_analysis as ra  # noqa: E402

HASH = "ab" * 32
QUOTE = "The syndicate  ceased underwriting\nand is in run-off."


def _entry(key, premium, in_runoff, **extra):
    syndicate, year = key.split("_")
    entry = {"stem": "syndicate_%s" % key, "syndicate": int(syndicate), "year": int(year),
             "premium_adopted_gbp_m": premium, "in_runoff": in_runoff, "runoff_from": None,
             "source_page": 7, "source_page_printed": "5", "source_sha256": HASH, "evidence": QUOTE}
    entry.update(extra)
    return entry


def _write(path, register):
    path.write_text(json.dumps(register), encoding="utf-8")
    return path


# the register for the three records, as the extraction writes it for the committed ones
REGISTER = {"records": [_entry("2468_2021", -2.19, True), _entry("3623_2018", -33.4, False),
                        _entry("2468_2022", 0.0, True)]}


# ---- the register -------------------------------------------------------------------------------------------------

def test_a_missing_register_stops_the_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="run-off register"):
        ra.load_runoff_register(tmp_path / "runoff_register.json")


@pytest.mark.parametrize("container", ["list", "records", "keyed"])
def test_the_register_reads_each_container(tmp_path, container):
    entries = REGISTER["records"]
    raw = {"list": entries, "records": {"_note": "test", "records": entries},
           "keyed": dict({"_note": "test"}, **{e["stem"]: {k: v for k, v in e.items() if k != "stem"}
                                               for e in entries})}[container]
    got = ra.load_runoff_register(_write(tmp_path / "r.json", raw))
    assert sorted(got) == ["2468_2021", "2468_2022", "3623_2018"]
    assert got["2468_2021"]["in_runoff"] is True and got["3623_2018"]["in_runoff"] is False


@pytest.mark.parametrize("raw", [{"entries": REGISTER["records"]}, {"records": {"a": 1}}, "records"],
                         ids=["unknown key", "records not a list", "a string"])
def test_a_container_it_cannot_read_stops_the_run(tmp_path, raw):
    with pytest.raises(ValueError, match="run-off register"):
        ra.load_runoff_register(_write(tmp_path / "r.json", raw))


@pytest.mark.parametrize("change, gap", [
    ({"evidence": None}, "evidence"), ({"evidence": "  "}, "evidence"),
    ({"source_page": None}, "source_page"), ({"source_page": True}, "source_page"), ({"source_page": "7"}, "source_page"),
    ({"source_sha256": "ab" * 31}, "source_sha256"), ({"source_sha256": None}, "source_sha256"),
])
def test_a_runoff_statement_without_its_evidence_stops_the_run(tmp_path, change, gap):
    """A statement that moves a record out of the corpus is applied only with the page, the file's hash and the
    filing's words."""
    path = _write(tmp_path / "r.json", {"records": [_entry("2468_2021", -2.19, True, **change)]})
    with pytest.raises(ValueError, match=gap):
        ra.load_runoff_register(path)


def test_a_statement_that_keeps_a_record_live_needs_no_quote(tmp_path):
    path = _write(tmp_path / "r.json", {"records": [_entry("3623_2018", -33.4, False, evidence=None,
                                                           source_page=None, source_sha256=None)]})
    assert ra.load_runoff_register(path)["3623_2018"]["in_runoff"] is False


@pytest.mark.parametrize("change, gap", [
    ({"in_runoff": "yes"}, "in_runoff"), ({"in_runoff": None}, "in_runoff"),
    ({"premium_adopted_gbp_m": 1.5}, "premium"), ({"premium_adopted_gbp_m": None}, "premium"),
    ({"premium_adopted_gbp_m": True}, "premium"),
])
def test_an_entry_must_decide_and_name_a_premium_at_or_below_zero(tmp_path, change, gap):
    path = _write(tmp_path / "r.json", {"records": [dict(_entry("2468_2021", -2.19, True), **change)]})
    with pytest.raises(ValueError, match=gap):
        ra.load_runoff_register(path)


def test_a_record_is_decided_once(tmp_path):
    path = _write(tmp_path / "r.json", {"records": [_entry("2468_2021", -2.19, True),
                                                    _entry("2468_2021", -2.19, False)]})
    with pytest.raises(ValueError, match="twice"):
        ra.load_runoff_register(path)


# ---- the decision -------------------------------------------------------------------------------------------------

def test_the_register_decides_a_negative_premium(tmp_path):
    register = ra.load_runoff_register(_write(tmp_path / "r.json", REGISTER))
    assert ra.runoff_by_statement("2468_2021", register, [-2.19, None, -2.19]) is True
    assert ra.runoff_by_statement("3623_2018", register, [-33.4, -33.4]) is False
    # within 2% of the register's premium: a model that read a rounded total is still the same record
    assert ra.runoff_by_statement("2468_2021", register, [-2.2]) is True


def test_a_negative_premium_the_register_does_not_decide_stops_the_run(tmp_path):
    register = ra.load_runoff_register(_write(tmp_path / "r.json", REGISTER))
    with pytest.raises(ValueError, match="does not decide"):
        ra.runoff_by_statement("1882_2018", register, [-1.88])


def test_an_entry_whose_premium_is_not_the_records_stops_the_run(tmp_path):
    """The register reads a filing; a premium that is none of the record's is a statement about another record."""
    register = ra.load_runoff_register(_write(tmp_path / "r.json", REGISTER))
    with pytest.raises(ValueError, match="none of the record's"):
        ra.runoff_by_statement("2468_2021", register, [-3.5, None])
    with pytest.raises(ValueError, match="none of the record's"):
        ra.runoff_by_statement("2468_2021", register, [None])
    # 2.7% away is outside the 2% the loader allows
    with pytest.raises(ValueError, match="none of the record's"):
        ra.runoff_by_statement("2468_2021", register, [-2.25])


def test_the_ledger_reason_quotes_the_filing(tmp_path):
    register = ra.load_runoff_register(_write(tmp_path / "r.json", REGISTER))
    assert ra.runoff_reason("2468_2022", 0.0, {}) == "gross written premium 0"
    reason = ra.runoff_reason("2468_2021", -2.19, register)
    assert reason == ('gross written premium -2.19m and the filing states the syndicate is in run-off '
                      '(page 7, printed 5): "The syndicate ceased underwriting and is in run-off."')


# ---- the loader ---------------------------------------------------------------------------------------------------

RECORDS = ("2468_2021", "3623_2018", "2468_2022", "457_2016")


def _run(tmp_path, register, keys=RECORDS):
    d = tmp_path / "records"
    d.mkdir()
    for key in keys:
        shutil.copy(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), str(d))
    path = tmp_path / "runoff_register.json"
    if register is not None:
        _write(path, register)
    # these tests are about the premium rule: the whole-year rule (src/test_runoff_whole_year.py) reads no year here
    corpus = _write(tmp_path / "runoff_corpus_register.json", {"records": []})
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(ra, "DATA_DIR", d)
        mp.setattr(ra, "RUNOFF_REGISTER", path)
        mp.setattr(ra, "RUNOFF_CORPUS_REGISTER", corpus)
        records, counters, log, files = ra.load_and_classify()
    finally:
        mp.undo()
    assert len(files) == len(keys)
    status = {e["file"][len("syndicate_"):-len(".json")]: e for e in log}
    kept = {"%s_%s" % (r["syndicate"], r["year"]) for r in records}
    return status, kept, counters


def test_the_records_are_the_ones_the_tests_describe():
    for key, premium in (("2468_2021", -2.19), ("3623_2018", -33.4), ("2468_2022", 0.0)):
        with open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), encoding="utf-8") as fh:
            models = json.load(fh)["models"]
        assert {m["gross_premiums_written_gbp_m"] for m in models.values()} == {premium}, key
        assert all(m.get("prior_year_development_pct") is not None for m in models.values()), key


def test_a_negative_premium_year_is_in_runoff_when_its_filing_says_so(tmp_path):
    status, kept, counters = _run(tmp_path, REGISTER)
    assert status["2468_2021"]["status"] == "IN RUNOFF"
    assert status["2468_2021"]["reason"].startswith("gross written premium -2.19m and the filing states")
    assert "2468_2021" not in kept
    # a live syndicate with a negative premium is not run-off: it stays in the corpus
    assert status["3623_2018"]["status"] != "IN RUNOFF" and "3623_2018" in kept
    # premium zero is run-off as before
    assert (status["2468_2022"]["status"], status["2468_2022"]["reason"]) == ("IN RUNOFF", "gross written premium 0")
    assert "457_2016" in kept
    assert (counters["in_runoff"], counters["in_runoff_by_statement"]) == (2, 1)


def test_a_negative_premium_year_the_filing_calls_live_stays_in_the_corpus(tmp_path):
    register = {"records": [_entry("2468_2021", -2.19, False), _entry("3623_2018", -33.4, False)]}
    status, kept, counters = _run(tmp_path, register)
    assert status["2468_2021"]["status"] != "IN RUNOFF" and "2468_2021" in kept
    assert (counters["in_runoff"], counters["in_runoff_by_statement"]) == (1, 0)


def test_the_loader_stops_at_a_negative_premium_the_register_does_not_decide(tmp_path):
    with pytest.raises(ValueError, match="3623_2018.*does not decide"):
        _run(tmp_path, {"records": [_entry("2468_2021", -2.19, True)]})


def test_the_loader_stops_when_a_negative_premium_meets_no_register(tmp_path):
    with pytest.raises(FileNotFoundError, match="run-off register"):
        _run(tmp_path, None)


def test_records_that_need_no_statement_run_without_the_register(tmp_path):
    """The register is read the first time a record needs it: premium zero and a written premium do not."""
    status, kept, counters = _run(tmp_path, None, keys=("2468_2022", "457_2016"))
    assert status["2468_2022"]["status"] == "IN RUNOFF" and "457_2016" in kept
    assert (counters["in_runoff"], counters["in_runoff_by_statement"]) == (1, 0)


# ---- the committed records ----------------------------------------------------------------------------------------

def test_the_committed_run_off_years_are_the_registers():
    """On the committed records and ledger (FIX3 A5; FIX4 A4): the loader's run-off years are the two rules' readings
    and only those. The premium rule's are the run-off register's entries at premium zero or whose filing states
    run-off: the register covers every record with a development figure and a premium at or below zero, and every one
    of them is a run-off year. The whole-year rule's are the corpus-wide register's WHOLE readings outside the RITC
    regime (the decision of 1 October 2026): each is a run-off year unless its record has no development figure to
    exclude. A stale ledger, or a reading the loader never applies, shows here."""
    import csv
    import io
    import assumed_business
    register = ra.load_runoff_register()
    corpus = ra.load_runoff_corpus_register()
    regime = assumed_business.keys()
    premium_rule = {k for k, e in register.items() if e["premium_adopted_gbp_m"] == 0 or e["in_runoff"]}
    whole_year = {k for k, e in corpus.items() if e["category"] == "WHOLE" and k not in regime}
    with io.open(os.path.join(HERE, "results", "disposition_ledger.csv"), encoding="utf-8") as fh:
        ledger = {row["file"][len("syndicate_"):-len(".json")]: row["disposition"] for row in csv.DictReader(fh)}
    found = {k for k, d in ledger.items() if d == "IN RUNOFF"}
    assert premium_rule <= found
    assert found <= premium_rule | whole_year, sorted(found - premium_rule - whole_year)
    with io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8") as fh:
        obs = {"%d_%d" % (o["syndicate"], o["year"]): o for o in json.load(fh)["observations"]}

    def without_a_figure(key):
        """Decided before the run-off step, or reaching it with no reliable development figure: after it, no reserves
        or a corpus record whose figure is missing."""
        disposition = ledger.get(key) or ""
        if disposition in ("EXCLUDED", "SKIPPED", "INCOMPLETE_PRE", "NO_RESERVES"):
            return True
        return disposition.startswith("CORPUS:") and key in obs and obs[key].get("pyd_pct") is None

    unapplied = sorted(k for k in whole_year - found if not without_a_figure(k))
    assert not unapplied, "whole-year run-off readings the loader kept although they carry a figure: %s" % unapplied
    assert all(os.path.exists(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % k)) for k in found)
