#!/usr/bin/env python3
"""The scope sensitivities of the adjudication of 22 October 2026: the earned basis (Q4) and the older-years bucket (Q5).

  * bucket_share.py, the share of gross reserves outside the years the stored grid develops: each method on a
    hand-built case, the order in which they decide, the year-by-year reconciliation of two disagreeing measures, and
    the records the adjudication said should be read before they are trusted;
  * check_earned_basis_sensitivity.py: the named records are the adjudication's, and the population count;
  * sample_scope.py: a record to leave out must be a primary record, and the primary must be the mature-cohort one;
  * the committed records (DEFERRED-TO-REFIT: written by the recorded pass).

Run:  python -m pytest src/test_scope_sensitivities.py -q
"""
import io
import json
import os

import numpy as np
import pytest

import bucket_share as BK
import check_bucket_share_sensitivity as BS
import check_earned_basis_sensitivity as EB
import sample_scope as SS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ bucket_share: the methods
def test_a_lines_cells_are_read_from_its_own_text_dashes_included():
    cells, scale = BK.line_cells("financial position 81,688 - - 2,418 9,379 18,386 111,871",
                                 [81.688, 2.418, 9.379, 18.386, 111.871])
    assert cells == [81.688, None, None, 2.418, 9.379, 18.386, 111.871] and scale == pytest.approx(1000.0)
    cells, _ = BK.line_cells("Provision as at 31 December 2020 4,890 7,683 491,323", [4.89, 7.683, 491.323])
    assert cells == [4.89, 7.683, 491.323]
    assert BK.line_cells("Gross reserves 1,234 5,678", [1.234, 9.999]) == (None, None)


def test_a_reserve_line_against_the_grid():
    latest = [100.0, 100.0, 100.0]
    # as many year cells as the grid has years, and a total: every reserve is in a developed year
    share, how, dev = BK.reserve_line_share([10.0, 20.0, 30.0, 60.0], 60.0, latest)
    assert share == pytest.approx(0.0) and dev == [10.0, 20.0, 30.0] and "oldest_first" in how
    # one more cell, the oldest: an older-years bucket outside the grid
    share, how, dev = BK.reserve_line_share([40.0, 10.0, 20.0, 30.0, 100.0], 100.0, latest)
    assert share == pytest.approx(0.4) and dev == [10.0, 20.0, 30.0]
    # printed newest first: only that ordering keeps each year within its incurred estimate
    share, how, dev = BK.reserve_line_share([30.0, 20.0, 5.0, 300.0], 355.0, [10.0, 25.0, 40.0])
    assert "newest_first" in how and dev == [5.0, 20.0, 30.0] and share == pytest.approx(1 - 55.0 / 355.0)
    # the last cell is CO_g and more than the others: a total that holds an older amount not printed by year
    share, _how, dev = BK.reserve_line_share([10.0, 20.0, 30.0, 100.0], 100.0, latest)
    assert dev == [10.0, 20.0, 30.0] and share == pytest.approx(0.4)
    assert BK.reserve_line_share([10.0, 20.0], 30.0, latest)[1] == "fewer_cells"
    assert BK.reserve_line_share([500.0, 20.0, 30.0], 550.0, latest)[1] == "no_ordering"


def test_two_orderings_that_disagree_are_decided_by_the_reserve_pattern_or_not_at_all():
    latest = [100.0, 100.0, 100.0, 100.0]
    # oldest first, the reserve-to-incurred ratio rises; read newest first it falls
    share, how, _ = BK.reserve_line_share([50.0, 5.0, 20.0, 40.0, 60.0], 175.0, latest)
    assert "oldest_first" in how and share == pytest.approx(1 - 125.0 / 175.0)
    share, why, dev = BK.reserve_line_share([50.0, 50.0, 50.0, 50.0, 49.0], 249.0, latest)
    assert (share, why, dev) == (None, "ambiguous_ordering", None)


def test_payments_cells_and_the_year_by_year_reconciliation():
    # a last amount that is not the others' total is a fourth year
    assert BK.payments_cells("Less gross claims paid (60.7) (58.6) (63.6) (298.4)", 1.0, 3) is None
    assert BK.payments_cells("Less gross claims paid (60.7) (58.6) (63.6) (182.9)", 1.0, 3) == [60.7, 58.6, 63.6]
    # an extra older column: not the grid's years
    assert BK.payments_cells("Less gross claims paid 22,254 3,022 138 25,414", 1000.0, 2) is None
    # a total cut short by the OCR is dropped
    assert BK.payments_cells("Less gross claims paid 244,181 317,391 2,343,42", 1000.0, 2) == [244.181, 317.391]
    latest, paid = [80.0, 110.0, 100.0], [65.8, 79.3, 63.3]
    folded = [27.1, 30.7, 36.7]                          # 2011's cell holds 12.9 more than 80.0 - 65.8
    assert BK.reconcile_by_year(latest, paid, folded)[0] == "folded"
    assert BK.reconcile_by_year(latest, paid, folded)[1] == pytest.approx(12.9)
    assert BK.reconcile_by_year(latest, paid, [14.2, 30.7, 50.0]) == ("paid", [2])
    assert BK.reconcile_by_year(latest, paid, [14.2, 30.7, 36.7]) == ("agree", None)


def test_a_bucket_line_and_an_eye_placement():
    share, _ = BK.bucket_line_share(["p33: Provision in respect of prior years 357,415"], 1513.556, 1000.0)
    assert share == pytest.approx(357.415 / 1513.556)
    for line in ("p34: Change in prior year provisions 25,459 8,014", "p32: Net ultimate claims reserve - 2010 & prior 18,579",
                 "p55: Provision in respect of prior years 160,76", "p41: earned to date for 2010 & Prior 9.0",
                 "p40: Provision in respect of prior years net of reinsurance 12,345",
                 "p40: Provision in respect of prior years 12,345 net of reinsurance",
                 "p40: Provision in respect of prior years 1,234 released in the year"):
        assert BK.bucket_line_share([line], 100.0, 1000.0) == (None, None), line
    share, _ = BK.eye_bucket_share(["Total Gross claims reserve (670,419) [= Gross claims reserve total (584,167) + "
                                    "Gross claims reserve for 2010 and prior years (86,252)]"])
    assert share == pytest.approx(86.252 / 670.419)


def test_the_methods_decide_in_order_and_the_others_are_kept_beside():
    census = {"co_g": 100.0, "class": "A", "canonical_model": "m", "grid_field": "_rag_triangle", "grid_scale": 1.0,
              "paid_line": "Less gross claims paid (50.0) (40.0) (30.0)",
              "detail": {"gross_hits": [{"line": "Gross reserves 10.0 20.0 30.0 60.0", "single": False,
                                         "line_values": [10.0, 20.0, 30.0, 60.0]}]}}
    rec = {"models": {"m": {"_rag_triangle": {"underwriting_years": [2014, 2015, 2016], "units": "millions",
                                              "development_rows": [[60.0, 60.0, 60.0], [60.0, 60.0, None],
                                                                   [60.0, None, None]]}}}}
    row = BK.measure("1_2016", census, {"uncovered_share": 0.4}, {}, rec)
    assert row["method"] == "design_dlp" and row["share"] == 0.4 and set(row["other_methods"]) == {"reserve_line"}
    row = BK.measure("780_2016", census, {"uncovered_share": 0.4}, {}, rec)
    assert row["method"] == "reading" and row["share"] == BK.READER_SHARES["780_2016"]
    row = BK.measure("1_2016", None, {}, {}, None)
    assert row["share"] is None and row["reasons_unmeasured"] == ["not_in_census"]


# ------------------------------------------------------------------ bucket_share: the population's records
@pytest.fixture(scope="module")
def measured():
    keys = ["1492_2023", "5678_2016", "1176_2022", "1084_2015", "33_2016", "2008_2023", "1206_2016", "727_2017"]
    return BK.measure_all(keys, BS.census_records(), SS.load_json(SS.POP_MEASURES), SS.load_json(SS.POP_CLASSIFIED),
                          BS.load_record)


def test_the_three_records_the_adjudication_said_to_read_before_trusting(measured):
    """1492/2023 (70%), 5678/2016 (70%) and 1176/2022 (59%) in the design's measure: 1492/2023's 'paid' line is its
    reserve line, which covers CO_g; 1176/2022's payments line has a column the grid does not; 5678/2016 stands."""
    assert measured["1492_2023"]["method"] == "reserve_line" and measured["1492_2023"]["share"] == 0.0
    assert measured["1176_2022"]["method"] == "reserve_line"
    assert measured["1176_2022"]["share"] == pytest.approx(0.555 / 38.646, abs=1e-6)
    assert measured["5678_2016"]["share"] == pytest.approx(81.688 / 111.871, rel=1e-3)


def test_the_measures_agree_where_a_reader_or_the_design_measured(measured):
    assert measured["1084_2015"]["method"] == "reading"
    assert measured["1084_2015"]["other_methods"]["reserve_line"] == pytest.approx(0.17, abs=0.005)
    assert measured["33_2016"]["method"] == "design_dlp" and measured["33_2016"]["share"] == pytest.approx(0.2361)
    # an older-years amount folded into the oldest cell: the payments measure keeps it, the reserve line cannot see it
    for k in ("2008_2023", "1206_2016"):
        assert measured[k]["method"] == "design_dlp" and measured[k]["other_methods"]["reserve_line"] < 0.02, k
    assert "folded" in measured["2008_2023"]["detail"]


def test_the_distribution_counts_the_lines_and_the_unmeasured():
    rows = {"a": {"share": 0.5, "method": "x", "reasons_unmeasured": []},
            "b": {"share": 0.05, "method": "x", "reasons_unmeasured": []},
            "c": {"share": 0.0, "method": "y", "reasons_unmeasured": []},
            "d": {"share": None, "method": None, "reasons_unmeasured": ["single_total", "bucket_unplaced"]}}
    d = BK.distribution(rows)
    assert (d["n"], d["n_measured"], d["n_unmeasured"]) == (4, 3, 1)
    assert (d["n_above_2_pct"], d["n_above_10_pct"], d["n_above_30_pct"]) == (2, 1, 1)
    assert d["by_method"] == {"x": 2, "y": 1} and d["reasons_unmeasured"] == {"single_total": 1, "bucket_unplaced": 1}


# ------------------------------------------------------------------ the earned basis
def test_the_named_records_are_the_adjudications_21():
    assert len(EB.NAMED) == 21
    assert set(EB.NAMED) == ({"1699_2024", "2015_2021", "5820_2015", "5820_2017"}
                             | {"1225_%d" % y for y in range(2016, 2023)} | {"2121_%d" % y for y in range(2015, 2025)})
    with io.open(os.path.join(HERE, "results", "extraction_error_rate", "mature-cohort", "adjudication.md"),
                 encoding="utf-8") as _fh:
        text = _fh.read()
    for phrase in ("1699/2024, 2015/2021, 1225/2016, 1225/2017-2022, 2121/2015-2024 (10), 5820/2015 and 2017: about 21",
                   "1699/2024, 2015/2021 and 780/2016 were found only by reading"):
        assert phrase in text


def test_the_earned_population_count():
    classified = {"1_2020": {"earned": "earned-basis table", "late_earning_wording": False},
                  "2_2020": {"earned": "no earned wording found", "late_earning_wording": True},
                  "1699_2024": {"earned": "no earned wording found", "late_earning_wording": False},
                  "3_2020": {"earned": "first diagonal earned", "late_earning_wording": False}}
    out = EB.earned_population(["1_2020", "2_2020", "1699_2024", "3_2020", "9_2020"], classified)
    assert out["earned_basis_tables_by_wording"] == 1 and out["found_only_by_reading"] == ["1699_2024"]
    assert out["earned_basis_tables_lower_bound"] == 2 and out["earned_basis_tables"] == ["1_2020", "1699_2024"]
    assert out["not_classified"] == ["9_2020"] and out["late_earning_wording"] == 1
    assert out["first_diagonal_only_earned"] == 1


# ------------------------------------------------------------------ sample_scope
def _obs(key, scope="mature-enforced"):
    s, y = (int(x) for x in key.split("_"))
    return {"syndicate": s, "year": y, "s_raw_a": 0.01, "opening_reserves_gbp_m": 100.0, "hhi": 0.3,
            "pyd_basis": "gross", "pyd_cohort_scope": scope}


def test_a_record_to_leave_out_must_be_a_primary_record(monkeypatch):
    import check_cohort_scope as CS
    monkeypatch.setattr(CS, "load", lambda: [_obs("1_2020"), _obs("2_2020")])
    with pytest.raises(SystemExit, match="not in the primary"):
        SS.refit_without(["1_2020", "3_2020"], "x", "y")


def test_the_primary_must_be_the_mature_cohort_outcome(monkeypatch):
    import check_cohort_scope as CS
    monkeypatch.setattr(CS, "load", lambda: [_obs("1_2020"), _obs("2_2020", "disclosed-prior-year")])
    with pytest.raises(SystemExit, match="not the primary outcome"):
        SS.primary()


# ------------------------------------------------------------------ the committed records (DEFERRED-TO-REFIT)
def _rec(name):
    with io.open(os.path.join(HERE, "results", name), encoding="utf-8") as _fh:
        return json.load(_fh)


def _check_refit_block(rec, n_left):
    assert rec["n_left_out"] == n_left == len(rec["left_out"]) and rec["n_fit"] == rec["n_primary"] - n_left
    d = rec["fit_convergence"]
    assert d["divergences"] == 0 and d["max_rhat"] <= 1.01
    v = rec["vignettes"]
    for q, c in v["centre"].items():
        assert v["relative_to_primary"][q] == pytest.approx(c / v["primary_centre"][q] - 1), q
    assert v["pool"]["n_donors"] == rec["n_fit"]
    assert (rec["operator"], rec["operator_role"]) == ("size_only", "headline")


def test_the_earned_basis_record():
    """DEFERRED-TO-REFIT: written by the recorded pass."""
    rec = _rec("check_earned_basis_sensitivity_results.json")
    _check_refit_block(rec, 21)
    assert sorted(r["record"] for r in rec["left_out"]) == sorted(EB.NAMED)
    p = rec["earned_basis_population"]
    assert p["n_primary"] == rec["n_primary"] and p["earned_basis_tables_lower_bound"] == len(p["earned_basis_tables"])


def test_the_bucket_share_record():
    """DEFERRED-TO-REFIT: written by the recorded pass."""
    rec = _rec("check_bucket_share_sensitivity_results.json")
    d = rec["distribution"]
    assert d["n"] == rec["n_primary"] == d["n_measured"] + d["n_unmeasured"]
    assert d["n_measured"] == len(rec["by_record"]) and d["n_unmeasured"] == len(rec["unmeasured"])
    above = sorted((k for k, r in rec["by_record"].items() if r["share"] > BS.THRESHOLD), key=SS.order_key)
    assert above == rec["above_threshold"] and d["n_above_30_pct"] == len(above)
    _check_refit_block(rec, len(above))
    assert [r["record"] for r in rec["left_out"]] == above
