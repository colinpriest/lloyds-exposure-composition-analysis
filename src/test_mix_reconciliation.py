"""Round 54 (review M01): a total row is not a class and an unreconciled mix is not a
partition. 623/2022's frozen record carried the closed 2020 year-of-account table:
classes 70.4 + 112.5 + 340.3 + 19.3 + 45.3 + 21.8 (542.5 direct + 67.1 reinsurance)
plus "Total Direct and Reinsurance accepted 609.6", against a recorded premium of
67.1. The loader normalised all positive rows and admitted the donor at HHI 0.374;
the annual table gives 0.464.

Run:  python -m pytest src/test_mix_reconciliation.py -q
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_analysis as ra  # noqa: E402

FROZEN_623 = [
    {"line_of_business": "Marine aviation and transport", "amount_gbp_m": 70.4},
    {"line_of_business": "Fire and other damage to property", "amount_gbp_m": 112.5},
    {"line_of_business": "Third party liability", "amount_gbp_m": 340.3},
    {"line_of_business": "Miscellaneous", "amount_gbp_m": 19.3},
    {"line_of_business": "Fire and other damage to property", "amount_gbp_m": 45.3},
    {"line_of_business": "Third party liability", "amount_gbp_m": 21.8},
    {"line_of_business": "Total Direct and Reinsurance accepted", "amount_gbp_m": 609.6},
]
ANNUAL_623 = [
    {"line_of_business": "Marine aviation and transport", "amount_gbp_m": 71.3},
    {"line_of_business": "Fire and other damage to property", "amount_gbp_m": 149.1},
    {"line_of_business": "Third party liability", "amount_gbp_m": 480.0},
    {"line_of_business": "Miscellaneous", "amount_gbp_m": 28.0},
    {"line_of_business": "Third party liability", "amount_gbp_m": 68.2},
    {"line_of_business": "Fire and other damage to property", "amount_gbp_m": 51.8},
    {"line_of_business": "Marine aviation and transport", "amount_gbp_m": 20.2},
]


def test_total_labels():
    for l in ("Total direct", "Total Direct and Reinsurance accepted", "Total - Direct",
              "Sub-total", "Grand total", "total"):
        assert ra.is_total_label(l), l
    assert not ra.is_total_label("Third party liability")


def test_the_frozen_623_mix_does_not_reconcile_with_its_premium():
    ok, s = ra.mix_reconciles(FROZEN_623, 67.1)
    assert not ok and abs(s - 609.6) < 0.05           # the total row is excluded from the sum
    w, src = ra.build_weight_vector(FROZEN_623, 67.1)
    assert src == "none" and w.sum() == 0


def test_the_annual_623_mix_reconciles_and_weights_sum_to_one():
    ok, s = ra.mix_reconciles(ANNUAL_623, 868.6)
    assert ok and abs(s - 868.6) < 0.05
    w, src = ra.build_weight_vector(ANNUAL_623, 868.6)
    assert src == "premium_mix" and abs(w.sum() - 1) < 1e-9
    hhi = float(np.sum(w ** 2))
    assert 0.40 < hhi < 0.52                          # the review's 0.4640 under the same coarse mapping


def test_a_total_row_beside_a_reconciling_partition_is_ignored():
    mix = ANNUAL_623 + [{"line_of_business": "Total", "amount_gbp_m": 868.6}]
    ok, _ = ra.mix_reconciles(mix, 868.6)
    assert ok
    w, src = ra.build_weight_vector(mix, 868.6)
    assert src == "premium_mix" and abs(w.sum() - 1) < 1e-9


def test_tolerance_is_ten_percent():
    assert ra.mix_reconciles([{"line_of_business": "Marine", "amount_gbp_m": 98.5}], 100.0)[0]
    assert not ra.mix_reconciles([{"line_of_business": "Marine", "amount_gbp_m": 97.5}], 100.0)[0]
    assert not ra.mix_reconciles([{"line_of_business": "Marine", "amount_gbp_m": 91.0}], 100.0)[0]  # the old 10%
    assert ra.mix_reconciles([{"line_of_business": "Marine", "amount_gbp_m": 4.85}], 5.0)[0]       # the 0.2m floor


# --- M03 (frozen review of 21 September 2026): the mix reconciles with a total another reader gave ----------------
SEVEN = [("Marine", 0.074), ("Aviation", 4.49), ("Energy-Marine", 1.376), ("Energy Non-Marine", 4.39),
         ("Fire and Other damage to Property", 6.52), ("Third party liability", 6.348), ("Reinsurance", 120.77)]
THREE = [("Fire and Other damage to Property", 6.5), ("Third party liability", 6.3), ("Energy", 1.4)]


def _mix(rows):
    return [{"line_of_business": k, "amount_gbp_m": v} for k, v in rows]


def _record(block_mix, table_mix, table_total, model_totals):
    models = {name: {"gross_premium_mix": block_mix, "gross_premiums_written_gbp_m": t}
              for name, t in zip(("a", "b"), model_totals)}
    return models, {"gross_premium_mix": table_mix, "table_total": table_total}


def test_a_partial_table_cannot_reconcile_with_itself():
    """1856/2018: the text fallback's three classes, their sum written as the table's total; the models read
    143.968m. The other readers' totals are the models', and 14.2m is not a partition of them."""
    models, table = _record(_mix(THREE), _mix(THREE), 14.2, (143.968, 143.968))
    totals = ra.premium_totals_from_other_readers(models["a"], models, "a", table)
    assert totals == [143.968, 143.968]
    assert not any(ra.mix_reconciles(_mix(THREE), t)[0] for t in totals)


def test_the_complete_table_reconciles_and_conserves_the_class_weights():
    models, table = _record(_mix(SEVEN), _mix(SEVEN), 143.968, (143.968, 143.968))
    totals = ra.premium_totals_from_other_readers(models["a"], models, "a", table)
    ok, s = ra.mix_reconciles(_mix(SEVEN), totals[0])
    assert ok and abs(s - 143.968) < 1e-9
    w, source = ra.build_weight_vector(_mix(SEVEN), totals[0])
    assert source == "premium_mix" and abs(w.sum() - 1.0) < 1e-12
    assert abs(w[ra.LOB_INDEX["Aggregate"]] - 120.77 / 143.968) < 1e-12


def test_a_models_own_mix_is_reconciled_with_another_reader_not_its_own_total():
    """When the block keeps its own mix, its own total is the same reading: the table's total or the other
    model's is the check."""
    models, table = _record(_mix(SEVEN), _mix(THREE), 14.2, (143.968, None))
    assert ra.premium_totals_from_other_readers(models["a"], models, "a", table) == [14.2]
    models, table = _record(_mix(SEVEN), _mix(THREE), None, (143.968, 143.968))
    assert ra.premium_totals_from_other_readers(models["a"], models, "a", table) == [143.968]


# --- R221, after the extraction's replay: negative classes, and the record's premium total -------------------------
#: 3624/2019 as both models read it: eight classes, four of them negative, summing with their signs to the 408.141m
#: both models read as the total. The positive classes sum to 417.386m, 2.3% over it.
MIX_3624_2019 = [("Accident and health", 0.635), ("Motor - third-party liability", -0.018),
                 ("Motor - other classes", -0.11), ("Marine aviation and transport", -1.553),
                 ("Fire and other damage to property", 3.613), ("Third-party liability", 408.883),
                 ("Credit and suretyship", 4.255), ("Reinsurance", -7.564)]


def test_negative_classes_are_part_of_the_partition():
    ok, s = ra.mix_reconciles(_mix(MIX_3624_2019), 408.141)
    assert ok and abs(s - 408.141) < 1e-9
    positive = sum(v for _, v in MIX_3624_2019 if v > 0)
    assert not ra.mix_reconciles(_mix([(k, v) for k, v in MIX_3624_2019 if v > 0]), 408.141)[0]
    w, source = ra.build_weight_vector(_mix(MIX_3624_2019), s)
    assert source == "premium_mix" and abs(w.sum() - 1.0) < 1e-12
    # the weights are the positive classes' shares: a negative class carries none
    assert abs(w[ra.classify_lob("Third-party liability")] - 408.883 / positive) < 1e-12
    assert w[ra.classify_lob("Marine aviation and transport")] == 0.0
    assert w[ra.classify_lob("Motor - other classes")] == 0.0


def test_a_mix_that_nets_to_nothing_is_no_partition():
    assert not ra.mix_reconciles(_mix([("Marine", 5.0), ("Reinsurance", -5.0)]), 0.1)[0]
    assert not ra.mix_reconciles(_mix([("Marine", 1.0), ("Reinsurance", -3.0)]), -2.0)[0]


FIXTURE_1969 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests_data",
                            "syndicate_1969_2024_round58.json")


def _load_one(tmp_path, rec, sub="records", name="syndicate_1969_2024.json"):
    import json
    import pytest
    d = tmp_path / sub
    d.mkdir()
    (d / name).write_text(json.dumps(rec), encoding="utf-8")
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(ra, "DATA_DIR", d)
        records, counters, log, _files = ra.load_and_classify()
    finally:
        mp.undo()
    return records, counters, [e for e in log if e["file"] == name]


def _fixture_1969():
    import io
    import json
    return json.load(io.open(FIXTURE_1969, encoding="utf-8"))


def test_a_block_without_a_total_takes_the_one_its_mix_reconciles_with(tmp_path):
    """1969/2024 as the round-58 extraction wrote it: the adopted gemini block read no total, gpt-5-mini read
    858.26 (USD m) and the table prints 858.26; the table's seven classes are in both blocks."""
    rec = _fixture_1969()
    gem, gpt = rec["models"]["gemini-2.5-flash"], rec["models"]["gpt-5-mini"]
    assert gem.get("gross_premiums_written_gbp_m") is None and gpt["gross_premiums_written_gbp_m"] == 858.26
    (obs,), counters, (entry,) = _load_one(tmp_path, rec)
    assert entry["status"] == "RELIABLE" and obs["model_key"] == "gemini-2.5-flash"
    assert counters["premium_total_from_another_reader"] == 1 and counters["mix_unreconciled"] == 0
    rate = obs["fx_rate_usd_per_gbp"]
    assert obs["fx_applied"] and abs(obs["gpw_gbp_m"] - 858.26 / rate) < 1e-9
    assert obs["weight_source"] == "premium_mix" and obs["hhi"] is not None


def test_a_total_that_disagrees_with_the_mix_gives_way_to_one_that_agrees(tmp_path):
    rec = _fixture_1969()
    rec["models"]["gemini-2.5-flash"]["gross_premiums_written_gbp_m"] = 958.26
    (obs,), counters, (entry,) = _load_one(tmp_path, rec)
    assert counters["premium_total_from_another_reader"] == 1
    assert abs(obs["gpw_gbp_m"] - 858.26 / obs["fx_rate_usd_per_gbp"]) < 1e-9
    rec["models"]["gemini-2.5-flash"]["gross_premiums_written_gbp_m"] = 858.4
    (obs,), counters, (entry,) = _load_one(tmp_path, rec, "own")
    assert counters["premium_total_from_another_reader"] == 0
    assert abs(obs["gpw_gbp_m"] - 858.4 / obs["fx_rate_usd_per_gbp"]) < 1e-9
