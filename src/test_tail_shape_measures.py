"""The tail diagnostics say what each one measures (frozen review of 21 September 2026, M05).

A constant rescaling of one group moves the |z| quantile ratios and no tail-shape statistic, so a
significant quantile ratio is extreme residual magnitude, not tail shape. These tests check both
properties on a rescaled copy of the same sample, and that the recorded results carry the label.
"""
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ritc_tail_shape as rts  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sample():
    return np.random.default_rng(20260921).standard_t(4, 20000)


def test_a_rescaled_copy_moves_the_quantile_ratio_by_exactly_the_scale():
    z = _sample()
    for p in (95, 99):
        assert abs(rts.q_ratio_stat(0.6 * z, p) / rts.q_ratio_stat(z, p) - 0.6) < 1e-12


def test_a_rescaled_copy_moves_no_shape_statistic():
    z = _sample()
    assert abs(rts.hill_xi(0.6 * z) - rts.hill_xi(z)) < 1e-12
    assert abs(rts.far_spread(0.6 * z) - rts.far_spread(z)) < 1e-12
    assert abs(rts.t_nu(0.6 * z) - rts.t_nu(z)) < 0.05


def test_each_statistic_is_labelled_by_what_it_measures():
    assert rts.MEASURES["q95(|z|) ratio"] == "magnitude"
    assert rts.MEASURES["q99(|z|) ratio"] == "magnitude"
    for name in ("Student-t nu (MLE)", "GPD xi (|z| exceedances)", "Hill xi (top 15% |z|)",
                 "far spread (q99-q50)/(q90-q50)"):
        assert rts.MEASURES[name] == "shape", name


def test_the_recorded_results_carry_the_label():
    res = json.load(io.open(os.path.join(ROOT, "results", "ritc_tail_shape_results.json"),
                            encoding="utf-8"))
    for pop in res.values():
        for name, r in pop["tests"].items():
            assert r.get("measures") == rts.MEASURES[name], (name, r.get("measures"))
