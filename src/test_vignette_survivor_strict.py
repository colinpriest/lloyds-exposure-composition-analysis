"""The survivor is strict at atoms, and VaR markers use actual empirical exceedances."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pytest

import make_v1_ritc_survivor as survivor
import transfer_operator as operator
from pool_quantile import var_q


def test_strict_survivor_handles_ties_and_full_sample_denominator():
    sample = np.array([-1., 0., 1., 1., 2., 3., 3.])
    x, probability = survivor.survivor(sample)
    np.testing.assert_array_equal(x, [1., 2., 3.])
    np.testing.assert_allclose(probability, [3/7, 2/7, 0.0], atol=0, rtol=1e-15)
    for i in range(len(x) - 1):
        at_and_after = [x[i], (x[i] + x[i + 1]) / 2]
        for value in at_and_after:
            assert probability[i] == pytest.approx(np.mean(sample > value))
    assert probability[-1] == np.mean(sample > np.max(sample)) == 0


def test_empty_positive_side_and_bad_inputs():
    for sample in (np.array([]), np.array([-2., -1., 0.])):
        x, p = survivor.survivor(sample)
        assert len(x) == len(p) == 0
    with pytest.raises(ValueError, match='finite'):
        survivor.survivor(np.array([1., np.nan]))
    with pytest.raises(ValueError, match='one-dimensional'):
        survivor.survivor(np.array([[1., 2.]]))


def test_real_quantile_markers_use_empirical_strict_survival():
    raw, transferred, sqrt_r, _ritc = survivor.pools(operator.HEADLINE)
    fig, ax, _note, _obstacles = survivor.build_figure(raw, transferred, sqrt_r, operator.HEADLINE)
    try:
        for values in (raw, sqrt_r, transferred):
            for alpha, marker in ((.99, 'o'), (.995, 's')):
                q = var_q(values, alpha)
                exceedance = np.mean(values > q)
                points = [line for line in ax.lines if line.get_marker() == marker
                          and len(line.get_xdata()) == 1
                          and np.isclose(line.get_xdata()[0], q)]
                assert points and any(float(line.get_ydata()[0]) == pytest.approx(exceedance) for line in points)
                assert exceedance != pytest.approx(1 - alpha)
    finally:
        plt.close(fig)


def test_visible_curve_is_unchanged_and_off_axis_endpoints_are_bounded():
    raw, transferred, sqrt_r, _ritc = survivor.pools(operator.HEADLINE)
    fig, ax, _note, _obstacles = survivor.build_figure(raw, transferred, sqrt_r, operator.HEADLINE)
    try:
        floor = ax.get_ylim()[0]
        for label, values in (("Raw (untransferred)", raw),
                              ("Square-root benchmark", sqrt_r),
                              ("Size-only transfer (headline)", transferred)):
            line = next(line for line in ax.lines if line.get_label() == label)
            x, probability = survivor.survivor(values)
            np.testing.assert_array_equal(line.get_xdata(), x)
            np.testing.assert_allclose(line.get_ydata(), np.maximum(probability, floor), rtol=0, atol=0)
            assert probability[-1] == 0.0 and line.get_ydata()[-1] == floor
    finally:
        plt.close(fig)
