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
    assert ra.mix_reconciles([{"line_of_business": "Marine", "amount_gbp_m": 91.0}], 100.0)[0]
    assert not ra.mix_reconciles([{"line_of_business": "Marine", "amount_gbp_m": 89.0}], 100.0)[0]
