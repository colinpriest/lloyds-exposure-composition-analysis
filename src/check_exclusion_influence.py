"""Influence sensitivities: the adopted model refitted without, and with, the records the small-book discussion turns on.

Three populations are derived from the loader by declared masks over one base list, the included-data comparison:

  primary               the loader's working sample: every base record except the census's rule-8 set-aside records;
  included_data_643     the included-data comparison: the primary plus the rule-8 set-aside records at their
                        pre-census figures, which is the base itself. It is NOT the earlier 643-record sample: the
                        three records the census corrected (1609/2024, 3330/2017 and 3330/2018) keep their census
                        figures here, so only the set-aside records differ from the primary;
  primary_without_1991  the primary without every Syndicate 1991 record (an influence sensitivity, not an eligibility
                        rule).

The base is built in memory with run_analysis.load_and_classify under the primary outcome and an empty rule-8 register
(check_cohort_scope.load_sensitivity is the template), so the set-aside records carry the figures they had. The run stops
if the base without the register's records is not the working sample in model/exposure_results.json, record for record
and figure for figure, or if the base does not reproduce the fixed original size bands from its own quartiles.

FOLDS ARE NEVER REDEALT. Every cross-validation and backtest in the repository takes its folds from the frozen map
(data/fold_map.json: the 118 syndicates of the 643-record sample, dealt once; oos_validation.fold_assignment reads it and
refuses a syndicate that is not in it). A population that lacks some syndicates simply has fewer, so removing a syndicate
(the census removes 2008) or all of Syndicate 1991 moves no other syndicate. Each population here takes the map restricted
to its own syndicates, and the primary's own operator backtest (check_operator_backtest.py) uses the same map, so its
folds are this record's primary folds. The size bands are fixed too: the cutoffs of the earlier 643-record sample,
172.5745, 425.362 and 837.0151141803343 (GBP m).

For each population: the full fit and the ten held-out fold fits of the adopted model (adopted_model.scale_block,
zero location, gamma fixed at 0, the headline's sampler: 4 chains of 1,500 retained draws after 1,500 warm-up, seed 42,
target_accept 0.98). A fit that diverges is refitted once at target_accept 0.995, with the same seed, and used only if
it then converges (no divergence, max R-hat at most 1.01); both attempts are recorded. The donor pools are rebuilt from
each population's own rows (the primary pool: every row of another fold; the target-year rule: also without the target's
reporting year), and the plug-in backtest reads the headline operator at each fold fit's posterior means. The likelihood
is unweighted and the donor CDF gives every row equal mass. At 99 and 99.5% the record holds, by fixed band, the targets,
distinct syndicates, exceedances, expected count, event syndicates and event record ids, and the mean pinball loss.

Vignette 1's GBP 500m VaR99.5 per population: the operator at the full fit's posterior means on the population's donors at
the precision the shipped tool carries (severity to 8 decimals, opening reserves to 2, concentration to 6), its cutpoint
donor, and a conditional interval from the Bayesian bootstrap by syndicate (uniform Dirichlet; a syndicate's weight is
shared by its rows and normalised over the rows, row mass w_s / sum_t(n_t w_t)) with one joint posterior draw per
replicate, at vignette_uncertainty.py's seed and B. The interval is conditional on the data, the model and the
dependence treatment; it is not a total uncertainty and not a paired posterior comparison between populations.

The common targets are the rows present in every population. They exclude the rule-8 set-aside rows (which are in the
included-data comparison only) and every Syndicate 1991 target (which is in the primary and the comparison, not in the
third population). So the without-1991 contrast measures Syndicate 1991's effect on the forecasts of OTHER targets only; its
own misses are in no common target, and its removal from scoring is not part of the contrast.

The common-target comparison: the targets present in every population, with each forecast origin keeping its own fit and
donors. For each origin the smallest-band misses and mean pinball; for each pair of origins the PAIRED per-row
differences (event indicator and pinball loss, new minus old), taken row by row BEFORE any weighting, then averaged under
the syndicate weights, so that two identical forecasts give exactly zero. Subtracting two separately weighted means can
leave rounding noise where the forecasts are identical.

Stored beside the record (check_exclusion_influence_draws.npz): each fit's joint posterior draws of the eight reported
parameters (600 evenly spaced through the chains, as check_operator_backtest.thin_draws does, and every draw of each full
fit) and each population's per-target thresholds.

Writes check_exclusion_influence_results.json and check_exclusion_influence_draws.npz.
Usage:  python src/check_exclusion_influence.py [workers]
        python src/check_exclusion_influence.py --dry-run     the populations, folds and fits, with no fit
"""
import hashlib
import io
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import arviz as az
import pymc as pm

import check_cohort_scope as CS
import oos_validation as OV
import check_operator_backtest as BT
import check_small_book_diagnosis as SB
import refit_vignettes as RV
import sample_scope as SS
import transfer_operator
from adopted_model import SD, SAMPLE_CORES, check_against_headline, scale_block
from pool_quantile import var_q
from vignette_uncertainty import build_resampler, load_pool, load_targets, posterior_draw, transfer

OUT = SD / "results" / "check_exclusion_influence_results.json"
DRAWS_OUT = SD / "results" / "check_exclusion_influence_draws.npz"
EXPOSURE = SD / "model" / "exposure_results.json"
VIGNETTE_RECORD = SD / "results" / "vignette_uncertainty_results.json"
LEVELS = SB.LEVELS
RULES = SB.RULES
K_FOLDS = BT.K_HONEST
FIXED_BAND_EDGES = SB.FIXED_BAND_EDGES
EXCLUDED_SYNDICATE = 1991
#: the three records the census corrected: in the included-data comparison they keep their census figures
CENSUS_CORRECTED = ("1609_2024", "3330_2017", "3330_2018")
POPULATIONS = ("primary", "included_data_643", "primary_without_1991")
POPULATION_LABELS = {
    "primary": "the revised primary: the loader's working sample, without the census's rule-8 set-aside records",
    "included_data_643": ("the included-data comparison: the primary plus the rule-8 set-aside records at their pre-census "
                          "figures (643 records); the three corrected records keep their census figures, so this is not "
                          "the earlier 643-record sample"),
    "primary_without_1991": "the primary without every Syndicate 1991 record (an influence sensitivity)",
}
#: the base the masks are cut from, as the loader gives it: the records and the syndicates of the included-data comparison
EXPECTED_BASE = (643, 118)
#: the contrasts, each "new minus old": the forecast origin whose forecasts are new, then the one they are set against
CONTRASTS = (("included_data_643", "primary"), ("primary_without_1991", "primary"),
             ("primary_without_1991", "included_data_643"))
TARGET_ACCEPT_FIRST, TARGET_ACCEPT_RETRY = 0.98, 0.995
N_THIN = BT.N_PRED_DRAWS
V1_ALPHA = 0.995
#: vignette_uncertainty.py's seed and B (its module reads them from sys.argv at import, so they are not imported: this
#: script's own first argument is the worker count). src/test_exclusion_influence.py holds them equal to its record's.
V1_SEED, V1_B = 20240704, 4000
#: how closely the primary's Vignette 1 centre and interval ends must equal vignette_uncertainty.py's committed ones (reserve
#: fraction): the same data, model, seed and stream, so equal to the sampler's reproducibility (src/test_exclusion_influence.py)
V1_CONTROL_TOL = 1.0e-6
DEFAULT_WORKERS = BT.DEFAULT_WORKERS
GROUPS = ("all", "fixed_band_1")
CI = (2.5, 97.5)


def level_key(a):
    return SB.level_key(a)


# --------------------------------------------------------------------------------- the base and the populations
def build_frame(records, set_aside_keys):
    """The base as arrays: the records' severity, opening reserves, concentration, year, syndicate, key and
    assumed-business flag (float), with the rule-8 set-aside keys. Every set-aside key must be a base record."""
    S, R, H, yr, key = CS.arrays(records)
    syn = np.array([o["syndicate"] for o in records])
    missing = sorted(set(set_aside_keys) - set(key.tolist()))
    if missing:
        raise SystemExit("%d rule-8 set-aside records are not in the included-data base: %s" % (len(missing), missing))
    return {"S": S, "R": R, "H": H, "yr": yr, "syn": syn, "key": key, "ritc": CS.ritc_flag(key),
            "set_aside": frozenset(set_aside_keys)}


def population_masks(frame):
    """{name: bool mask over the base}: the declared masks of the three populations."""
    key, syn = frame["key"], frame["syn"]
    primary = ~np.isin(key, sorted(frame["set_aside"]))
    return {"primary": primary,
            "included_data_643": np.ones(len(key), bool),
            "primary_without_1991": primary & (syn != EXCLUDED_SYNDICATE)}


def fold_map(frame, k=K_FOLDS):
    """{syndicate: fold}: the frozen map (oos_validation.fold_assignment) on the base's syndicates."""
    folds = BT.fold_assignment(frame["syn"], k)
    return {int(s): int(f) for s, f in zip(frame["syn"].tolist(), np.asarray(folds).tolist())}


def population_arrays(frame, mask, fmap):
    """One population's arrays, in base order, with each row's fold from the base map."""
    syn = frame["syn"][mask]
    return {"S": frame["S"][mask], "R": frame["R"][mask], "H": frame["H"][mask], "yr": frame["yr"][mask], "syn": syn,
            "key": frame["key"][mask], "ritc": frame["ritc"][mask],
            "fold": np.array([fmap[int(s)] for s in syn.tolist()], int), "idx": np.flatnonzero(mask)}


def check_fixed_bands(frame, edges):
    """Stop unless the base's own quartiles are the fixed original cutoffs (to 1e-9, relative): the bands are the
    included-data comparison's, and a base on other records would use them for other books."""
    mine = np.quantile(frame["R"], [0.25, 0.5, 0.75])
    if not np.allclose(mine, np.asarray(edges, float), rtol=1e-9, atol=0.0):
        raise SystemExit("the included-data base's quartiles %s are not the fixed original size bands %s"
                         % ([float(m) for m in mine], list(edges)))
    return [float(m) for m in mine]


def check_base_is_the_stored_sample(frame, stored_records):
    """The base without the set-aside records must be the working sample in model/exposure_results.json, record for
    record and figure for figure; a stale file would otherwise be fitted as the primary."""
    S, R, H, yr, key = CS.arrays(stored_records)
    mine = ~np.isin(frame["key"], sorted(frame["set_aside"]))
    problems = []
    if sorted(frame["key"][mine].tolist()) != sorted(key.tolist()):
        only_base = sorted(set(frame["key"][mine].tolist()) - set(key.tolist()))
        only_file = sorted(set(key.tolist()) - set(frame["key"][mine].tolist()))
        problems.append("records differ (base only: %s; file only: %s)" % (only_base[:5], only_file[:5]))
    else:
        by_key = {k: i for i, k in enumerate(frame["key"].tolist())}
        order = np.array([by_key[k] for k in key.tolist()])
        if not (np.array_equal(frame["S"][order], S) and np.array_equal(frame["R"][order], R)
                and np.array_equal(frame["H"][order], H)):
            problems.append("a severity, opening reserve or concentration differs")
    if problems:
        raise SystemExit("the loader's primary is not model/exposure_results.json's working sample (%s): run the "
                         "loader pass (build_working_sample.py) first" % "; ".join(problems))
    return {"keys_equal": True, "same_order": bool(np.array_equal(frame["key"][mine], key)),
            "figures_equal": True, "n": int(mine.sum())}


# ------------------------------------------------------------------------------------------------ the fits
def fit_attempt(task, target_accept):
    """The adopted model fitted on the task's training rows at `target_accept`: check_operator_backtest.fit_training's
    fit with the training rows given, not dealt. A top-level function with picklable arguments."""
    name, tag, S, R, H, yr, syn, ritc, train = task
    t0 = time.time()
    with pm.Model():
        b = scale_block(R[train], H[train], yr[train], ritc[train])
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S[train])
        idata = pm.sample(BT.DRAWS, tune=BT.TUNE, chains=BT.CHAINS, cores=SAMPLE_CORES, target_accept=target_accept,
                          random_seed=BT.FIT_SEED, progressbar=False)
    summ = az.summary(idata, var_names=list(BT.FIT_PARAMS), hdi_prob=0.95, round_to="none")
    post = idata.posterior
    return {"population": name, "tag": tag, "n_train": int(train.sum()), "n_held_out": int((~train).sum()),
            "n_train_syndicates": int(len(set(syn[train].tolist()))),
            "n_held_out_syndicates": int(len(set(syn[~train].tolist()))),
            "params": {p: {"mean": float(summ.loc[p, "mean"]), "sd": float(summ.loc[p, "sd"]),
                           "hdi_2.5": float(summ.loc[p, "hdi_2.5%"]), "hdi_97.5": float(summ.loc[p, "hdi_97.5%"])}
                       for p in BT.FIT_PARAMS},
            # gamma = 0 in the likelihood: the posterior has no gamma, and the operator reads it as 0
            "means": {p: float(post[p].values.mean()) if p in post else 0.0 for p in BT.OPERATOR_PARAMS},
            "draws": {p: np.asarray(post[p].values, float) for p in BT.FIT_PARAMS},
            "diagnostics": {"max_rhat": float(summ["r_hat"].max()), "min_ess_bulk": float(summ["ess_bulk"].min()),
                            "divergences": int(idata.sample_stats["diverging"].sum())},
            "seconds": time.time() - t0}


def converging_task(task, fit=None):
    """One fit under the retry rule: at TARGET_ACCEPT_FIRST; if that DIVERGES, once more at TARGET_ACCEPT_RETRY with the
    same seed and every other setting unchanged, used only if that refit converges (refit_vignettes.converged: no
    divergence, max R-hat at most 1.01). A fit that fails on R-hat without a divergence is not retried. If the last
    attempt has not converged the run stops and names both attempts' diagnostics.

    Returns the reported attempt's fit with "target_accept" and "attempts" (every attempt: target_accept, diagnostics,
    converged, reported; an attempt that is not reported keeps the "params" and "means" it would have reported).
    `fit(task, target_accept)` stands in for fit_attempt (a test's). Top-level, with picklable arguments."""
    fit = fit_attempt if fit is None else fit
    attempts, fitted = [], []
    for target_accept in (TARGET_ACCEPT_FIRST, TARGET_ACCEPT_RETRY):
        f = fit(task, target_accept)
        diag = f["diagnostics"]
        ok = bool(RV.converged(diag))
        attempts.append({"target_accept": target_accept, "diagnostics": diag, "converged": ok})
        fitted.append(f)
        if ok:
            for i, (a, earlier) in enumerate(zip(attempts, fitted)):
                a["reported"] = i == len(attempts) - 1
                if not a["reported"]:
                    a["params"], a["means"] = earlier["params"], earlier["means"]
            return {**f, "target_accept": target_accept, "attempts": attempts}
        if diag["divergences"] == 0:
            break
    raise SystemExit("the %s fit of population %s has not converged (%s): no figures are written"
                     % (task[1], task[0], "; ".join("target_accept %g: %s" % (a["target_accept"], a["diagnostics"])
                                                    for a in attempts)))


def fit_tasks(pops, k=K_FOLDS):
    """[(name, tag, S, R, H, yr, syn, ritc, train)]: for each population the full fit, then the k fold fits whose
    training rows are the rows of every other fold (the base map's folds)."""
    tasks = []
    for name, p in pops.items():
        n = len(p["S"])
        tasks.append((name, "full", p["S"], p["R"], p["H"], p["yr"], p["syn"], p["ritc"], np.ones(n, bool)))
        for f in range(k):
            held = p["fold"] == f
            if not held.any() or held.all():
                raise SystemExit("population %s: fold %d holds %d of %d rows" % (name, f, int(held.sum()), n))
            tasks.append((name, "fold_%d" % f, p["S"], p["R"], p["H"], p["yr"], p["syn"], p["ritc"], ~held))
    return tasks


def run_fits(tasks, workers, fitter=None):
    fitter = converging_task if fitter is None else fitter
    if workers <= 1:
        return [fitter(t) for t in tasks]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fitter, tasks))


def thin(arr, n=N_THIN):
    """`n` draws evenly spaced through the chains x draws (check_operator_backtest.thin_draws's rule), the same indices
    for every parameter, so the thinned draws are joint."""
    a = np.asarray(arr, float).reshape(-1)
    idx = np.linspace(0, a.size - 1, min(n, a.size)).astype(int)
    return a[idx]


# --------------------------------------------------------------------------------------- the plug-in backtest
def population_thresholds(p, fits_pop, cfg, levels=LEVELS, k=K_FOLDS):
    """{rule: {level: thresholds}}: every target's plug-in VaR under the headline operator at its fold fit's posterior
    means, the donors being the population's rows of the other folds (and, under the target-year rule, of other
    reporting years), equally weighted."""
    thetas = {f: BT.operator_params(fits_pop["fold_%d" % f]["means"]) for f in range(k)}
    ritc = np.asarray(p["ritc"], bool)
    out = {}
    for rule, drop in (("leave_out", False), ("leave_out_and_target_year", True)):
        out[rule] = BT.leave_out_quantiles(p["S"], p["R"], p["H"], ritc, p["fold"], p["syn"], p["yr"], thetas, cfg, drop,
                                           levels)[BT.OPERATOR_METHOD]
    return out


def group_masks(R, edges, groups=GROUPS):
    bands = SB.band_of(R, edges)
    out = {"all": np.ones(len(R), bool)}
    for j in range(1, SB.N_BANDS + 1):
        out["fixed_band_%d" % j] = bands == j
    return {g: out[g] for g in groups}, bands


def scored_row(S, q, mask, syn, yr, level):
    """SB.group_row plus the mean pinball loss over the group."""
    flags = S > q
    row = SB.group_row(flags, mask, syn, yr, level)
    row["pinball_mean"] = float(BT.pinball(S[mask], q[mask], level).mean()) if mask.any() else None
    return row


def score_population(p, thr, edges, levels=LEVELS):
    """{rule: {level: {"all": row, "fixed_band_j": row}}}: the plug-in backtest of one population by fixed band."""
    masks, bands = group_masks(p["R"], edges, groups=("all",) + tuple("fixed_band_%d" % j for j in range(1, 5)))
    out = {}
    for rule in RULES:
        out[rule] = {level_key(a): {g: scored_row(p["S"], thr[rule][a], m, p["syn"], p["yr"], a)
                                    for g, m in masks.items()} for a in levels}
    return out


# ------------------------------------------------------------------------------- the common-target comparison
def dist(a):
    a = np.asarray(a, float)
    return {"mean": float(a.mean()), "interval_95": [float(x) for x in np.percentile(a, CI)]}


def paired_draws(delta, mask, W):
    """The weighted mean of the PER-ROW differences `delta` over the rows in `mask` under each weight draw (rows of W):
    sum_i w_i delta_i / sum_i w_i. The difference is taken row by row first; this never subtracts two weighted means."""
    delta = np.asarray(delta, float)
    Wm = W[:, mask]
    return (Wm @ delta[mask]) / Wm.sum(axis=1)


def common_index(pops):
    """The base indices present in every population, ascending."""
    common = None
    for p in pops.values():
        common = set(p["idx"].tolist()) if common is None else common & set(p["idx"].tolist())
    return np.array(sorted(common), int)


def common_view(p, common):
    """`p`'s rows at the common base indices, in base order (p['idx'] is ascending, so every population aligns)."""
    pos = np.flatnonzero(np.isin(p["idx"], common))
    return pos


def common_target_comparison(pops, thr, edges, levels=LEVELS, reps=BT.BB_REPS, seed=BT.BB_SEED, contrasts=CONTRASTS):
    """Each origin's smallest-band misses and mean pinball on the targets present in every population, and the paired
    contrasts between origins with their conditional bootstrap summaries."""
    common = common_index(pops)
    if not len(common):
        raise SystemExit("no target is present in every population")
    view = {name: common_view(p, common) for name, p in pops.items()}
    ref = next(iter(pops))
    # the targets are the same rows in every population: check, on the quantities that define them
    for name, p in pops.items():
        if not (np.array_equal(p["key"][view[name]], pops[ref]["key"][view[ref]])
                and np.array_equal(p["R"][view[name]], pops[ref]["R"][view[ref]])
                and np.array_equal(p["S"][view[name]], pops[ref]["S"][view[ref]])):
            raise SystemExit("population %s's common targets are not the other populations' rows" % name)
    c = {k: pops[ref][k][view[ref]] for k in ("S", "R", "syn", "yr", "key")}
    masks, bands = group_masks(c["R"], edges)
    W = BT.bayes_bootstrap_weights(c["syn"], reps=reps, seed=seed)
    exc = {n: {} for n in pops}
    loss = {n: {} for n in pops}
    for n in pops:
        for rule in RULES:
            for a in levels:
                q = thr[n][rule][a][view[n]]
                exc[n][(rule, a)] = c["S"] > q
                loss[n][(rule, a)] = BT.pinball(c["S"], q, a)
    origins = {n: {rule: {level_key(a): {g: {**SB.group_row(exc[n][(rule, a)], m, c["syn"], c["yr"], a),
                                             "pinball_mean": float(loss[n][(rule, a)][m].mean()) if m.any() else None}
                                          for g, m in masks.items()} for a in levels} for rule in RULES}
               for n in pops}
    paired = {}
    for new, old in contrasts:
        name = "%s_minus_%s" % (new, old)
        paired[name] = {}
        for rule in RULES:
            paired[name][rule] = {}
            for a in levels:
                e_new, e_old = exc[new][(rule, a)], exc[old][(rule, a)]
                l_new, l_old = loss[new][(rule, a)], loss[old][(rule, a)]
                d_e = e_new.astype(float) - e_old.astype(float)         # per row, before any weighting
                d_l = l_new - l_old
                paired[name][rule][level_key(a)] = {}
                for g, m in masks.items():
                    de, dl = paired_draws(d_e, m, W), paired_draws(d_l, m, W)
                    old_mean = paired_draws(l_old, m, W)
                    with np.errstate(divide="ignore", invalid="ignore"):
                        rel = np.where(old_mean > 0, dl / old_mean, np.nan)
                    rel_ok = np.isfinite(rel).all()
                    n_m = int(m.sum())
                    paired[name][rule][level_key(a)][g] = {
                        "n_targets": n_m,
                        "events_old": int((e_old & m).sum()), "events_new": int((e_new & m).sum()),
                        "new_events": int((e_new & ~e_old & m).sum()), "removed_events": int((e_old & ~e_new & m).sum()),
                        "rate_difference_point": float(d_e[m].mean()) if n_m else None,
                        "pinball_mean_old": float(l_old[m].mean()) if n_m else None,
                        "pinball_mean_new": float(l_new[m].mean()) if n_m else None,
                        "pinball_difference_point": float(d_l[m].mean()) if n_m else None,
                        "pinball_relative_change_point": (float(l_new[m].mean() / l_old[m].mean() - 1.0)
                                                          if n_m and l_old[m].mean() > 0 else None),
                        "rate_difference_bootstrap": dist(de),
                        "pinball_difference_bootstrap": dist(dl),
                        "pinball_relative_change_bootstrap": dist(rel) if rel_ok else None,
                        "p_rate_increase": float((de > 0).mean()),
                        "p_pinball_improvement": float((dl < 0).mean())}
    return {"targets": {"n": int(len(common)), "n_syndicates": int(len(set(c["syn"].tolist()))),
                        "n_in_fixed_band_1": int(masks["fixed_band_1"].sum()),
                        "record_ids": c["key"].tolist()},
            "bootstrap": {"reps": reps, "seed": seed,
                          "weights": ("uniform Dirichlet over the common targets' syndicates; a syndicate's weight is "
                                      "shared by its rows and normalised over the rows of the group"),
                          "paired_difference_arithmetic": ("the per-row difference (new minus old) in the event "
                                                           "indicator and the pinball loss is taken first and then "
                                                           "weighted; two identical forecasts give exactly zero"),
                          "reading": ("a posterior over the average difference under the bootstrap, conditional on "
                                      "the computed forecasts and the observed population: not a total uncertainty, "
                                      "not a paired posterior comparison of the models, and no test")},
            "origins": origins, "paired": paired}


# ---------------------------------------------------------------------------------------- Vignette 1 per population
def shipped_precision(p):
    """The population's donors at the precision the shipped tool carries (severity to 8 decimals, opening reserves to
    2, concentration to 6), by Python's round as the tool's builder uses it, with the donor keys."""
    S = np.array([round(float(x), 8) for x in p["S"]], float)
    R = np.array([round(float(x), 2) for x in p["R"]], float)
    H = np.array([round(float(x), 6) for x in p["H"]], float)
    return S, R, H, np.asarray(p["syn"]), np.asarray(p["yr"]), np.asarray(p["ritc"], bool), np.asarray(p["key"])


def operator_draws_of(full_fit):
    """The operator's parameters' draws of a full fit, flattened chain by chain (gamma as exact zeros)."""
    d = {p: np.asarray(full_fit["draws"][p], float).reshape(-1) for p in BT.OPERATOR_PARAMS if p in full_fit["draws"]}
    n = len(d["k"])
    d["gamma"] = np.zeros(n)
    return {p: d[p] for p in BT.OPERATOR_PARAMS}


def vignette1_block(p, full_fit, cfg, target, b=V1_B, seed=V1_SEED, alpha=V1_ALPHA):
    """Vignette 1's VaR at `alpha` on the population's donors: the operator at the full fit's posterior means, its
    cutpoint donor, and the conditional interval (Bayesian bootstrap by syndicate x one joint posterior draw per
    replicate, vignette_uncertainty.py's stream). Returns (record, the replicates' VaRs)."""
    S, R, H, syn, yr, ritc, keys = shipped_precision(p)
    draws = transfer_operator.params(operator_draws_of(full_fit), transfer_operator.HEADLINE)
    thbar = {k: float(draws[k].mean()) for k in draws}
    adj = transfer(S, R, H, target, thbar, cfg, ritc)
    q = var_q(adj, alpha)
    atom = keys[adj == q].tolist()
    order = np.argsort(-adj, kind="stable")[:5]
    draw = build_resampler(syn, yr, "bayes")
    rng = np.random.default_rng(seed)
    ndraw = len(draws["k"])
    reps = np.empty(b)
    for r in range(b):
        idx, w = draw(rng)
        th = posterior_draw(draws, rng, ndraw)
        reps[r] = var_q(transfer(S[idx], R[idx], H[idx], target, th, cfg, ritc[idx]), alpha, w)
    lo, hi = (float(x) for x in np.percentile(reps, CI))
    return {"n_donors": int(len(S)), "n_syndicates": int(len(set(syn.tolist()))), "n_assumed_business": int(ritc.sum()),
            "target": {"reserve_size_gbp_m": float(target[0]), "hhi": float(target[1])},
            "alpha": alpha,
            "centre_reserve_fraction": float(q), "centre_gbp_m": float(q * target[0]),
            "cutpoint_donor": atom, "support_at_or_above": int((adj >= q).sum()),
            "most_adverse_donors": [{"donor": str(keys[i]), "transferred_severity": float(adj[i])} for i in order],
            "conditional_interval_95": [lo, hi],
            "conditional_interval_95_gbp_m": [lo * target[0], hi * target[0]],
            "replicate_mean": float(reps.mean()), "replicate_median": float(np.median(reps)),
            "interval": {"B": b, "seed": seed, "rule": "2.5 and 97.5 percentiles of the replicates' VaRs"},
            "reading": ("conditional on the population's data, the model and the dependence treatment; syndicate "
                        "reweighting does not correct the posterior's conditional independence; not a total "
                        "uncertainty and not a paired posterior comparison between populations")}, reps


# ---------------------------------------------------------------------------------------------- the record
def fit_summary(f):
    return {"n_train": f["n_train"], "n_held_out": f["n_held_out"], "n_train_syndicates": f["n_train_syndicates"],
            "n_held_out_syndicates": f["n_held_out_syndicates"], "params": f["params"],
            "diagnostics": f["diagnostics"], "target_accept": f["target_accept"], "attempts": f["attempts"]}


def population_summary(name, p, edges):
    own = SB.own_edges(p["R"])
    extra = ({"composition": ("the primary plus the rule-8 set-aside rows at their pre-census figures; the three records the "
                              "census corrected (%s) are at their census figures, so this is not the earlier 643-record "
                              "sample" % ", ".join(CENSUS_CORRECTED)),
              "census_corrected_records_at_census_figures": list(CENSUS_CORRECTED)}
             if name == "included_data_643" else {})
    return {**extra, "label": POPULATION_LABELS[name], "n": int(len(p["S"])), "n_syndicates": int(len(set(p["syn"].tolist()))),
            "n_assumed_business": int(np.asarray(p["ritc"], bool).sum()),
            "n_syndicate_1991_records": int((p["syn"] == EXCLUDED_SYNDICATE).sum()),
            "fixed_band_counts": [int((SB.band_of(p["R"], edges) == j).sum()) for j in range(1, SB.N_BANDS + 1)],
            "own_quartile_edges_gbp_m": list(own),
            "fold_sizes": [int((p["fold"] == f).sum()) for f in range(K_FOLDS)]}


def compute(frame, cfg, target, fitter=None, workers=DEFAULT_WORKERS, edges=FIXED_BAND_EDGES, expected_base=None,
            stored_records=None, shipped=None, vignette_record=None, headline_check=False, b=V1_B, reps=BT.BB_REPS):
    """The record and the arrays stored beside it. `fitter(task)` stands in for converging_task (a test's, which must
    be picklable where workers > 1). `expected_base` (records, syndicates) is checked against the base; `stored_records`
    (model/exposure_results.json's working sample), `shipped` (the vignette steps' pool) and `vignette_record` are
    controls, each skipped where None."""
    t0 = time.time()
    n_base, n_syn = len(frame["S"]), len(set(frame["syn"].tolist()))
    if expected_base is not None and (n_base, n_syn) != tuple(expected_base):
        raise SystemExit("the included-data base is %d records from %d syndicates, not the %d from %d the fixed bands "
                         "and fold map were set on" % (n_base, n_syn, expected_base[0], expected_base[1]))
    controls = {"fixed_bands_reproduced_by_the_base_quartiles": check_fixed_bands(frame, edges)}
    if stored_records is not None:
        controls["primary_equals_model_exposure_results"] = check_base_is_the_stored_sample(frame, stored_records)
    masks = population_masks(frame)
    fmap = fold_map(frame)
    pops = {name: population_arrays(frame, masks[name], fmap) for name in POPULATIONS}
    for name, p in pops.items():
        base_fold = np.array([fmap[int(s)] for s in p["syn"].tolist()])
        if not np.array_equal(p["fold"], base_fold):
            raise SystemExit("population %s's folds are not the base map restricted" % name)
    if shipped is not None:
        controls["primary_pool_equals_the_vignette_pool"] = check_vignette_pool(pops["primary"], shipped)

    tasks = fit_tasks(pops)
    t_fit = time.time()
    done = run_fits(tasks, workers, fitter)
    fit_wall = time.time() - t_fit
    fits = {name: {} for name in pops}
    for f in done:
        fits[f["population"]][f["tag"]] = f

    thr = {name: population_thresholds(pops[name], fits[name], cfg) for name in pops}
    backtest = {name: score_population(pops[name], thr[name], edges) for name in pops}
    common = common_target_comparison(pops, thr, edges, reps=reps)
    n_1991 = int((frame["syn"] == EXCLUDED_SYNDICATE).sum())
    common["targets"]["excludes"] = {
        "rule_8_set_aside_rows": sorted(frame["set_aside"]), "n_syndicate_1991_targets": n_1991,
        "reading": ("the common targets exclude the %d rule-8 set-aside rows (in the included-data comparison only) and "
                    "all %d Syndicate %d targets (not in the third population), so the without-1991 contrast measures "
                    "Syndicate %d's effect on the forecasts of other targets only; its own misses are in no common "
                    "target" % (len(frame["set_aside"]), n_1991, EXCLUDED_SYNDICATE, EXCLUDED_SYNDICATE))}
    v1, v1_reps = {}, {}
    for name in pops:
        v1[name], v1_reps[name] = vignette1_block(pops[name], fits[name]["full"], cfg, target, b=b)
    if headline_check:
        ok, rows = check_against_headline({p: fits["primary"]["full"]["draws"][p].reshape(-1)
                                           for p in fits["primary"]["full"]["draws"]})
        controls["primary_full_fit_vs_the_published_headline"] = {"consistent": bool(ok), "rows": rows}
        if not ok:
            raise SystemExit("the primary's full refit is not the published headline fit (%s): the fits and the "
                             "published posterior are on different data" % rows)
    if vignette_record is not None:
        controls["primary_vignette1_vs_vignette_uncertainty"] = vignette_control(v1["primary"], vignette_record)

    arrays = {}
    for name in pops:
        arrays["%s__keys" % name] = np.array(pops[name]["key"], dtype=str)
        arrays["%s__fold" % name] = pops[name]["fold"]
        for rule in RULES:
            for a in LEVELS:
                arrays["%s__threshold__%s__%s" % (name, rule, level_key(a))] = np.asarray(thr[name][rule][a], float)
        arrays["%s__v1_var995_replicates" % name] = v1_reps[name]
        for tag, f in fits[name].items():
            for prm in BT.FIT_PARAMS:
                arrays["%s__%s__%s" % (name, tag, prm)] = thin(f["draws"][prm])
        for prm in BT.FIT_PARAMS:
            arrays["%s__full_all__%s" % (name, prm)] = np.asarray(fits[name]["full"]["draws"][prm], float)

    record = {
        **transfer_operator.stamp(transfer_operator.HEADLINE),
        "question": ("How far do the records the small-book discussion turns on move the adopted model's held-out "
                     "adverse tail and Vignette 1's stress: the primary, the included-data comparison and the primary "
                     "without Syndicate 1991, on one fold map and one set of size bands?"),
        "reading": ("influence sensitivities on fixed folds and fixed bands: they do not select the sample, they are not "
                    "calibration evidence, and the bootstrap summaries are conditional on the computed forecasts"),
        "loader_run_id_without_calibration": loader_run_id(),
        "populations": {name: population_summary(name, pops[name], edges) for name in pops},
        "masks": {"primary": "every base record except the rule-8 set-aside records",
                  "included_data_643": "every base record (the primary plus the rule-8 set-aside records)",
                  "primary_without_1991": "the primary less every record of Syndicate %d" % EXCLUDED_SYNDICATE,
                  "rule_8_set_aside_records": sorted(frame["set_aside"])},
        "fold_map": {"rule": ("the frozen map data/fold_map.json (oos_validation.fold_assignment), dealt once on the "
                              "643-record sample's 118 syndicates; the base has %d of them, and every population takes "
                              "the map restricted to its own syndicates, so no fold is redealt" % n_syn),
                     "source_file": "data/fold_map.json",
                     "k": K_FOLDS, "syndicate_to_fold": {str(s): f for s, f in sorted(fmap.items())},
                     "file_sha256": OV.fold_map_sha256(),
                     "fold_digest_k10": hashlib.sha256(json.dumps(sorted(fmap.items())).encode()).hexdigest(),
                     "fold_digest_k10_is": ("SHA-256 of this base's sorted (syndicate, fold) pairs at k = 10, the "
                                            "restriction of the map to the base; file_sha256 is the map file's own "
                                            "canonical content")},
        "fixed_bands": {"edges_gbp_m": [float(e) for e in edges],
                        "reading": ("the cutoffs of the earlier 643-record sample, held fixed; reproduced by the "
                                    "included-data base's own quartiles"), "rule": "np.searchsorted(edges, R, side='right') + 1"},
        "sampler": {"draws": BT.DRAWS, "tune": BT.TUNE, "chains": BT.CHAINS, "target_accept": TARGET_ACCEPT_FIRST,
                    "seed": BT.FIT_SEED, "target_accept_retry": TARGET_ACCEPT_RETRY,
                    "retry_rule": ("a fit that diverges at target_accept is refitted once at target_accept_retry, same "
                                   "seed, and used only if that refit converges (no divergence, max R-hat <= 1.01); the "
                                   "run stops if it does not"),
                    "model": "adopted_model.scale_block, zero location, gamma fixed at 0, likelihood unweighted"},
        "weighting": {"likelihood": "unweighted, one term per row",
                      "donor_cdf": "every donor row has equal mass, at the fit's posterior means",
                      "bootstrap": ("uniform Dirichlet over syndicates; a syndicate's weight is shared by its rows and "
                                    "normalised over rows, row mass w_s / sum_t(n_t w_t), not w_s / n_s")},
        "exceedance": "S_target > the plug-in VaR of the rebuilt pool (strict); expected rate 1 - level",
        "fits": {name: {tag: fit_summary(f) for tag, f in fits[name].items()} for name in pops},
        "folds_retried": {name: [tag for tag, f in fits[name].items() if len(f["attempts"]) > 1] for name in pops},
        "plug_in_backtest": backtest,
        "vignette_1": v1,
        "common_target_comparison": common,
        "controls": controls,
        "arrays": {"file": "results/check_exclusion_influence_draws.npz",
                   "reading": ("<population>__<fold_j|full>__<parameter>: 600 joint posterior draws evenly spaced "
                               "through the chains; <population>__full_all__<parameter>: every draw of the full fit, "
                               "chains x draws; <population>__threshold__<rule>__<level>: each target's plug-in VaR, "
                               "in the order of <population>__keys; <population>__v1_var995_replicates: Vignette 1's "
                               "bootstrap replicates"),
                   "names": sorted(arrays)},
        "runtime_seconds": {"total": time.time() - t0, "fits_wall": fit_wall, "workers": int(workers),
                            "fits_seconds": [f["seconds"] for f in done]},
    }
    return record, arrays


def check_vignette_pool(p, pool):
    """Whether the primary's donors at the shipped tool's precision are the pool the vignette steps use (vignette_uncertainty
    .load_pool: donor_pool.py from model/exposure_results.json), key for key and value for value, RECORDED and not
    enforced. They are the same donors by construction; a difference means model/exposure_results.json is not the sample
    this record was built from. The Vignette 1 figures here are built from each population's own records."""
    S, R, H, synd, year = pool
    skeys = ["%s_%s" % (s, y) for s, y in zip(synd.tolist(), year.tolist())]
    mS, mR, mH, _syn, _yr, _ritc, mkeys = shipped_precision(p)
    theirs = {k: (float(s), float(r), float(h)) for k, s, r, h in zip(skeys, S, R, H)}
    mine = {k: (float(s), float(r), float(h)) for k, s, r, h in zip(mkeys.tolist(), mS, mR, mH)}
    only_pool = sorted(set(theirs) - set(mine))
    only_primary = sorted(set(mine) - set(theirs))
    differ = sorted(k for k in set(theirs) & set(mine) if theirs[k] != mine[k])
    equal = not (only_pool or only_primary or differ)
    out = {"n_vignette_pool": len(skeys), "n_primary": len(mkeys), "equal": bool(equal),
           "keys_only_in_the_vignette_pool": only_pool, "keys_only_in_the_primary": only_primary,
           "values_that_differ": differ,
           "reading": ("the pool the vignette steps use is the primary's, to the shipped tool's rounding" if equal else
                       "the pool the vignette steps use (model/exposure_results.json through donor_pool.py) is not this "
                       "primary: rerun the loader step before the paper quotes their Vignette 1 figures")}
    if not equal:
        print("WARNING: %s" % out["reading"])
    return out


def vignette_control(block, rec):
    """The primary's Vignette 1 against vignette_uncertainty.py's record of the headline: recorded, not asserted (a
    fresh fit can differ from the published draws in the last digits)."""
    centre = rec["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
    ci = rec["vignette1"]["adjusted"]["var995"]
    return {"centre_here": block["centre_reserve_fraction"], "centre_recorded": centre,
            "centre_difference": block["centre_reserve_fraction"] - centre,
            "interval_here": block["conditional_interval_95"], "interval_recorded": [ci["lo"], ci["hi"]],
            "interval_difference": [block["conditional_interval_95"][0] - ci["lo"],
                                    block["conditional_interval_95"][1] - ci["hi"]]}


def loader_run_id():
    if not EXPOSURE.exists():
        return None
    with io.open(str(EXPOSURE), encoding="utf-8") as fh:
        return json.load(fh).get("analysis_run_id_without_calibration")


# ------------------------------------------------------------------------------------------------- the loader
def load_base():
    """(base records, rule-8 set-aside keys): the primary outcome with an empty rule-8 register, so the set-aside records
    carry their figures, run through the loader's own later steps (check_cohort_scope.load_sensitivity)."""
    import run_analysis as ra
    register = ra.load_source_history_set_aside
    keys = sorted(register().keys())
    if not keys:
        raise SystemExit("data/restated_base_excluded.json holds no rule-8 set-aside record")

    def loader():
        ra.load_source_history_set_aside = lambda path=None: {}
        try:
            return ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)
        finally:
            ra.load_source_history_set_aside = register

    _all, working = CS.load_sensitivity(loader)
    return working, keys


def dry_run(frame, workers):
    masks = population_masks(frame)
    fmap = fold_map(frame)
    print("base: %d records, %d syndicates; rule-8 set-aside records: %d"
          % (len(frame["S"]), len(set(frame["syn"].tolist())), len(frame["set_aside"])))
    pops = {name: population_arrays(frame, masks[name], fmap) for name in POPULATIONS}
    for name, p in pops.items():
        print("  %-22s %4d records, %3d syndicates, %2d assumed-business; fold sizes %s"
              % (name, len(p["S"]), len(set(p["syn"].tolist())), int(np.asarray(p["ritc"], bool).sum()),
                 [int((p["fold"] == f).sum()) for f in range(K_FOLDS)]))
    tasks = fit_tasks(pops)
    print("fits: %d (%d populations x (1 full + %d folds)), %d workers, nothing is fitted" % (
        len(tasks), len(pops), K_FOLDS, workers))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv
    nums = [a for a in argv if a.isdigit()]
    workers = int(nums[0]) if nums else DEFAULT_WORKERS
    records, set_aside = load_base()
    frame = build_frame(records, set_aside)
    if dry:
        return dry_run(frame, workers)
    _draws, ref, hlo, hce = transfer_operator.load_draws(transfer_operator.HEADLINE)
    with io.open(str(VIGNETTE_RECORD), encoding="utf-8") as fh:
        vrec = json.load(fh)
    record, arrays = compute(
        frame, (ref, hlo, hce), load_targets()[0], workers=workers, expected_base=EXPECTED_BASE,
        stored_records=SS.primary(), shipped=load_pool(), vignette_record=vrec, headline_check=True)
    with io.open(str(OUT), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, indent=1) + "\n")
    np.savez_compressed(str(DRAWS_OUT), **arrays)
    print("Wrote %s and %s" % (OUT, DRAWS_OUT))
    for name in POPULATIONS:
        pq = record["plug_in_backtest"][name]["leave_out"]
        v = record["vignette_1"][name]
        print("  %-22s n=%d; band 1 q99.5 %d/%d, q99 %d/%d; V1 VaR99.5 %.4f [%.4f, %.4f], cutpoint %s"
              % (name, record["populations"][name]["n"],
                 pq["0.995"]["fixed_band_1"]["exceedances"], pq["0.995"]["fixed_band_1"]["n_targets"],
                 pq["0.99"]["fixed_band_1"]["exceedances"], pq["0.99"]["fixed_band_1"]["n_targets"],
                 v["centre_reserve_fraction"], v["conditional_interval_95"][0], v["conditional_interval_95"][1],
                 v["cutpoint_donor"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
