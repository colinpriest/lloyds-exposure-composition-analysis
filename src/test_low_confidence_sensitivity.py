#!/usr/bin/env python3
"""The least-certain-records sensitivity (round 2 of the filing readings, 23 October 2026).

  * the records are read from the two registers, never typed: the six older-years columns marked low_confidence in
    data/aggregated_column_review.json and the four exchange lines marked undeterminable_kept in
    data/fx_untranslated_excluded.json; changing a register changes the set;
  * every one is a record of the primary working sample, and a key outside it is refused (sample_scope.refit_without);
  * the script is in the manifest after the vignette record it checks against, and declares its output;
  * the committed record (DEFERRED-TO-REFIT: written by the recorded pass).

Run:  python -m pytest src/test_low_confidence_sensitivity.py -q
"""
import copy
import io
import json
import os
import sys

import pytest

import check_low_confidence_sensitivity as LC
import sample_scope as SS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import reproduce  # noqa: E402

COLUMNS = ["33_2015", "1200_2015", "1200_2017", "1955_2018", "2007_2015", "3624_2015"]
EXCHANGE = ["457_2015", "1301_2015", "4711_2017", "6105_2015"]


def _registers():
    return SS.load_json(LC.COLUMN_REGISTER), SS.load_json(LC.FX_REGISTER)


def test_the_ten_records_are_read_from_the_two_registers():
    cols, fx = _registers()
    named, c, e = LC.named_records(cols, fx)
    assert sorted(c, key=SS.order_key) == sorted(COLUMNS, key=SS.order_key)
    assert sorted(e, key=SS.order_key) == sorted(EXCHANGE, key=SS.order_key)
    assert sorted(named) == sorted(COLUMNS + EXCHANGE) and len(named) == 10
    for k, why in named.items():
        assert why.strip(), k


def test_every_named_record_is_in_the_primary_working_sample():
    """The primary's membership (model/exposure_results.json): all ten are in it, so the refit can drop them."""
    named, _c, _e = LC.named_records(*_registers())
    keys = {SS.key_of(o) for o in SS.primary()}
    assert sorted(set(named) - keys) == []


def test_the_set_follows_the_registers_not_a_list_in_the_script():
    """Mutation check: lowering one record's confidence, or raising another's, or changing an exchange reason, changes
    the set; so does a register with none."""
    cols, fx = _registers()
    c2 = copy.deepcopy(cols)
    c2["1084_2015"]["confidence"] = "low_confidence"
    c2["33_2015"]["confidence"] = "high"
    f2 = copy.deepcopy(fx)
    f2["read_and_kept"]["457_2015"]["reason"] = "table_retranslated"
    f2["read_and_kept"]["1084_2015"]["reason"] = "undeterminable_kept"
    named, c, e = LC.named_records(c2, f2)
    assert sorted(c) == sorted(set(COLUMNS) - {"33_2015"} | {"1084_2015"})
    assert sorted(e) == sorted(set(EXCHANGE) - {"457_2015"} | {"1084_2015"})
    assert sorted(named) == sorted(set(c) | set(e))
    assert "1084_2015" in named and "(" in named["1084_2015"] and " | " in named["1084_2015"]
    empty = LC.named_records({"_rule": "x"}, {"read_and_kept": {}})
    assert empty == ({}, [], [])


def test_an_entry_without_the_marker_is_not_named():
    cols, fx = _registers()
    assert set(LC.column_records({"_x": 1, **{k: v for k, v in cols.items() if not k.startswith("_")}})) == set(COLUMNS)
    assert LC.column_records({k: {kk: vv for kk, vv in v.items() if kk != "confidence"}
                              for k, v in cols.items() if not k.startswith("_")}) == {}
    assert LC.exchange_records({"read_and_kept": {"1_2015": {"reason": "no_fx_line_printed"}}}) == {}


def test_a_record_outside_the_primary_stops_the_refit(monkeypatch):
    import check_cohort_scope as CS
    s, y = 1, 2015
    ob = {"syndicate": s, "year": y, "s_raw_a": 0.01, "opening_reserves_gbp_m": 100.0, "hhi": 0.3, "pyd_basis": "gross",
          "pyd_cohort_scope": "mature-enforced"}
    monkeypatch.setattr(CS, "load", lambda: [ob, dict(ob, syndicate=2)])
    with pytest.raises(SystemExit, match="not in the primary"):
        SS.refit_without(["457_2015"], "x", "y")


def test_the_step_follows_the_vignette_record_and_declares_its_output():
    order = [sc for sc, _, _ in reproduce.STEPS]
    me = "check_low_confidence_sensitivity.py"
    assert order.count(me) == 1
    assert order.index(me) > order.index("check_gamma0_vignette.py") > -1
    assert order.index(me) > order.index("check_bucket_share_sensitivity.py")
    assert reproduce.OUTPUTS[me] == ("results/check_low_confidence_sensitivity_results.json",)
    assert str(LC.OUT).replace("\\", "/").endswith("results/check_low_confidence_sensitivity_results.json")


def test_the_script_refuses_to_run_with_no_named_record(monkeypatch):
    monkeypatch.setattr(LC, "named_records", lambda c, f: ({}, [], []))
    with pytest.raises(SystemExit, match="nothing to leave out"):
        LC.compute()


# ------------------------------------------------------------------ the committed record (DEFERRED-TO-REFIT)
def test_the_low_confidence_record():
    """DEFERRED-TO-REFIT: written by the recorded pass."""
    with io.open(os.path.join(HERE, "results", "check_low_confidence_sensitivity_results.json"), encoding="utf-8") as fh:
        rec = json.load(fh)
    assert rec["n_left_out"] == rec["named_records"] == len(rec["left_out"]) == 10
    assert rec["n_fit"] == rec["n_primary"] - 10
    assert sorted(r["record"] for r in rec["left_out"]) == sorted(COLUMNS + EXCHANGE)
    assert rec["older_years_columns_low_confidence"] == sorted(COLUMNS, key=SS.order_key)
    assert rec["exchange_lines_undeterminable"] == sorted(EXCHANGE, key=SS.order_key)
    d = rec["fit_convergence"]
    assert d["divergences"] == 0 and d["max_rhat"] <= 1.01
    v = rec["vignettes"]
    for q, c in v["centre"].items():
        assert v["relative_to_primary"][q] == pytest.approx(c / v["primary_centre"][q] - 1), q
    assert v["pool"]["n_donors"] == rec["n_fit"]
    assert (rec["operator"], rec["operator_role"]) == ("size_only", "headline")
    # the record was made from these registers, byte for byte
    for rel, h in rec["inputs_sha256"].items():
        assert LC.sha256(os.path.join(HERE, *rel.split("/"))) == h, rel
