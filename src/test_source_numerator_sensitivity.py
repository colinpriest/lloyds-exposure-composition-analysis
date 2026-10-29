"""Source-assumption sensitivities change only the declared observations."""
import numpy as np
import pytest

from check_source_numerator_sensitivity import case_sample, row_keys


def sample():
    return (np.array([0.1, 0.2, 0.3]), np.array([1., 2., 3.]),
            np.array([0.2, 0.3, 0.4]), np.array([2017, 2016, 2020]),
            np.array([3330, 1274, 33]), np.array([1., 0., 0.]))


@pytest.mark.parametrize("label,expected", [
    ("exclude_3330_2017", ["1274_2016", "33_2020"]),
    ("exclude_1274_2016", ["3330_2017", "33_2020"]),
    ("exclude_both", ["33_2020"]),
])
def test_only_specified_rows_are_excluded(label, expected):
    original = sample()
    changed, _ = case_sample(*original, label)
    assert row_keys(changed[4], changed[3]) == expected
    assert len(original[0]) == 3


@pytest.mark.parametrize("label,value", [
    ("printed_2016_table", 57.503),
    ("prior_cell_without_retranslation", 19.871),
])
def test_alternative_changes_one_severity_without_mutating_input(label, value):
    original = sample()
    changed, excluded = case_sample(*original, label)
    assert not excluded
    np.testing.assert_allclose(changed[0], [0.1, 0.2 * value / 22.6943, 0.3])
    for a, b in zip(changed[1:], original[1:]):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(original[0], [0.1, 0.2, 0.3])


def test_missing_or_duplicate_key_fails():
    original = sample()
    with pytest.raises(ValueError, match="absent"):
        case_sample(*(a[1:] for a in original), "exclude_both")
    duplicate = tuple(np.concatenate((x, x[1:2])) for x in original)
    with pytest.raises(ValueError, match="duplicate"):
        case_sample(*duplicate, "printed_2016_table")


def test_frozen_sample_contains_one_each_and_adopted_figure_matches():
    import json
    import adopted_model as am
    from check_source_numerator_sensitivity import ROOT, SOURCE_BASE_USD_M
    s = am.load_sample()
    keys = row_keys(s[4], s[3])
    assert len(keys) == 632
    assert keys.count("3330_2017") == keys.count("1274_2016") == 1
    data = json.loads((ROOT / "data/mature_cohort_figures.json").read_text(encoding="utf-8"))
    assert data["1274_2016"]["figure_m"] == SOURCE_BASE_USD_M
