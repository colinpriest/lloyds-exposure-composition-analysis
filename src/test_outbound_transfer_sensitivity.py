#!/usr/bin/env python3
"""The outbound-transfer sensitivity (check_outbound_transfer_sensitivity.py).

The headline keeps R as the unadjusted opening; the sensitivity replaces it by the balance kept after an outbound
reinsurance to close for the records the register confirms, and refits. These tests hold the adjustment arithmetic,
that the amounts come from the register and nowhere else, that only the confirmed records in the sample move, that a
register entry which is not the record's is refused, and that the output carries both fits side by side.

Run:  python -m pytest src/test_outbound_transfer_sensitivity.py -q
"""
import io
import json
import os

import numpy as np
import pytest

import check_outbound_transfer_sensitivity as O

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HERE, "src", "check_outbound_transfer_sensitivity.py")


def _register(**confirmed):
    return {"confirmed": confirmed, "named_not_adjusted": {}}


# ------------------------------------------------------------------ the arithmetic ------
def test_the_retained_base_is_the_opening_less_the_transfer_in_the_reports_currency():
    keys = ["1_2020", "2_2020", "3_2021"]
    S = np.array([0.10, 0.20, -0.30])
    R = np.array([50.0, 100.0, 100.0])                    # GBP m; 3_2021 reports in USD at 1.5
    fx = {"3_2021": (True, 1.5)}
    reg = _register(**{"2_2020": {"currency": "GBP", "opening_m": 100.0, "transferred_out_m": 40.0, "page": 1},
                       "3_2021": {"currency": "USD", "opening_m": 150.0, "transferred_out_m": 75.0, "page": 2},
                       "9_2022": {"currency": "GBP", "opening_m": 10.0, "transferred_out_m": 5.0, "page": 3}})
    S2, R2, rows = O.retained_base(S, R, keys, fx, reg)
    assert R2.tolist() == [50.0, 60.0, 50.0]              # 100 - 40; (150 - 75) / 1.5
    assert S2[0] == S[0] and R2[0] == R[0], "a record the register does not list is untouched"
    assert np.allclose(S2 * R2, S * R, rtol=1e-15), "the development S * R is unchanged"
    assert S2[1] == pytest.approx(0.20 * 100 / 60) and S2[2] == pytest.approx(-0.30 * 2)
    assert rows["3_2021"]["share_transferred"] == 0.5 and rows["2_2020"]["S_after"] == S2[1]
    assert rows["9_2022"] == dict(rows["9_2022"], in_working_sample=False, applied=False)
    assert S.tolist() == [0.10, 0.20, -0.30] and R.tolist() == [50.0, 100.0, 100.0], "inputs are not modified"


@pytest.mark.parametrize("entry,why", [
    ({"currency": "GBP", "opening_m": 110.0, "transferred_out_m": 40.0, "page": 1}, "not the record's R"),
    ({"currency": "USD", "opening_m": 100.0, "transferred_out_m": 40.0, "page": 1}, "the record is GBP"),
    ({"currency": "GBP", "opening_m": 100.0, "transferred_out_m": 100.0, "page": 1}, "below the opening"),
    ({"currency": "GBP", "opening_m": 100.0, "transferred_out_m": 0.0, "page": 1}, "positive"),
])
def test_an_entry_that_is_not_the_records_is_refused(entry, why):
    with pytest.raises(SystemExit) as exc:
        O.retained_base(np.array([0.1]), np.array([100.0]), ["2_2020"], {}, _register(**{"2_2020": entry}))
    assert why in str(exc.value)


def test_the_amounts_live_in_the_register_and_nowhere_else():
    reg = O.load_register()
    src = io.open(SCRIPT, encoding="utf-8").read()
    assert set(reg["confirmed"]) == {"780_2020", "1200_2023", "1861_2019", "1861_2021", "5820_2019", "2468_2022"}
    for key, e in reg["confirmed"].items():
        assert {"currency", "opening_m", "transferred_out_m", "page", "quote"} <= set(e), key
        for amount in (e["opening_m"], e["transferred_out_m"]):
            assert repr(amount) not in src, "%s's amount %r is typed into the script" % (key, amount)
    assert not set(reg["confirmed"]) & set(reg["named_not_adjusted"])


# ------------------------------------------------------------------ the committed sample ------
@pytest.fixture(scope="module")
def committed():
    from adopted_model import load_sample
    from fx_sensitivity import fx_map
    S, R, H, yr, syn, ritc = load_sample()
    keys = ["%s_%s" % (s, y) for s, y in zip(syn, yr)]
    return S, R, keys, O.retained_base(S, R, keys, fx_map(), O.load_register())


def test_only_the_confirmed_records_in_the_sample_move(committed):
    S, R, keys, (S2, R2, rows) = committed
    reg = O.load_register()
    moved = {keys[i] for i in np.flatnonzero((S2 != S) | (R2 != R))}
    assert moved == {k for k in reg["confirmed"] if k in keys}
    assert moved == {k for k, r in rows.items() if r["applied"]}
    for k in reg["named_not_adjusted"]:
        assert k not in moved, "%s is named without an amount and must not be adjusted" % k


def test_the_retained_bases_are_the_filings_adjusted_balances(committed):
    """An independent check: three filings print the adjusted opening themselves."""
    _S, _R, _keys, (_S2, _R2, rows) = committed
    printed = {"1861_2019": 268.320, "1861_2021": 443.429, "5820_2019": 29.679}
    for key, balance in printed.items():
        assert rows[key]["R_after_gbp_m"] == pytest.approx(balance, abs=5e-4), key


#: a word each pre-corpus disposition's explanation must carry, in the row's note and in the register's own note
DISPOSITION_KEYWORD = {"IN RUNOFF": "run-off", "NO_RESERVES": "opening reserve"}


def test_a_confirmed_record_outside_the_sample_carries_the_loaders_reason(committed):
    """Round 62's verification (N-V-A-3): the register and the docstring said 2468/2022 would enter the working
    sample once its re-decided record was imported. It was imported, and the loader puts it in run-off (gross written
    premium 0), a scientific exclusion. The row now names the loader's disposition, from the ledger, and the
    register's own note must say the same."""
    S, R, keys, _unused = committed
    from fx_sensitivity import fx_map
    ledger = O.loader_dispositions()
    _S2, _R2, rows = O.retained_base(S, R, keys, fx_map(), O.load_register(), ledger)
    reg = O.load_register()["confirmed"]
    outside = [k for k in reg if k not in keys]
    assert outside == ["2468_2022"], outside
    for key in outside:
        row, disposition = rows[key], ledger[key]
        assert not disposition.startswith("CORPUS:"), (key, disposition)
        assert row["applied"] is False and row["in_working_sample"] is False
        assert row["loader_disposition"] == disposition
        word = DISPOSITION_KEYWORD[disposition]
        assert word in row["note"] and word in reg[key]["note"], (key, row["note"], reg[key]["note"])
    assert rows["2468_2022"]["loader_disposition"] == "IN RUNOFF"
    assert "scientific exclusion" in rows["2468_2022"]["note"]
    # the run-off rule as the author's decision D1 states it; "no premium mix" was false for every such record
    assert "or below 0 where the filing states run-off" in rows["2468_2022"]["note"]
    assert "the filing states run-off for the whole year, outside the RITC regime" in rows["2468_2022"]["note"]
    assert "premium mix" not in rows["2468_2022"]["note"]


def _amounts_m(quote):
    """Every amount a quote prints, in millions: "811.6" and "$180.6 million" are millions; "510,238" and
    "295,729k" are thousands."""
    import re
    out = []
    for m in re.finditer(r"\$?(\d{1,3}(?:,\d{3})+|\d+\.\d+)(k\b| million\b)?", quote):
        number, unit = m.group(1), m.group(2)
        if "," in number:
            out.append(float(number.replace(",", "")) / (1.0 if unit == " million" else 1000.0))
        else:
            out.append(float(number) / (1000.0 if unit == "k" else 1.0))
    return out


def test_each_confirmed_amount_is_the_one_its_quote_prints():
    """Round 62's verification: a register amount retyped (1200/2023's 347.8 as 348.8) passed every test. Each
    transfer must be a figure its quote prints; an "At 1 January" figure in the quote must be the opening; and an
    "Adjusted 1 January" figure must be the opening less the transfer."""
    import re
    for key, e in O.load_register()["confirmed"].items():
        quote, printed = e["quote"], _amounts_m(e["quote"])
        assert any(abs(a - e["transferred_out_m"]) < 5e-4 for a in printed), (key, e["transferred_out_m"], printed)
        opening = re.search(r"At 1 January(?: \d{4})? (\d{1,3}(?:,\d{3})+|\d+\.\d+)", quote)
        if opening:
            assert abs(_amounts_m(opening.group(1))[0] - e["opening_m"]) < 5e-4, (key, e["opening_m"])
        adjusted = re.search(r"Adjusted 1 January(?: \d{4})? (\d{1,3}(?:,\d{3})+|\d+\.\d+)", quote)
        if adjusted:
            assert abs(_amounts_m(adjusted.group(1))[0] - (e["opening_m"] - e["transferred_out_m"])) < 5e-4, key
    assert _amounts_m("reserves of 295,729k; $180.6 million; (347.8); At 1 January 510,238") == \
        [295.729, 180.6, 347.8, 510.238]


# ------------------------------------------------------------------ the output ------
def test_the_output_carries_both_fits_side_by_side(monkeypatch, tmp_path):
    """main() with the refit replaced by the calibration's means, so it runs in seconds: the shape is the point."""
    cal = json.load(io.open(str(O.CALIBRATION), encoding="utf-8"))
    seen = {}

    def fake_fit(S, R, H, yr, ritc):
        seen["S"], seen["R"] = S, R
        means = {p: float(cal[p]) * (1.01 if p == "k" else 1.0) for p in O.PARAMS}
        return means, {}, {"max_rhat": 1.0, "min_ess_bulk": 1000.0, "divergences": 0}, {}, {}

    monkeypatch.setattr(O, "OUT", tmp_path / "out.json")
    assert O.main(fit=fake_fit) == 0
    out = json.load(io.open(str(tmp_path / "out.json"), encoding="utf-8"))
    for name in ("adopted", "retained_base"):
        fit = out["fits"][name]
        for key in ("k", "sd_undiv", "gamma", "nu_clean", "nu_ritc", "V1_VaR995", "V2_change995"):
            assert isinstance(fit[key], float), (name, key)
        assert fit["operator"] == "size_only" and fit["overlay_sensitivity"]["operator"] == "overlay"
    ps = out["point_sensitivities"]
    for name in ("k", "floor", "gamma", "nu_clean", "nu_ritc", "V1_VaR995", "V2_change995"):
        assert set(ps[name]) >= {"adopted", "retained_base", "change", "pct_change"}, name
    assert ps["k"]["retained_base"] == pytest.approx(1.01 * ps["k"]["adopted"])
    assert out["n_adjusted"] == len(out["adjusted"]) == sum(r["applied"] for r in out["records"].values())
    assert all(not v["adjusted"] for v in out["named_not_adjusted"].values())
    moved = [out["records"][k] for k in out["adjusted"]]
    assert all(r["S_after"] != r["S_before"] for r in moved)
    assert int((seen["R"] != O.load_sample()[1]).sum()) == out["n_adjusted"], "the refit saw the adjusted sample"


def test_the_recorded_run_carries_the_adjusted_records():
    """DEFERRED-TO-REFIT: results/check_outbound_transfer_sensitivity_results.json is written by the recorded pass."""
    path = os.path.join(HERE, "results", "check_outbound_transfer_sensitivity_results.json")
    if not os.path.exists(path):
        pytest.skip("results/check_outbound_transfer_sensitivity_results.json not present in this checkout")
    out = json.load(io.open(path, encoding="utf-8"))
    assert out["n_adjusted"] >= 5 and set(out["fits"]) == {"adopted", "retained_base"}
    assert out["fits"]["retained_base"]["diagnostics"]["divergences"] == 0
    # the count, the list and the rows are one fact (round 62's verification: n_adjusted retyped 5 -> 6 passed)
    applied = sorted(k for k, r in out["records"].items() if r["applied"])
    assert out["n_adjusted"] == len(out["adjusted"]) == len(applied)
    assert sorted(out["adjusted"]) == applied == sorted(k for k, r in out["records"].items() if r["in_working_sample"])
    assert out["records"]["2468_2022"]["loader_disposition"] == "IN RUNOFF"
