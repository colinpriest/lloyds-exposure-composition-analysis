r"""The concentration channel's sign is a property of the weighting, not of gamma >= 0 alone (frozen review of
24 September 2026, M01).

The manuscript said that because every donor's Herfindahl index exceeds the target's, every donor's adverse
severity falls under the move to the target basis "and the concentration contribution is negative under any
weighting of this pool". The first half is right and the second does not follow. The operator multiplies each
standardised residual by the target's scale instead of the donor's; where the target is less concentrated the
factor is below one, which moves an adverse, POSITIVE severity down and a favourable, NEGATIVE one UP, towards
zero. So the sign of the concentration player depends on which side of zero the pool's 99.5% point sits on, and a
weighting that puts it on a favourable severity reverses it.

That is not hypothetical here. Syndicate 318's retained years are all favourable, so weight 1 on that syndicate and
1e-8 on every other donor-year -- every weight strictly positive, inside the syndicate-weight simplex the
population model allows -- gives a positive concentration contribution. The reported pool is unaffected: at the
recorded weights, and in the 200 Dirichlet draws over syndicate weights the round checked, the contribution is
negative.

These tests run the production operator (vignette_uncertainty.shapley_v1, the same decomposition the tool
computes), not a re-implementation, at the posterior means.

Run:  python -m pytest src/test_concentration_sign.py -q
"""
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, HERE)
import vignette_uncertainty as vu  # noqa: E402


@pytest.fixture(scope="module")
def pool():
    """The donor pool, the operator's parameters at their posterior means, and Vignette 1's target."""
    S, R, H, synd, year = vu.load_pool()
    draws, ref, hlo, hce = vu.load_draws()
    th = {k: float(np.mean(v)) for k, v in draws.items()}
    ritc = vu.load_ritc(synd, year)
    tgt, _old, _new = vu.load_targets()
    return {"S": S, "R": R, "H": H, "synd": synd, "ritc": ritc, "th": th, "cfg": (ref, hlo, hce), "tgt": tgt,
            "idx": np.arange(len(S))}


def _contribution(p, w=None):
    """(tail, size, concentration) and the eight coalition VaRs under weights w."""
    te, se, ce, v = vu.shapley_v1_coalitions(p["S"], p["R"], p["H"], p["idx"], p["tgt"], p["th"], p["cfg"],
                                             p["ritc"], w)
    return te, se, ce, v


def test_the_target_is_less_concentrated_than_every_donor(pool):
    """The manuscript's premise: no donor sits below the target's H, so the move contracts every donor's scale."""
    _Rq, Hq = pool["tgt"]
    assert float(pool["H"].min()) > Hq


def test_contraction_lifts_a_favourable_severity_and_cuts_an_adverse_one(pool):
    """The mechanism, on the three cases the sign turns on: positive, zero and negative severities through the
    production transfer with the CONCENTRATION step alone, the donor's size held where it is."""
    th, cfg, tgt = pool["th"], pool["cfg"], pool["tgt"]
    _Rq, Hq = tgt
    R = np.array([2000.0, 2000.0, 2000.0])
    H = np.array([0.40, 0.40, 0.40])
    S = np.array([+1.0, 0.0, -1.0])
    out = vu.transfer(S, R, H, (R[0], Hq), th, cfg, ritc=np.zeros(3, bool))
    factor = out[0] / S[0]
    assert factor < 1.0                      # a donor above the target's H: the concentration step contracts
    assert out[0] < S[0]                     # an adverse severity falls
    assert out[1] == pytest.approx(0.0)      # zero is a fixed point
    assert out[2] > S[2]                     # a favourable severity RISES towards zero
    assert out[2] == pytest.approx(-out[0])


def test_the_reported_pool_gives_a_negative_concentration_contribution(pool):
    """At the recorded weights the reported sign holds, and the two ends of the decomposition are the pool VaRs the
    manuscript prints."""
    te, se, ce, v = _contribution(pool)
    assert ce < 0
    assert v[0] == pytest.approx(0.711, abs=0.001)   # raw pool
    assert v[7] == pytest.approx(0.278, abs=0.001)   # fully transferred
    assert te + se + ce == pytest.approx(v[7] - v[0])


def test_a_weighting_on_a_favourable_syndicate_reverses_the_sign(pool):
    """A weighting whose 99.5% point is a favourable severity makes the concentration contribution positive. Every
    weight is strictly positive, so this lies inside the weight space the population model admits."""
    synd, S = pool["synd"], pool["S"]
    favourable = [s for s in sorted(set(synd.tolist())) if np.all(S[synd == s] < 0)]
    assert favourable, "no syndicate has only favourable severities: the counterexample must be rebuilt"
    w = np.where(synd == favourable[0], 1.0, 1e-8)
    _te, _se, ce, v = _contribution(pool, w)
    assert v[0] < 0 and v[7] < 0             # the quantile sits on the favourable side, raw and transferred
    assert ce > 0                            # and the concentration player changes sign


def test_the_sign_follows_the_quantile_not_the_concentration_index(pool):
    """Stated as the rule the manuscript now carries: the contribution is negative when the fully transferred
    99.5% point is adverse and positive when it is favourable, with the same pool and the same target."""
    synd, S = pool["synd"], pool["S"]
    favourable = [s for s in sorted(set(synd.tolist())) if np.all(S[synd == s] < 0)]
    for w in (None, np.where(synd == favourable[0], 1.0, 1e-8)):
        _te, _se, ce, v = _contribution(pool, w)
        assert (ce < 0) == (v[7] > 0)
