r"""The whole-year run-off rule (the author's decision of 1 October 2026, in-sample option A).

A syndicate-year whose own filing states that the syndicate was in run-off for the whole year is a run-off year, a
scientific exclusion, unless the model assigns it to the assumed-business (RITC) regime: run-off consolidators and
legacy vehicles take on other syndicates' reserves, which the paper models on purpose. A year in which run-off began
(PART), began at or after the year end (AFTER), or a reading about another entity (NOTCOUNT) stays. The premium rule
of decision D1 stays as it is. The readings are the extraction's corpus-wide run-off register.

These tests build registers in a temporary directory and run committed records through the loader there: 1882/2017
(the clean regime; its filing says the syndicate ceased underwriting in 2016), 3500/2018 (the RITC regime, a run-off
consolidator), 1991/2020 (clean; run-off began on 6 November 2020) and 2468/2022 (premium zero).

Run:  python -m pytest src/test_runoff_whole_year.py -q
"""
import json
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import assumed_business  # noqa: E402
import run_analysis as ra  # noqa: E402

HASH = "cd" * 32
QUOTE = "The Syndicate  ceased underwriting\nat the end of 2016."


def _entry(key, category, **extra):
    syndicate, year = key.split("_")
    entry = {"stem": "syndicate_%s" % key, "syndicate": int(syndicate), "year": int(year), "category": category,
             "runoff_from": "31 December 2016", "source_page": 4, "source_page_printed": "3",
             "source_sha256": HASH, "evidence": QUOTE}
    entry.update(extra)
    return entry


def _write(path, register):
    path.write_text(json.dumps(register), encoding="utf-8")
    return path


# ---- the register -------------------------------------------------------------------------------------------------

def test_a_missing_register_stops_the_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="corpus-wide run-off register"):
        ra.load_runoff_corpus_register(tmp_path / "absent.json")


@pytest.mark.parametrize("container", ["list", "records", "keyed"])
def test_the_register_reads_each_container(tmp_path, container):
    entries = [_entry("1882_2017", "WHOLE"), _entry("1991_2020", "PART")]
    raw = {"list": entries, "records": {"_note": "test", "records": entries},
           "keyed": dict({"_note": "test"}, **{e["stem"]: {k: v for k, v in e.items() if k != "stem"}
                                               for e in entries})}[container]
    got = ra.load_runoff_corpus_register(_write(tmp_path / "r.json", raw))
    assert {k: v["category"] for k, v in got.items()} == {"1882_2017": "WHOLE", "1991_2020": "PART"}


@pytest.mark.parametrize("change, gap", [
    ({"category": "RUNOFF"}, "category"), ({"category": None}, "category"),
    ({"evidence": None}, "evidence"), ({"evidence": " "}, "evidence"),
    ({"source_page": None}, "source_page"), ({"source_page": True}, "source_page"),
    ({"source_sha256": "cd" * 31}, "source_sha256"),
])
def test_a_whole_year_reading_without_its_evidence_stops_the_run(tmp_path, change, gap):
    """A reading that moves a record out of the corpus is applied only with the page, the file's hash and the
    filing's words; a category outside the four stops the run too."""
    path = _write(tmp_path / "r.json", {"records": [dict(_entry("1882_2017", "WHOLE"), **change)]})
    with pytest.raises(ValueError, match=gap):
        ra.load_runoff_corpus_register(path)


def test_the_words_may_be_called_quote(tmp_path):
    entry = _entry("1882_2017", "WHOLE", quote=QUOTE)
    del entry["evidence"]
    got = ra.load_runoff_corpus_register(_write(tmp_path / "r.json", [entry]))
    assert ra.whole_year_runoff_reason(got["1882_2017"]).endswith('"The Syndicate ceased underwriting at the end '
                                                                   'of 2016."')


@pytest.mark.parametrize("category", ["PART", "AFTER", "NOTCOUNT"])
def test_a_reading_that_keeps_a_record_needs_no_quote(tmp_path, category):
    path = _write(tmp_path / "r.json", [_entry("1991_2020", category, evidence=None, source_page=None,
                                               source_sha256=None)])
    assert ra.load_runoff_corpus_register(path)["1991_2020"]["category"] == category


def test_a_syndicate_year_is_read_once(tmp_path):
    path = _write(tmp_path / "r.json", [_entry("1882_2017", "WHOLE"), _entry("1882_2017", "PART")])
    with pytest.raises(ValueError, match="twice"):
        ra.load_runoff_corpus_register(path)


# ---- the decision -------------------------------------------------------------------------------------------------

def test_only_a_whole_year_reading_outside_the_regime_excludes():
    register = {"1882_2017": _entry("1882_2017", "WHOLE"), "3500_2018": _entry("3500_2018", "WHOLE"),
                "1991_2020": _entry("1991_2020", "PART"), "1110_2019": _entry("1110_2019", "AFTER")}
    regime = {"3500_2018"}
    assert ra.whole_year_runoff("1882_2017", register, regime) is True
    assert ra.whole_year_runoff("3500_2018", register, regime) is False
    assert ra.whole_year_runoff("1991_2020", register, regime) is False
    assert ra.whole_year_runoff("1110_2019", register, regime) is False
    assert ra.whole_year_runoff("457_2016", register, regime) is False


def test_the_ledger_reason_quotes_the_filing():
    assert ra.whole_year_runoff_reason(_entry("1882_2017", "WHOLE")) == (
        'the filing states the syndicate was in run-off for the whole year (page 4, printed 3; run-off from '
        '31 December 2016), outside the assumed-business regime: "The Syndicate ceased underwriting at the end of '
        '2016."')


# ---- the loader ---------------------------------------------------------------------------------------------------

RECORDS = ("1882_2017", "3500_2018", "1991_2020", "2468_2022")


def _run(tmp_path, register, keys=RECORDS):
    d = tmp_path / "records"
    d.mkdir()
    for key in keys:
        shutil.copy(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), str(d))
    path = tmp_path / "runoff_corpus_register.json"
    if register is not None:
        _write(path, register)
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(ra, "DATA_DIR", d)
        mp.setattr(ra, "RUNOFF_CORPUS_REGISTER", path)
        records, counters, log, files = ra.load_and_classify()
    finally:
        mp.undo()
    assert len(files) == len(keys)
    status = {e["file"][len("syndicate_"):-len(".json")]: e for e in log}
    kept = {"%s_%s" % (r["syndicate"], r["year"]) for r in records}
    return status, kept, counters


def test_the_records_are_the_ones_the_tests_describe():
    regime = assumed_business.keys()
    assert "3500_2018" in regime and not {"1882_2017", "1991_2020", "2468_2022"} & regime
    for key in ("1882_2017", "3500_2018", "1991_2020"):
        with open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), encoding="utf-8") as fh:
            models = json.load(fh)["models"]
        assert all(m["gross_premiums_written_gbp_m"] > 0 for m in models.values()), key


def test_a_whole_year_run_off_year_outside_the_regime_leaves(tmp_path):
    register = [_entry("1882_2017", "WHOLE"), _entry("3500_2018", "WHOLE"), _entry("1991_2020", "PART"),
                _entry("2468_2022", "WHOLE")]
    status, kept, counters = _run(tmp_path, register)
    assert status["1882_2017"]["status"] == "IN RUNOFF" and "1882_2017" not in kept
    assert status["1882_2017"]["reason"].startswith("the filing states the syndicate was in run-off for the whole")
    # a run-off consolidator in the assumed-business regime stays, and so does a year whose run-off began in it
    assert status["3500_2018"]["status"] != "IN RUNOFF" and "3500_2018" in kept
    assert status["1991_2020"]["status"] != "IN RUNOFF" and "1991_2020" in kept
    # the premium rule decides premium zero first, with its own reason
    assert (status["2468_2022"]["status"], status["2468_2022"]["reason"]) == ("IN RUNOFF", "gross written premium 0")
    assert (counters["in_runoff"], counters["in_runoff_whole_year"]) == (2, 1)


def test_a_record_the_register_does_not_read_stays(tmp_path):
    status, kept, counters = _run(tmp_path, [_entry("1991_2020", "PART")])
    assert {"1882_2017", "3500_2018", "1991_2020"} <= kept
    assert (counters["in_runoff"], counters["in_runoff_whole_year"]) == (1, 0)


def test_the_loader_stops_without_the_register(tmp_path):
    with pytest.raises(FileNotFoundError, match="corpus-wide run-off register"):
        _run(tmp_path, None)
