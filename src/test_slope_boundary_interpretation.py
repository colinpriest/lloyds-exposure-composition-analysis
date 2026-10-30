"""Regression checks for the slope and flat-boundary interpretations."""
import ast
import json
from pathlib import Path

import numpy as np
import pytest

import check_large_book_slope as slope
import check_vignette2_sign as sign

ROOT = Path(__file__).resolve().parent.parent


def literal_dict_value(script, name, field):
    """Read the literal metadata emitted by a producer without running its fits."""
    tree = ast.parse((ROOT / "src" / script).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ) or not isinstance(node.value, ast.Dict):
            continue
        for key, value in zip(node.value.keys, node.value.values):
            if isinstance(key, ast.Constant) and key.value == field:
                return ast.literal_eval(value)
    raise AssertionError(f"{script}: missing {name}[{field!r}]")


@pytest.mark.parametrize(
    "script,result,field",
    [
        ("check_large_book_slope.py", "check_large_book_slope_results.json", "model_local_slopes_are"),
        ("check_large_book_slope_bayes.py", "check_large_book_slope_bayes_results.json", "b_is"),
        ("check_large_book_slope_conditional.py", "check_large_book_slope_conditional_results.json", "note"),
    ],
)
def test_recorded_slope_interpretation_matches_the_producer(script, result, field):
    recorded = json.loads((ROOT / "results" / result).read_text(encoding="utf-8"))[field]
    assert recorded == literal_dict_value(script, "res", field)
    assert "not" in recorded and "local derivative" in recorded


def test_floored_local_derivative_varies_across_range_and_matches_finite_difference():
    k, gamma, su, sd, H = 0.63, 0.4, 0.03, 0.05, 0.2
    sizes = np.array([100.0, 500.0, 2000.0])
    measured = slope.model_local_slope(sizes, H, k, gamma, su, sd)

    def log_scale(log_size):
        x = (np.exp(log_size) / slope.REF) * (1.0 / np.clip(H, slope.HLO, slope.HCE)) ** gamma
        return 0.5 * np.log(su**2 + sd**2 * x ** (2 * (k - 1)))

    h = 1e-5
    finite = (log_scale(np.log(sizes) + h) - log_scale(np.log(sizes) - h)) / (2 * h)
    np.testing.assert_allclose(measured, finite, atol=1e-9)
    assert np.all(np.diff(measured) > 0)  # one constant linear coefficient cannot equal all three
    assert measured[-1] - measured[0] > 0.05


@pytest.mark.parametrize("gamma", [0.0, 0.394])
def test_vignette2_flat_boundary_and_direction_both_sides(gamma):
    def ratio(k):
        new = sign.sigma(650.0, 0.2618, k, gamma, 0.03, 0.05, 500.0, 0.01, 1.0)
        old = sign.sigma(800.0, 0.21, k, gamma, 0.03, 0.05, 500.0, 0.01, 1.0)
        return float(new / old)

    assert ratio(0.9) > 1
    assert ratio(1.0) == pytest.approx(1)
    assert ratio(1.1) < 1
    result = json.loads((ROOT / "results" / "check_vignette2_sign_results.json").read_text(encoding="utf-8"))
    tree = ast.parse((ROOT / "src" / "check_vignette2_sign.py").read_text(encoding="utf-8"))
    notes = [
        ast.literal_eval(value)
        for node in ast.walk(tree) if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == "note"
    ]
    assert len(notes) == 1
    for block in (result, result["overlay_sensitivity"]):
        note = block["reversal"]["note"]
        assert note == notes[0]
        assert "flat boundary" in note and "k>1" in note
