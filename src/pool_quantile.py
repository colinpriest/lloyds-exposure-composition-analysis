"""The pool quantile every VaR in the analysis is read with (frozen review of 21 September 2026, M04).

The manuscript declares the population a transferred stress is read from (Section 3.6): a scenario
is a syndicate drawn in proportion to its exposure n_s, then one of its years uniformly. Under
Bayesian-bootstrap weights w each syndicate-year therefore carries mass w_s / sum_t n_t w_t, and at
equal weights each carries 1/N. VaR_alpha is a quantile of that discrete distribution, its inverse
CDF,

    VaR_alpha = min { x : F_w(x) >= alpha },

which is always one of the pool's own values: an order statistic at equal weights.

The earlier rule interpolated between weighted plotting positions (cw - w) / (W - mean w), a
generalisation of numpy's type 7. That is not a functional of the stated distribution. With values
[0, 1], masses [0.999, 0.001] and alpha 0.995 it gave 0.498 where the distribution's VaR is 0;
splitting an atom into identical sub-atoms moved it; and raising one value could lower it. The point
estimates used type 7 as well, which is not a quantile of the equal-weight distribution either.

So every pool VaR, the point estimate and each bootstrap replicate alike, is read by var_q. Tied
values are pooled into one atom first, so the result depends on the distribution alone. The
cumulative masses are compared with alpha less 1e-12: cumsum can round k/n to just below alpha (at
n = 4, weights 0.37, alpha 0.75 it gives 0.7499999999999999), and the rule must not step past an
atom whose F is alpha exactly.

Descriptive percentiles (quartiles, deciles), peaks-over-threshold thresholds and percentiles of
Monte Carlo draws are not VaRs of a scenario pool, and keep numpy's default.
"""
import numpy as np

NUMPY_METHOD = "inverted_cdf"
RULE = ("inverse CDF of the (weighted) empirical distribution, VaR_alpha = min{x : F(x) >= alpha}, "
        "numpy method 'inverted_cdf'; tied values pooled, so splitting an atom changes nothing")
_EPS = 1e-12


def var_q(arr, alpha, w=None):
    """VaR_alpha of the pool `arr` with scenario masses `w` (equal when None): its inverse CDF."""
    a = np.asarray(arr, dtype=float).ravel()
    if a.size == 0:
        raise ValueError("an empty pool has no quantile")
    if not np.all(np.isfinite(a)):
        raise ValueError("the pool holds a non-finite value")
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must lie in (0, 1], got %r" % (alpha,))
    m = np.ones(a.size) if w is None else np.asarray(w, dtype=float).ravel()
    if m.shape != a.shape:
        raise ValueError("%d weights for %d values" % (m.size, a.size))
    if not np.all(np.isfinite(m)) or np.any(m < 0) or m.sum() <= 0:
        raise ValueError("weights must be finite, non-negative and not all zero")
    xs, inv = np.unique(a, return_inverse=True)
    F = np.cumsum(np.bincount(inv.ravel(), weights=m, minlength=xs.size))
    F = F / F[-1]
    i = int(np.searchsorted(F, alpha - _EPS, side="left"))
    return float(xs[min(i, xs.size - 1)])


def tvar_q(arr, alpha, w=None):
    """TVaR as the manuscript defines it: the (weighted) mean of the pool's values at or beyond VaR_alpha."""
    a = np.asarray(arr, dtype=float).ravel()
    m = np.ones(a.size) if w is None else np.asarray(w, dtype=float).ravel()
    tail = a >= var_q(a, alpha, m)
    return float(np.sum(a[tail] * m[tail]) / np.sum(m[tail]))
