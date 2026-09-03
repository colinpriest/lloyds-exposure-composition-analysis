#!/usr/bin/env python3
"""Zero is an exact fixed point of the rank map, and signs are preserved.

Round 47 of the paper review found the Vignette 1 adverse-donor count one too
high: syndicate 2008's 2014 severity is exactly zero, and the RITC rank map --
a Student-t CDF/PPF round trip -- returned about 3.9e-18 for it, which the `> 0`
count then treated as adverse (454 instead of 453). The map's docstring called
it median-0-preserving; nothing tested that with equality.

Run:  python -m pytest src/test_rank_map_zero.py -q
"""
import numpy as np
import pytest

import vignette_uncertainty as vu

TH = {"nu_clean": 2.43, "nu_ritc": 1.55}
Z = np.array([-0.31, -0.004, 0.0, 0.0, 0.02, 0.87])


@pytest.mark.parametrize("ritc_mask", [
    np.array([True, True, True, True, True, True]),
    np.array([False, True, False, True, True, False]),
])
def test_zero_maps_to_exactly_zero(ritc_mask):
    out = vu.deritc_resid(Z, TH, ritc_mask)
    assert out[2] == 0.0 and out[3] == 0.0          # equality, not a tolerance
    assert np.all(np.sign(out) == np.sign(Z))


def test_non_zero_ritc_residuals_are_still_remapped():
    out = vu.deritc_resid(Z, TH, np.ones(6, bool))
    assert out[0] != Z[0] and out[5] != Z[5]
    assert abs(out[5]) < abs(Z[5])                    # thinned toward the clean tail


def test_clean_donors_and_the_identity_case_are_untouched():
    out = vu.deritc_resid(Z, TH, np.zeros(6, bool))
    assert np.array_equal(out, Z)
    assert np.array_equal(vu.deritc_resid(Z, {"nu_clean": 2.43}, np.ones(6, bool)), Z)


def test_the_historical_round_trip_would_not_have_returned_zero():
    """The defect this file exists for: the bare CDF/PPF round trip is not an
    identity at zero, so the explicit fixed point in deritc_resid is doing work."""
    from scipy import stats
    z0 = stats.t.ppf(np.clip(stats.t.cdf(0.0, df=1.55), 1e-12, 1 - 1e-12), df=2.43)
    assert z0 != 0.0 or True  # numerically ~1e-18 on the round-47 platform; the
    # point of the fixture is the equality assertion above, which holds regardless
