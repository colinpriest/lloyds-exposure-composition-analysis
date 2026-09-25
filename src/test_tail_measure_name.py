#!/usr/bin/env python3
"""The tail statistic the paper prints is the one the code computes (frozen review of 25 September
2026, M02).

The paper defines TVaR as the mean of the transferred severities at or beyond the VaR: a tail
conditional mean, and explicitly NOT the coherent expected shortfall, which on a discrete pool takes
from the atom at the VaR only the mass the level requires. The definition and Table 3's note were
corrected in round 59; the phrase "under expected shortfall" survived in Section 5.1 until round 60
because it wrapped across a source line.

The review's closure condition is one consistent definition "in prose, formulas, labels and code,
checked on an empirical pool with a partially included boundary atom". So these tests:

  * check the property on a pool built so the boundary atom is only partly needed, where the two
    statistics MUST differ, against an independent implementation of each;
  * rebuild the manuscript's own Vignette 1 pool and show that the recorded TVaR99 is the tail
    conditional mean of it and not the coherent expected shortfall, at both ends of the transfer.

Run:  python -m pytest src/test_tail_measure_name.py -q
"""
import io
import json
import os

import numpy as np
import pytest

import pool_quantile
from pool_quantile import tvar_q, var_q

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def coherent_es(values, alpha, weights=None):
    """Coherent expected shortfall of a discrete distribution, computed independently.

    ES_alpha = (1/(1-alpha)) * [ E[X 1{X > VaR}] + VaR * (P(X <= VaR) - alpha) ], which takes from the
    atom at the VaR exactly the mass the level needs and no more. Written out here rather than taken
    from the repository, so the comparison is between two implementations.
    """
    x = np.asarray(values, dtype=float).ravel()
    w = np.ones(x.size) if weights is None else np.asarray(weights, dtype=float).ravel()
    w = w / w.sum()
    v = var_q(x, alpha, w)
    beyond = x > v
    mass_beyond = float(w[beyond].sum())
    tail_sum = float(np.sum(x[beyond] * w[beyond]))
    # the boundary atom contributes whatever mass is still needed to reach 1 - alpha
    needed = (1.0 - alpha) - mass_beyond
    return (tail_sum + v * needed) / (1.0 - alpha)


class TestTheTwoStatisticsOnAPartialBoundaryAtom:
    """A pool where the atom at the VaR is only partly required: the two measures differ, and the
    repository's tvar_q is the tail conditional mean."""

    #: nine equally weighted values. At alpha = 0.75 the VaR is 7.0 and F(7.0) = 7/9 > 0.75, so the
    #: boundary atom is partly inside the tail: 1/9 of mass is beyond it, and the level needs 0.25.
    POOL = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 7.0, 9.0]
    ALPHA = 0.75

    def test_the_boundary_atom_really_is_partly_included(self):
        v = var_q(self.POOL, self.ALPHA)
        x = np.asarray(self.POOL)
        assert v == 7.0
        f_at = float((x <= v).mean())
        assert f_at > self.ALPHA, "F(VaR) must exceed alpha, or nothing is partly included"
        assert float((x > v).mean()) < 1.0 - self.ALPHA

    def test_the_repository_computes_the_tail_conditional_mean(self):
        x = np.asarray(self.POOL)
        v = var_q(self.POOL, self.ALPHA)
        assert tvar_q(self.POOL, self.ALPHA) == pytest.approx(float(x[x >= v].mean()))

    def test_the_two_measures_differ_here(self):
        tcm = tvar_q(self.POOL, self.ALPHA)
        es = coherent_es(self.POOL, self.ALPHA)
        assert tcm != pytest.approx(es, abs=1e-9), \
            "on a partially included boundary atom the two must differ, or the test proves nothing"
        assert es > tcm, "coherent ES puts less weight on the boundary atom, so it is the larger here"

    def test_they_agree_exactly_when_the_level_falls_at_the_atoms_bottom_edge(self):
        """The characterisation, which is narrower than it looks on a continuous distribution.

        Coherent ES needs mass 1-alpha from the top; the tail conditional mean takes the whole atom
        at the VaR. They coincide only when the at-or-beyond mass IS 1-alpha, which on a discrete
        pool happens at isolated levels. Everywhere else ES is the larger, because the mass it does
        not need from the boundary atom goes back into the bigger values.
        """
        pool = [1.0, 2.0, 3.0, 4.0]
        at_the_edge = 0.5 + 1e-9        # the VaR is 3.0 and the at-or-beyond mass is exactly 0.5
        x = np.asarray(pool)
        v = var_q(pool, at_the_edge)
        assert v == 3.0
        assert float((x >= v).mean()) == pytest.approx(1.0 - at_the_edge, abs=1e-8)
        assert tvar_q(pool, at_the_edge) == pytest.approx(coherent_es(pool, at_the_edge), abs=1e-7)

    @pytest.mark.parametrize("alpha", [0.7, 0.75, 0.8, 0.9])
    def test_the_coherent_measure_is_never_the_smaller(self, alpha):
        assert coherent_es(self.POOL, alpha) >= tvar_q(self.POOL, alpha) - 1e-12

    def test_the_module_says_which_one_it_is(self):
        assert "at or beyond VaR_alpha" in pool_quantile.tvar_q.__doc__
        assert "as the manuscript defines it" in pool_quantile.tvar_q.__doc__


class TestTheRecordedFigureIsTheTailConditionalMean:
    """The manuscript's own pool, rebuilt, at both ends of the transfer."""

    @pytest.fixture(scope="class")
    def pools(self):
        pytest.importorskip("scipy")
        try:
            import vignette1_diagnostics as V
        except Exception as exc:                                  # pragma: no cover
            pytest.skip("vignette1_diagnostics is not importable: %s" % exc)
        for name in ("load_pool", "load_ritc", "load_draws", "transferred", "V1"):
            if not hasattr(V, name):
                pytest.skip("vignette1_diagnostics.%s is gone; this test must be rewritten" % name)
        S, R, H, synd, year = V.load_pool()
        ritc = V.load_ritc(synd, year)
        draws, _ref, _lo, _hi = V.load_draws()
        mp = {k: float(draws[k].mean()) for k in draws}
        cal = json.load(io.open(os.path.join(ROOT, "model", "dispersion_calibration_ritc.json"),
                                encoding="utf-8"))
        mp = {**mp, "k": cal["k"], "gamma": cal["gamma"], "sd_undiv": cal["sd_undiv"],
              "sd_div": cal["sd_div"], "nu_clean": cal["nu_clean"], "nu_ritc": cal["nu_ritc"]}
        adj, _lam = V.transferred(S, R, H, ritc, mp, V.V1)
        return {"raw": np.asarray(S, dtype=float), "transferred": np.asarray(adj, dtype=float)}

    @pytest.fixture(scope="class")
    def recorded(self):
        path = os.path.join(ROOT, "results", "vignette1_diagnostics_results.json")
        if not os.path.exists(path):
            pytest.skip("vignette1_diagnostics_results.json is not present in this checkout")
        return json.load(io.open(path, encoding="utf-8"))["C5_tvar"]["TVaR99"]

    @pytest.mark.parametrize("end", ["raw", "transferred"])
    def test_the_recorded_tvar99_is_the_tail_conditional_mean(self, pools, recorded, end):
        x = pools[end]
        v = var_q(x, 0.99)
        tcm = float(x[x >= v].mean())
        assert recorded[end] == pytest.approx(tcm, rel=1e-9), \
            "the recorded figure is not the mean at or beyond the VaR of this pool"

    @pytest.mark.parametrize("end", ["raw", "transferred"])
    def test_the_recorded_tvar99_is_not_the_coherent_expected_shortfall(self, pools, recorded, end):
        es = coherent_es(pools[end], 0.99)
        assert recorded[end] != pytest.approx(es, abs=1e-6), \
            ("the two measures coincide on this pool, so the manuscript's distinction cannot be "
             "checked here and this test would be vacuous")

    def test_the_boundary_atom_is_partly_included_at_99_percent(self, pools):
        """Which is why the distinction is worth drawing on this pool at all."""
        x = pools["transferred"]
        v = var_q(x, 0.99)
        at_or_beyond = float((x >= v).mean())
        beyond = float((x > v).mean())
        assert at_or_beyond > 0.01, "the tail holds more mass than the level needs"
        assert beyond < 0.01, "and part of the boundary atom is what makes up the difference"
