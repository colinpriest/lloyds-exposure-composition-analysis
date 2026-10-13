r"""Checks of scan_triangle_tables.py (the fourteenth amendment's census). Named checks_*.py, not test_*.py, so the
analysis suite (whose collection count a gate records) does not collect it; run it by name:

    LLOYDS_EXTRACTION_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider checks_scan_triangle_tables.py

The positive controls read the real records and filings: 1274/2023 and 4472/2022 must land in class B (a net table
read as gross), and 4020/2017 in class C (its printed gross triangle fails to reconcile to the filing's own gross
total). Nothing here is skipped: a missing filing or record fails.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("LLOYDS_EXTRACTION_OFFLINE", "1")
import scan_triangle_tables as st  # noqa: E402


# --- the controls, on the real records and filings ----------------------------------------------------------------

@pytest.fixture(scope="module")
def controls():
    rows = st.main(["--stems", "syndicate_1274_2023", "syndicate_4472_2022", "syndicate_4020_2017"])
    return {r["stem"]: r for r in rows}


def test_controls_all_scanned(controls):
    assert set(controls) == {"syndicate_1274_2023", "syndicate_4472_2022", "syndicate_4020_2017"}


def test_1274_2023_is_a_net_table_candidate(controls):
    r = controls["syndicate_1274_2023"]
    assert r["class"] == "B", r["reason"]
    assert r["locate"]["pages"] == [36]
    assert abs(r["co_g"] - 1141.38) < 1e-6 and abs(r["co_n"] - 939.759) < 1e-6
    assert any(abs(c["value"] - 939.759) < 1e-6 for c in r["detail"]["net_hits"])
    assert r["grid_reproduces_adopted"] and abs(r["recomputed_m"] - 58.692) < 1e-6


def test_4472_2022_is_a_net_table_candidate(controls):
    r = controls["syndicate_4472_2022"]
    assert r["class"] == "B", r["reason"]
    assert r["locate"]["pages"] == [53]
    assert abs(r["co_g"] - 3851.9) < 1e-6 and abs(r["co_n"] - 2346.0) < 1e-6
    assert any(abs(c["value"] - 2346.0) < 1e-6 for c in r["detail"]["net_hits"])
    assert not r["detail"]["gross_hits"]


def test_4020_2017_is_faulty(controls):
    r = controls["syndicate_4020_2017"]
    assert r["class"] == "C", r["reason"]
    assert abs(r["d_used"] - 2006.546) < 1e-6
    assert abs(r["i_g"] - 1935.876) < 1e-6 and abs(r["i_n"] - 1596.671) < 1e-6
    assert abs(r["co_g"] - 497.27) < 1e-6 and abs(r["co_n"] - 377.596) < 1e-6


def test_controls_have_their_reading_status(controls):
    assert controls["syndicate_1274_2023"]["reading_status"] == "draw four, random sample"
    assert controls["syndicate_4020_2017"]["reading_status"].startswith("draw four, census stratum")


# --- the rule, on placed totals ----------------------------------------------------------------------------------------

def cand(v, labelled=True, line=None):
    return {"value": v, "labelled": labelled, "single": False, "line": line or "total %s" % v}


def base(**kw):
    t = {"located": True, "co_g": 1000.0, "co_n": 700.0, "i_g": None, "i_n": None, "d_used": 5000.0, "cands": []}
    t.update(kw)
    return t


def test_gross_total_is_a():
    assert st.classify(base(cands=[cand(1000.0)]))[0] == "A"


def test_net_total_is_b():
    assert st.classify(base(cands=[cand(700.0)]))[0] == "B"


def test_neither_is_c():
    assert st.classify(base(cands=[cand(850.0)]))[0] == "C"


def test_tolerance_is_two_per_cent():
    assert st.classify(base(cands=[cand(1019.0)]))[0] == "A"      # 1.9%
    assert st.classify(base(cands=[cand(1021.0)]))[0] == "C"      # 2.1%
    assert st.classify(base(cands=[cand(713.0)]))[0] == "B"       # 1.86% of 700
    assert st.classify(base(cands=[cand(715.0)]))[0] == "C"       # 2.14% of 700


def test_nearer_basis_wins():
    # gross 1000, net 975: indistinguishable (2.5% apart) -> A by the indistinguishable rule
    assert st.classify(base(co_n=975.0, cands=[cand(980.0)]))[1].startswith("gross and net")
    # gross 1000, net 950 (5% apart): 968 is within 2% of 950 only
    assert st.classify(base(co_n=950.0, cands=[cand(968.0)]))[0] == "B"


def test_not_located_is_d():
    c, why, _ = st.classify(base(located=False, locate_why="image page"))
    assert c == "D" and "not located" in why


def test_no_printed_total_is_d():
    c, why, _ = st.classify(base(cands=[cand(123.0, labelled=False)]))
    assert c == "D" and "prints no total" in why


def test_net_not_placed_and_no_gross_match_is_d():
    c, why, _ = st.classify(base(co_n=None, cands=[cand(850.0)]))
    assert c == "D" and "net claims outstanding is not placed" in why


def test_gross_not_placed_is_d():
    c, why, _ = st.classify(base(co_g=None, cands=[cand(700.0)]))
    assert c == "D" and "gross claims outstanding" in why


def test_both_bases_in_one_block_is_d():
    c, why, _ = st.classify(base(cands=[cand(1000.0, line="a"), cand(700.0, line="b")]))
    assert c == "D" and "gross and another to net" in why


def test_a_summary_line_printing_both_binds_to_neither():
    c, _why, _ = st.classify(base(cands=[cand(1000.0, line="s"), cand(700.0, line="s")]))
    assert c == "C"


def test_diagonal_against_latest_totals():
    assert st.classify(base(i_g=5000.0, i_n=4000.0, d_used=5050.0))[0] == "A"
    assert st.classify(base(i_g=5000.0, i_n=4000.0, d_used=4010.0))[0] == "B"
    assert st.classify(base(i_g=5000.0, i_n=4000.0, d_used=5300.0))[0] == "C"


def test_gross_reserve_with_faulty_diagonal_is_c():
    c, why, _ = st.classify(base(cands=[cand(1000.0)], i_g=5000.0, i_n=4000.0, d_used=5300.0))
    assert c == "C" and "latest diagonal" in why


# --- the text and the placements ---------------------------------------------------------------------------------------

def test_amounts():
    assert st.amount("(1,234)") == -1234.0
    assert st.amount("1,141,380") == 1141380.0
    assert st.amount("765.5") == 765.5
    assert st.amount("£12,345") == 12345.0
    assert st.amount("2014") is None
    assert st.amount("-") is None
    assert st.amounts_of("At 31 December 2022 3,851.9 (1,505.9) 2,346.0") == [3851.9, -1505.9, 2346.0]


class FakeFiling:
    def __init__(self, pages):
        self.pages = {p: [st.Line(p, k, t) for k, t in enumerate(lines)] for p, lines in pages.items()}
        self.how = {p: "text layer" for p in pages}

    def lines(self):
        for p in sorted(self.pages):
            for ln in self.pages[p]:
                yield ln


STACKED = ["Gross claims", "2019 2020 2021 Total",
           "At end of underwriting year 100,000 110,000 120,000",
           "One year later 150,000 160,000",
           "Two years later 170,000",
           "Cumulative payments (120,000) (90,000) (30,000)",
           "Estimated balance to pay 50,000 70,000 90,000 210,000",
           "Net claims", "2019 2020 2021 Total",
           "At end of underwriting year 80,000 90,000 100,000",
           "One year later 120,000 130,000",
           "Two years later 140,000",
           "Cumulative payments (100,000) (80,000) (25,000)",
           "Estimated balance to pay 40,000 50,000 75,000 165,000"]


def grid(rows):
    return {"units": "thousands", "underwriting_years": [2019, 2020, 2021], "development_rows": rows}


def test_block_stops_at_the_next_table():
    f = FakeFiling({1: STACKED})
    g = grid([[100000, 110000, 120000], [150000, 160000, None], [170000, None, None]])
    loc = st.locate(f, g)
    assert loc["located"] and loc["pages"] == [1]
    vals = {c["value"] for c in st.candidates(st.block_lines(f, loc))}
    assert 210000.0 in vals and 165000.0 not in vals


def test_block_of_the_second_table():
    f = FakeFiling({1: STACKED})
    g = grid([[80000, 90000, 100000], [120000, 130000, None], [140000, None, None]])
    loc = st.locate(f, g)
    vals = {c["value"] for c in st.candidates(st.block_lines(f, loc))}
    assert 165000.0 in vals and 210000.0 not in vals


def test_paid_subtable_does_not_end_the_block():
    lines = ["Gross Claims", "2019 2020 2021 Total",
             "At the end of underwriting year 100,000 110,000 120,000",
             "One year later 150,000 160,000", "Two years later 170,000",
             "Gross paid claims position",
             "At the end of underwriting year 10,000 11,000 12,000",
             "One year later 50,000 60,000", "Two years later 90,000",
             "Gross claims reserve 80,000 100,000 108,000 288,000"]
    f = FakeFiling({1: lines})
    g = grid([[100000, 110000, 120000], [150000, 160000, None], [170000, None, None]])
    vals = {c["value"] for c in st.candidates(st.block_lines(f, st.locate(f, g)))}
    assert 288000.0 in vals


def test_a_label_wrapped_around_its_amounts_is_a_total():
    lines = ["Gross Claims", "2019 2020 2021 Total",
             "At end of underwriting year 100,000 110,000 120,000",
             "One year later 150,000 160,000", "Two years later 170,000",
             "Gross claims", "80,000 100,000 108,000 288,000", "reserve"]
    f = FakeFiling({1: lines})
    g = grid([[100000, 110000, 120000], [150000, 160000, None], [170000, None, None]])
    cs = st.candidates(st.block_lines(f, st.locate(f, g)))
    assert any(c["value"] == 288000.0 and c["labelled"] for c in cs)


def test_a_paid_row_and_a_year_row_are_not_totals():
    lines = ["Gross Claims", "2019 2020 2021 Total",
             "At end of underwriting year 100,000 110,000 120,000",
             "One year later 150,000 160,000", "Two years later 170,000",
             "Total claims paid 120,000 90,000 30,000 240,000",
             "2018 59,093 143,878 144,456"]
    f = FakeFiling({1: lines})
    g = grid([[100000, 110000, 120000], [150000, 160000, None], [170000, None, None]])
    vals = {c["value"] for c in st.candidates(st.block_lines(f, st.locate(f, g)))}
    assert 240000.0 not in vals and 30000.0 not in vals and 144456.0 not in vals


def test_claims_outstanding_from_the_movement_note():
    f = FakeFiling({1: ["13. Claims Outstanding", "Gross Reinsurers' Share Net",
                        "At 1 January 2022 3,291.5 (1,232.2) 2,059.3",
                        "Claims incurred during the year 1,140.0 (382.7) 757.3",
                        "Claims paid during the year (874.1) 231.1 (643.0)",
                        "Foreign exchange 294.5 (122.1) 172.4",
                        "At 31 December 2022 3,851.9 (1,505.9) 2,346.0"]})
    g, n = st.place_claims_outstanding(f, [3291.5], [], 2022)
    assert abs(g["value"] - 3851.9) < 1e-9 and abs(n["value"] - 2346.0) < 1e-9


def test_claims_outstanding_from_the_balance_sheet():
    f = FakeFiling({1: ["Reinsurers' share of technical provisions", "Claims outstanding 15 201,621 166,000"],
                    2: ["Technical Provisions", "Claims Outstanding 15 1,141,380 1,075,038"]})
    g, n = st.place_claims_outstanding(f, [1075.038], [], 2023)
    assert abs(g["value"] - 1141.38) < 1e-9
    assert abs(n["value"] - (1141.38 - 201.621)) < 1e-6
