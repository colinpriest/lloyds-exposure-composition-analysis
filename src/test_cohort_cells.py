#!/usr/bin/env python3
"""The per-cohort cells of the register figures (the cohort-depth repair of 26 October 2026).

A register figure that no stored grid computes (a corrected or confirmed table) carries the cells it is the sum of, so that
the cohort-depth sensitivity can take the figure on u <= t-3 from the register. The loader checks its own register
(run_analysis.cohort_cells_gaps); this file holds the register to the evidence:

  * every entry that carries cohort_cells sums to its figure on u <= t-2, at the table's rounding, and every term follows
    from its printed cells (a derived term states its basis);
  * every printed cell string appears in the entry's quote or in the record's section of the archived second reading
    (results/.../round9/depth/second_reading.md) or, for the census's 3330 figures, in the round-9 readings L4 and Z12:
    a transcription slip fails here;
  * the committed registers equal what build_mature_cohort_figures.py builds from DEPTH_CELLS (no drift between the two);
  * the loader refuses a block whose terms do not follow from their cells or do not sum to the figure.

Run:  python -m pytest src/test_cohort_cells.py -q
"""
import copy
import io
import json
import os
import re

import pytest

import build_mature_cohort_figures as bm
import run_analysis as ra

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUND9 = os.path.join(HERE, "results", "extraction_error_rate", "mature-cohort", "round9")
EXPECTED = ["1274_2016", "1274_2022", "1609_2023", "1991_2018", "2232_2020", "318_2024", "3330_2017", "3330_2018",
            "3334_2018", "3500_2018", "382_2015", "382_2016", "382_2017", "382_2018", "382_2019", "382_2020", "4242_2022",
            "4444_2022", "4472_2022", "4472_2023"]


def _read(rel):
    with io.open(os.path.join(HERE, *rel.split("/")), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def registers():
    conf = json.loads(_read("data/pyd_confirmed_figures.json"))
    mature = json.loads(_read("data/mature_cohort_figures.json"))
    out = {}
    for name, reg in (("data/pyd_confirmed_figures.json", conf), ("data/mature_cohort_figures.json", mature)):
        for k, e in reg.items():
            if not k.startswith("_") and isinstance(e, dict) and "cohort_cells" in e:
                assert k not in out, k
                out[k] = (name, e)
    return out


def _second_reading_section(key):
    text = _read("results/extraction_error_rate/mature-cohort/round9/depth/second_reading.md")
    head = "## %s " % key.replace("_", "/")
    i = text.find(head)
    if i < 0:
        return ""
    j = text.find("\n## ", i + 3)
    return text[i:j if j > 0 else len(text)]


def test_the_cells_are_on_exactly_the_twenty_records_no_stored_grid_reproduces(registers):
    assert sorted(registers) == EXPECTED
    assert registers["1274_2016"][0] == "data/mature_cohort_figures.json" and registers["382_2015"][0] == "data/pyd_confirmed_figures.json"


def test_every_entrys_cells_sum_to_its_figure_and_every_term_follows_from_its_cells(registers):
    for key, (_name, e) in registers.items():
        cc = e["cohort_cells"]
        assert ra.cohort_cells_gaps(e) == [], key
        total = ra.cohort_cells_figure_m(cc, 2)
        assert total == pytest.approx(e["figure_m"], abs=ra.COHORT_CELLS_TOL), (key, total, e["figure_m"])
        assert cc["report_year"] == int(key.split("_")[1]) and cc["agree"] is True and len(cc["readings"]) == 2, key
        derived = [t["u"] for t in cc["terms"] if t.get("derived")]
        assert derived == ([2012] if key == "1274_2016" else ([[2011, 2012]] if key == "3330_2017" else [])), key
        for t in cc["terms"]:
            if t.get("derived"):
                assert t["basis"].strip(), key
                continue
            want = ra.cohort_cells_term_value(t, cc["table_kind"])
            assert t["term"] == pytest.approx(want, abs=1e-6), (key, t)
        # every term's year is a mature one at t-2
        assert all((max(x["u"]) if isinstance(x["u"], list) else x["u"]) <= cc["report_year"] - 2 for x in cc["terms"]), key


def test_every_printed_cell_is_in_the_entrys_quote_or_the_archived_second_reading(registers):
    """A cell string that is in neither is a transcription slip (the cells are what two independent readings quote)."""
    for key, (_name, e) in registers.items():
        cc = e["cohort_cells"]
        evidence = e["quote"] + " " + _second_reading_section(key)
        if key in ("3330_2017", "3330_2018"):
            for rid in ("L4", "Z12"):
                evidence += " " + json.dumps(json.loads(_read("results/extraction_error_rate/mature-cohort/round9/readings/%s.json" % rid))[key],
                                             ensure_ascii=False)
        assert evidence.strip(), key
        for s in ra._cohort_cells_cell_strings(cc):
            assert re.search(r"(?<![\d.,])%s(?![\d]|,\d|\.\d)" % re.escape(s), evidence), (key, s)
    # the pattern is strict: a cell off by one digit is not found
    assert not re.search(r"(?<![\d.,])763\.6(?!\d|,\d|\.\d)", registers["4472_2022"][1]["quote"] + _second_reading_section("4472_2022"))


def test_the_two_readings_of_each_depth_record_agree_on_the_figure():
    """The first reading (depth/audit.md) and the second (depth/second_reading.md) both give the u <= t-2 and u <= t-3
    figures the register's cells give (the second reading's summary table)."""
    second = _read("results/extraction_error_rate/mature-cohort/round9/depth/second_reading.md")
    audit = _read("results/extraction_error_rate/mature-cohort/round9/depth/audit.md")
    reg = json.loads(_read("data/pyd_confirmed_figures.json"))
    for key, t3 in (("1274_2022", "+27,851"), ("1991_2018", "+4,085"), ("3334_2018", "-14"), ("3500_2018", "-408"),
                    ("382_2015", "+3,649"), ("382_2019", "-9,557"), ("4444_2022", "+9,387"), ("4472_2023", "+73.2"),
                    ("4472_2022", "+97.6")):
        label = key.replace("_", "/")
        row = [ln for ln in second.splitlines() if ln.startswith("| %s " % label)]
        assert row and t3 in row[0], (key, t3)
        cc = reg[key]["cohort_cells"]
        v = ra.cohort_cells_figure_m(cc, 3) * (1000.0 if cc["unit"] == "000" else 1.0)
        assert v == pytest.approx(float(t3.replace(",", "")), abs=1e-6), key
        assert label in audit


def test_the_committed_registers_equal_what_the_builder_builds_from_its_cells():
    conf = _read("data/pyd_confirmed_figures.json")
    assert conf == bm.confirmed_with_cells(conf)
    for key in bm.DEPTH_CELLS:
        reg = json.loads(conf)
        if key in reg:
            assert reg[key]["cohort_cells"] == bm.cohort_cells_block(key), key


@pytest.mark.parametrize("change", ["term-value", "cell-string", "missing-readings", "unit", "kind", "year-after-report",
                                    "derived-without-basis", "duplicate-year", "sum-off", "no-terms"])
def test_the_loader_refuses_a_cohort_cells_block_that_does_not_follow_from_its_cells(registers, change):
    e = copy.deepcopy(registers["382_2016"][1])
    cc = e["cohort_cells"]
    if change == "term-value":
        cc["terms"][0]["term"] += 0.5
    elif change == "cell-string":
        cc["terms"][1]["movement"] = "(1,000)"
    elif change == "missing-readings":
        cc["readings"] = cc["readings"][:1]
    elif change == "unit":
        cc["unit"] = "bn"
    elif change == "kind":
        cc["table_kind"] = "triangle"
    elif change == "year-after-report":
        cc["terms"][0]["u"] = 2020
    elif change == "derived-without-basis":
        cc["terms"][0]["derived"] = True
    elif change == "duplicate-year":
        cc["terms"][1]["u"] = cc["terms"][0]["u"]
    elif change == "sum-off":
        cc["terms"][2]["term"] = 0.0
        cc["terms"][2]["movement"] = "0"
    else:
        cc["terms"] = []
    assert ra.cohort_cells_gaps(e) != []
    assert ra.cohort_cells_gaps(registers["382_2016"][1]) == [], "the unmutated entry has none"


def test_an_empty_older_set_is_none_not_zero(registers):
    """cohort_cells_figure_m returns None when no term is that old; the depth script reads None as 'no figure at t-3'."""
    cc = registers["1609_2023"][1]["cohort_cells"]
    assert ra.cohort_cells_figure_m(cc, 2) == pytest.approx(8.834)
    assert ra.cohort_cells_figure_m(cc, 3) is None
    one = registers["3500_2018"][1]["cohort_cells"]
    assert ra.cohort_cells_figure_m(one, 3) == pytest.approx(ra.cohort_cells_figure_m(one, 2)) == pytest.approx(-0.408)
    agg = registers["3330_2017"][1]["cohort_cells"]
    assert ra.cohort_cells_figure_m(agg, 3) == pytest.approx(0.559)
    assert ra.cohort_cells_figure_m(agg, 6) is None, "an aggregate term counts only when every one of its years does"
