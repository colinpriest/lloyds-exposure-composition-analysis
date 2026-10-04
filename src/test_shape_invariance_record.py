"""The shape-invariance record the paper cites (the review of 2 October 2026, P-17).

The size- and concentration-axis "no drift" claims rested on src/test_shape_invariance.py, which only printed, on a
legacy 348-record population. src/check_shape_invariance.py, a manifest step, writes the same statistics on the
working sample. The closing check: the record's population is the working sample the calibration is fitted on, every
interval the text summarises covers zero, and the Anderson-Darling p clears its line on both axes.

Run:  python -m pytest src/test_shape_invariance_record.py -q
"""
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import adopted_model as am  # noqa: E402
import check_shape_invariance as CSI  # noqa: E402

AXES = ("size_opening_reserves", "concentration_hhi")
STATS = ("Bowley skew", "Tail skew ratio", "Moors kurtosis")


def _record():
    with io.open(CSI.OUT, encoding="utf-8") as fh:
        return json.load(fh)


def test_the_record_is_on_the_working_sample():
    rec = _record()
    S, R, H, yr, syn, ritc = am.load_sample()
    assert rec["n"] == len(S) and rec["n_syndicates"] == len(np.unique(syn))
    assert rec["population"].startswith("adopted_model.load_sample()")


def test_every_interval_the_text_summarises_covers_zero():
    rec = _record()
    assert set(rec["axes"]) == set(AXES)
    for axis in AXES:
        a = rec["axes"][axis]
        assert a["shape_anderson_darling"]["p"] >= rec["anderson_darling_line"], axis
        for stat in STATS:
            for block in (a["top_less_bottom_quartile"][stat], a["decile_slope"][stat]):
                lo, hi = block["interval_95_cluster_bootstrap"]
                assert lo <= 0.0 <= hi, (axis, stat, lo, hi)
        assert a["no_drift"] is True
    assert rec["no_drift_on_either_axis"] is True


def test_the_verdict_follows_the_intervals():
    """A drift planted along the size axis turns the verdict; the statistics are the script's own."""
    rng = np.random.default_rng(0)
    n = 600
    R = np.exp(rng.uniform(2, 8, n))
    syn = rng.integers(0, 120, n)
    S = rng.standard_t(5, n)
    flat = CSI.run(S, R, R * 0 + 0.3 + rng.uniform(0, 0.4, n), syn, n_boot=200)
    skewed = np.where(R > np.median(R), np.abs(S) * 2.0, S)
    drift = CSI.run(skewed, R, R * 0 + 0.3 + rng.uniform(0, 0.4, n), syn, n_boot=200)
    assert drift["axes"]["size_opening_reserves"]["no_drift"] is False
    assert set(flat["axes"]) == set(AXES) and flat["n"] == n
