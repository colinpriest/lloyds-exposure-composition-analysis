"""The long-tail share of business, scored the way the manuscript's other model comparisons are.

compose_robust.py fits the share on a single-regime base and compares models by
observation-level PSIS-LOO, which is optimistic when a syndicate contributes several years.
This script asks the two questions that decide whether the transfer operator should carry
the share:

  1. Does it predict unseen syndicates better? Five-fold cross-validation BY SYNDICATE on
     oos_validation.py's folds: check_cv_clustered_se.py's composition model (free k on its
     bracket, floor, concentration, no year shock) against the same model with
     beta_LT * LT added to the log-scale (beta_LT ~ Normal(0, 1)). The paired difference is
     summarised by check_cv_clustered_se.contrast, the Bayesian bootstrap over syndicate
     totals. Each fold's slope and each fit's divergent transitions are recorded.
  2. Does the slope hold in the adopted likelihood? The adopted two-regime model
     (adopted_model.scale_block) with the same term through its extra_log_scale option, its
     parameters set beside the published fit's.

It also records the working sample's long-tail share distribution and how many records have
their largest premium weight in each of compose_robust.py's dominant-class groups.

LT is the summed premium weight of Casualty, Professional Lines, Reinsurance-Casualty and
Motor (compose_robust.LONG_TAIL_IDX).

Writes check_long_tail_share_results.json.
Usage:  python src/check_long_tail_share.py
"""
import io
import json

import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from adopted_model import (SD, RESULTS, load_sample, scale_block, check_against_headline, headline,
                           SAMPLE_CORES)
from oos_validation import load as load_cv, SEED, K
import check_cv_clustered_se as cse
from compose_robust import LONG_TAIL_IDX, DOM_MAP

OUT = SD / "results" / "check_long_tail_share_results.json"
LONG_TAIL_LINES = ["Casualty", "Professional Lines", "Reinsurance-Casualty", "Motor"]
GROUPS = ["Aggregate", "Property", "Casualty", "Aviation", "Other"]
PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s")
DRAWS, TUNE, CHAINS, TARGET_ACCEPT = 1500, 1500, 4, 0.98


def hdi95(x):
    a = np.asarray(x, float).ravel()
    return [float(v) for v in az.hdi(a, hdi_prob=0.95)]


def shares():
    """LT and the dominant-class group for every working-sample record, in the loaders' order."""
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None]
    if not all(o.get("weights") for o in recs):
        raise SystemExit("a working-sample record has no premium weights: its long-tail share is undefined")
    W = np.array([o["weights"] for o in recs], float)
    lt = W[:, LONG_TAIL_IDX].sum(axis=1)
    dom = np.array([DOM_MAP.get(int(i), "Other") for i in W.argmax(axis=1)])
    S = np.array([o["s_raw_a"] for o in recs], float)
    return S, lt, dom


def cross_validate(S, R, H, syn, lt):
    uniq = np.array(sorted(set(syn)))
    fold_of = {s: i % K for i, s in enumerate(uniq)}
    fold = np.array([fold_of[s] for s in syn])
    cfg = cse.MODELS["composition"]
    e0 = np.full(len(S), np.nan)
    e1 = np.full(len(S), np.nan)
    per_fold = []
    for f in range(K):
        te = fold == f
        tr = ~te
        print("  fold %d: train %d / test %d" % (f, tr.sum(), te.sum()))
        d0 = cse.fit(S[tr], R[tr], H[tr], cfg)
        d1 = cse.fit(S[tr], R[tr], H[tr], cfg, extra=lt[tr])
        e0[te] = cse.lppd(S[te], R[te], H[te], d0)
        e1[te] = cse.lppd(S[te], R[te], H[te], d1, extra_t=lt[te])
        b = d1["beta_LT"]
        per_fold.append({"fold": f, "n_test": int(te.sum()), "n_test_syndicates": int(len(set(syn[te]))),
                         "delta_ELPD": float(np.nansum(e1[te] - e0[te])),
                         "beta_LT": {"mean": float(b.mean()), "hdi": hdi95(b), "P_gt_0": float((b > 0).mean())},
                         "divergences": {"composition": d0["_divergences"], "long_tail": d1["_divergences"]}})
    rec = cse.contrast(e1 - e0, syn)
    fits = [x for p in per_fold for x in p["divergences"].values()]
    return {"criterion": "5-fold by-syndicate held-out ELPD on oos_validation.py's folds; Bayesian bootstrap over "
                         "syndicate totals",
            "models": {"composition": "free k in [1/2, 1], floor, concentration, no year shock",
                       "long_tail": "the composition model with beta_LT * LT on the log-scale, beta_LT ~ Normal(0, 1)"},
            "held_out_ELPD": {"composition": float(np.nansum(e0)), "long_tail": float(np.nansum(e1))},
            "long_tail_minus_composition": rec,
            "per_fold": per_fold,
            "fold_fits": len(fits), "fold_fits_with_divergences": int(sum(1 for x in fits if x))}


def adopted_with_share(lt):
    S, R, H, yr, syn, ritc = load_sample()
    with pm.Model():
        beta_LT = pm.Normal("beta_LT", 0.0, 1.0)
        b = scale_block(R, H, yr, ritc, extra_log_scale=beta_LT * lt)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=SAMPLE_CORES,
                          target_accept=TARGET_ACCEPT, random_seed=SEED, progressbar=False)
    summ = az.summary(idata, var_names=list(PARAMS) + ["beta_LT"], hdi_prob=0.95)
    post = idata.posterior
    bl = post["beta_LT"].values.ravel()
    ok, rows = check_against_headline({p: post[p].values.ravel() for p in PARAMS})
    h = headline()
    params = {}
    for p in PARAMS:
        # from the draws at full precision, as check_against_headline takes them: az.summary rounds its means and
        # intervals, and a gap from rounded means need not be the guard's gap (the A+/L1 review, B-02 (ii))
        a = post[p].values.ravel()
        m = float(a.mean())
        lo, hi = hdi95(a)
        params[p] = {"mean": m, "hdi_2.5": lo, "hdi_97.5": hi,
                     "headline_mean": float(h[p]["mean"]),
                     "gap_in_headline_sd": abs(m - float(h[p]["mean"])) / float(h[p]["sd"])}
    return {"spec": ("adopted_model.scale_block(extra_log_scale=beta_LT * LT), beta_LT ~ Normal(0, 1); data, priors, "
                     "sampler and seed as the headline calibration"),
            "beta_LT": {"mean": float(bl.mean()), "hdi": hdi95(bl), "P_gt_0": float((bl > 0).mean()),
                        "multiplier_over_observed_range": float(np.exp(bl.mean() * (lt.max() - lt.min())))},
            "params": params, "within_headline_tolerance": bool(ok), "headline_rows": rows,
            "diagnostics": {"max_rhat": float(summ["r_hat"].max()), "min_ess_bulk": float(summ["ess_bulk"].min()),
                            "divergences": int(idata.sample_stats["diverging"].sum())}}


def main():
    S, R, H, syn = load_cv()
    S_a, R_a, H_a, yr, syn_a, ritc = load_sample()
    S_w, lt, dom = shares()
    same = (np.array_equal(S, S_a) and np.array_equal(S, S_w) and np.array_equal(R, R_a)
            and np.array_equal(H, H_a) and np.array_equal(syn.astype(str), syn_a.astype(str)))
    if not same:
        raise SystemExit("the loaders do not select the same records in the same order")
    print("n=%d syndicates=%d folds=%d" % (len(S), len(set(syn)), K))

    counts = {g: int((dom == g).sum()) for g in GROUPS}
    res = {"n": int(len(S)), "n_syndicates": int(len(set(syn))), "folds": K, "seed": SEED,
           "bootstrap_draws": cse.BB, "long_tail_lines": LONG_TAIL_LINES,
           "share": {"median": float(np.median(lt)), "mean": float(lt.mean()),
                     "p90": float(np.percentile(lt, 90)), "min": float(lt.min()), "max": float(lt.max()),
                     "n_zero": int((lt == 0).sum())},
           "dominant_class": {"groups": GROUPS, "counts": counts,
                              "most_common": max(GROUPS, key=lambda g: counts[g]),
                              "majority": bool(max(counts.values()) > len(S) / 2)}}
    res["by_syndicate"] = cross_validate(S, R, H, syn, lt)
    print("fitting the adopted model with the share ...")
    res["adopted_model"] = adopted_with_share(lt)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")

    r = res["by_syndicate"]["long_tail_minus_composition"]
    a = res["adopted_model"]
    print("Wrote %s" % OUT)
    print("  by syndicate: dELPD (share - composition) %+.2f, 95%% [%+.2f, %+.2f], P(share better) %.3f"
          % (r["delta_ELPD"], r["bb_2.5"], r["bb_97.5"], r["P_first_better"]))
    print("  adopted model: beta_LT %+.3f [%+.3f, %+.3f], P>0 %.4f; divergences %d, max R-hat %.3f"
          % (a["beta_LT"]["mean"], a["beta_LT"]["hdi"][0], a["beta_LT"]["hdi"][1], a["beta_LT"]["P_gt_0"],
             a["diagnostics"]["divergences"], a["diagnostics"]["max_rhat"]))
    print("  largest premium weight: %s" % counts)


if __name__ == "__main__":
    main()
