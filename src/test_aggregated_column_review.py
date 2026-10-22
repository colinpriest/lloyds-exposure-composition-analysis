r"""The review of the older-years ("& prior") columns of the primary sample (data/aggregated_column_review.json).

Appendix 2.1: an older-years column is one of the mature years of Equation (1) only if its last step is a like-for-like
movement of the same underwriting years during year t. Round 2 (23 October 2026) read the 64 records of the primary
sample that carry such a column, once in each of two independent arms (X, Y), and the 13 on which the arms could not
settle the construction or disagreed a third time (Z1, Z2). The register is built by src/build_aggregated_column_review.py
from the archived readings (results/extraction_error_rate/mature-cohort/round2/).

Run:  python -m pytest src/test_aggregated_column_review.py -q
"""
import copy
import io
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import build_aggregated_column_review as bag  # noqa: E402
import run_analysis as ra  # noqa: E402

LOW = ["3624_2015", "1955_2018", "1200_2015", "2007_2015", "33_2015", "1200_2017"]
#: the 13 records the tie-break readers Z1 and Z2 read, and the register's construction for each
TIE_BREAK = {"2791_2022": "calendar_year", "2791_2023": "calendar_year", "2791_2024": "calendar_year",
             "1955_2018": "calendar_year", "1200_2015": "calendar_year", "1955_2020": "calendar_year",
             "1200_2017": "development_age", "1945_2022": "development_age", "4242_2021": "development_age",
             "4242_2023": "development_age", "2007_2015": "development_age"}


def _register():
    with io.open(str(bag.REGISTER), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def reg():
    return _register()


@pytest.fixture(scope="module")
def entries(reg):
    return {k: v for k, v in reg.items() if not k.startswith("_")}


@pytest.fixture(scope="module")
def primary():
    records, counters, log, files = ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)
    return {"%s_%s" % (r["syndicate"], r["year"]): r for r in records}


def test_the_register_equals_its_rebuild_from_the_archived_readings():
    with io.open(str(bag.REGISTER), encoding="utf-8", newline="") as fh:
        assert fh.read() == bag.dumps(bag.build())


def test_the_register_is_a_raw_byte_file_in_gitattributes():
    with io.open(os.path.join(HERE, ".gitattributes"), encoding="utf-8") as fh:
        assert "data/aggregated_column_review.json -text" in fh.read().splitlines()


def test_the_register_states_its_rule_and_how_the_64_were_chosen(reg, entries):
    assert "last step" in reg["_rule"] and "like-for-like" in reg["_rule"] and "Appendix 2.1" in reg["_rule"]
    pop = reg["_population"]
    assert len(entries) == pop["records_read"] == 64
    assert len(pop["part_a_in_primary"]) == 24 and len(pop["part_b_in_primary"]) == 47
    assert sorted(k for k, e in entries.items() if e["part"] == "A") == sorted(
        set(pop["part_a_in_primary"]) - set(pop["part_a_not_read_again"]))
    assert sorted(k for k, e in entries.items() if e["part"] == "B") == sorted(pop["part_b_in_primary"])
    assert sorted(pop["part_a_not_read_again"]) == sorted(
        ["218_2016", "218_2017", "218_2018", "218_2019", "218_2020", "1945_2023", "1945_2024"])
    assert len(pop["section_c_heuristic_candidates_not_read"]) == 12
    assert not set(pop["section_c_heuristic_candidates_not_read"]) & set(entries)
    assert "primary" in pop["how_chosen"] and "Part B" in pop["how_chosen"] and "Part A" in pop["how_chosen"]
    assert pop["low_confidence"] == LOW


def test_exactly_the_six_unsettled_records_are_low_confidence(entries):
    assert sorted(k for k, e in entries.items() if e["confidence"] == "low_confidence") == sorted(LOW)
    assert {e["confidence"] for e in entries.values()} == {"high", "medium", "low_confidence"}
    assert list(bag.LOW_CONFIDENCE) == LOW


def test_the_rule_figure_is_the_figure_the_last_step_test_gives(entries):
    for key, e in entries.items():
        assert e["construction"] in bag.CONSTRUCTIONS, key
        if e["rule_includes_column"] is True:
            assert e["rule_figure_m"] == e["figure_with_column_m"], key
        elif e["rule_includes_column"] is False:
            assert e["rule_figure_m"] == e["figure_without_column_m"], key
        else:
            assert e["rule_figure_m"] is None and e["construction"] == "undeterminable", key
        if e["rule_figure_m"] is not None:
            assert e["consistent"] is (abs(e["adopted_figure_m"] - e["rule_figure_m"]) <= 0.0015), key
            assert e["agrees_within_tolerance"] is bag.within_tolerance(e["adopted_figure_m"], e["rule_figure_m"]), key
            assert e["difference_m"] == pytest.approx(e["adopted_figure_m"] - e["rule_figure_m"], abs=1e-6), key
        # a column that develops by calendar year stays in; one built by age or without development of its own is out
        if e["construction"] == "calendar_year":
            assert e["rule_includes_column"] is True and e["last_step_like_for_like"] is True, key
        if e["construction"] == "no_own_development":
            assert e["rule_includes_column"] is False and e["last_step_like_for_like"] is None, key
    assert entries["3624_2015"]["consistent"] is None and entries["3624_2015"]["agrees_within_tolerance"] is False
    assert entries["1955_2015"]["consistent"] is None and entries["1955_2015"]["agrees_within_tolerance"] is True
    assert [k for k, e in entries.items() if e["consistent"] is not True] == ["1955_2015", "3624_2015"]


def test_the_adopted_figure_is_the_primarys(entries, primary):
    """Driven by the loader, not by the register: every entry's adopted figure (in sterling) is the figure the primary
    adopts for the record, and whether the column is in it follows the register."""
    for key, e in entries.items():
        rec = primary[key]
        assert rec["pyd_gbp_m"] == pytest.approx(e["adopted_figure_gbp_m"], abs=0.0015), key
        assert rec["s_raw_a"] is not None, key


def test_1945_2022_is_the_one_record_whose_figure_moves(entries):
    e = entries["1945_2022"]
    assert (e["figure_before_this_register_m"], e["adopted_figure_m"], e["rule_figure_m"]) == (-13.84, -13.831, -13.831)
    assert e["adopted_includes_column"] is False and e["consistent"] is True and e["consistent_before"] is False
    moved = [k for k, x in entries.items() if x["adopted_figure_m"] != x["figure_before_this_register_m"]]
    assert moved == ["1945_2022"]


def test_1200_2017_keeps_the_column_by_the_analysis_sessions_decision_and_records_both_readings(entries):
    e = entries["1200_2017"]
    assert e["construction"] == "development_age" and e["adopted_figure_m"] == 44.9 and e["adopted_includes_column"]
    assert e["rule_figure_m"] == 44.9 and e["last_step_like_for_like"] is True
    assert e["readers_rule_figure_m"] == 40.5 and e["readers_rule_includes_column"] is False
    assert e["decision"].startswith("Decision of the Claude analysis session")
    assert "266.9" in e["decision"] and "UY2011" in e["decision"] and "Z2 would leave it out (40.5)" in e["decision"]
    assert sorted(r["reader"] for r in e["tie_break_readers"]) == ["Z1", "Z2"]
    assert all(r["construction"] == "development_age" for r in e["tie_break_readers"])


def test_the_tie_break_records_carry_both_tie_break_readings(entries):
    assert {k for k, e in entries.items() if e["tie_break_readers"]} == set(TIE_BREAK)
    for key, construction in TIE_BREAK.items():
        e = entries[key]
        assert e["construction"] == construction, key
        assert sorted(r["reader"] for r in e["tie_break_readers"]) == ["Z1", "Z2"], key
        assert sorted(r["reader"][0] for r in e["readers"]) == ["X", "Y"], key
    # the calendar-restated records stay in and the development-age ones stay out (1200/2017 by decision)
    for key in ("2791_2022", "2791_2023", "2791_2024", "1955_2018", "1955_2020", "1200_2015"):
        assert entries[key]["adopted_includes_column"] is True, key
    for key in ("4242_2021", "4242_2023", "2007_2015", "1945_2022"):
        assert entries[key]["adopted_includes_column"] is False, key


def test_every_entry_names_its_readers_verdicts_and_pages(entries):
    for key, e in entries.items():
        assert [r["arm"] for r in e["readers"]] == ["X", "Y"], key
        for r in e["readers"]:
            assert r["verdict"] in ("consistent", "inconsistent", "undeterminable"), (key, r["reader"])
            assert r["pages"]["year_t"] and all(isinstance(p, int) for p in r["pages"]["year_t"]), (key, r["reader"])
        assert e["pages"] and e["decision"].strip(), key
        assert e["part"] in ("A", "B") and e["adopted_figure_m"] is not None


def test_the_register_agrees_with_the_archived_readings_it_is_built_from(entries):
    """The arms' constructions and rule figures in the register are the archived readings' (normalising the readers' own
    words), and an entry the arms did not agree on has an explicit decision."""
    arms = bag.load_arm_readings()
    for key, e in entries.items():
        got = {r["reader"]: r for r in e["readers"]}
        for rid, raw in arms[key]:
            assert got[rid]["construction"] == bag.norm_construction(raw["construction"]), (key, rid)
            assert got[rid]["rule_figure_m"] == bag._num(raw.get("rule_figure_m")), (key, rid)
            assert got[rid]["verdict"] == raw["verdict"], (key, rid)
        agreed = len({r["construction"] for r in e["readers"]}) == 1 and all(
            r["verdict"] == "consistent" for r in e["readers"])
        assert agreed or key in bag.DECISIONS, key


@pytest.mark.parametrize("change", ["drop-decision-1955_2015", "drop-decision-1200_2017", "low-list-short",
                                    "low-list-extra"])
def test_the_build_refuses_an_unexplained_disagreement_or_a_low_confidence_list_that_does_not_match(monkeypatch, change):
    """Mutation check on the builder's guards: a record the arms did not settle without its decision, a low-confidence
    list that is not the decisions', stops the build."""
    if change == "drop-decision-1955_2015":
        monkeypatch.setattr(bag, "DECISIONS", {k: v for k, v in bag.DECISIONS.items() if k != "1955_2015"})
    elif change == "drop-decision-1200_2017":
        monkeypatch.setattr(bag, "DECISIONS", {k: v for k, v in bag.DECISIONS.items() if k != "1200_2017"})
    elif change == "low-list-short":
        monkeypatch.setattr(bag, "LOW_CONFIDENCE", bag.LOW_CONFIDENCE[:-1])
    else:
        monkeypatch.setattr(bag, "LOW_CONFIDENCE", bag.LOW_CONFIDENCE + ("1084_2015",))
    with pytest.raises(SystemExit):
        bag.build()


def test_a_wrong_agreed_figure_is_caught_by_the_consistency_field(monkeypatch):
    """Mutation check: move one record's adopted figure by 5m and the register says it is neither the rule's figure nor
    within the readers' tolerance; by 0.3m it is not the rule's figure but is within the tolerance."""
    monkeypatch.setattr(bag, "ADOPTED_AFTER", {"1945_2022": -13.831, "2007_2016": 60.0, "4020_2016": 25.603})
    built = bag.build()
    assert built["2007_2016"]["consistent"] is False and built["2007_2016"]["difference_m"] == pytest.approx(5.2)
    assert built["2007_2016"]["agrees_within_tolerance"] is False
    assert built["4020_2016"]["consistent"] is False and built["4020_2016"]["agrees_within_tolerance"] is True
    assert built["1945_2022"]["consistent"] is True and built["1945_2022"]["agrees_within_tolerance"] is True


def test_within_tolerance_is_half_a_million_or_one_percent():
    assert bag.within_tolerance(10.4, 10.0) and not bag.within_tolerance(10.6, 10.0)
    assert bag.within_tolerance(1004.0, 1000.0) and bag.within_tolerance(1009.0, 1000.0)
    assert not bag.within_tolerance(1011.0, 1000.0)
