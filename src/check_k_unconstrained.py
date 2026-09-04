"""Referee check: is P(k>0.5) / P(k<1) an empirical finding or an artefact of the prior support?

The adopted model parameterises the pooling exponent as k = 1/2 + 1/2*logistic(theta),
which CONFINES k to (0.5, 1) before any data are seen.  Under that parameterisation
P(k>0.5)=1 and P(k<1)=1 are consequences of the transform, not findings.

This refits the SAME two-regime headline model (year shock + RITC tail regime + floor,
mu=0) with k given UNCONSTRAINED real-line support under three priors, so the two
posterior probabilities become genuine empirical statements:

  C0  k = 0.5 + 0.5*logistic(theta), theta ~ N(0,1.5)   (adopted; reference only)
  U1  k ~ Normal(0.5, 0.5)    centred ON the independence benchmark  -> prior P(k>0.5)=0.500
  U2  k ~ Normal(0.75, 0.5)   centred mid-interval                   -> prior P(k>0.5)=0.691
  U3  k ~ Uniform(-0.5, 2.0)  flat over a wide range                 -> prior P(k>0.5)=0.600

U1 is the primary specification: its prior is centred exactly on the null the referee
says is unadjudicated, so any posterior mass shift away from 0.5 is carried by the data.

Reports, for each: posterior mean/sd/HDI for k, the prior and posterior P(k>0.5) and
P(k<1), the prior->posterior probability shift, and gamma / floor / nu / tau for
comparability with Table 1.

Writes check_k_unconstrained_results.json.
Usage:  python src/check_k_unconstrained.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
from adopted_model import scale_block
import arviz as az

SD = Path(__file__).resolve().parent.parent
RESULTS = SD / "model" / "exposure_results.json"
RITC = SD / "pdf_extraction" / "ritc_scan.json"
OUT = SD / "results" / "check_k_unconstrained_results.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42
DRAWS, TUNE, CHAINS = 1500, 1500, 4


def load_sample():
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    key = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    return S, R, H, yr, key


def ritc_flag(key):
    r = json.load(io.open(RITC, encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([k in occ for k in key])


def fit(S, R, H, yidx, n_y, ritc, kprior):
    """The adopted model (scale_block); the only departure is the support/prior
    of k, selected through the block's k_prior option."""
    logR = np.log(R / REF); logH = np.log(H)
    with pm.Model():
        b = scale_block(ritc=ritc, logR=logR, logH=logH, yidx=yidx, n_y=n_y,
                        k_prior="logistic" if kprior == "constrained" else kprior)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=1,
                          target_accept=0.98, random_seed=SEED, progressbar=False)
    return idata


def prior_probs(kprior):
    """Analytic prior P(k>0.5) and P(k<1) for each specification."""
    if kprior == "constrained":
        return {"P_k_gt_0.5": 1.0, "P_k_lt_1": 1.0}
    if kprior == "normal_0.5":
        return {"P_k_gt_0.5": float(1 - stats.norm.cdf(0.5, 0.5, 0.5)),
                "P_k_lt_1": float(stats.norm.cdf(1.0, 0.5, 0.5))}
    if kprior == "normal_0.75":
        return {"P_k_gt_0.5": float(1 - stats.norm.cdf(0.5, 0.75, 0.5)),
                "P_k_lt_1": float(stats.norm.cdf(1.0, 0.75, 0.5))}
    if kprior == "uniform":
        lo, hi = -0.5, 2.0
        return {"P_k_gt_0.5": float((hi - 0.5) / (hi - lo)),
                "P_k_lt_1": float((1.0 - lo) / (hi - lo))}
    raise ValueError(kprior)


def main():
    S, R, H, yr, key = load_sample()
    ritc = ritc_flag(key).astype(float)
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    n_y = len(years)
    print(f"n={len(S)}  RITC={int(ritc.sum())}  years={n_y}")

    specs = [("constrained", "k = 1/2 + 1/2 logistic(theta), theta~N(0,1.5)  [adopted]"),
             ("normal_0.5", "k ~ Normal(0.5, 0.5)   [primary unconstrained: prior centred on k=1/2]"),
             ("normal_0.75", "k ~ Normal(0.75, 0.5)  [unconstrained, centred mid-interval]"),
             ("uniform", "k ~ Uniform(-0.5, 2.0) [flat over a wide range]")]

    out = {"n": int(len(S)), "n_ritc": int(ritc.sum()), "n_years": int(n_y), "seed": SEED,
           "draws": DRAWS, "tune": TUNE, "chains": CHAINS,
           "question": ("Are P(k>0.5) and P(k<1) empirical findings, or artefacts of the "
                        "logistic transform that confines k to (0.5,1) a priori?"),
           "models": {}}

    for kprior, desc in specs:
        print(f"\n--- {kprior}: {desc}")
        idata = fit(S, R, H, yidx, n_y, ritc, kprior)
        vn = ["k", "gamma", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc",
              "tau_s", "sd_undiv", "sd_div"]
        summ = az.summary(idata, var_names=vn, hdi_prob=0.95)
        p = idata.posterior
        kf = p["k"].values.ravel()
        pri = prior_probs(kprior)
        post = {"P_k_gt_0.5": float((kf > 0.5).mean()), "P_k_lt_1": float((kf < 1.0).mean())}
        rec = {
            "spec": desc,
            "k": {"mean": float(kf.mean()), "sd": float(kf.std()),
                  "hdi_2.5": float(summ.loc["k", "hdi_2.5%"]),
                  "hdi_97.5": float(summ.loc["k", "hdi_97.5%"])},
            "prior_prob": pri, "posterior_prob": post,
            "prob_shift": {q: post[q] - pri[q] for q in post},
            "other": {v: {"mean": float(summ.loc[v, "mean"]),
                          "hdi_2.5": float(summ.loc[v, "hdi_2.5%"]),
                          "hdi_97.5": float(summ.loc[v, "hdi_97.5%"])}
                      for v in vn if v != "k"},
            "diagnostics": {"max_rhat": float(summ["r_hat"].max()),
                            "min_ess_bulk": float(summ["ess_bulk"].min()),
                            "divergences": int(idata.sample_stats["diverging"].sum())},
        }
        out["models"][kprior] = rec
        print(f"    k = {rec['k']['mean']:.3f} [{rec['k']['hdi_2.5']:.3f}, {rec['k']['hdi_97.5']:.3f}]")
        print(f"    P(k>0.5): prior {pri['P_k_gt_0.5']:.3f} -> posterior {post['P_k_gt_0.5']:.3f}")
        print(f"    P(k<1)  : prior {pri['P_k_lt_1']:.3f} -> posterior {post['P_k_lt_1']:.3f}")
        print(f"    divergences={rec['diagnostics']['divergences']}  "
              f"max_rhat={rec['diagnostics']['max_rhat']:.3f}")

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
