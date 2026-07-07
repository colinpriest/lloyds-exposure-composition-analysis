"""Bayesian GPD return-level for the vignette VaR99.5 (spec: Bayesian alternative).

For each tail distribution (V1 adjusted, V2 new), fit a Bayesian generalised-Pareto (POT)
tail to the exceedances of the full-pool transferred-severity sample (evaluated at the
operator's posterior-mean parameters), with weakly-informative priors:

    xi ~ Normal(0, 0.5),   log sigma ~ Normal(log(mean exceedance), 1)

and report the posterior VaR99.5 return-level median and 95% credible interval. This captures
the GPD-parameter (tail-shape) uncertainty; it is the cheaper alternative to bootstrapping the
whole pipeline (that combined version is in gpd_var_uncertainty.py).

Return level:  VaR_0.995 = u + (sigma/xi)[((N/Nu)(1-0.995))^(-xi) - 1]  (xi->0 continuity limit).

Run: python bayesian_gpd.py [threshold_pctile]
"""
import json, sys
from pathlib import Path
import numpy as np
import pytensor; pytensor.config.mode = "NUMBA"
import pytensor.tensor as pt
import pymc as pm
import arviz as az

from vignette_uncertainty import load_pool, load_draws, load_targets, transfer, load_ritc

SCRIPT_DIR = Path(__file__).resolve().parent
U_Q = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
ALPHA = 0.995
SEED = 20240705
EMPIRICAL = {"V1_adjusted": 0.427, "V2_new": 0.407}    # de-RITC pool
FREQ_POINT = {"V1_adjusted": 0.483, "V2_new": 0.460}   # full-sample POT point (gpd_var_uncertainty.py, de-RITC)


def gpd_logp(value, xi, sigma):
    z = value / sigma
    safe = 1.0 + xi * z
    ll = pt.switch(pt.abs(xi) < 1e-6,
                   -pt.log(sigma) - z,
                   -pt.log(sigma) - (1.0 / xi + 1.0) * pt.log(pt.maximum(safe, 1e-12)))
    return pt.switch(safe > 0.0, ll, -np.inf)


def fit_one(name, exc, N, Nu, u):
    m = float(np.log(exc.mean()))
    with pm.Model():
        xi = pm.Normal("xi", 0.0, 0.5)
        log_sigma = pm.Normal("log_sigma", m, 1.0)
        sigma = pm.Deterministic("sigma", pm.math.exp(log_sigma))
        pm.CustomDist("y", xi, sigma, logp=gpd_logp, observed=exc)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.97,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    xis = p["xi"].values.ravel(); sigs = p["sigma"].values.ravel()
    a = (N / Nu) * (1.0 - ALPHA)
    vl = np.where(np.abs(xis) < 1e-6, u - sigs * np.log(a), u + (sigs / xis) * (a ** (-xis) - 1.0))
    emp = EMPIRICAL[name]
    summ = az.summary(idata, var_names=["xi", "sigma"])
    return {
        "threshold_u": float(u), "N": int(N), "Nu": int(Nu),
        "var995_median": float(np.median(vl)), "var995_2.5": float(np.percentile(vl, 2.5)),
        "var995_97.5": float(np.percentile(vl, 97.5)),
        "xi_median": float(np.median(xis)), "xi_2.5": float(np.percentile(xis, 2.5)), "xi_97.5": float(np.percentile(xis, 97.5)),
        "sigma_median": float(np.median(sigs)), "sigma_2.5": float(np.percentile(sigs, 2.5)), "sigma_97.5": float(np.percentile(sigs, 97.5)),
        "empirical": emp, "empirical_inside_ci": bool(np.percentile(vl, 2.5) <= emp <= np.percentile(vl, 97.5)),
        "freq_point": FREQ_POINT[name],
        "max_rhat": float(summ["r_hat"].max()), "divergences": int(idata.sample_stats["diverging"].sum()),
        "prior": "xi~N(0,0.5), log_sigma~N(log(mean exceedance),1)",
        "tail_shape": "heavy (xi>0, unbounded)" if np.median(xis) > 0 else "bounded (xi<0)",
    }


def main():
    S, R, H, synd, year = load_pool()
    draws, ref, hlo, hce = load_draws(); cfg = (ref, hlo, hce)
    ritc = load_ritc(synd, year)
    v1, v2_old, v2_new = load_targets()
    thbar = {p: float(draws[p].mean()) for p in draws}
    res = {}
    for name, tgt in [("V1_adjusted", v1), ("V2_new", v2_new)]:
        samp = transfer(S, R, H, tgt, thbar, cfg, ritc)
        u = float(np.percentile(samp, U_Q, method="linear"))
        exc = samp[samp > u] - u
        res[name] = fit_one(name, exc, len(samp), len(exc), u)

    out = {"meta": {"seed": SEED, "threshold_rule": f"{U_Q:.0f}th percentile of the signed transferred-severity sample",
                    "method": "Bayesian GPD (NUTS) on full-pool exceedances at operator posterior mean",
                    "return_level_formula": "u + (sigma/xi)[((N/Nu)(1-0.995))^(-xi) - 1]"},
           "distributions": res}
    (SCRIPT_DIR / "bayesian_gpd_results.json").write_text(json.dumps(out, indent=2))
    for name, r in res.items():
        print(f"=== {name} ===  (Rhat {r['max_rhat']:.2f}, div {r['divergences']})")
        print(f"  posterior VaR99.5: median {r['var995_median']:.3f}  95% CrI [{r['var995_2.5']:.3f}, {r['var995_97.5']:.3f}]")
        print(f"  threshold u={r['threshold_u']:.3f}  N={r['N']}  Nu={r['Nu']}")
        print(f"  xi:    {r['xi_median']:+.3f} [{r['xi_2.5']:+.3f}, {r['xi_97.5']:+.3f}]  -> {r['tail_shape']}")
        print(f"  sigma: {r['sigma_median']:.4f} [{r['sigma_2.5']:.4f}, {r['sigma_97.5']:.4f}]")
        print(f"  empirical {r['empirical']:.3f} inside 95% CrI? {'YES' if r['empirical_inside_ci'] else 'NO'}  "
              f"(freq POT point {r['freq_point']:.3f})\n")
    print("Wrote bayesian_gpd_results.json")


if __name__ == "__main__":
    main()
