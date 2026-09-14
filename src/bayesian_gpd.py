"""Bayesian GPD return-level for the vignette VaR99.5 (spec: Bayesian alternative).

For each tail distribution (V1 adjusted, V2 new), fit a Bayesian generalised-Pareto (POT)
tail to the exceedances of the full-pool transferred-severity sample (evaluated at the
operator's posterior-mean parameters), with weakly-informative priors:

    xi ~ Normal(0, 0.5),   log sigma ~ Normal(log(mean exceedance), 1)

and report the posterior VaR99.5 return-level median and 95% credible interval. This captures
the GPD-parameter (tail-shape) uncertainty; it is the cheaper alternative to bootstrapping the
whole pipeline (that combined version is in gpd_var_uncertainty.py).

The GPD's support requires 1 + xi*y/sigma > 0 for every exceedance y, i.e. xi > -sigma/max(y).
Sampled freely, xi met that edge as a hard wall inside the sampled space, and NUTS reported the
trajectories that hit it as divergent (18 in each fit at target_accept 0.97). So xi is sampled as
its bound plus a positive offset, xi = -sigma/max(y) + exp(eta), and the Normal(0, 0.5) density
on xi enters as a potential together with the log-Jacobian of that map, which is eta. On the
support the joint density over (log sigma, xi) is the one above, so the posterior is the same;
only the geometry the sampler sees has changed.

Return level:  VaR_0.995 = u + (sigma/xi)[((N/Nu)(1-0.995))^(-xi) - 1]  (xi->0 continuity limit).

Run: python src/bayesian_gpd.py [threshold_pctile]
"""
import io, json, sys
from pathlib import Path
import numpy as np
import pytensor; pytensor.config.mode = "NUMBA"
import pytensor.tensor as pt
import pymc as pm
from adopted_model import SAMPLE_CORES
import arviz as az

from vignette_uncertainty import load_pool, load_draws, load_targets, transfer, load_ritc

SCRIPT_DIR = Path(__file__).resolve().parent.parent
U_Q = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
ALPHA = 0.995
SEED = 20240705
# Both comparators are read from the current run rather than typed: the empirical
# VaR99.5 from the sample being fitted, and the frequentist POT point from
# gpd_var_uncertainty_results.json. They used to be four literals from an earlier
# fit (0.427/0.407 and 0.483/0.460), which then travelled into the committed JSON.
FREQ_RESULTS = SCRIPT_DIR / "results" / "gpd_var_uncertainty_results.json"
SHAPE_PARAMETERISATION = ("xi = -sigma/max(exceedance) + exp(eta); prior xi~N(0,0.5) on xi itself, "
                          "with the map's log-Jacobian eta")


def freq_point(name):
    """The frequentist POT point for this target, from its own results file."""
    try:
        d = json.load(io.open(FREQ_RESULTS, encoding="utf-8"))
        return float(d["distributions"][name]["point_var995"])
    except Exception:
        return None


def gpd_logp(value, xi, sigma):
    z = value / sigma
    safe = 1.0 + xi * z
    ll = pt.switch(pt.abs(xi) < 1e-6,
                   -pt.log(sigma) - z,
                   -pt.log(sigma) - (1.0 / xi + 1.0) * pt.log(pt.maximum(safe, 1e-12)))
    return pt.switch(safe > 0.0, ll, -np.inf)


def tail_shape(xis):
    """The shape's sign as its 95% interval resolves it. The label used to be read off the
    median alone, and so called the tail heavy while the interval spanned zero."""
    lo, hi = np.percentile(xis, [2.5, 97.5])
    if lo > 0:
        return "heavy (xi>0 across the 95% interval)"
    if hi < 0:
        return "bounded (xi<0 across the 95% interval)"
    return "not resolved (the 95% interval of xi spans zero)"


def fit_one(name, exc, N, Nu, u, emp):
    m = float(np.log(exc.mean()))
    ymax = float(exc.max())
    with pm.Model():
        log_sigma = pm.Normal("log_sigma", m, 1.0)
        sigma = pm.Deterministic("sigma", pm.math.exp(log_sigma))
        # xi above its support bound -sigma/max(y), on an unconstrained offset (module docstring);
        # the potential is the N(0, 0.5) prior on xi plus the log-Jacobian of xi = bound + exp(eta)
        eta = pm.Flat("xi_offset_log")
        xi = pm.Deterministic("xi", -sigma / ymax + pm.math.exp(eta))
        pm.Potential("xi_prior", pm.logp(pm.Normal.dist(0.0, 0.5), xi) + eta)
        pm.CustomDist("y", xi, sigma, logp=gpd_logp, observed=exc)
        idata = pm.sample(1500, tune=1500, chains=4, cores=SAMPLE_CORES, target_accept=0.97,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    xis = p["xi"].values.ravel(); sigs = p["sigma"].values.ravel()
    a = (N / Nu) * (1.0 - ALPHA)
    vl = np.where(np.abs(xis) < 1e-6, u - sigs * np.log(a), u + (sigs / xis) * (a ** (-xis) - 1.0))
    summ = az.summary(idata, var_names=["xi", "sigma"])
    return {
        "threshold_u": float(u), "N": int(N), "Nu": int(Nu),
        "var995_median": float(np.median(vl)), "var995_2.5": float(np.percentile(vl, 2.5)),
        "var995_97.5": float(np.percentile(vl, 97.5)),
        "xi_median": float(np.median(xis)), "xi_2.5": float(np.percentile(xis, 2.5)), "xi_97.5": float(np.percentile(xis, 97.5)),
        "sigma_median": float(np.median(sigs)), "sigma_2.5": float(np.percentile(sigs, 2.5)), "sigma_97.5": float(np.percentile(sigs, 97.5)),
        "empirical": emp, "empirical_inside_ci": bool(np.percentile(vl, 2.5) <= emp <= np.percentile(vl, 97.5)),
        "freq_point": freq_point(name),
        "max_rhat": float(summ["r_hat"].max()), "divergences": int(idata.sample_stats["diverging"].sum()),
        "prior": "xi~N(0,0.5), log_sigma~N(log(mean exceedance),1)",
        "tail_shape": tail_shape(xis),
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
        # the empirical comparator comes from the sample being fitted, not a
        # literal carried over from an earlier fit
        emp = float(np.percentile(samp, 100.0 * ALPHA, method="linear"))
        res[name] = fit_one(name, exc, len(samp), len(exc), u, emp)

    out = {"meta": {"seed": SEED, "threshold_rule": f"{U_Q:.0f}th percentile of the signed transferred-severity sample",
                    "method": "Bayesian GPD (NUTS) on full-pool exceedances at operator posterior mean",
                    "shape_parameterisation": SHAPE_PARAMETERISATION,
                    "return_level_formula": "u + (sigma/xi)[((N/Nu)(1-0.995))^(-xi) - 1]"},
           "distributions": res}
    (SCRIPT_DIR / "results" / "bayesian_gpd_results.json").write_text(json.dumps(out, indent=2))
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
