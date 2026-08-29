"""The concentration-mean relationship, estimated as a posterior rather than by OLS.

Table 6 of the manuscript reports the relationship mu = m0 + m1*H under a column
headed "95% HDI", with a tablenote quoting a slope standard error and a p-value. The
interval printed there, [-0.081, +0.052], is exactly -0.014 +/- 1.96*0.034: a Wald
interval from the superseded least-squares method, not a posterior at all. No script
in this repository produced it, which is why it survived: nothing could check it.

This refits the same relationship inside the adopted dispersion model -- identical
priors, likelihood, year shock and scale law to calibrate_dispersion.py -- with the
mean freed instead of fixed at zero:

    S_it ~ StudentT(nu, mu_it, sigma_it)
    mu_it = m0 + m1 * (H_it - Hbar)                 [+ m2 * (logR_it - logRbar)]

so that m1 carries the same meaning as before but is reported as a posterior with a
highest-density interval and a posterior probability, per the paper's conventions.

Run: python check_mean_concentration_bayes.py
"""
import io
import json
from pathlib import Path

import numpy as np
import pytensor

pytensor.config.mode = "NUMBA"
import arviz as az
import pymc as pm

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_mean_concentration_bayes_results.json"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0
SEED = 42


def hdi95(x):
    a = np.asarray(x, float).ravel()
    return [float(v) for v in az.hdi(a, hdi_prob=0.95)]


def load_sample():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    return S, R, H, yr


def fit(S, R, H, yr, size_control):
    """The adopted dispersion model with the mean freed on centred concentration."""
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    n_y = len(years)
    logR = np.log(R / REFERENCE_SIZE)
    logH = np.log(H)
    Hc = H - H.mean()
    logRc = logR - logR.mean()

    with pm.Model():
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        gamma = pm.HalfNormal("gamma", 1.0)
        log_tot = pm.Normal("log_tot", np.log(0.05), 1.0)
        tot_sd = pm.math.exp(log_tot)
        f = pm.Beta("f", 1.0, 1.0)
        sd_undiv = pm.Deterministic("sd_undiv", tot_sd * pm.math.sqrt(f))
        sd_div = pm.Deterministic("sd_div", tot_sd * pm.math.sqrt(1.0 - f))
        tau_s = pm.HalfNormal("tau_s", 0.5)
        z_s = pm.Normal("z_s", 0.0, 1.0, shape=n_y)
        s_y = tau_s * z_s
        log_reff = logR - gamma * logH
        var = sd_undiv ** 2 + sd_div ** 2 * pm.math.exp(2.0 * (k - 1.0) * log_reff)
        sigma = pm.math.exp(s_y[yidx]) * pm.math.sqrt(var)
        nu = pm.Gamma("nu", 2.0, 0.1)

        m0 = pm.Normal("m0", 0.0, 0.1)
        m1 = pm.Normal("m1", 0.0, 0.5)
        mu = m0 + m1 * Hc
        if size_control:
            m2 = pm.Normal("m2", 0.0, 0.5)
            mu = mu + m2 * logRc

        pm.StudentT("S_obs", nu=nu, mu=mu, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)

    names = ["m0", "m1", "k", "gamma", "nu", "sd_undiv"] + (["m2"] if size_control else [])
    s = az.summary(idata, var_names=names, hdi_prob=0.95)
    post = idata.posterior
    m1d = post["m1"].values.ravel()
    gd = post["gamma"].values.ravel()
    # the fitted scale at the reference point, so the mean shift can be expressed in
    # dispersion-scale units without anyone having to divide by a remembered number
    su = post["sd_undiv"].values.ravel()
    sv = post["sd_div"].values.ravel()
    ref_sigma = float(np.sqrt(su ** 2 + sv ** 2).mean())
    return {
        "m1_mean": float(m1d.mean()),
        "m1_hdi": hdi95(m1d),
        "P_m1_lt_0": float((m1d < 0).mean()),
        "m0_mean": float(post["m0"].values.ravel().mean()),
        "k_mean": float(post["k"].values.ravel().mean()),
        "gamma_mean": float(gd.mean()),
        "gamma_hdi": hdi95(gd),
        "sigma_at_reference": ref_sigma,
        "max_rhat": float(s["r_hat"].max()),
        "min_ess_bulk": float(s["ess_bulk"].min()),
        "divergences": int(idata.sample_stats["diverging"].sum()),
    }, m1d


def main():
    S, R, H, yr = load_sample()
    print("n=%d  Hbar=%.4f" % (len(S), H.mean()))

    base, m1d = fit(S, R, H, yr, size_control=False)
    ctrl, _ = fit(S, R, H, yr, size_control=True)

    # the manuscript also reports the implied mean shift across the H range
    shift = m1d * (0.9 - 0.1)
    ref_sigma = base["sigma_at_reference"]
    res = {
        "n": int(len(S)), "seed": SEED, "H_mean": float(H.mean()),
        "spec": ("adopted dispersion model (identical priors, year shock and scale law "
                 "to calibrate_dispersion.py) with mu = m0 + m1*(H - Hbar)"),
        "replaces": ("Wald interval -0.014 +/- 1.96*0.034 from the superseded "
                     "least-squares method, printed in Table 6 under an HDI heading"),
        "m1_concentration_slope": base,
        "m1_with_logR_control": ctrl,
        "mean_shift_H_0.1_to_0.9": {
            "mean": float(shift.mean()),
            "hdi": hdi95(shift),
            "P_lt_0": float((shift < 0).mean()),
            "in_dispersion_scale_units": float(shift.mean() / ref_sigma),
        },
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")

    print("\nm1 (concentration slope)   %+.4f  95%% HDI [%+.4f, %+.4f]  P(m1<0)=%.2f"
          % (base["m1_mean"], base["m1_hdi"][0], base["m1_hdi"][1], base["P_m1_lt_0"]))
    print("m1 (with log R control)    %+.4f  95%% HDI [%+.4f, %+.4f]  P(m1<0)=%.2f"
          % (ctrl["m1_mean"], ctrl["m1_hdi"][0], ctrl["m1_hdi"][1], ctrl["P_m1_lt_0"]))
    print("mean shift H 0.1->0.9      %+.4f  95%% HDI [%+.4f, %+.4f]  P(<0)=%.2f"
          % (res["mean_shift_H_0.1_to_0.9"]["mean"],
             res["mean_shift_H_0.1_to_0.9"]["hdi"][0],
             res["mean_shift_H_0.1_to_0.9"]["hdi"][1],
             res["mean_shift_H_0.1_to_0.9"]["P_lt_0"]))
    print("\ndiagnostics: max Rhat %.3f / %.3f, divergences %d / %d"
          % (base["max_rhat"], ctrl["max_rhat"],
             base["divergences"], ctrl["divergences"]))
    print("written to", OUT)


if __name__ == "__main__":
    main()
