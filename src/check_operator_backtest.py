"""Backtest of the transfer operator on held-out syndicates (the paper's one-sided tail claim, scored out of sample).

The operator takes the market's pooled donor severities, rescales each to a target book (size, concentration) and
reads a tail quantile from the rescaled pool. Every held-out syndicate-year here is a target: its own reserves and
concentration (R, H) define the book, the other syndicates' donor rows are the pool, and the realised severity S is
scored against the VaR the operator reads from that pool at 90, 95, 99 and 99.5%. An exceedance is S > VaR; at
level a the expected rate is 1 - a.

Three methods read the same pool:
  raw_pool          the donors' raw severities (no rescaling);
  sqrt_R            each donor rescaled by sqrt(R_donor / R_target) (the simple scaling: k = 1/2, no floor, no tail
                    map), so what the operator adds beyond it is measured;
  operator_size_only  the paper's headline operator, vignette_uncertainty.transfer at a gamma = 0 fit's posterior
                    means (transfer_operator.params), the floor and the de-RITC tail map. A RITC-regime target is
                    scored under the clean target regime, the only one the Python operator has.
There is no overlay method: since option B (the author's decision of 10 October 2026) every fit here, the fold
refits and the full-sample headline, has gamma fixed at 0 in the likelihood, so none has a fitted concentration
exponent for an overlay to apply.
Every VaR is pool_quantile.var_q, the rule behind every VaR in the paper.

Two versions of the backtest, in one results file:
  honest  the syndicates are split into 10 folds by oos_validation.fold_assignment (the rule oos_validation.py uses,
          imported, not copied); the adopted model is REFITTED on each fold's training syndicates (scale_block, the
          headline's sampler, seed and settings) and each held-out syndicate-year is transferred from the training
          pool at that fold's posterior means. The fold's syndicates leak into neither the pool nor the scale law.
          The folds run in a pool of worker processes; the worker count is an argument (default 3) and does not
          change the numbers.
  cheap   a leave-one-syndicate-out over all syndicates reusing the FULL-SAMPLE posterior means. The pool is
          honest; the scale law and tail indices were fitted with the held-out syndicate in the sample, so this
          version leaks it into them, and is recorded to measure how much, beside the honest version.
Each version is also scored with the target's own reporting year dropped from the pool (no shared year shock).

Beside the honest version, the same ten fold fits with their parameter uncertainty propagated
(`honest_posterior_draws`): each held-out target's predictive distribution is the operator's transferred pool under
every one of N_PRED_DRAWS posterior draws of the fold fit, evenly spaced through its 6,000, mixed with equal weight, and
its VaR_alpha is that mixture's inverse CDF (pool_quantile.var_q's rule). The honest version reads the pool at the
fold fit's posterior means (a plug-in); this one integrates over the draws. Only the operator has parameters, so only
its leg changes; both pool rules are scored, and the block records the exceedances and pinball loss beside the plug-in
figures of the same targets.

For each version, pool rule and method the record holds: exceedance counts against expected counts overall, by size
quartile of the target's R, and for clean and RITC years separately; the mean pinball (quantile) loss at each level,
the same splits; and the exceedance rate under a by-syndicate Bayesian bootstrap (Rubin; uniform Dirichlet weights over
syndicates, every year of a syndicate sharing its weight), with the share of the posterior above the nominal rate.
That is a posterior over the rate, not a test. Power in the far tail is small (3.4 exceedances expected at 99.5% in 672).

`per_target` keeps what the totals hide. The overall counts can be right while a size band is not: the record stores, for
the honest plug-in and the posterior-draw versions and each pool rule, every target's exceedance flag at each level (with
its syndicate, reporting year, R, size quartile and RITC flag), and from the flags a by-size-quartile table: exceedances
against the expected count, the by-syndicate Bayesian-bootstrap posterior of the quartile's rate (mean, 95% credible
interval) with the posterior probability that it exceeds the nominal rate, and how many distinct syndicates carry the
quartile's exceedances (a few syndicates carrying them are strongly dependent exceedances). It names the quartile each
vignette's R falls in (the vignettes' targets, read from vignette_uncertainty.load_targets).

It also records the full-sample sqrt(R)-scaled VaR99 and VaR99.5 at Vignette 1's target and the Vignette 2 pair, from the
same pool and the same var_q as the operator's vignette figures, beside the operator's own and the raw pool's. The
operator's figures are checked against check_gamma0_vignette.py's record, or nothing is written.

Writes check_operator_backtest_results.json.
Usage:  python src/check_operator_backtest.py [workers]
"""
import io
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

import transfer_operator
from pool_quantile import var_q
from adopted_model import SD, load_sample, scale_block, SAMPLE_CORES
from oos_validation import fold_assignment
from check_gamma0_vignette import centres
from vignette_uncertainty import transfer, load_pool, load_draws, load_ritc, load_targets, sigma_theta, deritc_resid

OUT = SD / "results" / "check_operator_backtest_results.json"
GAMMA0 = SD / "results" / "check_gamma0_vignette_results.json"
LEVELS = (0.90, 0.95, 0.99, 0.995)
#: the methods, in the record's order (no overlay method: the fits have gamma = 0 in the likelihood)
METHODS = ("raw_pool", "sqrt_R", "operator_size_only")
#: the method whose per-target exceedance flags the record keeps (the headline operator)
OPERATOR_METHOD = "operator_size_only"
K_HONEST = 10
DEFAULT_WORKERS = 3
DRAWS, TUNE, CHAINS, TARGET_ACCEPT, FIT_SEED = 1500, 1500, 4, 0.98, 42     # calibrate_dispersion_ritc.py's
FIT_PARAMS = ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s")
OPERATOR_PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")
POOL_RULES = ("leave_out", "leave_out_and_target_year")
BB_REPS, BB_SEED = 4000, 20261010
CI = (2.5, 97.5)
#: the posterior draws of each fold fit the draw-based predictive mixes, evenly spaced through its DRAWS x CHAINS
N_PRED_DRAWS = 600
#: the inverse-CDF rule's tolerance, pool_quantile's (var_q compares the cumulative mass with alpha less this)
_EPS = 1e-12


# ----------------------------------------------------------------------------- scoring
def size_quartiles(R):
    """(edges, index 0..3) of each target's R among all targets: quartile 0 holds the smallest books."""
    edges = np.quantile(R, [0.25, 0.5, 0.75])
    return edges, np.searchsorted(edges, R, side="right")


def pinball(S, q, a):
    """The quantile (pinball) loss of a level-a quantile forecast q for the outcome S: (a - 1[S < q]) (S - q)."""
    S, q = np.asarray(S, float), np.asarray(q, float)
    return (a - (S < q)) * (S - q)


def method_pools(Sp, Rp, Hp, rp, target, th_head, cfg):
    """The three transferred pools for one target (R, H), from the donor rows (Sp, Rp, Hp, rp)."""
    Rt = target[0]
    return {"raw_pool": Sp,
            "sqrt_R": Sp * np.sqrt(Rp / Rt),
            "operator_size_only": transfer(Sp, Rp, Hp, target, th_head, cfg, rp)}


def leave_out_quantiles(S, R, H, ritc, held, syn, yr, thetas, cfg, drop_year, levels=LEVELS):
    """Every target's VaR under every method.

    `held[i]` labels target i's held-out unit (its fold, or its syndicate): the pool for target i is every row whose
    label differs, and, when `drop_year`, every row not in its reporting year as well. `thetas[label]` is the
    headline operator's parameters for that unit. Returns {method: {level: array}}."""
    n = len(S)
    q = {m: {a: np.empty(n) for a in levels} for m in METHODS}
    for i in range(n):
        keep = held != held[i]
        if drop_year:
            keep &= yr != yr[i]
        th_head = thetas[held[i]]
        pools = method_pools(S[keep], R[keep], H[keep], ritc[keep], (R[i], H[i]), th_head, cfg)
        for m, pool in pools.items():
            for a in levels:
                q[m][a][i] = var_q(pool, a)
    return q


def bayes_bootstrap_weights(syn, reps=BB_REPS, seed=BB_SEED):
    """(reps x n) row weights: Rubin's uniform Dirichlet over syndicates, a syndicate's years sharing its weight."""
    keys = sorted(set(syn.tolist()))
    pos = {k: i for i, k in enumerate(keys)}
    sidx = np.array([pos[s] for s in syn.tolist()])
    w = np.random.default_rng(seed).dirichlet(np.ones(len(keys)), size=reps)
    return w[:, sidx]


def rate_posterior(exceed, mask, W, nominal):
    """The exceedance rate over the rows in `mask` under the weight draws W: mean, 95% interval, share above nominal."""
    Wm = W[:, mask]
    r = (Wm @ exceed[mask].astype(float)) / Wm.sum(axis=1)
    return {"mean": float(r.mean()), "lo": float(np.percentile(r, CI[0])), "hi": float(np.percentile(r, CI[1])),
            "nominal": float(nominal), "share_above_nominal": float((r > nominal).mean())}


def summarise_method(S, qs, quart, ritc, W, levels=LEVELS):
    """Counts against expectations, pinball loss and bootstrap rates for one method's VaRs `qs` {level: array}."""
    groups = {"all": np.ones(len(S), bool), "clean": ~ritc, "ritc": ritc}
    for j in range(4):
        groups["size_quartile_%d" % (j + 1)] = quart == j
    out = {}
    for a in levels:
        exc = S > qs[a]
        loss = pinball(S, qs[a], a)
        row = {"exceedances": {}, "expected": {}, "pinball_mean": {}, "rate_bayes_bootstrap": {}}
        for g, mask in groups.items():
            row["exceedances"][g] = int(exc[mask].sum())
            row["expected"][g] = float(mask.sum() * (1.0 - a))
            row["pinball_mean"][g] = float(loss[mask].mean())
            row["rate_bayes_bootstrap"][g] = rate_posterior(exc, mask, W, 1.0 - a)
        out["%g" % a] = row
    return out


def backtest(S, R, H, ritc, syn, yr, held, thetas, cfg, drop_year, W, levels=LEVELS, capture=None):
    """{method: summary}. When `capture` is a dict, the operator's VaRs {level: array} are put in it under "operator", so
    the caller can keep the per-target exceedance flags (per_target_block)."""
    q = leave_out_quantiles(S, R, H, ritc, held, syn, yr, thetas, cfg, drop_year, levels)
    _edges, quart = size_quartiles(R)
    if capture is not None:
        capture["operator"] = q[OPERATOR_METHOD]
    return {m: summarise_method(S, q[m], quart, ritc, W, levels) for m in METHODS}


# ------------------------------------------------------- the operator with its parameter uncertainty
def mixture_var(values, levels=LEVELS):
    """{level: VaR} of the equally weighted values, by pool_quantile.var_q's rule (the inverse CDF, min{x : F(x) >=
    alpha}), from one sort: at equal weights the rule's value is the order statistic at position ceil(n (alpha - eps))
    counted from 1, ties included, which is what var_q returns after pooling them."""
    a = np.sort(np.asarray(values, float).ravel())
    n = a.size
    out = {}
    for lv in levels:
        i = int(np.ceil(n * (lv - _EPS))) - 1
        out[lv] = float(a[min(max(i, 0), n - 1)])
    return out


def donor_residuals(S, R, H, ritc, draws, cfg):
    """(n x D) the operator's de-RITC'd standardised residual of each donor row under each draw: deRITC(S / sigma_src),
    the part of vignette_uncertainty.transfer that does not depend on the target. `draws` maps OPERATOR_PARAMS to
    arrays of D posterior draws (gamma identically 0)."""
    D = len(draws["k"])
    Z = np.empty((len(S), D))
    for j in range(D):
        th = {p: float(draws[p][j]) for p in draws}
        si = sigma_theta(R, H, th["k"], th["gamma"], th["sd_undiv"], th["sd_div"], *cfg)
        Z[:, j] = deritc_resid(S / si, th, ritc)
    return Z


def target_scales(Rq, Hq, draws, cfg):
    """(D,) the target book's sigma under each draw: the other part of the transfer."""
    return sigma_theta(Rq, Hq, np.asarray(draws["k"], float), np.asarray(draws["gamma"], float),
                       np.asarray(draws["sd_undiv"], float), np.asarray(draws["sd_div"], float), *cfg)


def draw_quantiles(S, R, H, ritc, held, yr, draws_by_label, cfg, drop_year, levels=LEVELS):
    """{level: array}: every target's VaR from the operator's posterior predictive pool, the transferred pool under each
    of its held-out unit's posterior draws mixed with equal weight. The pool rule is leave_out_quantiles's (every row of
    another unit, and with `drop_year` of another reporting year too). transfer(S, ...) under draw j is
    donor_residuals(...)[:, j] * target_scales(...)[j], so the residuals are computed once per unit."""
    n = len(S)
    q = {a: np.empty(n) for a in levels}
    for lab in sorted(set(np.asarray(held).tolist())):
        draws = transfer_operator.params(draws_by_label[lab], transfer_operator.HEADLINE)
        donors = held != lab
        Z = donor_residuals(S[donors], R[donors], H[donors], ritc[donors], draws, cfg)
        yr_d = yr[donors]
        for i in np.flatnonzero(held == lab):
            keep = (yr_d != yr[i]) if drop_year else np.ones(len(yr_d), bool)
            sq = target_scales(R[i], H[i], draws, cfg)
            v = mixture_var(Z[keep] * sq[None, :], levels)
            for a in levels:
                q[a][i] = v[a]
    return q


def thin_draws(post, names=OPERATOR_PARAMS, n=N_PRED_DRAWS):
    """{name: n draws evenly spaced through the fit's chains x draws}, gamma as exact zeros where the fit has none."""
    total = post["k"].values.size
    idx = np.linspace(0, total - 1, min(n, total)).astype(int)
    return {p: (post[p].values.reshape(total)[idx] if p in post else np.zeros(len(idx))) for p in names}


def posterior_draws_block(S, R, H, ritc, syn, yr, held, fits, cfg, W, plug_in, levels=LEVELS, capture=None):
    """The honest version's operator leg with the fold fits' draws in place of their means, beside the plug-in figures
    (`plug_in`, the honest version's pool_rules block) for the same targets. When `capture` is a dict, each pool rule's
    VaRs {level: array} are put in it under the rule's name."""
    draws_by_label = {int(f["fold"]): {p: np.asarray(f["draws"][p], float) for p in OPERATOR_PARAMS} for f in fits}
    _edges, quart = size_quartiles(R)
    m = "operator_size_only"
    rules, against = {}, {}
    for rule, drop in (("leave_out", False), ("leave_out_and_target_year", True)):
        q = draw_quantiles(S, R, H, ritc, held, yr, draws_by_label, cfg, drop, levels)
        if capture is not None:
            capture[rule] = q
        blk = summarise_method(S, q, quart, ritc, W, levels)
        rules[rule] = {"pool": plug_in[rule]["pool"], m: blk}
        against[rule] = {"%g" % a: {
            "exceedances_all": {"posterior_draws": blk["%g" % a]["exceedances"]["all"],
                                "posterior_mean_plug_in": plug_in[rule][m]["%g" % a]["exceedances"]["all"],
                                "expected": blk["%g" % a]["expected"]["all"]},
            "pinball_mean_all": {"posterior_draws": blk["%g" % a]["pinball_mean"]["all"],
                                 "posterior_mean_plug_in": plug_in[rule][m]["%g" % a]["pinball_mean"]["all"]},
            "exceedances_by_size_quartile": {
                "posterior_draws": [blk["%g" % a]["exceedances"]["size_quartile_%d" % j] for j in (1, 2, 3, 4)],
                "posterior_mean_plug_in": [plug_in[rule][m]["%g" % a]["exceedances"]["size_quartile_%d" % j]
                                           for j in (1, 2, 3, 4)]}} for a in levels}
    return {**transfer_operator.stamp(transfer_operator.HEADLINE),
            "label": ("honest, with parameter uncertainty: the operator's predictive VaR integrates over each fold "
                      "fit's posterior draws"),
            "method": ("for each held-out target, the operator transfers the fold's pool under each of %d posterior "
                       "draws of the fold fit (evenly spaced through its chains), the transferred pools are mixed with "
                       "equal weight, and VaR_alpha is the mixture's inverse CDF; the folds, pools, targets, bootstrap "
                       "weights and splits are the honest version's" % N_PRED_DRAWS),
            "draws_per_fold": N_PRED_DRAWS, "method_scored": m,
            "pool_rules": rules,
            "against_posterior_mean_plug_in": against}


# ----------------------------------------------------------------------------- the fold refits
def fit_training(fold, k=K_HONEST):
    """The adopted model refitted on the training syndicates of one fold; returns its posterior means and diagnostics.

    A top-level function with only picklable arguments, so a pool of worker processes can run it."""
    t0 = time.time()
    S, R, H, yr, syn, ritc = load_sample()
    tr = fold_assignment(syn, k) != fold
    with pm.Model():
        b = scale_block(R[tr], H[tr], yr[tr], ritc[tr])
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S[tr])
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=SAMPLE_CORES, target_accept=TARGET_ACCEPT,
                          random_seed=FIT_SEED, progressbar=False)
    summ = az.summary(idata, var_names=list(FIT_PARAMS), hdi_prob=0.95, round_to="none")
    post = idata.posterior
    return {"fold": int(fold), "n_train": int(tr.sum()), "n_held_out": int((~tr).sum()),
            "n_train_syndicates": int(len(set(syn[tr].tolist()))),
            "n_held_out_syndicates": int(len(set(syn[~tr].tolist()))),
            "params": {p: {"mean": float(summ.loc[p, "mean"]), "hdi_2.5": float(summ.loc[p, "hdi_2.5%"]),
                           "hdi_97.5": float(summ.loc[p, "hdi_97.5%"])} for p in FIT_PARAMS},
            # gamma = 0 in the likelihood: the posterior has no gamma, and the operator reads it as 0
            "means": {p: float(post[p].values.mean()) if p in post else 0.0 for p in OPERATOR_PARAMS},
            # the draws the parameter-uncertainty version mixes over (honest_posterior_draws); not written to the record
            "draws": {p: v.tolist() for p, v in thin_draws(post).items()},
            "diagnostics": {"max_rhat": float(summ["r_hat"].max()), "min_ess_bulk": float(summ["ess_bulk"].min()),
                            "divergences": int(idata.sample_stats["diverging"].sum())},
            "seconds": time.time() - t0}


def run_folds(workers, k=K_HONEST):
    if workers <= 1:
        return [fit_training(f, k) for f in range(k)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fit_training, range(k)))


def operator_params(means):
    """The headline operator's parameters from a gamma = 0 fit's posterior means (transfer_operator.params refuses
    a fitted gamma)."""
    return transfer_operator.params(means, transfer_operator.HEADLINE)


# ------------------------------------------------------------- the vignette figures, scaled by sqrt(R)
def vignette_figures(pool, ritc_pool, draws, cfg, targets, recorded):
    """The raw, sqrt(R)-scaled and operator VaR99 / VaR99.5 at Vignette 1's target and the Vignette 2 pair, on the full
    pool, with the operator's figures checked against check_gamma0_vignette.py's record."""
    S, R, H, _synd, _year = pool
    v1, v2o, v2n = targets
    means = {p: float(np.mean(draws[p])) for p in draws}
    th = transfer_operator.params(means, transfer_operator.HEADLINE)

    def fig(pool_of):
        out = {}
        for tag, tgt in (("V1", v1), ("V2_old", v2o), ("V2_new", v2n)):
            a = pool_of(tgt)
            out[tag] = {"v99": var_q(a, 0.99), "v995": var_q(a, 0.995)}
        out["V2_d99"] = out["V2_new"]["v99"] - out["V2_old"]["v99"]
        out["V2_d995"] = out["V2_new"]["v995"] - out["V2_old"]["v995"]
        return out

    sqrt_r = fig(lambda t: S * np.sqrt(R / t[0]))
    oper = fig(lambda t: transfer(S, R, H, t, th, cfg, ritc_pool))
    raw = {"v99": var_q(S, 0.99), "v995": var_q(S, 0.995)}
    _th, cen = centres(transfer_operator.HEADLINE, pool, draws, cfg, ritc_pool, targets)
    mine = {"V1_v99": oper["V1"]["v99"], "V1_v995": oper["V1"]["v995"], "V2_old_v995": oper["V2_old"]["v995"],
            "V2_new_v995": oper["V2_new"]["v995"], "V2_d995": oper["V2_d995"]}
    rec = recorded[transfer_operator.HEADLINE]["centre"]
    if mine != cen or cen != rec:
        raise SystemExit("the operator's vignette figures differ from check_gamma0_vignette.py's: %s, %s, record %s"
                         % (mine, cen, rec))
    return {**transfer_operator.stamp(transfer_operator.HEADLINE),
            # the count is the pool's: a typed 674 outlived the sample's change to 672 (the final review of 14 October
            # 2026, P19), as did the size quartiles' label below
            "pool": "the published %d-donor pool, full sample (no donor held out)" % len(S),
            "targets": {"V1": list(v1), "V2_old": list(v2o), "V2_new": list(v2n)},
            "sqrt_R_rule": "S_i sqrt(R_i / R_target) on the same pool, read with pool_quantile.var_q",
            "raw_pool": raw, "sqrt_R": sqrt_r, "operator_size_only": oper,
            "sqrt_R_over_operator": {"V1_v99": sqrt_r["V1"]["v99"] / oper["V1"]["v99"],
                                     "V1_v995": sqrt_r["V1"]["v995"] / oper["V1"]["v995"]},
            "checked_against": "results/check_gamma0_vignette_results.json (size_only centre), equal exactly"}


# ------------------------------------------------- exceedances by size quartile, per target and by syndicate
def quartile_of(R, edges):
    """The size quartile (1..4, 1 the smallest books) of a book of size R: size_quartiles's rule, edges from the targets."""
    return int(np.searchsorted(np.asarray(edges, float), R, side="right")) + 1


def quartile_table(flags, quart, syn, W, levels=LEVELS):
    """{level: {"size_quartile_j": row}}: the operator's exceedances by size quartile, from the per-target flags `flags`
    {level: bool array}. A row holds the targets and syndicates in the quartile, the exceedances against the expected
    count, how many distinct syndicates carry the exceedances (and how many each carries), and the exceedance rate's
    posterior under the by-syndicate Bayesian bootstrap `W`: mean, 95% credible interval, and the posterior probability
    that the rate exceeds the nominal 1 - level. A posterior over the rate, not a test."""
    out = {}
    for a in levels:
        exc = np.asarray(flags[a], bool)
        tab = {}
        for j in range(4):
            mask = quart == j
            hit = syn[mask & exc].tolist()
            by_syn = {}
            for s in hit:
                by_syn[s] = by_syn.get(s, 0) + 1
            rate = rate_posterior(exc, mask, W, 1.0 - a)
            tab["size_quartile_%d" % (j + 1)] = {
                "n_targets": int(mask.sum()), "n_syndicates": int(len(set(syn[mask].tolist()))),
                "exceedances": int(len(hit)), "expected": float(mask.sum() * (1.0 - a)),
                "n_syndicates_with_exceedances": int(len(by_syn)),
                "exceedances_by_syndicate": [[s, c] for s, c in sorted(by_syn.items(), key=lambda kv: (-kv[1], kv[0]))],
                "rate_mean": rate["mean"], "rate_credible_interval_95": [rate["lo"], rate["hi"]],
                "nominal_rate": rate["nominal"], "p_rate_above_nominal": rate["share_above_nominal"]}
        out["%g" % a] = tab
    return out


def per_target_block(S, R, ritc, syn, yr, W, plug_in_q, draw_q, vignettes, levels=LEVELS):
    """The per-target exceedance flags of the headline operator, for the honest plug-in and the posterior-draw versions,
    under each pool rule, and the by-size-quartile tables built from them.

    `plug_in_q` {rule: {level: VaRs}} and `draw_q` {rule: {level: VaRs}} are the operator's VaRs; `vignettes` {tag:
    (R, H)} the vignettes' targets, whose size quartile (the targets' quartiles' edges) is recorded."""
    edges, quart = size_quartiles(R)
    sources = {"honest_plug_in": plug_in_q, "honest_posterior_draws": draw_q}
    flags, tables = {}, {}
    for src, by_rule in sources.items():
        flags[src], tables[src] = {}, {}
        for rule, q in by_rule.items():
            f = {a: np.asarray(S > q[a], bool) for a in levels}
            flags[src][rule] = {"%g" % a: f[a].astype(int).tolist() for a in levels}
            tables[src][rule] = quartile_table(f, quart, syn, W, levels)
    lo = [None] + [float(e) for e in edges]
    hi = [float(e) for e in edges] + [None]
    return {
        "targets": {"syndicate": syn.tolist(), "year": yr.tolist(), "R_gbp_m": R.tolist(),
                    "size_quartile": (quart + 1).tolist(), "ritc": ritc.astype(int).tolist()},
        "exceedance_flags": {"reading": ("1 where the realised severity S exceeds the operator's VaR at the level, in the "
                                         "order of `targets`; the headline operator (%s), pool rules as named"
                                         % OPERATOR_METHOD),
                             **flags},
        "by_size_quartile": {
            "reading": ("exceedances by quartile of the targets' R (1 the smallest books), with the by-syndicate Bayesian "
                        "bootstrap posterior of the exceedance rate (mean, 95% credible interval) and its posterior "
                        "probability of exceeding the nominal rate; a posterior, not a test. The exceedances' "
                        "concentration in syndicates is n_syndicates_with_exceedances and exceedances_by_syndicate."),
            "edges_gbp_m": [float(e) for e in edges],
            "quartile_ranges_gbp_m": {"size_quartile_%d" % (j + 1): [lo[j], hi[j]] for j in range(4)},
            **tables},
        "vignette_size_quartiles": {
            tag: {"R_gbp_m": float(t[0]), "size_quartile": quartile_of(t[0], edges)} for tag, t in vignettes.items()}}


# ----------------------------------------------------------------------------- the record
def version_block(label, note, leaks, S, R, H, ritc, syn, yr, held, thetas, cfg, W, capture=None):
    """The version's record. When `capture` is a dict, the operator's VaRs {level: array} of each pool rule are put in it
    under the rule's name."""
    cap = {rule: {} for rule in POOL_RULES}
    blk = {"label": label, "note": note, "leaks_held_out_syndicate_into_scale_law": leaks,
           "pool_rules": {
               "leave_out": {"pool": "every row whose held-out unit differs from the target's",
                             **backtest(S, R, H, ritc, syn, yr, held, thetas, cfg, False, W, capture=cap["leave_out"])},
               "leave_out_and_target_year": {
                   "pool": "as leave_out, and without the rows of the target's own reporting year",
                   **backtest(S, R, H, ritc, syn, yr, held, thetas, cfg, True, W,
                              capture=cap["leave_out_and_target_year"])}}}
    if capture is not None:
        for rule in POOL_RULES:
            capture[rule] = cap[rule]["operator"]
    return blk


def compute(workers=DEFAULT_WORKERS, k=K_HONEST, folds=None):
    t0 = time.time()
    S, R, H, yr, syn, ritc_f = load_sample()
    ritc = ritc_f.astype(bool)
    draws, ref, hlo, hce = load_draws(transfer_operator.HEADLINE)
    cfg = (ref, hlo, hce)
    edges, quart = size_quartiles(R)
    W = bayes_bootstrap_weights(syn)
    fold = fold_assignment(syn, k)

    t_fit = time.time()
    fits = folds if folds is not None else run_folds(workers, k)
    fit_wall = time.time() - t_fit
    thetas_honest = {int(f["fold"]): operator_params(f["means"]) for f in fits}
    plug_in_q, draw_q = {}, {}
    honest = version_block(
        "honest: %d-fold by syndicate, adopted model refitted on each fold's training syndicates" % k,
        "fold assignment is oos_validation.fold_assignment; held-out syndicates are in neither the pool nor the fit",
        False, S, R, H, ritc, syn, yr, fold, thetas_honest, cfg, W, capture=plug_in_q)
    honest["folds"] = k
    honest["fits"] = [{key: f[key] for key in ("fold", "n_train", "n_held_out", "n_train_syndicates",
                                               "n_held_out_syndicates", "params", "diagnostics")} for f in fits]
    t_draws = time.time()
    honest_draws = posterior_draws_block(S, R, H, ritc, syn, yr, fold, fits, cfg, W, honest["pool_rules"],
                                         capture=draw_q)
    draws_wall = time.time() - t_draws

    means_full = {p: float(np.mean(draws[p])) for p in OPERATOR_PARAMS}
    th_full = operator_params(means_full)
    thetas_cheap = {s: th_full for s in set(syn.tolist())}
    cheap = version_block(
        "cheap: leave-one-syndicate-out reusing the full-sample posterior means",
        "the pool is honest; the scale law and tail indices were fitted WITH the held-out syndicate in the sample",
        True, S, R, H, ritc, syn, yr, syn, thetas_cheap, cfg, W)
    cheap["folds"] = int(len(set(syn.tolist())))
    cheap["posterior_means_used"] = means_full

    pool = load_pool()
    ritc_pool = load_ritc(pool[3], pool[4])
    targets = load_targets()
    with io.open(GAMMA0, encoding="utf-8") as _fh:
        gamma0_record = json.load(_fh)
    figures = vignette_figures(pool, ritc_pool, draws, cfg, targets, gamma0_record)
    vig_targets = dict(zip(("V1", "V2_old", "V2_new"), targets))
    per_target = per_target_block(S, R, ritc, syn, yr, W, plug_in_q, draw_q, vig_targets)

    out = {
        **transfer_operator.stamp(transfer_operator.HEADLINE),
        "question": ("Does the operator's tail, read from the other syndicates' pool, hold out of sample: at 90, 95, "
                     "99 and 99.5%, overall and across the size of the target book, against the raw pool and the "
                     "simple sqrt(R) scaling?"),
        "n": int(len(S)), "n_syndicates": int(len(set(syn.tolist()))), "n_ritc": int(ritc.sum()),
        "levels": list(LEVELS), "methods": list(METHODS),
        "method_notes": {
            "raw_pool": "the donors' raw severities",
            "sqrt_R": "S_i sqrt(R_i / R_target): k = 1/2, no floor, no tail map",
            "operator_size_only": ("the headline operator: " + transfer_operator.CONSTRUCTION[transfer_operator.HEADLINE])},
        "overlay_sensitivity_note": "no overlay leg: the fold refits fix gamma at 0 in the likelihood, as the headline does since option B (10 October 2026), so they have no fitted concentration exponent for an overlay to apply; the overlay is reported on the full-sample gamma-free fit only",
        "ritc_targets": ("a RITC-regime held-out year is scored under the clean target regime, the only one the Python "
                         "operator has; its exceedances are reported separately"),
        "exceedance": "S_target > VaR_alpha of the transferred pool; expected rate 1 - alpha",
        "quantile_rule": "pool_quantile.var_q (the inverse CDF)",
        "size_quartiles": {"of": "R of the %d targets" % len(R), "edges_gbp_m": [float(e) for e in edges],
                           "counts": [int((quart == j).sum()) for j in range(4)]},
        "bayes_bootstrap": {"reps": BB_REPS, "seed": BB_SEED,
                            "weights": "uniform Dirichlet over syndicates, a syndicate's years sharing its weight",
                            "reading": "a posterior over the exceedance rate under the bootstrap, not a test"},
        "sampler": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS, "target_accept": TARGET_ACCEPT, "seed": FIT_SEED},
        "honest": honest,
        "honest_posterior_draws": honest_draws,
        "per_target": per_target,
        "cheap": cheap,
        "vignette_figures": figures,
        # one key the verifier strips (reproduce.VOLATILE): how long, with how many workers, on how many processors
        "runtime_seconds": {"total": time.time() - t0, "fold_fits_wall": fit_wall, "workers": int(workers),
                            "posterior_draws_scoring": draws_wall,
                            "fits_seconds": [f["seconds"] for f in fits], "logical_processors": os.cpu_count()},
    }
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    workers = int(argv[0]) if argv and argv[0].isdigit() else DEFAULT_WORKERS
    out = compute(workers)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print("Wrote %s" % OUT)
    fits = out["honest"]["fits"]
    print("  %d fold fits on %d workers, %.0f s; divergences %s, max R-hat %.4f"
          % (len(fits), workers, out["runtime_seconds"]["fold_fits_wall"],
             [f["diagnostics"]["divergences"] for f in fits], max(f["diagnostics"]["max_rhat"] for f in fits)))
    for ver in ("honest", "cheap"):
        for rule, blk in out[ver]["pool_rules"].items():
            print("  %s / %s: exceedances at 90/95/99/99.5 (expected %s)"
                  % (ver, rule, "/".join("%.1f" % blk["raw_pool"]["%g" % a]["expected"]["all"] for a in LEVELS)))
            for m in METHODS:
                print("    %-19s %s   pinball 99%% %.5f" % (
                    m, "/".join("%3d" % blk[m]["%g" % a]["exceedances"]["all"] for a in LEVELS),
                    blk[m]["0.99"]["pinball_mean"]["all"]))
    for rule, blk in out["honest_posterior_draws"]["against_posterior_mean_plug_in"].items():
        print("  honest / %s, operator over the fold fits' draws against the plug-in:" % rule)
        for a in LEVELS:
            row = blk["%g" % a]
            print("    %-6g exceedances %3d (plug-in %3d, expected %.1f)   pinball %.5f (plug-in %.5f)"
                  % (a, row["exceedances_all"]["posterior_draws"], row["exceedances_all"]["posterior_mean_plug_in"],
                     row["exceedances_all"]["expected"], row["pinball_mean_all"]["posterior_draws"],
                     row["pinball_mean_all"]["posterior_mean_plug_in"]))
    vf = out["vignette_figures"]
    print("  V1 VaR99.5: raw %.4f, sqrt(R) %.4f, operator %.4f"
          % (vf["raw_pool"]["v995"], vf["sqrt_R"]["V1"]["v995"], vf["operator_size_only"]["V1"]["v995"]))


if __name__ == "__main__":
    sys.exit(main())
