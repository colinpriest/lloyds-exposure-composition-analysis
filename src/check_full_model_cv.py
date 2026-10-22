"""The adopted two-regime model scored by held-out density, on the cross-validation's folds (reviewer 2).

Table 4's cross-validation (oos_validation.py, oos_size_only.py) scores single-regime models without the
reporting-year shock: the composition model, the size-only model and the naive market pool. They validate the scale
form. The model the paper adopts is the two-regime fit (adopted_model.scale_block with gamma fixed at 0 in the
likelihood, calibrate_dispersion_ritc.py), and until now it had not been scored by held-out density. This script does
so, on the same five folds by syndicate (oos_validation.fold_assignment at K = 5, the folds Table 4 uses), and scores
the three single-regime models of Table 4 on the same folds beside it, so every difference is paired observation by
observation.

For each fold the adopted model is refitted on the training syndicates with the headline's sampler, seed and settings,
and each held-out syndicate-year's log predictive density is averaged over the fold fit's posterior draws (800 draws
evenly spaced through the 6,000, as the single-regime scores are):

    p(S_i | fold fit) = mean over draws j of StudentT(S_i; nu_ij, 0, sigma_ij),
    nu_ij    = nu_clean_j exp(-lambda_ritc_j 1[RITC_i]),
    sigma_ij = exp(s_{t(i), j} + beta_ritc_j 1[RITC_i]) sqrt(sd_undiv_j^2 + sd_div_j^2 (R_i / 500)^{2(k_j - 1)}).

Two things the single-regime models do not need, stated:

  * the regime of a held-out record. The two-regime density needs the held-out record's assumed-business flag (RITC
    or a confirmed inward transfer). Each held-out record's RECORDED flag is used (assumed_business.keys(), the flag
    the headline fit reads), as a practitioner would know a target's own RITC history.
  * the reporting-year shock s_t. The held-out syndicates are new; their reporting years are not, and every year of
    the sample is in every fold's training data. The headline score ("year_shock_conditional") reads the fold fit's
    posterior draw of the shock for the held-out record's year: the posterior predictive for a new syndicate in an
    observed year. Beside it ("year_shock_marginal"), the shock is integrated out over a new year's N(0, tau_s) by
    Gauss-Hermite quadrature at each draw, which uses nothing from the held-out year's other syndicates. A held-out
    year absent from a fold's training data would be scored marginally under both; the record counts them (none
    expected).

The single-regime scores are oos_validation's and oos_size_only's own fits and densities (their functions, seed and
draws), and the script refuses to write unless their fold totals reproduce results/oos_validation_results.json and
results/oos_size_only_results.json, which run earlier in the manifest on the same sample.

Each difference is summarised as Table 4's are (check_cv_clustered_se.contrast): the paired held-out ELPD difference,
and a Bayesian bootstrap over syndicates (Dirichlet(1, ..., 1) weights on the syndicate totals of the pointwise
differences), which gives a posterior for the population difference, its 95% interval and P(first model predicts
better). The record keeps the plain and syndicate-clustered standard errors beside it, and no z-score.

Writes check_full_model_cv_results.json.
Usage:  python src/check_full_model_cv.py [workers]
"""
import io
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import stats
from scipy.special import logsumexp
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from adopted_model import SD, load_sample, scale_block, SAMPLE_CORES, REFERENCE_SIZE, HHI_FLOOR, HHI_CEIL
import check_cv_clustered_se as CV
import oos_size_only as OSO
import oos_validation as OV

OUT = SD / "results" / "check_full_model_cv_results.json"
OOS = SD / "results" / "oos_validation_results.json"
OOS_SIZE = SD / "results" / "oos_size_only_results.json"
K = OV.K
DEFAULT_WORKERS = 3
#: calibrate_dispersion_ritc.py's sampler, seed and settings (the headline)
DRAWS, TUNE, CHAINS, TARGET_ACCEPT, FIT_SEED = 1500, 1500, 4, 0.98, 42
#: the posterior draws each held-out density averages over, evenly spaced (the single-regime scores' 800)
THIN = 800
#: Gauss-Hermite nodes for the marginal year shock
GH_NODES = 32
#: the parameters each fold fit's convergence is read on: every scale and tail parameter the headline reports
DIAG = ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s")
MODELS = ("adopted_two_regime", "adopted_two_regime_year_shock_marginal", "composition", "size_only", "naive")
#: the contrasts the record reports, first model minus second
PAIRS = (("adopted_two_regime", "naive"), ("adopted_two_regime", "size_only"),
         ("adopted_two_regime", "composition"),
         ("adopted_two_regime_year_shock_marginal", "naive"),
         ("adopted_two_regime_year_shock_marginal", "size_only"),
         ("adopted_two_regime_year_shock_marginal", "composition"),
         ("adopted_two_regime", "adopted_two_regime_year_shock_marginal"),
         ("size_only", "naive"), ("composition", "naive"), ("composition", "size_only"))
#: keys of check_cv_clustered_se.contrast the record keeps: a z-score is not a summary this paper reports
CONTRAST_KEYS = ("delta_ELPD", "SE_plain", "SE_clustered", "bb_mean", "bb_sd", "bb_2.5", "bb_97.5",
                 "P_first_better", "n_clusters", "pct_obs_first_better", "pct_syndicates_first_better")
#: how far a single-regime fold total may lie from the recorded one: the fits are seeded, so this is rounding only
REPRODUCE_TOL = 1e-6


def thin_index(n, thin=THIN):
    return np.linspace(0, n - 1, min(thin, n)).astype(int)


def two_regime_lppd(S, R, ritc, yidx, post, marginal=False, nodes=GH_NODES):
    """Per-observation held-out log predictive density under the two-regime model, averaged over the draws in `post`
    ({name: draws}, with `s_y` as a draws x years array). `yidx` is each observation's index into the fold's years, or
    -1 for a year the fold's fit has not seen, which is then scored with the shock integrated out. With `marginal`,
    every observation is scored that way: the shock s ~ N(0, tau_s) integrated by Gauss-Hermite quadrature."""
    S, R, ritc = np.asarray(S, float), np.asarray(R, float), np.asarray(ritc, float)
    k, su, sd = post["k"][None, :], post["sd_undiv"][None, :], post["sd_div"][None, :]
    nu = post["nu_clean"][None, :] * np.exp(-post["lambda_ritc"][None, :] * ritc[:, None])
    base = np.exp(post["beta_ritc"][None, :] * ritc[:, None]) * np.sqrt(
        su ** 2 + sd ** 2 * (R[:, None] / REFERENCE_SIZE) ** (2.0 * (k - 1.0)))
    yidx = np.asarray(yidx)
    seen = (yidx >= 0) & (not marginal)
    out = np.empty(len(S))
    if np.any(seen):
        shock = post["s_y"][:, yidx[seen]].T                                 # (n_seen, draws)
        lp = stats.t.logpdf(S[seen, None], df=nu[seen], scale=base[seen] * np.exp(shock))
        out[seen] = logsumexp(lp, axis=1) - np.log(lp.shape[1])
    rest = ~seen
    if np.any(rest):
        x, w = np.polynomial.hermite.hermgauss(nodes)                        # integral of exp(-x^2) f(x)
        s = np.sqrt(2.0) * post["tau_s"][None, :, None] * x[None, None, :]   # s = sqrt(2) tau x ~ N(0, tau^2)
        lp = stats.t.logpdf(S[rest, None, None], df=nu[rest][:, :, None],
                            scale=base[rest][:, :, None] * np.exp(s))
        lw = np.log(w / np.sqrt(np.pi))[None, None, :]
        per_draw = logsumexp(lp + lw, axis=2)                                # (n_rest, draws)
        out[rest] = logsumexp(per_draw, axis=1) - np.log(per_draw.shape[1])
    return out


def fit_two_regime(S, R, H, yr, ritc):
    """The adopted model on one fold's training rows: the headline's block, sampler, seed and settings. Returns the
    thinned draws (with the year shocks s_y = tau_s z_s by the fold's years), the fold's years and diagnostics."""
    years = np.sort(np.unique(yr))
    with pm.Model():
        b = scale_block(R, H, yr, ritc)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=SAMPLE_CORES, target_accept=TARGET_ACCEPT,
                          random_seed=FIT_SEED, progressbar=False)
    p = idata.posterior
    n = p["k"].values.size
    idx = thin_index(n)
    post = {v: p[v].values.reshape(n)[idx] for v in ("k", "sd_undiv", "sd_div", "nu_clean", "lambda_ritc",
                                                     "beta_ritc", "tau_s")}
    z = p["z_s"].values.reshape(n, len(years))[idx]
    post["s_y"] = post["tau_s"][:, None] * z
    s = az.summary(idata, var_names=list(DIAG), round_to="none")
    diag = {"divergences": int(idata.sample_stats["diverging"].sum()), "max_rhat": float(s["r_hat"].max()),
            "min_ess_bulk": float(s["ess_bulk"].min()), "min_ess_tail": float(s["ess_tail"].min())}
    means = {v: float(p[v].values.mean()) for v in DIAG}
    return post, years, diag, means


def fold_scores(fold, k=K):
    """Every model's held-out log predictive density on one fold's held-out rows. A top-level function with only
    picklable arguments, so a pool of worker processes can run it."""
    t0 = time.time()
    S, R, H, yr, syn, ritc = load_sample()
    te = OV.fold_assignment(syn, k) == fold
    tr = ~te
    post, years, diag, means = fit_two_regime(S[tr], R[tr], H[tr], yr[tr], ritc[tr])
    pos = {y: i for i, y in enumerate(years.tolist())}
    yidx = np.array([pos.get(y, -1) for y in yr[te].tolist()])
    out = {"fold": int(fold), "test_index": np.flatnonzero(te).tolist(),
           "n_train": int(tr.sum()), "n_held_out": int(te.sum()),
           "n_held_out_syndicates": int(len(set(syn[te].tolist()))),
           "n_held_out_ritc": int(ritc[te].sum()),
           "n_held_out_in_unseen_year": int((yidx < 0).sum()),
           "adopted_fit": {"diagnostics": diag, "posterior_means": means}}
    lp = {"adopted_two_regime": two_regime_lppd(S[te], R[te], ritc[te], yidx, post),
          "adopted_two_regime_year_shock_marginal": two_regime_lppd(S[te], R[te], ritc[te], yidx, post,
                                                                    marginal=True)}
    divs = {}
    dm = OV.fit(S[tr], R[tr], H[tr], "model")
    dn = OV.fit(S[tr], R[tr], H[tr], "naive")
    ds = OSO.fit(S[tr], R[tr])
    lp["composition"] = OV.held_out_lppd(S[te], R[te], H[te], dm, "model")
    lp["naive"] = OV.held_out_lppd(S[te], R[te], H[te], dn, "naive")
    lp["size_only"] = OSO.lppd(S[te], R[te], ds)
    divs = {"composition": dm["_divergences"], "naive": dn["_divergences"], "size_only": ds["_divergences"]}
    out["lppd"] = {m: v.tolist() for m, v in lp.items()}
    out["single_regime_divergences"] = divs
    out["seconds"] = time.time() - t0
    return out


def run_folds(workers, k=K):
    if workers <= 1:
        return [fold_scores(f, k) for f in range(k)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fold_scores, range(k)))


def assemble(n, folds):
    """{model: per-observation held-out lppd} over the whole sample, from the fold results, every row scored once."""
    e = {m: np.full(n, np.nan) for m in MODELS}
    seen = np.zeros(n, int)
    for f in folds:
        idx = np.asarray(f["test_index"], int)
        seen[idx] += 1
        for m in MODELS:
            e[m][idx] = np.asarray(f["lppd"][m], float)
    if not np.all(seen == 1):
        raise SystemExit("the folds do not score every observation exactly once")
    for m in MODELS:
        if not np.all(np.isfinite(e[m])):
            raise SystemExit("%s has a non-finite held-out density" % m)
    return e


def check_reproduces(totals, n, oos, oos_size, tol=REPRODUCE_TOL):
    """The single-regime totals must be Table 4's: results/oos_validation_results.json and oos_size_only_results.json,
    on the same sample, folds and seed. Returns the comparison, or exits."""
    for key, val in (("n", n), ("folds", K), ("seed", OV.SEED)):
        if oos.get(key) != val:
            raise SystemExit("oos_validation_results.json has %s=%r; this run has %r" % (key, oos.get(key), val))
    want = {"composition": float(oos["held_out_ELPD_model"]), "naive": float(oos["held_out_ELPD_naive"]),
            "size_only": float(oos_size["held_out_ELPD"])}
    gaps = {m: totals[m] - w for m, w in want.items()}
    if any(abs(g) > tol for g in gaps.values()):
        raise SystemExit("the single-regime fold totals do not reproduce Table 4's records (computed - recorded): %s"
                         % gaps)
    return {"recorded": want, "computed_minus_recorded": gaps, "tolerance": tol,
            "sources": ["results/oos_validation_results.json", "results/oos_size_only_results.json"]}


def summarise(d, syn):
    rec = CV.contrast(d, syn)
    return {k: rec[k] for k in CONTRAST_KEYS}


def compute(workers=DEFAULT_WORKERS, folds=None):
    t0 = time.time()
    S, R, H, yr, syn, ritc = load_sample()
    S2, R2, H2, syn2 = OV.load()
    if not (np.array_equal(S, S2) and np.array_equal(R, R2) and np.array_equal(H, H2)
            and np.array_equal(syn, syn2)):
        raise SystemExit("adopted_model.load_sample and oos_validation.load disagree on the sample")
    t_fit = time.time()
    fr = folds if folds is not None else run_folds(workers)
    fit_wall = time.time() - t_fit
    e = assemble(len(S), fr)
    totals = {m: float(e[m].sum()) for m in MODELS}
    with io.open(OOS, encoding="utf-8") as _fh:
        oos = json.load(_fh)
    with io.open(OOS_SIZE, encoding="utf-8") as _fh:
        oos_size = json.load(_fh)
    reproduced = check_reproduces(totals, len(S), oos, oos_size)
    contrasts = {"%s__minus__%s" % (a, b): summarise(e[a] - e[b], syn) for a, b in PAIRS}
    fits = [{"fold": f["fold"], "n_train": f["n_train"], "n_held_out": f["n_held_out"],
             "n_held_out_syndicates": f["n_held_out_syndicates"], "n_held_out_ritc": f["n_held_out_ritc"],
             "n_held_out_in_unseen_year": f["n_held_out_in_unseen_year"], **f["adopted_fit"],
             "single_regime_divergences": f["single_regime_divergences"]} for f in sorted(fr, key=lambda x: x["fold"])]
    return {
        "question": ("does the adopted two-regime model (the headline likelihood, gamma fixed at 0) predict held-out "
                     "syndicates better than the naive market pool and the single-regime size-only model, on the "
                     "folds Table 4 uses?"),
        "n": int(len(S)), "n_syndicates": int(len(set(syn.tolist()))), "n_ritc": int(ritc.sum()),
        "folds": K, "fold_rule": "oos_validation.fold_assignment at K = 5 (the folds of Table 4)",
        "criterion": "held-out ELPD: the sum over held-out syndicate-years of the log of the posterior-mean density",
        "models": {
            "adopted_two_regime": ("the headline: adopted_model.scale_block with gamma = 0, refitted on each fold's "
                                   "training syndicates with the headline's sampler, seed and settings; the held-out "
                                   "record's reporting-year shock is the fold fit's posterior draw for that year"),
            "adopted_two_regime_year_shock_marginal": ("the same fits, with each held-out record's year shock "
                                                       "integrated out over a new year's N(0, tau_s) (Gauss-Hermite, "
                                                       "%d nodes)" % GH_NODES),
            "composition": "oos_validation.fit 'model': single-regime, size + concentration + floor, no year shock",
            "size_only": "oos_size_only.fit: single-regime, size + floor, no year shock",
            "naive": "oos_validation.fit 'naive': one market-wide Student-t scale"},
        "ritc_flag_of_held_out_records": ("the two-regime density reads the held-out record's assumed-business flag "
                                          "(its tail index and RITC scale term): each held-out record's recorded flag "
                                          "is used, assumed_business.keys(), the flag the headline fit reads"),
        "draws_per_density": THIN,
        "sampler": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS, "target_accept": TARGET_ACCEPT, "seed": FIT_SEED},
        "held_out_ELPD": totals,
        "held_out_ELPD_per_observation": {m: totals[m] / len(S) for m in MODELS},
        "contrasts": contrasts,
        "contrast_method": ("check_cv_clustered_se.contrast, Table 4's: the paired difference of pointwise held-out "
                            "log densities summed; bb_* is a Bayesian bootstrap over syndicates (Dirichlet(1, ..., 1) "
                            "weights on the %d syndicate totals, %d draws, seed %d): a posterior for the population "
                            "difference, its mean, SD, 95%% interval (bb_2.5, bb_97.5) and P_first_better; SE_plain "
                            "and SE_clustered are kept for comparison" % (len(set(syn.tolist())), CV.BB, CV.SEED)),
        "single_regime_reproduce_table_4": reproduced,
        "fold_fits": fits,
        "fold_fits_converged": bool(all(f["diagnostics"]["divergences"] == 0 and f["diagnostics"]["max_rhat"] <= 1.01
                                        for f in fits)),
        # the one key the verifier strips (reproduce.VOLATILE)
        "runtime_seconds": {"total": time.time() - t0, "fold_fits_wall": fit_wall, "workers": int(workers),
                            "folds_seconds": [f["seconds"] for f in sorted(fr, key=lambda x: x["fold"])],
                            "logical_processors": os.cpu_count()},
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    workers = int(argv[0]) if argv and argv[0].isdigit() else DEFAULT_WORKERS
    out = compute(workers)
    if not out["fold_fits_converged"]:
        raise SystemExit("a fold fit of the adopted model did not sample cleanly: %s"
                         % [f["diagnostics"] for f in out["fold_fits"]])
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print("Wrote %s" % OUT)
    print("  n=%d, %d syndicates, %d folds; held-out ELPD:" % (out["n"], out["n_syndicates"], out["folds"]))
    for m in MODELS:
        print("    %-40s %9.2f" % (m, out["held_out_ELPD"][m]))
    for key, c in out["contrasts"].items():
        print("  %-66s %+8.2f  BB 95%% [%+.2f, %+.2f]  P %.4f"
              % (key, c["delta_ELPD"], c["bb_2.5"], c["bb_97.5"], c["P_first_better"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
