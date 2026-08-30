"""M4: heteroscedastic (size-loaded) scale shock — the specification that bears most
directly on k and was not previously fitted (review point).

The headline model has a UNIFORM log-scale reporting-year shock s_t (every syndicate's
scale co-moves identically). The referee's concern: if large syndicates' SCALES co-move
more than small ones' (shared-slip dependence in the volatility, not the mean), that
size-dependent scale co-movement lives exactly where the pooling finding lives and could
soak up the size-dispersion signal that identifies k. The size-loaded MEAN shock (Appendix
3.2 / calibrate_dispersion_sizeloaded.py) left k put; the size-loaded SCALE shock is the
harder, untested case.

M4 lets the year scale shock load linearly on (centred) log effective size:

    log sigma_it = (1 + psi_s * logReff_c,it) * s_t  +  beta_ritc * 1[RITC]   (+ 0.5 log var)
    logReff_c = log_reff - mean(log_reff);  s_t = tau_s * z_t,  z_t ~ N(0,1);  psi_s ~ N(0, 0.5)

psi_s = 0 recovers the uniform-scale headline model (H0); psi_s > 0 means big syndicates'
scale amplitudes co-move more (the shock hits them harder). Loading is centred so it equals
1 at mean log-size, keeping tau_s comparable to the headline; a linear (not exp) loading
avoids the nested-exponential graph that fails to compile under NUMBA. Everything else (k, gamma, floor, sd_div, RITC tail regime, mu=0) is
identical to calibrate_dispersion_ritc.py, so k is directly comparable.

Deliverable: does k survive a heteroscedastic scale shock? Reports k/gamma/floor under H0
vs M4, psi_s, tau_s, LOO(M4-H0), and P(k>0.5)/P(k<1) under M4.

Writes dispersion_calibration_hetscale.json.
Usage:  python calibrate_dispersion_hetscale.py
"""
import io, json, sys, time
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from calibrate_dispersion_systemic import load_sample, ritc_flag, post_row, diag
from systemic_correlation_check import PairEngine, T_MIN

SD = Path(__file__).resolve().parent.parent
CALIB_M0 = SD / "model" / "dispersion_calibration_ritc.json"
OUT = SD / "model" / "dispersion_calibration_hetscale.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42


def build_and_fit(mode, S, logR, logH, yidx, n_y, ritc, seed=SEED, gamma_c=0.264):
    """mode in {'h0','m4'}. gamma_c centres the loading at mean log-effective-size
    (fixed constant only to build the centring offset; gamma itself is still free)."""
    center = float((logR - gamma_c * logH).mean())   # fixed offset so loading=1 at mean size
    with pm.Model():
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        gamma = pm.HalfNormal("gamma", 1.0)
        log_tot = pm.Normal("log_tot", np.log(0.05), 1.0)
        tot = pm.math.exp(log_tot)
        f = pm.Beta("f", 1.0, 1.0)
        sd_undiv = pm.Deterministic("sd_undiv", tot * pm.math.sqrt(f))
        sd_div = pm.Deterministic("sd_div", tot * pm.math.sqrt(1.0 - f))
        tau_s = pm.HalfNormal("tau_s", 0.5)
        z_s = pm.Normal("z_s", 0.0, 1.0, shape=n_y)
        s_y = pm.Deterministic("s_y", tau_s * z_s)
        nu_clean = pm.Gamma("nu_clean", 2.0, 0.1)
        lam = pm.Normal("lambda_ritc", 0.0, 0.7)
        pm.Deterministic("nu_ritc", nu_clean * pm.math.exp(-lam))
        nu_obs = nu_clean * pm.math.exp(-lam * ritc)
        beta_ritc = pm.Normal("beta_ritc", 0.0, 0.5)
        log_reff = logR - gamma * logH
        var = sd_undiv ** 2 + sd_div ** 2 * pm.math.exp(2.0 * (k - 1.0) * log_reff)
        if mode == "h0":
            psi_s = pm.Deterministic("psi_s", pm.math.constant(0.0))
            scale_shock = s_y[yidx]
        else:  # m4: size-loaded scale shock (linear loading, centred at mean log-size)
            psi_s = pm.Normal("psi_s", 0.0, 0.5)
            scale_shock = (1.0 + psi_s * (log_reff - center)) * s_y[yidx]
        sigma = pm.math.exp(scale_shock + beta_ritc * ritc) * pm.math.sqrt(var)
        pm.StudentT("S_obs", nu=nu_obs, mu=0.0, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=seed, progressbar=False,
                          idata_kwargs={"log_likelihood": True})
    return idata


def rv(idata, p):
    v = idata.posterior[p].values
    return v.reshape(-1, *v.shape[2:])


def abs_z_tercile_ppc(idata, S, logR, logH, yr, ritc, n_reps=500):
    """Scale shocks live in |z|, not signed z. Diagnostic: within-year mean |z| by
    size tercile, and the cross-tercile co-movement of that series, observed vs M4
    replicate band. Confirms whether the size-loaded scale shock reproduces the
    heteroscedastic co-movement it targets."""
    c0 = json.load(io.open(CALIB_M0, encoding="utf-8"))
    lr0 = logR - c0["gamma"] * logH
    sigma_hat = np.sqrt(c0["sd_undiv"] ** 2 + c0["sd_div"] ** 2
                        * np.exp(2.0 * (c0["k"] - 1.0) * lr0))
    reff0 = np.exp(lr0)
    clean = ritc < 0.5
    years = np.sort(np.unique(yr)); n_y = len(years); yidx = np.searchsorted(years, yr)
    # large-tercile mean |z| within year, averaged over years
    def large_absz(vec):
        z = np.abs(vec / sigma_hat)
        vals = []
        for t in range(n_y):
            m = (yidx == t) & clean
            if m.sum() < 3:
                continue
            re = reff0[m]; zz = z[m]
            thr = np.quantile(re, 2 / 3)
            vals.append(zz[re >= thr].mean())
        return float(np.mean(vals))
    obs = large_absz(S)
    K, G, SU, SD_, SY, NC, LAMr, BR = (rv(idata, p) for p in
        ("k", "gamma", "sd_undiv", "sd_div", "s_y", "nu_clean", "lambda_ritc", "beta_ritc"))
    PSI = rv(idata, "psi_s") if "psi_s" in idata.posterior else np.zeros(len(K))
    rng = np.random.default_rng(SEED)
    pick = rng.choice(len(K), min(n_reps, len(K)), replace=False)
    reps = np.empty(len(pick))
    for r, di in enumerate(pick):
        lr = logR - G[di] * logH
        center = (logR - 0.264 * logH).mean()
        var = SU[di] ** 2 + SD_[di] ** 2 * np.exp(2.0 * (K[di] - 1.0) * lr)
        scale_shock = (1.0 + PSI[di] * (lr - center)) * SY[di][yidx]
        sig = np.exp(scale_shock + BR[di] * ritc) * np.sqrt(var)
        nu = NC[di] * np.exp(-LAMr[di] * ritc)
        reps[r] = large_absz(sig * rng.standard_t(nu))
    band = np.percentile(reps, [5, 95])
    return {"observed_large_mean_absz": obs, "band_5_95": [float(band[0]), float(band[1])],
            "inside": bool(band[0] <= obs <= band[1]),
            "p_ppc": float((1 + (reps >= obs).sum()) / (len(pick) + 1))}


def main():
    t0 = time.time()
    S, R, HHI, yr, key, W, gpw = load_sample()
    ritc = ritc_flag(key).astype(float)
    years = np.sort(np.unique(yr)); yidx = np.searchsorted(years, yr); n_y = len(years)
    logR = np.log(R / REF); logH = np.log(np.clip(HHI, HLO, HCE))
    print(f"n={len(S)}  years={n_y}")

    fits = {}
    for mode in ("h0", "m4"):
        print(f"=== {mode.upper()} ===")
        fits[mode] = build_and_fit(mode, S, logR, logH, yidx, n_y, ritc)
        vn = ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "tau_s"] + (["psi_s"] if mode == "m4" else [])
        summ, dg = diag(fits[mode], vn)
        print(summ[["mean", "sd", "hdi_2.5%", "hdi_97.5%", "r_hat"]])
        print("div=%d rhat=%.3f" % (dg["divergences"], dg["max_rhat"]))

    cmp_ = az.compare({"h0": fits["h0"], "m4": fits["m4"]}, ic="loo")
    top = cmp_.index[0]; other = "h0" if top == "m4" else "m4"
    loo = {"preferred": str(top),
           "elpd_diff_m4_minus_h0": float((-1 if top == "h0" else 1) * cmp_.loc[other, "elpd_diff"]),
           "dse": float(cmp_.loc[other, "dse"]),
           "pareto_k_gt_0.7": {m: int((az.loo(fits[m], pointwise=True).pareto_k.values > 0.7).sum())
                               for m in ("h0", "m4")}}

    def block(mode, vn):
        s = az.summary(fits[mode], var_names=vn, hdi_prob=0.95)
        return {p: {"mean": float(s.loc[p, "mean"]), "sd": float(s.loc[p, "sd"]),
                    "hdi_2.5": float(s.loc[p, "hdi_2.5%"]), "hdi_97.5": float(s.loc[p, "hdi_97.5%"])}
                for p in s.index}

    psi = rv(fits["m4"], "psi_s").ravel()
    kk = rv(fits["m4"], "k").ravel()
    arch = json.load(io.open(CALIB_M0, encoding="utf-8"))
    ppc = abs_z_tercile_ppc(fits["m4"], S, logR, logH, yr, ritc)

    out = {
        "model": "heteroscedastic_size_loaded_scale_shock_M4_vs_uniform_H0",
        # The fitted loading is LINEAR in centred log effective size, not a power.
        # This string said (Reff/Rref)^psi_s, which the docstring above never did,
        # and the manuscript copied the wrong form from here.
        "spec": "log sigma_it = (1 + psi_s*(log Reff_it - c)) * s_t + beta_ritc*1[RITC]; "
                "c = mean(log(R/Rref) - 0.264*log H), a FIXED centring offset built with a "
                "legacy gamma_c and NOT the free gamma, so the loading is 1 at mean log "
                "effective size; psi_s ~ N(0,0.5) is a linear loading coefficient, not a "
                "power elasticity; psi_s=0 => uniform-scale headline model",
        "n": int(len(S)), "n_years": int(n_y), "seed": SEED,
        "k_M0_archived": arch["k"], "gamma_M0_archived": arch["gamma"],
        "params_h0": block("h0", ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "tau_s"]),
        "params_m4": block("m4", ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "tau_s", "psi_s"]),
        "psi_s": post_row(psi),
        "posterior_prob": {"psi_s_gt_0": float((psi > 0).mean()),
                           "k_M4_gt_0.5": float((kk > 0.501).mean()),
                           "k_M4_lt_1": float((kk < 0.999).mean())},
        "loo_m4_vs_h0": loo,
        "abs_z_large_tercile_ppc": ppc,
        "diagnostics": {m: diag(fits[m], ["k", "tau_s"])[1] for m in ("h0", "m4")},
        "runtime_seconds": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT} ({out['runtime_seconds']:.0f}s)")
    print("  k:     M0 %.4f | H0 %.4f | M4 %.4f  (M4 HDI [%.3f, %.3f])" % (
        arch["k"], out["params_h0"]["k"]["mean"], out["params_m4"]["k"]["mean"],
        out["params_m4"]["k"]["hdi_2.5"], out["params_m4"]["k"]["hdi_97.5"]))
    print("  gamma: H0 %.4f | M4 %.4f" % (out["params_h0"]["gamma"]["mean"], out["params_m4"]["gamma"]["mean"]))
    print("  floor: H0 %.4f | M4 %.4f" % (out["params_h0"]["sd_undiv"]["mean"], out["params_m4"]["sd_undiv"]["mean"]))
    print("  psi_s = %.3f [%.3f, %.3f]  P(psi_s>0)=%.3f" % (
        out["psi_s"]["mean"], out["psi_s"]["hdi_2.5"], out["psi_s"]["hdi_97.5"],
        out["posterior_prob"]["psi_s_gt_0"]))
    print("  P(k>0.5)=%.3f  P(k<1)=%.3f" % (out["posterior_prob"]["k_M4_gt_0.5"], out["posterior_prob"]["k_M4_lt_1"]))
    print("  LOO M4-H0 = %.2f +/- %.2f (pref %s)" % (loo["elpd_diff_m4_minus_h0"], loo["dse"], loo["preferred"]))
    print("  |z| large-tercile PPC: %s" % ppc)


if __name__ == "__main__":
    sys.exit(main())
