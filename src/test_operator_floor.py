"""The transfer operator's floored scale ratio, at concentrations away from one, in every implementation.

Until the review of 29 September 2026 (test upgrade 7) run_analysis.dispersion_adjustment was asserted on
ONE line, at H = 1, where (1/H)^gamma = 1 and the concentration exponent never acts; and the only
"size" tests exercised a floorless helper. So a wrong sign on gamma, a dropped floor at H != 1 or a lost
clip would all have passed. These tests pin the closed form

    sigma(R, H) = sqrt(su^2 + sd^2 * [(R/R_ref)(1/clip(H))^gamma]^{2(k-1)}),   ratio = sigma(t) / sigma(o)

at H_t != H_o < 1 on both sides of reference_hhi and at both clip bounds, under both transfer operators (each from
its own fit since option B, 10 October 2026: the headline's gamma is 0, the overlay's the gamma-free fit's),
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
    """Each operator's own fit: the headline with gamma = 0 and the gamma-free fit with MODEL's gamma, the other
    parameters equal, so the two modes differ in gamma alone."""
    original = ra.COMBINED_MODEL, ra.COMBINED_MODEL_OVERLAY
    extra = dict(nu=4.0, nu_clean=4.0, nu_ritc=3.0, params={}, posterior_prob={}, n=1, source="test_operator_floor")
    ra.COMBINED_MODEL = dict(MODEL, gamma=0.0, **extra)
    ra.COMBINED_MODEL_OVERLAY = dict(MODEL, **extra)
    yield
    ra.COMBINED_MODEL, ra.COMBINED_MODEL_OVERLAY = original


def gamma_for(mode):
    """The gamma each operator's own fit carries here."""
    return transfer_operator.gamma_in_force(0.0 if mode == transfer_operator.SIZE_ONLY else MODEL["gamma"], mode)


def closed_sigma(R, H, gamma, m=MODEL):
    """The operator's scale, written independently of every implementation under test."""
    h = min(max(H, m["hhi_floor"]), m["hhi_ceil"])
    x = (R / m["reference_size"]) * (1.0 / h) ** gamma
    return math.sqrt(m["sd_undiv"] ** 2 + m["sd_div"] ** 2 * x ** (2.0 * (m["k"] - 1.0)))


def closed_ratio(Rt, Ht, Ro, Ho, mode):
    g = gamma_for(mode)
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
    g = gamma_for(mode)
    for (Ht, Ho), (Rt, Ro) in itertools.product(H_PAIRS, R_PAIRS):
        if Rt == Ro and (g == 0.0 or Ht == Ho):
            continue
        floored = ra.dispersion_adjustment(Rt, Ht, Ro, Ho, operator=mode)
        floorless = (Rt / Ro) ** (MODEL["k"] - 1.0) * (Ho / Ht) ** (g * (MODEL["k"] - 1.0))
        assert abs(floored - floorless) > 1e-3, (Rt, Ht, Ro, Ho, mode)


@pytest.mark.parametrize("mode", transfer_operator.MODES)
def test_an_infinitely_large_target_keeps_only_the_floor(mode):
    Ro, Ho = 150.0, 0.3
    limit = MODEL["sd_undiv"] / closed_sigma(Ro, Ho, gamma_for(mode))
    got = ra.dispersion_adjustment(1e15, 0.2, Ro, Ho, operator=mode)
    assert got == pytest.approx(limit, rel=1e-6)
    assert got > 0.0, "the floor must stop the ratio falling to zero"


@pytest.mark.parametrize("mode", transfer_operator.MODES)
def test_comonotonic_pooling_is_flat(mode):
    ra.COMBINED_MODEL["k"] = 1.0
    ra.COMBINED_MODEL_OVERLAY["k"] = 1.0
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
    g = gamma_for(mode)
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
    g = gamma_for(mode)
    want = np.array([closed_sigma(r, h, g) for r, h in GRID])
    for name, got in python_sigmas(mode).items():
        assert np.allclose(got, want, rtol=1e-12, atol=0), name


@pytest.mark.parametrize("mode", transfer_operator.MODES)
def test_the_tools_javascript_is_the_same_operator_on_the_grid(mode):
    """The shipped tool's sigmaSys and transferLambda, under node, against the Python operator, with a floor."""
    import json
    from test_distortion_tool import harness
    data = {"pooling_model": dict(MODEL, gamma=0.0, nu_clean=4.0, nu_ritc=3.0),
            "pooling_model_overlay": dict(MODEL, nu_clean=4.0, nu_ritc=3.0)}
    body = ("const grid = %s;\n"
            "console.log(JSON.stringify({s: grid.map(p => sigmaSys(p[0], p[1])),"
            " l: grid.map(p => transferLambda(p[0], p[1], 250.0, 0.33))}));" % json.dumps(GRID))
    got = harness(body, data, mode=mode)
    g = gamma_for(mode)
    want_s = [closed_sigma(r, h, g) for r, h in GRID]
    want_l = [closed_sigma(r, h, g) / closed_sigma(250.0, 0.33, g) for r, h in GRID]
    assert np.allclose(got["s"], want_s, rtol=1e-12, atol=0)
    assert np.allclose(got["l"], want_l, rtol=1e-12, atol=0)
    py = [ra.dispersion_adjustment(r, h, 250.0, 0.33, operator=mode) for r, h in GRID]
    assert np.allclose(got["l"], py, rtol=1e-12, atol=0), "the tool and run_analysis disagree"


# ------------------------------------------------ each operator reads its own fit ------
def test_each_operator_reads_its_own_fit():
    """Option B: the size-only operator is the headline fit's (gamma = 0), the overlay the gamma-free fit's, with its own
    k and scales: a change to the overlay's fit moves the overlay's ratio and leaves the headline's."""
    head = ra.dispersion_adjustment(2000.0, 0.25, 150.0, 0.60, operator=transfer_operator.SIZE_ONLY)
    ra.COMBINED_MODEL_OVERLAY["k"] = 0.75
    over = ra.dispersion_adjustment(2000.0, 0.25, 150.0, 0.60, operator=transfer_operator.OVERLAY)
    m = dict(MODEL, k=0.75)
    assert over == pytest.approx(closed_sigma(2000.0, 0.25, MODEL["gamma"], m) / closed_sigma(150.0, 0.60, MODEL["gamma"], m),
                                 rel=1e-12)
    assert ra.dispersion_adjustment(2000.0, 0.25, 150.0, 0.60, operator=transfer_operator.SIZE_ONLY) == head
    assert ra.operator_gamma_in_force(transfer_operator.SIZE_ONLY) == 0.0
    assert ra.operator_gamma_in_force(transfer_operator.OVERLAY) == MODEL["gamma"]


def test_an_operator_whose_fit_is_not_loaded_is_the_identity():
    ra.COMBINED_MODEL_OVERLAY = None
    assert ra.dispersion_adjustment(2000.0, 0.25, 150.0, 0.60, operator=transfer_operator.OVERLAY) == 1.0
    assert ra.operator_gamma_in_force(transfer_operator.OVERLAY) is None
    assert ra.dispersion_adjustment(2000.0, 0.25, 150.0, 0.60) != 1.0


def test_a_mixed_up_fit_is_refused():
    """A headline model carrying a fitted gamma, or an overlay model with gamma 0, is the other mode's fit."""
    ra.COMBINED_MODEL["gamma"] = 0.35
    with pytest.raises(ValueError):
        ra.dispersion_adjustment(2000.0, 0.25, 150.0, 0.60)
    ra.COMBINED_MODEL["gamma"] = 0.0
    ra.COMBINED_MODEL_OVERLAY["gamma"] = 0.0
    with pytest.raises(ValueError):
        ra.dispersion_adjustment(2000.0, 0.25, 150.0, 0.60, operator=transfer_operator.OVERLAY)


def _write(path, obj):
    import json
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


CAL = {"k": 0.58, "sd_undiv": 0.03, "sd_div": 0.05, "nu": 4.9, "nu_clean": 4.9, "nu_ritc": 7.4, "n": 674}


def test_the_loader_takes_both_calibrations(tmp_path):
    head = _write(tmp_path / "head.json", dict(CAL, gamma=0.0, gamma_prior="fixed_0"))
    free = _write(tmp_path / "free.json", dict(CAL, gamma=0.36, k=0.59))
    assert ra.load_dispersion_calibration(head, free) is ra.COMBINED_MODEL
    assert (ra.COMBINED_MODEL["gamma"], ra.COMBINED_MODEL_OVERLAY["gamma"], ra.COMBINED_MODEL_OVERLAY["k"]) == \
        (0.0, 0.36, 0.59)


def test_the_loader_disables_the_operator_on_a_calibration_from_before_option_b(tmp_path):
    """The loader pass before the fits reads whatever the checkout holds; a headline file that carries a fitted gamma is
    the earlier gamma-free headline and is not used as the size-only operator's fit."""
    stale = _write(tmp_path / "stale.json", dict(CAL, gamma=0.356))
    free = _write(tmp_path / "free.json", dict(CAL, gamma=0.36))
    assert ra.load_dispersion_calibration(stale, free) is None
    assert ra.COMBINED_MODEL is None and ra.COMBINED_MODEL_OVERLAY is None
    no_prior = _write(tmp_path / "no_prior.json", dict(CAL, gamma=0.0))        # gamma 0 but not the fixed_0 fit
    assert ra.load_dispersion_calibration(no_prior, free) is None


def test_the_loader_leaves_the_overlay_out_when_its_file_is_absent(tmp_path):
    head = _write(tmp_path / "head.json", dict(CAL, gamma=0.0, gamma_prior="fixed_0"))
    assert ra.load_dispersion_calibration(head, tmp_path / "absent.json") is ra.COMBINED_MODEL
    assert ra.COMBINED_MODEL_OVERLAY is None


def test_the_loader_refuses_an_overlay_file_with_gamma_zero(tmp_path):
    head = _write(tmp_path / "head.json", dict(CAL, gamma=0.0, gamma_prior="fixed_0"))
    zero = _write(tmp_path / "zero.json", dict(CAL, gamma=0.0))
    with pytest.raises(SystemExit):
        ra.load_dispersion_calibration(head, zero)
