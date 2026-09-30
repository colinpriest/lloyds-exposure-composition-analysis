r"""The active-syndicate denominator (market_active.py; FIX4 scope items 2, 3 and 4).

The official lists for 2020-2024 in data/market_active_syndicates.json lacked Syndicate 33 (Hiscox) in every year,
while the extraction's workbook built from Lloyd's official files lists it: the workbook minus the file was {33}
each year. The coverage figure and the systemic-share note typed their own copies of the counts, so repairing the
file alone would not have reached them. These tests hold the file to the workbook, every consumer to the one module,
the appendix's account of the off-list records to what their filings state, and the provenance note's count of
filings without a dual-model output to the loader's.

Run:  python -m pytest src/test_market_active.py -q
"""
import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import openpyxl  # noqa: E402
import pytest  # noqa: E402

import build_current_results as bcr  # noqa: E402
import generate_data_audit as gda  # noqa: E402
import make_paper_figures as MPF  # noqa: E402
import market_active  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def workbook():
    return openpyxl.load_workbook(str(market_active.WORKBOOK), read_only=True, data_only=True)


def _sheet(wb, year):
    return {int(r[0]) for r in list(wb[str(year)].iter_rows(values_only=True))[1:] if isinstance(r[0], (int, float))}


def _overview(wb):
    """{year: (SFCR active count, the file's own list count)} from the workbook's Overview sheet."""
    out = {}
    for r in wb["Overview"].iter_rows(values_only=True):
        cells = [x for x in r if x is not None]
        if len(cells) >= 3 and isinstance(cells[0], int) and 2014 <= cells[0] <= 2024:
            out[cells[0]] = (cells[1], cells[2])
    return out


def test_the_official_lists_are_the_workbooks_sheets(workbook):
    lists = market_active.official_lists()
    assert sorted(lists) == [2020, 2021, 2022, 2023, 2024]
    for year, listed in lists.items():
        assert listed == _sheet(workbook, year), year


def test_syndicate_33_is_listed_every_year():
    assert all(33 in listed for listed in market_active.official_lists().values())


def test_the_counts_are_the_workbooks_own(workbook):
    """The annual reports' counts before 2020 are the workbook's SFCR column; the official lists' lengths are its
    count of each year's list (98/92/93/95/95), which the file missing Syndicate 33 fell one short of."""
    overview = _overview(workbook)
    active = market_active.active_by_year()
    for year in range(2014, 2020):
        assert active[year] == market_active.MARKET_AR[year] == overview[year][0], year
    for year in range(2020, 2025):
        assert active[year] == overview[year][1], year
    assert market_active.active_total() == sum(active.values())


def test_every_coverage_figure_reads_the_one_denominator(monkeypatch, tmp_path):
    """A list with 50 syndicates a year must reach the coverage figure's bars, the provenance note's coverage and
    the data audit: none of them may carry its own copy."""
    fake = tmp_path / "lists.json"
    fake.write_text(json.dumps({str(y): list(range(1, 51)) for y in range(2020, 2025)}), encoding="utf-8")
    monkeypatch.setattr(market_active, "LIST", fake)
    yr = np.array([2020, 2021, 2024])
    fig, ax, _legend = MPF.coverage_figure(yr, {2020: 1, 2021: 1, 2024: 1})
    heights = [p.get_height() for p in ax.containers[0]]
    plt.close(fig)
    assert heights[-5:] == [50] * 5 and heights[:6] == [market_active.MARKET_AR[y] for y in range(2014, 2020)]
    assert bcr._active_by_year()[2022] == 50
    assert gda.compute()["market"][2022] == 50


def test_the_systemic_share_note_counts_the_active_years():
    import check_systemic_share as css
    assert css.N_ACTIVE == market_active.active_total()


# ---- scope item 3: the off-list records' account ---------------------------------------------------------------

REGISTER = {"1884_2023": {"category": "WHOLE"}, "1110_2024": {"category": "PART"}, "780_2020": {"category": "AFTER"},
            "2014_2020": {"category": "NOTCOUNT"}}


def test_the_off_list_account_is_what_the_filings_state():
    text = gda.offlist_sentence(["1110_2023", "1110_2024", "1884_2023", "2014_2020"], REGISTER)
    assert text == ("Of the 4 corpus records whose syndicate is not on that year's list, 2 have filings that state "
                    "that the syndicate is in run-off or has ceased underwriting (1110/2024, 1884/2023; the "
                    "corpus-wide run-off register, `pdf_extraction/audit/runoff_corpus_register.json`), and for 2 "
                    "the register reads no such statement (1110/2023, 2014/2020).")
    assert "run-off years" not in text and "run-off syndicates" not in text


def test_the_off_list_account_counts_one_record_and_none():
    assert gda.offlist_sentence(["780_2020"], REGISTER).startswith(
        "Of the 1 corpus record whose syndicate is not on that year's list, 1 has a filing that states that")
    assert gda.offlist_sentence(["2014_2020"], REGISTER).startswith(
        "Of the 1 corpus record whose syndicate is not on that year's list, none has a filing that states")
    assert gda.offlist_sentence([], REGISTER) == "Every corpus record's syndicate is on that year's list."


def test_the_appendix_prints_the_off_list_account(monkeypatch):
    """The appendix said the off-list records "are run-off syndicates that still file accounts" (FIX4 scope item 3):
    it now prints what their filings state, from the register it reads."""
    c, r = gda.compute(), gda.mine_raw()
    monkeypatch.setattr(gda, "load_runoff_corpus_register", lambda: REGISTER)
    text = gda.md(c, r)
    assert "  " + gda.offlist_sentence(c["offlist"], REGISTER) in text
    assert "run-off syndicates that still file accounts" not in text


def test_the_off_list_records_are_the_corpus_less_the_lists():
    c = gda.compute()
    lists = market_active.official_lists()
    obs = json.load(io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8"))["observations"]
    expected = sorted("%d_%d" % (o["syndicate"], o["year"]) for o in obs
                      if o["year"] in lists and o["syndicate"] not in lists[o["year"]])
    assert sorted(c["offlist"]) == expected
    assert sum(e["extra"] for e in c["diff"].values()) == len(expected)


# ---- scope item 4: the provenance note's count of filings without a dual-model output ---------------------------

def test_the_provenance_note_counts_the_loaders_filings_without_a_dual_model_output():
    ex = json.load(io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8"))
    doc = io.open(os.path.join(HERE, "docs", "data-provenance.md"), encoding="utf-8").read()
    fresh = bcr.provenance_clauses(doc, ex)
    n = ex["disposition_flow"]["files_without_dual_model_record_overlapping_audit_count"]
    assert "The %d filings with no usable dual-model output cannot all be labelled OCR failures" % n in fresh
    planted = fresh.replace("The %d filings with no usable" % n, "The 128 filings with no usable")
    assert bcr.provenance_clauses(planted, ex) == fresh
