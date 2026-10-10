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
  operator_size_only  the paper's headline operator, vignette_uncertainty.transfer with gamma = 0
                    (transfer_operator.params), the floor and the de-RITC tail map. A RITC-regime target is scored
                    under the clean target regime, the only one the Python operator has.
A fourth, operator_overlay, applies the fitted concentration exponent (the labelled sensitivity).
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

For each version, pool rule and method the record holds: exceedance counts against expected counts overall, by size
quartile of the target's R, and for clean and RITC years separately; the mean pinball (quantile) loss at each level,
the same splits; and the exceedance rate under a by-syndicate Bayesian bootstrap (Rubin; uniform Dirichlet weights over
syndicates, every year of a syndicate sharing its weight), with the share of the posterior above the nominal rate.
That is a posterior over the rate, not a test. Power in the far tail is small (3.4 exceedances expected at 99.5% in 674).

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
from vignette_uncertainty import transfer, load_pool, load_draws, load_ritc, load_targets

OUT = SD / "results" / "check_operator_backtest_results.json"
GAMMA0 = SD / "results" / "check_gamma0_vignette_results.json"
LEVELS = (0.90, 0.95, 0.99, 0.995)
#: the methods, in the record's order; the first three are the comparison, the fourth the labelled sensitivity
METHODS = ("raw_pool", "sqrt_R", "operator_size_only", "operator_overlay")
K_HONEST = 10
DEFAULT_WORKERS = 3
DRAWS, TUNE, CHAINS, TARGET_ACCEPT, FIT_SEED = 1500, 1500, 4, 0.98, 42     # calibrate_dispersion_ritc.py's
FIT_PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s")
OPERATOR_PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")
POOL_RULES = ("leave_out", "leave_out_and_target_year")
BB_REPS, BB_SEED = 4000, 20261010
CI = (2.5, 97.5)


# ----------------------------------------------------------------------------- scoring
def size_quartiles(R):
    """(edges, index 0..3) of each target's R among all targets: quartile 0 holds the smallest books."""
    edges = np.quantile(R, [0.25, 0.5, 0.75])
    return edges, np.searchsorted(edges, R, side="right")


def pinball(S, q, a):
    """The quantile (pinball) loss of a level-a quantile forecast q for the outcome S: (a - 1[S < q]) (S - q)."""
    S, q = np.asarray(S, float), np.asarray(q, float)
    return (a - (S < q)) * (S - q)


def method_pools(Sp, Rp, Hp, rp, target, th_head, th_over, cfg):
    """The four transferred pools for one target (R, H), from the donor rows (Sp, Rp, Hp, rp)."""
    Rt = target[0]
    return {"raw_pool": Sp,
            "sqrt_R": Sp * np.sqrt(Rp / Rt),
            "operator_size_only": transfer(Sp, Rp, Hp, target, th_head, cfg, rp),
            "operator_overlay": transfer(Sp, Rp, Hp, target, th_over, cfg, rp)}


def leave_out_quantiles(S, R, H, ritc, held, syn, yr, thetas, cfg, drop_year, levels=LEVELS):
    """Every target's VaR under every method.

    `held[i]` labels target i's held-out unit (its fold, or its syndicate): the pool for target i is every row whose
    label differs, and, when `drop_year`, every row not in its reporting year as well. `thetas[label]` is the pair
    (headline parameters, overlay parameters) the operator uses for that unit. Returns {method: {level: array}}."""
    n = len(S)
    q = {m: {a: np.empty(n) for a in levels} for m in METHODS}
    for i in range(n):
        keep = held != held[i]
        if drop_year:
            keep &= yr != yr[i]
        th_head, th_over = thetas[held[i]]
        pools = method_pools(S[keep], R[keep], H[keep], ritc[keep], (R[i], H[i]), th_head, th_over, cfg)
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


def backtest(S, R, H, ritc, syn, yr, held, thetas, cfg, drop_year, W, levels=LEVELS):
    q = leave_out_quantiles(S, R, H, ritc, held, syn, yr, thetas, cfg, drop_year, levels)
    _edges, quart = size_quartiles(R)
    return {m: summarise_method(S, q[m], quart, ritc, W, levels) for m in METHODS}


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
            "means": {p: float(post[p].values.mean()) for p in OPERATOR_PARAMS},
            "diagnostics": {"max_rhat": float(summ["r_hat"].max()), "min_ess_bulk": float(summ["ess_bulk"].min()),
                            "divergences": int(idata.sample_stats["diverging"].sum())},
            "seconds": time.time() - t0}


def run_folds(workers, k=K_HONEST):
    if workers <= 1:
        return [fit_training(f, k) for f in range(k)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fit_training, range(k)))


def operator_pair(means):
    """(headline parameters, overlay parameters) from posterior means: gamma zeroed, or as fitted."""
    return (transfer_operator.params(means, transfer_operator.HEADLINE),
            transfer_operator.params(means, transfer_operator.SENSITIVITY))


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
            "pool": "the published 674-donor pool, full sample (no donor held out)",
            "targets": {"V1": list(v1), "V2_old": list(v2o), "V2_new": list(v2n)},
            "sqrt_R_rule": "S_i sqrt(R_i / R_target) on the same pool, read with pool_quantile.var_q",
            "raw_pool": raw, "sqrt_R": sqrt_r, "operator_size_only": oper,
            "sqrt_R_over_operator": {"V1_v99": sqrt_r["V1"]["v99"] / oper["V1"]["v99"],
                                     "V1_v995": sqrt_r["V1"]["v995"] / oper["V1"]["v995"]},
            "checked_against": "results/check_gamma0_vignette_results.json (size_only centre), equal exactly"}


# ----------------------------------------------------------------------------- the record
def version_block(label, note, leaks, S, R, H, ritc, syn, yr, held, thetas, cfg, W):
    return {"label": label, "note": note, "leaks_held_out_syndicate_into_scale_law": leaks,
            "pool_rules": {
                "leave_out": {"pool": "every row whose held-out unit differs from the target's",
                              **backtest(S, R, H, ritc, syn, yr, held, thetas, cfg, False, W)},
                "leave_out_and_target_year": {
                    "pool": "as leave_out, and without the rows of the target's own reporting year",
                    **backtest(S, R, H, ritc, syn, yr, held, thetas, cfg, True, W)}}}


def compute(workers=DEFAULT_WORKERS, k=K_HONEST, folds=None):
    t0 = time.time()
    S, R, H, yr, syn, ritc_f = load_sample()
    ritc = ritc_f.astype(bool)
    draws, ref, hlo, hce = load_draws()
    cfg = (ref, hlo, hce)
    edges, quart = size_quartiles(R)
    W = bayes_bootstrap_weights(syn)
    fold = fold_assignment(syn, k)

    t_fit = time.time()
    fits = folds if folds is not None else run_folds(workers, k)
    fit_wall = time.time() - t_fit
    thetas_honest = {int(f["fold"]): operator_pair(f["means"]) for f in fits}
    honest = version_block(
        "honest: %d-fold by syndicate, adopted model refitted on each fold's training syndicates" % k,
        "fold assignment is oos_validation.fold_assignment; held-out syndicates are in neither the pool nor the fit",
        False, S, R, H, ritc, syn, yr, fold, thetas_honest, cfg, W)
    honest["folds"] = k
    honest["fits"] = [{key: f[key] for key in ("fold", "n_train", "n_held_out", "n_train_syndicates",
                                               "n_held_out_syndicates", "params", "diagnostics")} for f in fits]

    means_full = {p: float(np.mean(draws[p])) for p in OPERATOR_PARAMS}
    pair = operator_pair(means_full)
    thetas_cheap = {s: pair for s in set(syn.tolist())}
    cheap = version_block(
        "cheap: leave-one-syndicate-out reusing the full-sample posterior means",
        "the pool is honest; the scale law and tail indices were fitted WITH the held-out syndicate in the sample",
        True, S, R, H, ritc, syn, yr, syn, thetas_cheap, cfg, W)
    cheap["folds"] = int(len(set(syn.tolist())))
    cheap["posterior_means_used"] = means_full

    pool = load_pool()
    ritc_pool = load_ritc(pool[3], pool[4])
    figures = vignette_figures(pool, ritc_pool, draws, cfg, load_targets(), json.load(io.open(GAMMA0, encoding="utf-8")))

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
            "operator_size_only": ("the headline operator: " + transfer_operator.CONSTRUCTION[transfer_operator.HEADLINE]),
            "operator_overlay": ("a labelled sensitivity: "
                                 + transfer_operator.CONSTRUCTION[transfer_operator.SENSITIVITY])},
        "overlay_sensitivity": transfer_operator.stamp(transfer_operator.SENSITIVITY),
        "ritc_targets": ("a RITC-regime held-out year is scored under the clean target regime, the only one the Python "
                         "operator has; its exceedances are reported separately"),
        "exceedance": "S_target > VaR_alpha of the transferred pool; expected rate 1 - alpha",
        "quantile_rule": "pool_quantile.var_q (the inverse CDF)",
        "size_quartiles": {"of": "R of the 674 targets", "edges_gbp_m": [float(e) for e in edges],
                           "counts": [int((quart == j).sum()) for j in range(4)]},
        "bayes_bootstrap": {"reps": BB_REPS, "seed": BB_SEED,
                            "weights": "uniform Dirichlet over syndicates, a syndicate's years sharing its weight",
                            "reading": "a posterior over the exceedance rate under the bootstrap, not a test"},
        "sampler": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS, "target_accept": TARGET_ACCEPT, "seed": FIT_SEED},
        "honest": honest,
        "cheap": cheap,
        "vignette_figures": figures,
        # one key the verifier strips (reproduce.VOLATILE): how long, with how many workers, on how many processors
        "runtime_seconds": {"total": time.time() - t0, "fold_fits_wall": fit_wall, "workers": int(workers),
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
    vf = out["vignette_figures"]
    print("  V1 VaR99.5: raw %.4f, sqrt(R) %.4f, operator %.4f"
          % (vf["raw_pool"]["v995"], vf["sqrt_R"]["V1"]["v995"], vf["operator_size_only"]["V1"]["v995"]))


if __name__ == "__main__":
    sys.exit(main())
