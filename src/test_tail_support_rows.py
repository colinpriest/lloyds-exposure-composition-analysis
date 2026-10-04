"""The vignettes' tail-support counts include the VaR atom (the review of 2 October 2026, A-9).

The tables counted pool values at or beyond a VaR rounded to six decimals, so whenever the rounding went up the
atom dropped out: the committed tables print 6 and 3 where 7 and 4 lie at or beyond VaR99 and VaR99.5, beside a
snippet that says 7 and 4. The count is now pool_quantile.support_at_or_beyond_var on the unrounded pool, and the
column says what it counts.

Run:  python -m pytest src/test_tail_support_rows.py -q
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import pool_quantile  # noqa: E402
import run_analysis as ra  # noqa: E402


def _pool():
    # 674 values whose VaRs carry digits beyond the sixth, rounding up
    return np.sort(np.linspace(-0.5, 0.7, 674) + 0.0000004 + 0.00000049 * np.arange(674) / 674)


def test_the_count_includes_the_atom_that_a_rounded_var_drops():
    a = _pool()
    stats = {"var99": round(pool_quantile.var_q(a, 0.99), 6), "var995": round(pool_quantile.var_q(a, 0.995), 6)}
    assert stats["var995"] > pool_quantile.var_q(a, 0.995)       # the case the review found
    rows = ra.tail_support_rows([("Raw market", "raw", a, stats)], None)
    got = {r["metric"]: r["tail_support_at_or_beyond_var_incl_atom"] for r in rows}
    assert got == {"VaR99": pool_quantile.support_at_or_beyond_var(a, 0.99),
                   "VaR99.5": pool_quantile.support_at_or_beyond_var(a, 0.995)}
    assert got["VaR99.5"] == int(np.sum(a >= pool_quantile.var_q(a, 0.995))) == int(np.sum(a >= stats["var995"])) + 1


def test_the_rows_carry_the_intervals_and_the_named_column():
    a = _pool()
    stats = {"var99": 0.6, "var995": 0.65}
    boot = {"raw_var99": (0.5, 0.7), "raw_var995": (0.55, 0.75)}
    rows = ra.tail_support_rows([("Raw market", "raw", a, stats)], boot)
    assert [(r["metric"], r["point_estimate"], r["ci_lower"], r["ci_upper"]) for r in rows] == [
        ("VaR99", 0.6, 0.5, 0.7), ("VaR99.5", 0.65, 0.55, 0.75)]
    assert all(set(r) == set(ra.TAIL_SUPPORT_FIELDS) for r in rows)
    assert "tail_support_count" not in ra.TAIL_SUPPORT_FIELDS
