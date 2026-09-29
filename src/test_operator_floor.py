"""The transfer operator's floored scale ratio, at concentrations away from one, in every implementation.

Until the review of 29 September 2026 (test upgrade 7) run_analysis.dispersion_adjustment was asserted on
ONE line, at H = 1, where (1/H)^gamma = 1 and the concentration exponent never acts; and the only
"size" tests exercised a floorless helper. So a wrong sign on gamma, a dropped floor at H != 1 or a lost
clip would all have passed. These tests pin the closed form

    sigma(R, H) = sqrt(su^2 + sd^2 * [(R/R_ref)(1/clip(H))^gamma]^{2(k-1)}),   ratio = sigma(t) / sigma(o)

at H_t != H_o < 1 on both sides of reference_hhi and at both clip bounds, under both transfer operators,
check that the floor matters, that R -> infinity leaves only the floor, that k = 1 is flat, and that
every Python implementation of sigma in src/ and the shipped tool's JavaScript agree on one grid with a
nonzero floor.

Run:  python -m pytest src/test_operator_floor.py -q
"""
import itertools
import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_analysis as ra                # noqa: E402
import transfer_operator                 # noqa: E402

MODEL = {"k": 0.60, "gamma": 0.35, "sd_undiv": 0.02, "sd_div": 0.06,
         "reference_size": 500.0, "reference_hhi": 0.4, "hhi_floor": 0.01, "hhi_ceil": 1.0}


@pytest.fixture(autouse=True)
def _model():
    original = ra.COMBINED_MODEL
    ra.COMBINED_MODEL = dict(MODEL, nu=4.0, nu_clean=4.0, nu_ritc=3.0, params={}, posterior_prob={}, n=1,
                             source="test_operator_floor")
    yield
    ra.COMBINED_MODEL = original


def closed_sigma(R, H, gamma, m=MODEL):
    """The operator's scale, written independently of every implementation under test."""
    h = min(max(H, m["hhi_floor"]), m["hhi_ceil"])
    x = (R / m["reference_size"]) * (1.0 / h) ** gamma
    return math.sqrt(m["sd_undiv"] ** 2 + m["sd_div"] ** 2 * x ** (2.0 * (m["k"] - 1.0)))


def closed_ratio(Rt, Ht, Ro, Ho, mode):
    g = transfer_operator.gamma_in_force(MODEL["gamma"], mode)
    return closed_sigma(Rt, Ht, g) / closed_sigma(Ro, Ho, g)


# H_t != H_o, both below one, straddling reference_hhi = 0.4 in both directions
H_PAIRS = [(0.25, 0.60), (0.60, 0.25), (0.15, 0.35), (0.80, 0.45), (0.30, 0.55)]
R_PAIRS = [(500.0, 120.0), (80.0, 2000.0), (1000.0, 1000.0), (3000.0, 450.0)]


@pytest.mark.parametrize("mode", transfer_operator.MODES)
@pytest.mark.parametrize("hp", H_PAIRS)
@pytest.mark.parametrize("rp", R_PAIRS)
def test_the_floored_ratio_is_the_closed_form_away_from_h_one(mode, hp, rp):
    (Ht, Ho), (Rt, Ro) = hp, rp
    got = ra.dispersion_adjustment(Rt, Ht, Ro, Ho, operator=mode)
    assert got == pytest.approx(closed_ratio(Rt, Ht, Ro, Ho, mode), rel=1e-12)


def test_both_sides_of_the_reference_hhi_are_exercised():
    ref = MODEL["reference_hhi"]
    assert any(ht < ref < ho for ht, ho in H_PAIRS) and any(ho < ref < ht for ht, ho in H_PAIRS)
    assert all(h < 1.0 for pair in H_PAIRS for h in pair)


def test_the_overlay_moves_with_concentration_and_the_headline_does_not():
    over = ra.dispersion_adjustment(500.0, 0.25, 500.0, 0.60, operator=transfer_operator.OVERLAY)
    head = ra.dispersion_adjustment(500.0, 0.25, 500.0, 0.60, operator=transfer_operator.SIZE_ONLY)
    assert over < 1.0 - 1e-3, "a more diversified target must shrink the scale under the overlay (gamma > 0)"
    assert head == 1.0, "at gamma = 0 a pure change of concentration moves nothing"
    assert ra.dispersion_adjustment(500.0, 0.25, 500.0, 0.60) == head, "the default operator is the headline"


@pytest.mark.parametrize("mode", transfer_operator.MODES)
def test_the_clip_bounds_hold_on_both_sides(mode):
    lo, hi = MODEL["hhi_floor"], MODEL["hhi_ceil"]
    below = ra.dispersion_adjustment(400.0, 1e-4, 900.0, 0.5, operator=mode)
    at_lo = ra.dispersion_adjustment(400.0, lo, 900.0, 0.5, operator=mode)
    above = ra.dispersion_adjustment(400.0, 0.5, 900.0, 7.0, operator=mode)
    at_hi = ra.dispersion_adjustment(400.0, 0.5, 900.0, hi, operator=mode)
    assert below == pytest.approx(at_lo, rel=1e-14)
    assert above == pytest.approx(at_hi, rel=1e-14)
    assert at_lo == pytest.approx(closed_ratio(400.0, lo, 900.0, 0.5, mode), rel=1e-12)


@pytest.mark.parametrize("mode", transfer_operator.MODES)
def test_the_floor_matters(mode):
    """The floored ratio is not the floorless power law, wherever the scales differ."""
    g = transfer_operator.gamma_in_force(MODEL["gamma"], mode)
    for (Ht, Ho), (Rt, Ro) in itertools.product(H_PAIRS, R_PAIRS):
        if Rt == Ro and (g == 0.0 or Ht == Ho):
            continue
        floored = ra.dispersion_adjustment(Rt, Ht, Ro, Ho, operator=mode)
        floorless = (Rt / Ro) ** (MODEL["k"] - 1.0) * (Ho / Ht) ** (g * (MODEL["k"] - 1.0))
        assert abs(floored - floorless) > 1e-3, (Rt, Ht, Ro, Ho, mode)


@pytest.mark.parametrize("mode", transfer_operator.MODES)
def test_an_infinitely_large_target_keeps_only_the_floor(mode):
    Ro, Ho = 150.0, 0.3
    limit = MODEL["sd_undiv"] / closed_sigma(Ro, Ho, transfer_operator.gamma_in_force(MODEL["gamma"], mode))
    got = ra.dispersion_adjustment(1e15, 0.2, Ro, Ho, operator=mode)
    assert got == pytest.approx(limit, rel=1e-6)
    assert got > 0.0, "the floor must stop the ratio falling to zero"


@pytest.mark.parametrize("mode", transfer_operator.MODES)
def test_comonotonic_pooling_is_flat(mode):
    ra.COMBINED_MODEL["k"] = 1.0
    for (Ht, Ho), (Rt, Ro) in itertools.product(H_PAIRS, R_PAIRS):
        assert ra.dispersion_adjustment(Rt, Ht, Ro, Ho, operator=mode) == pytest.approx(1.0, abs=1e-15)


# ------------------------------------------------ every implementation, one grid ------
GRID = [(R, H) for R in (30.0, 180.0, 500.0, 1400.0, 4200.0) for H in (0.005, 0.12, 0.4, 0.73, 1.0)]


def python_sigmas(mode):
    """sigma on GRID from each Python implementation in src/, gamma in force for `mode`."""
    import vignette_uncertainty as vu
    import dispersion_mle as dm
    import worked_example_donor as we
    import check_vignette2_sign as v2
    import make_paper_figures as mf
    import adopted_model as am
    import check_pooling_cv_extended as pcv
    g = transfer_operator.gamma_in_force(MODEL["gamma"], mode)
    k, su, sd = MODEL["k"], MODEL["sd_undiv"], MODEL["sd_div"]
    ref, lo, hi = MODEL["reference_size"], MODEL["hhi_floor"], MODEL["hhi_ceil"]
    R = np.array([r for r, _ in GRID]); H = np.array([h for _, h in GRID])
    out = {
        "vignette_uncertainty.sigma_theta": vu.sigma_theta(R, H, k, g, su, sd, ref, lo, hi),
        "dispersion_mle.sigma": dm.sigma(R, H, k, g, su, sd),
        "worked_example_donor.sigma": we.sigma(R, H, k, g, su, sd, ref, lo, hi),
        "check_vignette2_sign.sigma": v2.sigma(R, H, k, g, su, sd, ref, lo, hi),
        "make_paper_figures.sigma": mf.sigma(R, H, {"k": k, "gamma": g, "sd_undiv": su, "sd_div": sd}),
        "adopted_model.sigma_numeric": am.sigma_numeric(R, H, np.zeros(len(R)), {
            "k": k, "gamma": g, "sd_undiv": su, "sd_div": sd, "beta_ritc": 0.0}),
        "check_pooling_cv_extended.sigma_draws": pcv.sigma_draws(R, H, {
            "k": np.array([k]), "gamma": np.array([g]), "sd_undiv": np.array([su]),
            "sd_div": np.array([sd])})[:, 0],
    }
    return {name: np.asarray(v, float) for name, v in out.items()}


@pytest.mark.parametrize("mode", transfer_operator.MODES)
def test_every_python_sigma_is_the_closed_form(mode):
    g = transfer_operator.gamma_in_force(MODEL["gamma"], mode)
    want = np.array([closed_sigma(r, h, g) for r, h in GRID])
    for name, got in python_sigmas(mode).items():
        assert np.allclose(got, want, rtol=1e-12, atol=0), name


@pytest.mark.parametrize("mode", transfer_operator.MODES)
def test_the_tools_javascript_is_the_same_operator_on_the_grid(mode):
    """The shipped tool's sigmaSys and transferLambda, under node, against the Python operator, with a floor."""
    import json
    from test_distortion_tool import harness
    data = {"pooling_model": dict(MODEL, nu_clean=4.0, nu_ritc=3.0)}
    body = ("const grid = %s;\n"
            "console.log(JSON.stringify({s: grid.map(p => sigmaSys(p[0], p[1])),"
            " l: grid.map(p => transferLambda(p[0], p[1], 250.0, 0.33))}));" % json.dumps(GRID))
    got = harness(body, data, mode=mode)
    g = transfer_operator.gamma_in_force(MODEL["gamma"], mode)
    want_s = [closed_sigma(r, h, g) for r, h in GRID]
    want_l = [closed_sigma(r, h, g) / closed_sigma(250.0, 0.33, g) for r, h in GRID]
    assert np.allclose(got["s"], want_s, rtol=1e-12, atol=0)
    assert np.allclose(got["l"], want_l, rtol=1e-12, atol=0)
    py = [ra.dispersion_adjustment(r, h, 250.0, 0.33, operator=mode) for r, h in GRID]
    assert np.allclose(got["l"], py, rtol=1e-12, atol=0), "the tool and run_analysis disagree"
