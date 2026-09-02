"""The large-book size-dispersion slope, estimated Bayesianly.

check_large_book_slope.py answered this with a Theil-Sen point estimate and a
frequentist syndicate-cluster bootstrap, alongside Spearman rank tests. In a Bayesian
paper the slope should come from a posterior, so this refits it directly:

    log|S_it| = a + b * log R_it + alpha_i + eps_it,
    alpha_i ~ Normal(0, tau_alpha^2),      eps_it ~ StudentT(nu, 0, sigma)

restricted to R above a threshold. Because S is a scale family, b estimates
d log sigma / d log R, the same quantity the two candidate scale laws disagree about:

    no-floor law   b = k - 1 = -0.342, constant at every size
    floor law      b -> 0 as R grows, because the floor comes to dominate

The Student-t likelihood absorbs the heavy lower tail of log|S| that made an OLS
slope unstable, and the syndicate intercept stops a syndicate with many years from
dominating. We report the posterior for b with a credible interval, and the posterior
probabilities that bear on the question: P(b < 0), P(b < -0.342) and
P(b > -0.171), the last being "the decline is at most half the floorless rate".

Writes check_large_book_slope_bayes_results.json.
Usage:  python src/check_large_book_slope_bayes.py
"""
import io, json
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from oos_validation import load, REF, HLO, HCE, SEED

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_large_book_slope_bayes_results.json"
CV = SD / "results" / "check_pooling_cv_extended_results.json"
ZERO = 1e-6
THRESHOLDS = [("above_500m", 500.0), ("above_1bn", 1000.0), ("above_2bn", 2000.0)]


def fit_slope(logR, logA, sidx, n_s):
    with pm.Model():
        a = pm.Normal("a", 0.0, 5.0)
        b = pm.Normal("b", 0.0, 1.0)
        tau_a = pm.HalfNormal("tau_alpha", 1.0)
        z_a = pm.Normal("z_alpha", 0.0, 1.0, shape=n_s)
        sigma = pm.HalfNormal("sigma", 2.0)
        nu = pm.Gamma("nu", 2.0, 0.1)
        mu = a + b * logR + (tau_a * z_a)[sidx]
        pm.StudentT("y", nu=nu, mu=mu, sigma=sigma, observed=logA)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    return idata


def main():
    S, R, H, syn = load()
    cv = json.load(io.open(CV, encoding="utf-8"))["full_sample_params"]
    k_nf = cv["M7_free_k_nofloor"]["k"][0]
    b_nofloor = k_nf - 1.0
    print(f"no-floor law implies a constant local slope of {b_nofloor:+.3f}")

    res = {"seed": SEED,
           "model": ("log|S| = a + b logR + alpha_i + StudentT error; "
                     "alpha_i ~ N(0, tau_alpha^2)"),
           "b_implied_by_nofloor_law": b_nofloor,
           "thresholds": {}}

    for name, T in THRESHOLDS:
        m = (R >= T) & (np.abs(S) > ZERO)
        lr, la, sy = np.log(R[m]), np.log(np.abs(S[m])), syn[m]
        ids = np.sort(np.unique(sy)); sidx = np.searchsorted(ids, sy)
        print(f"\n{name}: n={m.sum()} obs, {len(ids)} syndicates")
        idata = fit_slope(lr, la, sidx, len(ids))
        b = idata.posterior["b"].values.ravel()
        s = az.summary(idata, var_names=["b", "tau_alpha", "sigma", "nu"], hdi_prob=0.95)
        rec = {"threshold_m": T, "n": int(m.sum()), "n_syndicates": int(len(ids)),
               "b_mean": float(b.mean()),
               "b_hdi_2.5": float(s.loc["b", "hdi_2.5%"]),
               "b_hdi_97.5": float(s.loc["b", "hdi_97.5%"]),
               "P_b_lt_0": float((b < 0).mean()),
               "P_b_lt_nofloor": float((b < b_nofloor).mean()),
               "P_b_gt_half_nofloor": float((b > b_nofloor / 2).mean()),
               "tau_alpha_mean": float(s.loc["tau_alpha", "mean"]),
               "nu_mean": float(s.loc["nu", "mean"]),
               "max_rhat": float(s["r_hat"].max()),
               "divergences": int(idata.sample_stats["diverging"].sum())}
        res["thresholds"][name] = rec
        print(f"   b = {rec['b_mean']:+.3f}  95% HDI "
              f"[{rec['b_hdi_2.5']:+.3f}, {rec['b_hdi_97.5']:+.3f}]")
        print(f"   P(b<0) = {rec['P_b_lt_0']:.3f}   "
              f"P(b < {b_nofloor:+.2f}) = {rec['P_b_lt_nofloor']:.3f}   "
              f"P(b > half that rate) = {rec['P_b_gt_half_nofloor']:.3f}")
        print(f"   tau_alpha={rec['tau_alpha_mean']:.3f} nu={rec['nu_mean']:.2f} "
              f"div={rec['divergences']} rhat={rec['max_rhat']:.3f}")

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
