r"""Checks of scan_grid_shape.py (the fifteenth amendment's grid shape check). Named checks_*.py, not test_*.py, so the
analysis suite (whose collection count a gate records) does not collect it; run it by name:

    LLOYDS_EXTRACTION_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider checks_scan_grid_shape.py

The positive control reads the real record: 4444/2022's raw stored grid sits one underwriting year early and must be a
shape-fail by S4, S5 and S6, and already registered. Three grids two readings found correct (draw four, verdict
"correct") must pass. The rule is held on synthetic grids. Nothing here is skipped: a missing record fails.
"""
import json
import io
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("LLOYDS_EXTRACTION_OFFLINE", "1")
import scan_grid_shape as sg  # noqa: E402

GOOD = ("syndicate_1176_2024", "syndicate_1218_2020", "syndicate_1221_2020")


# --- the controls, on the real records -------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def controls():
    rows = sg.main(["--stems", "syndicate_4444_2022"] + list(GOOD))
    return {r["stem"]: r for r in rows}


def test_controls_all_scanned(controls):
    assert set(controls) == {"syndicate_4444_2022"} | set(GOOD)


def test_4444_2022_raw_grid_is_a_shape_fail(controls):
    r = controls["syndicate_4444_2022"]
    assert r["class"] == "shape-fail", r["reasons"]
    failed = {x.split(":")[0] for x in r["reasons"]}
    assert failed == {"S4", "S5", "S6"}, r["reasons"]
    assert "one row up" in r["detail"]["tests"]["S4"]["detail"]
    assert r["raw_route"] == "code_triangle" and r["grid_field"] == "_claims_triangle"
    assert r["grid_model"] == "gemini-2.5-flash"
    assert abs(r["raw_m"] - 435.491) < 1e-6
    assert abs(r["detail"]["tests"]["S7"]["recomputed_m"] - 435.491) < 1e-6


def test_4444_2022_is_already_registered(controls):
    r = controls["syndicate_4444_2022"]
    assert r["registered"] and r["shape_fail_status"] == "already registered"
    assert abs(r["adopted_m"] - 34.9) < 1e-6 and abs(r["register_entry"]["figure_m"] - 34.9) < 1e-6


@pytest.mark.parametrize("stem", GOOD)
def test_known_good_grids_pass(controls, stem):
    r = controls[stem]
    assert r["class"] == "pass", r["reasons"]
    assert r["shape_fail_status"] is None
    assert all(c["status"] == "on" or c["status"].startswith("untested") for c in r["detail"]["columns"])


def test_population_is_the_census_population():
    W, pop, _loader, outside = sg.population()
    assert len(W) == 674 and len(pop) == 573
    assert sum(outside.values()) == 674 - 573


def test_written_output_is_whole():
    out = json.load(io.open(str(sg.OUT), encoding="utf-8"))
    assert out["population"]["n"] == 573 == len(out["records"])
    assert sum(out["counts"].values()) == 573
    conf = sg.load(sg.AN / "data" / "pyd_confirmed_figures.json")
    for r in out["records"]:
        key = r["stem"].replace("syndicate_", "")
        assert r["registered"] == (key in conf)
        if r["class"] == "shape-fail":
            assert r["shape_fail_status"] == ("already registered" if key in conf else "open")
        else:
            assert r["shape_fail_status"] is None
    s4444 = [r for r in out["records"] if r["stem"] == "syndicate_4444_2022"][0]
    assert s4444["class"] == "shape-fail"


# --- the rule, on synthetic grids ------------------------------------------------------------------------------------

def tri(years, t, scale=1.0, shift=0, width=None):
    """A cumulative triangle in the stored layout: columns are underwriting years, rows development ages. Column y
    holds t - y + 1 cells (capped at width); `shift` moves the labels (-1: one year early)."""
    width = width or len(years)
    cols = []
    for y in years:
        n = min(t - y + 1, width)
        cols.append([100.0 * (y - years[0] + 1) * scale + 10.0 * k for k in range(max(n, 0))])
    rows = [[(c[r] if r < len(c) else None) for c in cols] for r in range(width)]
    return {"underwriting_years": [y + shift for y in years], "development_rows": rows, "units": "millions"}


def rec(grid, t, raw):
    return sg.shape_tests(grid, t, raw, recompute=lambda g, tt, r: r)


def failed(res):
    return {x.split(":")[0] for x in res[1]}


def test_correct_staircase_passes():
    g = tri(list(range(2013, 2023)), 2022)
    assert rec(g, 2022, 1.0)[0] == "pass"


def test_labels_one_year_early_fail_s4_s5_s6():
    g = tri(list(range(2013, 2022)), 2021)       # a staircase that ends at 2021 ...
    # ... read as the 2022 report's, with an empty 2022 column, as 4444/2022's grid is
    g["underwriting_years"].append(2022)
    for r in g["development_rows"]:
        r.append(None)
    cls, reasons, d = rec(g, 2022, 1.0)
    assert cls == "shape-fail" and failed((cls, reasons)) == {"S4", "S5", "S6"}


def test_labels_one_year_late_fail_s4():
    g = tri(list(range(2013, 2022)), 2022, width=9)   # 2013..2021 developed to 2022, labelled a year late
    g["underwriting_years"] = list(range(2014, 2023))
    cls, reasons, _ = rec(g, 2022, 1.0)
    assert cls == "shape-fail" and "S4" in failed((cls, reasons)) and "S1" not in failed((cls, reasons))
    assert "one row down" in [x for x in reasons if x.startswith("S4")][0]


def test_label_after_t_holding_cells_fails_s1():
    g = tri(list(range(2014, 2023)), 2022)
    g["underwriting_years"][-1] = 2023
    assert "S1" in failed(rec(g, 2022, 1.0))


def test_duplicated_label_fails_s1():
    g = tri(list(range(2014, 2023)), 2022)
    g["underwriting_years"][0] = 2015
    assert "S1" in failed(rec(g, 2022, 1.0))


def test_unlabelled_values_fail_s2():
    g = tri(list(range(2014, 2023)), 2022)
    g["development_rows"][0].append(55.0)
    assert failed(rec(g, 2022, 1.0)) == {"S2"}


def test_label_gap_fails_s3():
    g = tri([2014, 2015, 2016, 2018, 2019, 2020], 2022)
    assert failed(rec(g, 2022, 1.0)) == {"S3"}


def test_one_mature_column_off_its_diagonal_fails_s6_only():
    g = tri(list(range(2013, 2023)), 2022)
    c = g["underwriting_years"].index(2016)
    g["development_rows"][6][c] = None              # 2016's diagonal cell (row 6) lost
    assert failed(rec(g, 2022, 1.0)) == {"S6"}


def test_printed_estimate_places_a_short_column():
    g = tri(list(range(2013, 2023)), 2022)
    c = g["underwriting_years"].index(2016)
    g["development_rows"][6][c] = None
    g["current_estimate_row"] = [None] * 10
    g["current_estimate_row"][c] = 999.0            # stands in for the missing diagonal cell
    assert rec(g, 2022, 1.0)[0] == "pass"


def test_printed_estimate_places_a_cell_beyond():
    g = tri(list(range(2013, 2023)), 2022)
    c = g["underwriting_years"].index(2016)
    g["development_rows"][7][c] = 7.0               # a stray cell beyond the staircase
    assert failed(rec(g, 2022, 1.0)) == {"S6"}
    g["current_estimate_row"] = [None] * 10
    g["current_estimate_row"][c] = g["development_rows"][6][c]
    assert rec(g, 2022, 1.0)[0] == "pass"


def test_young_column_off_diagonal_is_not_s6():
    g = tri(list(range(2013, 2023)), 2022)
    c = g["underwriting_years"].index(2021)
    g["development_rows"][1][c] = None              # 2021 (not mature) one short
    assert rec(g, 2022, 1.0)[0] == "pass"


def test_reproduction_fails_s7():
    g = tri(list(range(2013, 2023)), 2022)
    res = sg.shape_tests(g, 2022, 50.0, recompute=lambda gg, tt, r: 40.0)
    assert failed(res) == {"S7"}
    res = sg.shape_tests(g, 2022, 50.0, recompute=lambda gg, tt, r: 48.0)   # within 5%
    assert res[0] == "pass"


def test_default_recompute_is_the_census_recompute():
    g = tri(list(range(2013, 2023)), 2022)
    # each mature column (2013..2020) develops by 10 in its last step: 8 columns x 10
    assert abs(sg.default_recompute(g, 2022, 80.0) - 80.0) < 1e-9


def test_zero_cells_are_dashes():
    g = tri(list(range(2013, 2023)), 2022)
    c = g["underwriting_years"].index(2015)
    g["development_rows"][8][c] = 0.0               # a dash read as nil beyond 2015's diagonal (row 7)
    assert rec(g, 2022, 1.0)[0] == "pass"


def test_trailing_empty_rows_are_dropped_and_old_columns_beyond_the_grid_untested():
    g = tri(list(range(2010, 2023)), 2022, width=10)    # 13 years, 10 development rows: 2010..2012 capped
    g["development_rows"].append([None] * 13)
    cls, reasons, d = rec(g, 2022, 1.0)
    assert cls == "pass", reasons
    assert d["n_rows"] == 10
    assert sum(1 for c in d["columns"] if c["status"].startswith("untested")) == 3


def test_code_triangle_grid_is_the_named_models():
    a, b = tri([2019, 2020, 2021, 2022], 2022), tri([2018, 2019, 2020, 2021, 2022], 2022)
    data = {"models": {"m-canonical": {"_claims_triangle": a}, "m-other": {"_claims_triangle": b}}}
    route = {"source": "code_triangle", "note": "OVERRIDE from m-other triangle"}
    g, field, model = sg.tested_grid(data, "m-canonical", route)
    assert g is b and field == "_claims_triangle" and model == "m-other"
    g, field, model = sg.tested_grid(data, "m-canonical", {"source": "code_triangle", "note": None})
    assert g is a and model == "m-canonical"


def test_not_checkable():
    assert sg.shape_tests(None, 2022, 1.0)[0] == "not checkable"
    assert sg.shape_tests({"underwriting_years": [], "development_rows": [[1, 2]]}, 2022, 1.0)[1] == \
        ["the grid has no integer labels"]
    one = {"underwriting_years": [2020, 2021], "development_rows": [[5.0, 6.0]]}
    assert sg.shape_tests(one, 2022, 1.0)[1] == ["the grid has fewer than two development rows"]
