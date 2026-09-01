"""Calibrate the robust Bayesian pooling dispersion model and persist parameters.

Fits the final specification (see scaling_analysis_writeup.md):

    S_it ~ Student-t(nu, 0, sigma_it)
    log sigma_it = b0 + (k-1) * log( R_it * (1/H_it)^gamma ) + s_t
    s_t ~ Normal(0, tau_s)                      # reporting-year shared shock

with mu = 0 fixed, k in [0.5, 1] (pooling exponent), gamma >= 0 (concentration via
effective line count n_eff = 1/H), no scale floor, heavy-tailed (Student-t) errors.

Writes dispersion_calibration.json consumed by run_analysis.py.  Run this whenever the
underlying data change; the main pipeline only *loads* the result (keeps runs fast and
deterministic, and avoids a hard PyMC dependency in the analysis pipeline).

Usage:  python calibrate_dispersion.py
"""
import json, sys
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

SCRIPT_DIR = Path(__file__).resolve().parent.parent
RESULTS = SCRIPT_DIR / "model" / "exposure_results.json"
OUT = SCRIPT_DIR / "model" / "dispersion_calibration.json"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0
SEED = 42


def load_sample():
    """Full sample: all reporting years, valid severity/reserves/HHI, single-line retained."""
    d = json.load(open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    HHI = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    return S, R, HHI, yr


def main():
    S, R, HHI, yr = load_sample()
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    n_y, n = len(years), len(S)
    logR = np.log(R / REFERENCE_SIZE)
    logH = np.log(HHI)   # 1/H form: log R_eff = log(R/ref) - gamma*log H  (0 at H=1)

    with pm.Model():
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))     # [0.5, 1]
        gamma = pm.HalfNormal("gamma", 1.0)
        # Variance = undiversifiable floor + diversifiable power term.  The undiversifiable
        # VARIANCE SHARE at the reference (R=500m, H=1) has a uniform prior (no mass piled
        # at zero), so the data — not the prior — decide the floor.
        log_tot = pm.Normal("log_tot", np.log(0.05), 1.0)   # total SD at reference
        tot_sd = pm.math.exp(log_tot)
        f = pm.Beta("f", 1.0, 1.0)                           # undiversifiable variance share
        sd_undiv = pm.Deterministic("sd_undiv", tot_sd * pm.math.sqrt(f))
        sd_div = pm.Deterministic("sd_div", tot_sd * pm.math.sqrt(1.0 - f))
        tau_s = pm.HalfNormal("tau_s", 0.5)
        z_s = pm.Normal("z_s", 0.0, 1.0, shape=n_y)
        s_y = tau_s * z_s
        # effective-size power term relative to reference: [ (R/500)*(1/H)^gamma ]^{2(k-1)}
        log_reff = logR - gamma * logH
        var = sd_undiv ** 2 + sd_div ** 2 * pm.math.exp(2.0 * (k - 1.0) * log_reff)
        sigma = pm.math.exp(s_y[yidx]) * pm.math.sqrt(var)
        nu = pm.Gamma("nu", 2.0, 0.1)
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)

    summ = az.summary(idata, var_names=["k", "gamma", "nu", "tau_s", "sd_undiv", "sd_div", "f"], hdi_prob=0.95)
    def row(p):
        r = summ.loc[p]
        return {"mean": float(r["mean"]), "sd": float(r["sd"]),
                "hdi_2.5": float(r["hdi_2.5%"]), "hdi_97.5": float(r["hdi_97.5%"])}
    post = idata.posterior
    kf = post["k"].values.ravel(); gf = post["gamma"].values.ravel(); nuf = post["nu"].values.ravel()
    suf = post["sd_undiv"].values.ravel(); ff = post["f"].values.ravel()

    out = {
        "model": "robust_bayesian_pooling_with_floor",
        "spec": "S ~ StudentT(nu,0,sigma); sigma = sqrt(sd_undiv^2 + sd_div^2 * [(R/500)(1/H)^gamma]^{2(k-1)}) * exp(s_t)",
        "reference_size": REFERENCE_SIZE,
        "hhi_floor": HHI_FLOOR, "hhi_ceil": HHI_CEIL,
        "n": int(n), "n_years": int(n_y), "years": [int(y) for y in years],
        "seed": SEED,
        # point estimates used by the operator
        "k": float(kf.mean()),
        "gamma": float(gf.mean()),
        "nu": float(nuf.mean()),
        "sd_undiv": float(suf.mean()),
        "sd_div": float(post["sd_div"].values.ravel().mean()),
        # full summaries for tables
        "params": {p: row(p) for p in ["k", "gamma", "nu", "tau_s", "sd_undiv", "sd_div", "f"]},
        "posterior_prob": {
            # (k_lt_1 removed: identically 1 by construction on the bracket)
            "gamma_gt_0.05": float((gf > 0.05).mean()),
            "nu_lt_2": float((nuf < 2.0).mean()),
            "sd_undiv_gt_0.005": float((suf > 0.005).mean()),
            "undiv_share_gt_0.05": float((ff > 0.05).mean()),
        },
        "diagnostics": {
            "max_rhat": float(summ["r_hat"].max()),
            "min_ess_bulk": float(summ["ess_bulk"].min()),
            "divergences": int(idata.sample_stats["diverging"].sum()),
        },
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Persist the full posterior draws of the operator parameters so downstream
    # uncertainty analyses (e.g. vignette VaR intervals) can propagate parameter
    # uncertainty, not just the posterior mean.
    draws_path = SCRIPT_DIR / "model" / "dispersion_posterior_draws.npz"
    np.savez(
        draws_path,
        k=post["k"].values.ravel(),
        gamma=post["gamma"].values.ravel(),
        sd_undiv=post["sd_undiv"].values.ravel(),
        sd_div=post["sd_div"].values.ravel(),
        reference_size=np.array([REFERENCE_SIZE]),
        hhi_floor=np.array([HHI_FLOOR]), hhi_ceil=np.array([HHI_CEIL]),
    )
    print(f"Wrote {OUT}\nWrote {draws_path} ({post['k'].values.size} draws)")
    print(f"  k={out['k']:.4f}  gamma={out['gamma']:.4f}  nu={out['nu']:.3f}  "
          f"sd_undiv={out['sd_undiv']:.4f}  sd_div={out['sd_div']:.4f}  "
          f"n={n}  divergences={out['diagnostics']['divergences']}  maxRhat={out['diagnostics']['max_rhat']:.3f}")


if __name__ == "__main__":
    sys.exit(main())
