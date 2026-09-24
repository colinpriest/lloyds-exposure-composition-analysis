r"""The demeaning benchmark is the population value of the statistic section 9 reports (R222, and its correction).

check_pyd_temporal_correlation reports a pooled lag-1 correlation of severities demeaned within syndicate, and
section 9 now says how strong a level-free AR(1) could be and still read like that. The benchmark is closed-form
covariance algebra, so it is only worth printing if it is grouped the way the statistic is grouped: lag_pairs
demeans over a syndicate's WHOLE series and then keeps the pairs whose years are consecutive. The first version
demeaned each maximal run of consecutive years instead. Thirty-seven of the 88 syndicates have a gap, and the
difference was large: at the observed raw lag-1 it read 0.170 where the right grouping reads 0.245, and the bound
it printed on the serial component was 0.29 where the right one is 0.21.

These tests hold the closed form against a simulation that draws AR(1) paths over real year sets and pools them
through lag_pairs itself, so the grouping cannot drift again without a red test.

Run:  python -m pytest src/test_demeaning_benchmark.py -q
"""
import io
import json
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import check_pyd_temporal_correlation as c  # noqa: E402

RECORD = os.path.join(HERE, "results", "check_pyd_temporal_correlation_results.json")

#: Two syndicates, one of them with a gap in its years, so grouping by run and grouping by syndicate differ.
FIXTURE = {1: (np.array([2014, 2015, 2016, 2017]), np.zeros(4)),
           2: (np.array([2014, 2015, 2018, 2019, 2020]), np.zeros(5))}


def _by_run(series, rho):
    """The grouping the first version used: each maximal run of consecutive years demeaned on its own."""
    blocks = []
    for _s, (yy, _ss) in series.items():
        start = 0
        for i in range(1, len(yy)):
            if yy[i] != yy[i - 1] + 1:
                blocks.append(i - start)
                start = i
        blocks.append(len(yy) - start)
    num = den_a = den_b = 0.0
    for length in blocks:
        if length < 2:
            continue
        ix = np.arange(length)
        cov = float(rho) ** np.abs(ix[:, None] - ix[None, :])
        m = np.eye(length) - np.ones((length, length)) / length
        cc = m @ cov @ m
        num += float(np.diag(cc, 1).sum())
        den_a += float(np.diag(cc)[:-1].sum())
        den_b += float(np.diag(cc)[1:].sum())
    return float(num / np.sqrt(den_a * den_b))


def test_the_closed_form_is_the_population_value_of_the_pooled_statistic():
    """Paths simulated over the fixture's own year sets, pooled through lag_pairs, land on the closed form."""
    for rho in (0.3, 0.6):
        closed = c.demeaned_lag1_under_ar1(FIXTURE, rho)
        simulated = c.benchmark_monte_carlo(FIXTURE, rho, draws=6000, seed=11)
        assert closed == pytest.approx(simulated, abs=0.02), (rho, closed, simulated)


def test_it_groups_by_syndicate_and_not_by_run():
    """The fixture's second syndicate has a gap, so the two groupings disagree, and the simulation picks the one
    the statistic uses."""
    rho = 0.6
    closed, byrun = c.demeaned_lag1_under_ar1(FIXTURE, rho), _by_run(FIXTURE, rho)
    assert abs(closed - byrun) > 0.02
    simulated = c.benchmark_monte_carlo(FIXTURE, rho, draws=6000, seed=12)
    assert abs(closed - simulated) < abs(byrun - simulated)


def test_four_consecutive_years_at_0_6_read_minus_0_064():
    """The case the docstring quotes: on a short panel, all dynamics and no level reads as no dynamics."""
    four = {1: (np.array([2014, 2015, 2016, 2017]), np.zeros(4))}
    assert c.demeaned_lag1_under_ar1(four, 0.6) == pytest.approx(-0.0638, abs=1e-3)


def test_the_solver_inverts_the_benchmark():
    for rho in (0.2, 0.5):
        target = c.demeaned_lag1_under_ar1(FIXTURE, rho)
        assert c.ar1_rho_reading(FIXTURE, target) == pytest.approx(rho, abs=1e-6)


def test_the_benchmark_rises_with_the_serial_correlation():
    values = [c.demeaned_lag1_under_ar1(FIXTURE, r) for r in (0.0, 0.2, 0.4, 0.6, 0.8)]
    assert values == sorted(values)


def test_the_recorded_benchmark_agrees_with_its_own_simulation():
    """The committed record carries the cross-check the check ran; a record whose closed form and simulation drift
    apart must not be printed."""
    with io.open(RECORD, encoding="utf-8") as fh:
        rec = json.load(fh)
    mc = rec["e_demeaning_benchmark"]["monte_carlo_check"]
    assert abs(mc["difference"]) <= c.MC_TOL
    assert (mc["rho"], mc["draws"], mc["seed"]) == (c.MC_RHO, c.MC_DRAWS, c.MC_SEED)


def test_the_recorded_benchmark_is_ordered_and_bounds_the_serial_component():
    with io.open(RECORD, encoding="utf-8") as fh:
        b = json.load(fh)["e_demeaning_benchmark"]
    assert 0 < b["rho_reading_the_observed_demeaned"] < b["rho_reading_the_interval_upper"] < b["observed_raw_lag1"]
    assert b["at_observed_raw_lag1"] > 0
