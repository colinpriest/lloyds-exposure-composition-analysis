"""The vignette figures under a refit's own posterior, beside the headline's: one implementation for the sensitivities
that report the transferred stresses of a fit other than the headline calibration.

Two sensitivities refit the adopted model and, since the author's decision of 14 October 2026, report what the refit
does to the stresses a practitioner uses, not only to its parameters:

  - check_cohort_scope.py: the fit on the 672 construction (the extraction's precedence rules, the working sample
    before the owner's decision of 22 October 2026 made the mature-cohort outcome the primary), transferring from its
    own donors (until then: the records whose figure a triangle produced);
  - check_missingness_sensitivity.py: the selection-weighted fits, transferring from the model sample.

Each computes Vignette 1's VaR99 and VaR99.5 and Vignette 2's paired change at 99.5% through
check_gamma0_vignette.operator_vignettes, the headline estimator's own function: the size-only operator (gamma = 0 in
the likelihood, the paper's headline; transfer_operator.py), the targets, the cluster resampler by syndicate, and the
seed and B of check_gamma0_vignette.py's record, which are read from that record. The headline's figures are that
record's size-only block, used only after its centre is recomputed here on the full pool from the headline fit's
draws and found equal, so the two sides are computed alike.
"""
import io
import json

import arviz as az
import numpy as np

import transfer_operator
from adopted_model import SD, posterior_draws
from check_gamma0_vignette import QUANTITIES, centres, operator_vignettes
from pool_quantile import var_q
from vignette_uncertainty import load_pool, load_ritc, load_targets, transfer

GAMMA0 = SD / "results" / "check_gamma0_vignette_results.json"
#: the operator every figure here is computed under: the paper's headline, size-only (gamma = 0)
OPERATOR = transfer_operator.HEADLINE
#: the parameters a fit's convergence is read on: every scale and tail parameter the headline reports
DIAG_VARS = ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s")
#: the most adverse Vignette 1 donors whose membership of a pool is reported
TOP_N = 20
ESTIMATOR = ("check_gamma0_vignette.operator_vignettes under the headline size-only operator: centre on the pool at "
             "the fit's posterior means; intervals are the 2.5 and 97.5 percentiles over a cluster bootstrap by "
             "syndicate with one posterior draw per replicate (a conditional resampling interval, not a posterior "
             "interval), at the seed and B of check_gamma0_vignette.py's record")


def convergence(idata, names=DIAG_VARS):
    """Divergent transitions, and the largest R-hat and smallest bulk and tail ESS over `names`, all unrounded."""
    names = [n for n in names if n in idata.posterior]
    rhat = az.rhat(idata, var_names=names)
    bulk = az.ess(idata, var_names=names, method="bulk")
    tail = az.ess(idata, var_names=names, method="tail")
    return {"divergences": int(idata.sample_stats["diverging"].sum()),
            "max_rhat": float(max(float(rhat[n].values.max()) for n in names)),
            "min_ess_bulk": float(min(float(bulk[n].values.min()) for n in names)),
            "min_ess_tail": float(min(float(tail[n].values.min()) for n in names)),
            "parameters": list(names)}


def converged(diag, rhat_max=1.01):
    """Whether a fit's figures may be reported: no divergence and every R-hat at or below `rhat_max`."""
    return diag["divergences"] == 0 and diag["max_rhat"] <= rhat_max


def operator_draws(idata):
    """The operator's parameters (transfer_operator.OPERATOR_KEYS) from a gamma = 0 refit's own posterior, gamma as
    exact zeros, which the size-only operator takes as they are."""
    return posterior_draws(idata, transfer_operator.OPERATOR_KEYS)


def donor_keys(synd, year):
    return np.array(["%s_%s" % (s, y) for s, y in zip(synd, year)])


def pool_for(keys=None):
    """(pool, assumed-business flags, keys): the vignette donor pool (the shipped tool's donors, in the tool's order)
    restricted to `keys`, or the whole pool. A key outside the pool is an error, not a smaller pool."""
    S, R, H, synd, year = load_pool()
    k = donor_keys(synd, year)
    if keys is None:
        m = np.ones(len(k), bool)
    else:
        wanted = set(keys)
        missing = wanted - set(k.tolist())
        if missing:
            raise SystemExit("%d of the fit's records are not in the vignette donor pool: %s"
                             % (len(missing), sorted(missing)[:5]))
        m = np.array([x in wanted for x in k])
    pool = (S[m], R[m], H[m], synd[m], year[m])
    return pool, load_ritc(pool[3], pool[4]), k[m]


#: how far a donor's value in the shipped tool may lie from the model file's: the tool embeds each severity to 8
#: decimals and each opening reserve to 2 (GBP 0.01m), so a larger gap is a different record, not rounding
POOL_TOL = {"severity": 5.0e-9 + 1e-15, "opening_reserves_m": 0.005 + 1e-9}


def check_pool_is_the_fit_sample(pool, keys, fit_keys, fit_S, fit_R):
    """The donors a refit's stresses transfer are the records it was fitted on, with the same severity and opening
    reserves to the tool's rounding (POOL_TOL): the pool is read from the shipped tool and the fit from the model
    file, as for every headline vignette figure."""
    if sorted(np.asarray(keys).tolist()) != sorted(list(fit_keys)):
        raise SystemExit("the donor pool (%d) is not the fit's sample (%d)" % (len(keys), len(fit_keys)))
    fit = {k: (float(s), float(r)) for k, s, r in zip(fit_keys, fit_S, fit_R)}
    bad = [k for k, s, r in zip(keys, pool[0], pool[1])
           if abs(fit[k][0] - float(s)) > POOL_TOL["severity"] or abs(fit[k][1] - float(r)) > POOL_TOL["opening_reserves_m"]]
    if bad:
        raise SystemExit("%d donors' severity or opening reserves differ from the fit's records by more than the tool's "
                         "rounding: %s" % (len(bad), [str(k) for k in bad[:5]]))


def headline_record():
    """check_gamma0_vignette.py's record, which must name the size-only operator as its headline."""
    with io.open(GAMMA0, encoding="utf-8") as _fh:
        rec = json.load(_fh)
    if rec.get("headline_operator") != OPERATOR or rec[OPERATOR].get("operator") != OPERATOR:
        raise SystemExit("check_gamma0_vignette_results.json does not name %s as its headline operator" % OPERATOR)
    return rec


def headline_block(recorded):
    """The record's headline block, once its centre is recomputed here (the whole pool, the headline fit's draws) and
    found equal: otherwise the refit's figures and the headline's would not be computed alike."""
    draws, ref, hlo, hce = transfer_operator.load_draws(OPERATOR)
    pool, ritc, _keys = pool_for()
    _thbar, centre = centres(OPERATOR, pool, draws, (ref, hlo, hce), ritc, load_targets())
    if centre != recorded[OPERATOR]["centre"]:
        raise SystemExit("the headline's vignette centres differ from check_gamma0_vignette.py's record: %s against %s"
                         % (centre, recorded[OPERATOR]["centre"]))
    return recorded[OPERATOR], draws, (ref, hlo, hce)


def vignettes(draws, pool, ritc, cfg, recorded):
    """The refit's vignette block: operator_vignettes under the headline operator, at the record's seed and B."""
    return operator_vignettes(OPERATOR, pool, draws, cfg, ritc, load_targets(), b=recorded["B"],
                              seed=recorded["seed"])


def relative(centre, head_centre):
    """Each figure's centre relative to the headline's: centre / headline - 1."""
    return {q: centre[q] / head_centre[q] - 1.0 for q in QUANTITIES}


def centre_only(draws, pool, ritc, cfg, weights=None):
    """The vignette centres on `pool` at the posterior means of `draws` (centres(), the headline estimator's), or, with
    `weights` (one scenario mass per donor, in the pool's order), the weighted inverse-CDF VaR of the same transfer."""
    if weights is None:
        return centres(OPERATOR, pool, draws, cfg, ritc, load_targets())[1]
    S, R, H, _synd, _year = pool
    v1, v2o, v2n = load_targets()
    th = transfer_operator.params(draws, OPERATOR)
    thbar = {p: float(th[p].mean()) for p in th}
    w = np.asarray(weights, float)
    a1, ao, an = (transfer(S, R, H, t, thbar, cfg, ritc) for t in (v1, v2o, v2n))
    return {"V1_v99": var_q(a1, 0.99, w), "V1_v995": var_q(a1, 0.995, w),
            "V2_old_v995": var_q(ao, 0.995, w), "V2_new_v995": var_q(an, 0.995, w),
            "V2_d995": var_q(an, 0.995, w) - var_q(ao, 0.995, w)}


def rank_from_top(n, alpha):
    """Which order statistic, counted from the largest, the inverse-CDF VaR_alpha of `n` equally weighted distinct
    values is (pool_quantile.var_q's rule): a pool of another size can read another one, so a change in VaR between
    pools of different sizes is partly the index, not the donors."""
    i = int(np.searchsorted(np.arange(1, n + 1) / n, alpha - 1e-12, side="left"))
    return n - i


def v1_top_donors(draws, pool, ritc, keys, cfg, n=TOP_N):
    """The `n` most adverse Vignette 1 donors on `pool` at the posterior means of `draws`, most adverse first: each
    donor's key and transferred severity (the values whose upper order statistics are VaR99 and VaR99.5)."""
    S, R, H, _synd, _year = pool
    th = transfer_operator.params(draws, OPERATOR)
    thbar = {p: float(th[p].mean()) for p in th}
    a = transfer(S, R, H, load_targets()[0], thbar, cfg, ritc)
    order = np.argsort(-a, kind="stable")[:n]
    return [{"donor": str(keys[i]), "transferred_severity": float(a[i])} for i in order]
