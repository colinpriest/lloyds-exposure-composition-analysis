r"""The whole-year run-off rule (the author's decision of 1 October 2026, in-sample option A).

A syndicate-year whose own filing states that the syndicate was in run-off for the whole year is a run-off year, a
scientific exclusion, unless the model assigns it to the assumed-business (RITC) regime: run-off consolidators and
legacy vehicles take on other syndicates' reserves, which the paper models on purpose. A year in which run-off began
(PART), began at or after the year end (AFTER), or a reading about another entity (NOTCOUNT) stays. The premium rule
of decision D1 stays as it is. The readings are the extraction's corpus-wide run-off register.

These tests build registers in a temporary directory and run committed records through the loader there: 1882/2017
(the clean regime; its filing says the syndicate ceased underwriting in 2016), 3500/2018 (the RITC regime, a run-off
consolidator), 1991/2020 (clean; run-off began on 6 November 2020), 2468/2022 (premium zero), 510/2017 (clean; a
combined report whose run-off is another syndicate's) and 435/2014 (clean; neither model reads a development figure).
The loader's replay on the whole committed corpus is in test_disposition_ledger.py.

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
                "1991_2020": _entry("1991_2020", "PART"), "1110_2019": _entry("1110_2019", "AFTER"),
                "510_2017": _entry("510_2017", "NOTCOUNT")}
    regime = {"3500_2018"}
    assert ra.whole_year_runoff("1882_2017", register, regime) is True
    assert ra.whole_year_runoff("3500_2018", register, regime) is False
    assert ra.whole_year_runoff("1991_2020", register, regime) is False
    assert ra.whole_year_runoff("1110_2019", register, regime) is False
    assert ra.whole_year_runoff("510_2017", register, regime) is False
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
    assert "3500_2018" in regime and not {"1882_2017", "1991_2020", "2468_2022", "510_2017", "435_2014"} & regime
    records = {}
    for key in ("1882_2017", "3500_2018", "1991_2020", "510_2017", "435_2014"):
        with open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), encoding="utf-8") as fh:
            records[key] = json.load(fh)
        assert all(m["gross_premiums_written_gbp_m"] > 0 for m in records[key]["models"].values()), key
    # 435/2014 has no development figure to move: validation passed on both models reading none
    assert records["435_2014"]["validation"]["passed"] is True
    assert all(m["prior_year_development_pct"] is None for m in records["435_2014"]["models"].values())


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


def test_a_reading_about_another_entity_keeps_the_record(tmp_path):
    """510/2017's combined report says "the syndicate has now been placed into run-off", and the run-off is Syndicate
    308's: the register reads it NOTCOUNT, and the record stays. Counted with the whole-year readings it would leave
    the sample (review of 1 October 2026, finding 1: no test held a NOTCOUNT entry)."""
    status, kept, counters = _run(tmp_path, [_entry("510_2017", "NOTCOUNT")], keys=("510_2017",))
    assert status["510_2017"]["status"] == "RELIABLE" and "510_2017" in kept
    assert (counters["in_runoff"], counters["in_runoff_whole_year"]) == (0, 0)


def test_a_whole_year_reading_of_a_record_with_no_figure_changes_nothing(tmp_path):
    """The rule moves a record only if it has a development figure, as the premium rule does. 435/2014's models
    read none, so a whole-year reading leaves it as it is without one: in the corpus, incomplete, not in run-off."""
    for name in ("without", "with"):
        (tmp_path / name).mkdir()
    base, _kept, _counters = _run(tmp_path / "without", [], keys=("435_2014",))
    status, kept, counters = _run(tmp_path / "with", [_entry("435_2014", "WHOLE")], keys=("435_2014",))
    assert base["435_2014"]["status"] == "INCOMPLETE"
    assert status["435_2014"] == base["435_2014"] and "435_2014" in kept
    assert (counters["in_runoff"], counters["in_runoff_whole_year"]) == (0, 0)


def test_the_loader_stops_without_the_register(tmp_path):
    with pytest.raises(FileNotFoundError, match="corpus-wide run-off register"):
        _run(tmp_path, None)


def test_a_whole_year_reading_of_a_record_with_no_models_makes_it_a_run_off_year(tmp_path):
    """1400/2014's filing says the syndicate "ceased underwriting new business with effect from the end of 2013" (PDF p9),
    and since the import its record has no models, so the premium register no longer lists it and the whole-year rule
    (which needs a development figure) did not reach it: the ledger classed it eligibility unresolved and left it in the
    broader target. Where the corpus-wide register reads a syndicate-year as WHOLE, outside the assumed-business regime,
    it is a run-off year whether or not its record has models; 3210/2018 is the other one."""
    for name in ("without", "with"):
        (tmp_path / name).mkdir()
    keys = ("1400_2014", "3210_2018")
    base, _kept, base_counters = _run(tmp_path / "without", [], keys=keys)
    assert all(base[k]["status"] == "EXCLUDED" for k in keys)
    status, kept, counters = _run(tmp_path / "with", [_entry(k, "WHOLE") for k in keys], keys=keys)
    for k in keys:
        assert status[k]["status"] == "IN RUNOFF" and status[k]["no_models"] is True, k
        assert status[k]["reason"].startswith("the filing states the syndicate was in run-off for the whole year"), k
        assert k not in kept
    assert (counters["in_runoff"], counters["in_runoff_whole_year"]) == (2, 2)
    assert counters["excluded"] == base_counters["excluded"] - 2
    # a reading that does not count (PART, AFTER, NOTCOUNT), or a syndicate-year in the regime, leaves the record as it was
    for category in ("PART", "AFTER", "NOTCOUNT"):
        sub = tmp_path / category
        sub.mkdir()
        status, _kept, counters = _run(sub, [_entry(k, category) for k in keys], keys=keys)
        assert all(status[k]["status"] == "EXCLUDED" for k in keys), category
        assert counters["in_runoff"] == 0, category
    # a syndicate-year the model assigns to the assumed-business regime is not a run-off year, models or not: the loader
    # reads the regime, so a record in it stays as it was
    sub = tmp_path / "regime"
    sub.mkdir()
    mp = pytest.MonkeyPatch()
    mp.setattr(assumed_business, "keys", lambda: {"1400_2014": ["transfer_takeon"]})
    try:
        status, _kept, counters = _run(sub, [_entry("1400_2014", "WHOLE")], keys=("1400_2014",))
    finally:
        mp.undo()
    assert status["1400_2014"]["status"] == "EXCLUDED" and counters["in_runoff"] == 0


def test_the_ledger_reads_the_run_off_record_not_unresolved():
    """The sources the ledger is checked against (missingness_check.unresolved_filings_from_sources) leave out a
    record the corpus-wide register reads as a whole-year run-off year: 1400/2014 and 3210/2018 are decided."""
    import missingness_check as MC
    unresolved = MC.unresolved_filings_from_sources()
    assert "syndicate_1400_2014.json" not in unresolved and "syndicate_3210_2018.json" not in unresolved
    register = ra.load_runoff_corpus_register()
    assert register["1400_2014"]["category"] == register["3210_2018"]["category"] == "WHOLE"
    assert not {"1400_2014", "3210_2018"} & assumed_business.keys()
