"""Regression tests for audited zero mature-reserve proxies."""

import numpy as np

import check_maturity_denominator as cmd


def test_zero_phi_is_retained_upstream_but_excluded_from_logphi_regression():
    phi = np.array([0.0, 0.25, np.nan, np.inf, -0.1])
    assert cmd.positive_phi_mask(phi).tolist() == [False, True, False, False, False]


def test_nonzero_phi_guard_is_distinct_from_the_refit_guard():
    phi = np.array([0.01, cmd.PHI_MIN, 0.50])
    assert cmd.positive_phi_mask(phi).tolist() == [True, True, True]
    assert (phi >= cmd.PHI_MIN).tolist() == [False, True, True]
