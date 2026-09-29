#!/usr/bin/env python3
"""The size effect's floorless comparator is a fitted law (check_pooling_cv_extended.size_ratio_block).

The manuscript compared the adopted 100m-to-2,000m scale ratio with "about 3.56x a floorless power law", which
was the adopted k with the floor deleted, (2000/100)^(1-k): a counterfactual no fit produced (review of
29 September 2026, M-6). The block now records the ratio under the fitted floorless model (M7) and the
floored one (M1), over draws and at posterior means, and keeps the counterfactual labelled as not a fit.

Run:  python -m pytest src/test_size_ratio_block.py -q
"""
import io
import json
import os

import numpy as np
import pytest

import check_pooling_cv_extended as P

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _draws(k, gamma, su, sd, n=40, seed=0):
    rng = np.random.default_rng(seed)
    j = lambda x: x * (1.0 + 0.02 * rng.standard_normal(n)) if x else np.zeros(n)
    return {"k": j(k), "gamma": j(gamma), "sd_undiv": j(su), "sd_div": j(sd), "nu": np.full(n, 4.0)}


@pytest.fixture
def full():
    return {"M1_free_k_floor": {"_draws": _draws(0.60, 0.3, 0.02, 0.06, seed=1)},
            "M7_free_k_nofloor": {"_draws": _draws(0.70, 0.3, 0.0, 0.06, seed=2)}}


@pytest.mark.parametrize("H", [0.1, 0.4, 0.9])
def test_without_a_floor_the_ratio_is_the_power_law_at_any_concentration(full, H):
    out = P.size_ratio_block(full, Hbar_ratio=H)
    k7 = float(np.mean(full["M7_free_k_nofloor"]["_draws"]["k"]))
    assert out["M7_free_k_nofloor"]["ratio_at_posterior_means"] == pytest.approx(20.0 ** (1.0 - k7), rel=1e-12)


def test_the_floor_shrinks_the_size_effect(full):
    out = P.size_ratio_block(full)
    k1 = float(np.mean(full["M1_free_k_floor"]["_draws"]["k"]))
    assert 1.0 < out["M1_free_k_floor"]["ratio_at_posterior_means"] < 20.0 ** (1.0 - k1)


def test_the_draws_summary_brackets_its_mean(full):
    out = P.size_ratio_block(full)
    for name in ("M1_free_k_floor", "M7_free_k_nofloor"):
        lo, hi = out[name]["ratio_hdi95"]
        assert lo <= out[name]["ratio_mean_over_draws"] <= hi


def test_the_counterfactual_is_the_adopted_k_and_says_it_is_not_a_fit(full):
    cal = json.load(io.open(os.path.join(HERE, "model", "dispersion_calibration_ritc.json"), encoding="utf-8"))
    out = P.size_ratio_block(full)
    cf = out["adopted_k_floor_deleted"]
    assert cf["k"] == cal["k"] and cf["ratio"] == pytest.approx(20.0 ** (1.0 - cal["k"]), rel=1e-12)
    assert "not a fit" in cf["note"]
    assert (out["R_small_m"], out["R_large_m"], out["H"]) == (100.0, 2000.0, P.RATIO_H) and P.RATIO_H == 0.4


def test_the_recorded_block_is_the_fitted_comparator():
    """DEFERRED-TO-REFIT: results/check_pooling_cv_extended_results.json carries size_ratio_100_2000."""
    rec = json.load(io.open(os.path.join(HERE, "results", "check_pooling_cv_extended_results.json"),
                            encoding="utf-8"))
    blk = rec["size_ratio_100_2000"]
    for name in ("M1_free_k_floor", "M7_free_k_nofloor"):
        assert set(blk[name]) == {"ratio_mean_over_draws", "ratio_hdi95", "ratio_at_posterior_means"}
    assert blk["M7_free_k_nofloor"]["ratio_at_posterior_means"] < blk["adopted_k_floor_deleted"]["ratio"]
