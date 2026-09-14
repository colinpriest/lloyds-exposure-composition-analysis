#!/usr/bin/env python3
"""Tests for the Bayesian GPD return level: its sampler must reach the posterior it reports.

The fit sampled the GPD shape xi freely. The likelihood is -inf wherever 1 + xi*y/sigma <= 0
for an exceedance y, i.e. below xi = -sigma/max(y), so that edge was a hard wall inside the
sampled space: NUTS reported 18 divergent transitions in each fit at target_accept 0.97, and
the record's tail-shape label, read off the median, called the tail heavy while the shape's
interval spanned zero. The appendix table generator repeated both. So:

  * the recorded fits have no divergent transitions and converged chains;
  * the source samples xi above its support bound, on an offset whose log-Jacobian enters the
    target with the prior density on xi itself, and no longer samples xi freely;
  * the record's shape label says what the 95% interval resolves;
  * the appendix note's shape sentence follows the intervals in the record.

The paths are module globals, so a mutation check can point each test at an altered copy.

Run:  python -m pytest src/test_bayesian_gpd.py -q
"""
import io
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(HERE, "results", "bayesian_gpd_results.json")
SOURCE = os.path.join(HERE, "src", "bayesian_gpd.py")
APPENDIX = os.path.join(HERE, "figures", "appendix_c_tail_comparison.tex")
TARGETS = ("V1_adjusted", "V2_new")


def _fits():
    d = json.load(io.open(RESULTS, encoding="utf-8"))["distributions"]
    assert set(TARGETS) <= set(d), sorted(d)
    return d


def test_the_recorded_fits_have_no_divergent_transitions():
    for name, fit in _fits().items():
        assert fit["divergences"] == 0, (name, fit["divergences"])
        assert fit["max_rhat"] <= 1.01, (name, fit["max_rhat"])


def test_the_shape_is_sampled_above_its_support_bound():
    src = " ".join(io.open(SOURCE, encoding="utf-8").read().split())
    assert 'pm.Normal("xi"' not in src, "xi is sampled freely again"
    assert "-sigma / ymax + pm.math.exp(eta)" in src
    assert "pm.logp(pm.Normal.dist(0.0, 0.5), xi) + eta" in src


def test_the_offset_map_has_the_log_jacobian_the_potential_adds():
    """xi = -sigma/ymax + exp(eta): at fixed sigma, dxi/deta = exp(eta), so log|J| = eta, and
    every eta maps above the bound."""
    rng = np.random.default_rng(7)
    ymax = 0.4
    for sigma, eta in zip(rng.uniform(0.02, 0.2, 200), rng.normal(0.0, 3.0, 200)):
        xi = lambda e: -sigma / ymax + np.exp(e)
        assert xi(eta) > -sigma / ymax
        h = 1e-6
        slope = (xi(eta + h) - xi(eta - h)) / (2 * h)
        assert abs(np.log(slope) - eta) < 1e-5, (sigma, eta, slope)


def test_the_shape_label_follows_its_interval():
    for name, fit in _fits().items():
        lo, hi, label = fit["xi_2.5"], fit["xi_97.5"], fit["tail_shape"]
        if lo > 0:
            assert label.startswith("heavy"), (name, lo, hi, label)
        elif hi < 0:
            assert label.startswith("bounded"), (name, lo, hi, label)
        else:
            assert label.startswith("not resolved"), (name, lo, hi, label)


def test_the_appendix_note_follows_the_shape_intervals():
    fits = _fits()
    flat = " ".join(io.open(APPENDIX, encoding="utf-8").read().split())
    spans = all(fits[t]["xi_2.5"] <= 0 <= fits[t]["xi_97.5"] for t in TARGETS)
    if spans:
        assert "credibly heavy" not in flat
        assert "not resolved" in flat
        for t in TARGETS:
            assert "[%+.2f,%+.2f]" % (fits[t]["xi_2.5"], fits[t]["xi_97.5"]) in flat, t
    elif all(fits[t]["xi_2.5"] > 0 for t in TARGETS):
        assert "credibly heavy" in flat
