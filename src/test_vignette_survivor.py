import numpy as np
from run_analysis import _vig_survivor_points


def test_survivor_uses_all_observations_and_groups_ties():
    x, p = _vig_survivor_points([-1, 0, 1, 1, 2])
    np.testing.assert_array_equal(x, [1, 2])
    np.testing.assert_allclose(p, [.2, 0])
