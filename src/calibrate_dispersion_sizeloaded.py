"""M3: size-loaded systemic shock, to close the referee point that k-robustness
(section 2.8 / Appendix 3.2) was only tested against a UNIFORM directional shock (M1),
which the PPC shows under-fits co-movement at the top of the size ladder.

M3 lets the location year effect load on effective size:

    S_it ~ StudentT(nu_it, mu_it, sigma_it)
    mu_it = (Reff_it / Rref)^psi * m_t ,   m_t = tau_m * z_t
    psi ~ Normal(0, 0.5)                    (psi>0 => big syndicates co-move more)

with lambda(Rref)=1 so tau_m is the loading at the reference size. psi=0 recovers the
uniform M1. Everything else (k, gamma, floor, sd_div, s_t scale shock, RITC tail regime)
is identical to M1, so k is directly comparable.

Question answered: does the pooling exponent k survive a co-movement model that CAN fit
the size-dependent correlation the diagnostic flagged? Reports k/gamma/floor under M1 vs
M3, psi, LOO M3-M1, and the large-tercile posterior-predictive correlation under M3.

Writes dispersion_calibration_sizeloaded.json.
Usage:  python src/calibrate_dispersion_sizeloaded.py
"""
import io, json, sys, time
from pathlib import Path
import numpy as np
from scipy import stats
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from calibrate_dispersion_systemic import (load_sample, ritc_flag, post_row, diag,
                                           REFERENCE_SIZE)
from systemic_correlation_check import PairEngine, T_MIN

SCRIPT_DIR = Path(__file__).resolve().parent.parent
CALIB_M0 = SCRIPT_DIR / "model" / "dispersion_calibration_ritc.json"
OUT = SCRIPT_DIR / "model" / "dispersion_calibration_sizeloaded.json"
SEED = 42


def build_and_fit(mode, S, logR, logH, yidx, n_y, ritc, seed=SEED):
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
        s_y = pm.Deterministic("s_y", tau_s * z_s)
        nu_clean = pm.Gamma("nu_clean", 2.0, 0.1)
        lam = pm.Normal("lambda_ritc", 0.0, 0.7)
        pm.Deterministic("nu_ritc", nu_clean * pm.math.exp(-lam))
        nu_obs = nu_clean * pm.math.exp(-lam * ritc)
        beta_ritc = pm.Normal("beta_ritc", 0.0, 0.5)
        log_reff = logR - gamma * logH
        var = sd_undiv ** 2 + sd_div ** 2 * pm.math.exp(2.0 * (k - 1.0) * log_reff)
        sigma = pm.math.exp(s_y[yidx] + beta_ritc * ritc) * pm.math.sqrt(var)
        tau_m = pm.HalfNormal("tau_m", 0.05)
        z_m = pm.Normal("z_m", 0.0, 1.0, shape=n_y)
        m_y = pm.Deterministic("m_y", tau_m * z_m)
        if mode == "m1":
            psi = pm.Deterministic("psi", pm.math.constant(0.0))
            load = 1.0
        else:  # m3: size-loaded
            psi = pm.Normal("psi", 0.0, 0.5)
            load = pm.math.exp(psi * log_reff)   # (Reff/Rref)^psi
        mu = load * m_y[yidx]
        pm.StudentT("S_obs", nu=nu_obs, mu=mu, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=seed, progressbar=False,
                          idata_kwargs={"log_likelihood": True})
    return idata


def rav(idata, p):
    v = idata.posterior[p].values
    return v.reshape(-1, *v.shape[2:])


def _ppc_impl(idata, S, logR, logH, yr, ritc, sigma_hat, reff0, clean, n_reps=500):
    from calibrate_dispersion_systemic import load_sample as _ls
    Sx, R, H, yrx, key, W, gpw = _ls()
    synd = np.array([k.split("_")[0] for k in key])
    years = np.sort(np.unique(yr)); n_y = len(years)
    yidx = np.searchsorted(years, yr)
    csynd, cy, cre = synd[clean], yidx[clean], reff0[clean]
    synds = np.sort(np.unique(csynd)); n_s = len(synds)
    sidx = np.searchsorted(synds, csynd)
    obs_mask = np.zeros((n_s, n_y), bool); obs_mask[sidx, cy] = True
    RE = np.full((n_s, n_y), np.nan); RE[sidx, cy] = cre
    eng = PairEngine(obs_mask, T_MIN)
    med = np.nanmedian(RE, axis=1)
    ps = np.array([np.sqrt(med[i] * med[j]) for i, j in eng.pairs])
    order = np.argsort(ps); terc = np.zeros(eng.n_pairs, int)
    for g, ch in enumerate(np.array_split(order, 3)):
        terc[ch] = g

    def large_mean(vec):
        z = (vec / sigma_hat)[clean]
        Z = np.full((n_s, n_y), np.nan); Z[sidx, cy] = z
        rho = eng.rhos(Z)
        return rho[terc == 2].mean()

    obs = large_mean(S)
    d = idata.posterior
    def rv(p):
        v = d[p].values; return v.reshape(-1, *v.shape[2:])
    K, G, SU, SD = rv("k"), rv("gamma"), rv("sd_undiv"), rv("sd_div")
    SY, MY, NC, LAMr, BR = rv("s_y"), rv("m_y"), rv("nu_clean"), rv("lambda_ritc"), rv("beta_ritc")
    PSI = rv("psi") if "psi" in d else np.zeros(len(K))
    rng = np.random.default_rng(SEED)
    pick = rng.choice(len(K), min(n_reps, len(K)), replace=False)
    reps = np.empty(len(pick))
    for r, di in enumerate(pick):
        lr = logR - G[di] * logH
        var = SU[di] ** 2 + SD[di] ** 2 * np.exp(2.0 * (K[di] - 1.0) * lr)
        sig = np.exp(SY[di][yidx] + BR[di] * ritc) * np.sqrt(var)
        nu = NC[di] * np.exp(-LAMr[di] * ritc)
        load = np.exp(PSI[di] * lr)
        Srep = load * MY[di][yidx] + sig * rng.standard_t(nu)
        reps[r] = large_mean(Srep)
    band = np.percentile(reps, [5, 95])
    return {"observed_large_rho": float(obs), "band_5_95": [float(band[0]), float(band[1])],
            "inside": bool(band[0] <= obs <= band[1]),
            "p_ppc": float((1 + (reps >= obs).sum()) / (len(pick) + 1))}


def main():
    t0 = time.time()
    S, R, HHI, yr, key, W, gpw = load_sample()
    ritc = ritc_flag(key).astype(float)
    years = np.sort(np.unique(yr)); yidx = np.searchsorted(years, yr); n_y = len(years)
    logR = np.log(R / REFERENCE_SIZE); logH = np.log(HHI)
    print(f"n={len(S)}  years={n_y}")

    fits = {}
    for mode in ("m1", "m3"):
        print(f"=== {mode.upper()} ===")
        fits[mode] = build_and_fit(mode, S, logR, logH, yidx, n_y, ritc)
        vn = ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "tau_m"] + (["psi"] if mode == "m3" else [])
        summ, dg = diag(fits[mode], vn)
        print(summ[["mean", "sd", "hdi_2.5%", "hdi_97.5%", "r_hat"]])
        print("div=%d rhat=%.3f" % (dg["divergences"], dg["max_rhat"]))

    cmp_ = az.compare({"m1": fits["m1"], "m3": fits["m3"]}, ic="loo")
    top = cmp_.index[0]; other = "m1" if top == "m3" else "m3"
    loo = {"preferred": str(top),
           "elpd_diff_m3_minus_m1": float((-1 if top == "m1" else 1) * cmp_.loc[other, "elpd_diff"]),
           "dse": float(cmp_.loc[other, "dse"])}

    def block(mode, vn):
        s = az.summary(fits[mode], var_names=vn, hdi_prob=0.95)
        return {p: {"mean": float(s.loc[p, "mean"]), "sd": float(s.loc[p, "sd"]),
                    "hdi_2.5": float(s.loc[p, "hdi_2.5%"]), "hdi_97.5": float(s.loc[p, "hdi_97.5%"])}
                for p in s.index}

    psi = rav(fits["m3"], "psi").ravel()
    ppc_m1 = _ppc_impl(fits["m1"], S, logR, logH, yr, ritc,
                       *(_prep(logR, logH, ritc)))
    ppc_m3 = _ppc_impl(fits["m3"], S, logR, logH, yr, ritc,
                       *(_prep(logR, logH, ritc)))
    arch = json.load(io.open(CALIB_M0, encoding="utf-8"))
    kk = rav(fits["m3"], "k").ravel()
    out = {
        "model": "size_loaded_systemic_shock_M3_vs_uniform_M1",
        "spec": "mu_it = (Reff_it/Rref)^psi * m_t ; psi~N(0,0.5); psi=0 => uniform M1",
        "n": int(len(S)), "n_years": int(n_y), "seed": SEED,
        "k_M0_archived": arch["k"], "gamma_M0_archived": arch["gamma"],
        "params_m1": block("m1", ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "tau_m"]),
        "params_m3": block("m3", ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "tau_m", "psi"]),
        "psi": post_row(psi),
        # (a k_M3_lt_1 key computed at 0.999 was removed: the bracketed transform
        # guarantees k<1 by construction, and an endpoint label on an interior
        # proximity threshold misstates what was computed)
        "posterior_prob": {"psi_gt_0": float((psi > 0).mean())},
        "loo_m3_vs_m1": loo,
        "large_tercile_ppc": {"m1_uniform": ppc_m1, "m3_size_loaded": ppc_m3},
        "diagnostics": {m: diag(fits[m], ["k", "tau_m"])[1] for m in ("m1", "m3")},
        "runtime_seconds": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT} ({out['runtime_seconds']:.0f}s)")
    print("  k:   M0 %.4f | M1 %.4f | M3 %.4f" % (
        arch["k"], out["params_m1"]["k"]["mean"], out["params_m3"]["k"]["mean"]))
    print("  gamma: M1 %.4f | M3 %.4f" % (out["params_m1"]["gamma"]["mean"], out["params_m3"]["gamma"]["mean"]))
    print("  floor: M1 %.4f | M3 %.4f" % (out["params_m1"]["sd_undiv"]["mean"], out["params_m3"]["sd_undiv"]["mean"]))
    print("  psi = %.3f [%.3f, %.3f]  P(psi>0)=%.3f" % (
        out["psi"]["mean"], out["psi"]["hdi_2.5"], out["psi"]["hdi_97.5"], out["posterior_prob"]["psi_gt_0"]))
    print("  LOO M3-M1 = %.2f +/- %.2f (pref %s)" % (loo["elpd_diff_m3_minus_m1"], loo["dse"], loo["preferred"]))
    print("  large-tercile PPC: M1 %s | M3 %s" % (ppc_m1, ppc_m3))


def _prep(logR, logH, ritc):
    c0 = json.load(io.open(CALIB_M0, encoding="utf-8"))
    lr0 = logR - c0["gamma"] * logH
    sigma_hat = np.sqrt(c0["sd_undiv"] ** 2 + c0["sd_div"] ** 2 * np.exp(2.0 * (c0["k"] - 1.0) * lr0))
    reff0 = np.exp(lr0)
    clean = ritc < 0.5
    return sigma_hat, reff0, clean


if __name__ == "__main__":
    sys.exit(main())
