"""Regression tests for audited zero mature-reserve proxies, and for the refits' phi guard.

The guard phi >= PHI_MIN was applied at delta = 2 alone while the paper said every refit record satisfied it;
two records sat below it at delta = 1 (review of 29 September 2026, M-15). refit_subsample() applies it at
every delta; the tests below hold it there, on synthetic rows and on the committed inputs.
"""
import io
import json
import os

import numpy as np
import pytest

import check_maturity_denominator as cmd

TAGS = ["inf", "4", "2", "1"]


def test_zero_phi_is_retained_upstream_but_excluded_from_logphi_regression():
    phi = np.array([0.0, 0.25, np.nan, np.inf, -0.1])
    assert cmd.positive_phi_mask(phi).tolist() == [False, True, False, False, False]


def test_nonzero_phi_guard_is_distinct_from_the_refit_guard():
    phi = np.array([0.01, cmd.PHI_MIN, 0.50])
    assert cmd.positive_phi_mask(phi).tolist() == [True, True, True]
    assert (phi >= cmd.PHI_MIN).tolist() == [False, True, True]


def test_the_guard_holds_at_every_delta_not_only_at_two():
    phis = {"inf": np.array([0.50, 0.50, 0.50, 0.50, cmd.PHI_MIN]),
            "4":   np.array([0.40, 0.40, 0.40, 0.40, cmd.PHI_MIN]),
            "2":   np.array([0.30, 0.30, 0.30, 0.30, cmd.PHI_MIN]),
            "1":   np.array([0.20, 0.05, np.nan, 0.20, cmd.PHI_MIN])}
    phis["inf"][3] = 0.02
    sub = cmd.refit_subsample(phis, TAGS)
    assert sub.tolist() == [True, False, False, False, True], \
        "below the guard at delta = 1 only, missing at delta = 1, below it at delta = inf: all excluded; at it: kept"


def _committed_phis():
    """The maturity shares at every delta, aligned to the model sample, as check_maturity_denominator reads them."""
    if not os.path.exists(str(cmd.MAT)):
        pytest.skip("model/maturity_share.json not present in this checkout")
    _S, _R, _H, _yr, key = cmd.load_sample()
    mat = json.load(io.open(str(cmd.MAT), encoding="utf-8"))["records"]
    phis = {t: np.array([mat[k]["phi_delta_%s" % t] if k in mat else np.nan for k in key]) for t in TAGS}
    return key, phis


def test_on_the_committed_inputs_every_refit_record_meets_the_guard_at_every_delta():
    key, phis = _committed_phis()
    sub = cmd.refit_subsample(phis, TAGS)
    for t in TAGS:
        assert np.all(phis[t][sub] >= cmd.PHI_MIN), "delta = %s holds a refit record below the guard" % t
    # measured, not assumed: what the superseded delta = 2 rule let through
    delta2_only = np.isfinite(phis["2"]) & (phis["2"] >= cmd.PHI_MIN)
    let_through = sorted(key[delta2_only & ~sub].tolist())
    assert let_through == ["5678_2016", "6130_2018"], let_through
    assert int(sub.sum()) == int(delta2_only.sum()) - 2


def test_the_recorded_refits_say_so_at_every_delta():
    """DEFERRED-TO-REFIT: the result records the minimum phi of the refit subsample at each delta, beside the guard."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "results", "check_maturity_denominator_results.json")
    if not os.path.exists(path):
        pytest.skip("results/check_maturity_denominator_results.json not present in this checkout")
    rec = json.load(io.open(path, encoding="utf-8"))
    by = rec["phi_guard_by_delta"]
    assert set(by) == set(TAGS)
    assert all(by[t]["min_phi_in_refit_subsample"] >= rec["phi_min_guard"] == cmd.PHI_MIN for t in TAGS)
    assert rec["phi_guard_scope"].startswith("every delta")
    _key, phis = _committed_phis()
    assert rec["n_refit_subsample"] == int(cmd.refit_subsample(phis, TAGS).sum())
