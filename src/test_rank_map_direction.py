"""The rank map is described by what it does in both orderings (frozen review, 21 September 2026, M06).

The adopted refit reads the RITC regime as the lighter at the posterior mean, so the map fattens an
RITC donor's tail there; the producers had described it as thinning, unconditionally.
"""
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vignette_uncertainty as vu  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _map(nu_ritc, nu_clean):
    z = np.array([-6.0, -3.0, 0.0, 3.0, 6.0])
    return z, vu.deritc_resid(z, {"nu_ritc": nu_ritc, "nu_clean": nu_clean}, np.ones(5, bool))


def test_a_heavier_ritc_tail_is_thinned():
    z, m = _map(3.0, 6.0)
    assert np.all(np.abs(m[[0, 1, 3, 4]]) < np.abs(z[[0, 1, 3, 4]]))


def test_a_lighter_ritc_tail_is_fattened():
    z, m = _map(6.0, 3.0)
    assert np.all(np.abs(m[[0, 1, 3, 4]]) > np.abs(z[[0, 1, 3, 4]]))


def test_zero_is_fixed_and_signs_are_kept_in_both_orderings():
    for a, b in ((3.0, 6.0), (6.0, 3.0)):
        z, m = _map(a, b)
        assert m[2] == 0.0 and np.all(np.sign(m) == np.sign(z))


def test_no_producer_says_the_map_thins_unconditionally():
    for rel in ("src/vignette_uncertainty.py", "src/make_v1_ritc_survivor.py",
                "src/calibrate_dispersion_ritc.py"):
        text = " ".join(io.open(os.path.join(ROOT, rel), encoding="utf-8").read().split())
        assert "tail thinned from" not in text and "tails thinned to" not in text, rel
        assert "that regime is heavier" not in text, rel
    res = json.load(io.open(os.path.join(ROOT, "results", "vignette_uncertainty_results.json"),
                            encoding="utf-8"))
    label = json.dumps(res)
    assert "tail thinned from" not in label
