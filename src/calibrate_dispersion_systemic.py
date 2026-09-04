"""Stage 1 of specifications/systemic-correlation-analysis.md.

Extends the two-regime RITC model (calibrate_dispersion_ritc.py) with a LOCATION
reporting-year effect:

    M0:  S_it ~ StudentT(nu_it, mu = 0,          sigma_it)   (baseline, refit for LOO)
    M1:  S_it ~ StudentT(nu_it, mu = m_t,        sigma_it)   m_t = tau_m * z_t
    M2:  S_it ~ StudentT(nu_it, mu = c_it * m_t, sigma_it)   c_it = cos-sim(w_it, wbar_t)

with tau_m ~ HalfNormal(0.05) and everything else identical to the baseline
(k, gamma, floor, scale shock s_t, RITC tail regime, beta_ritc falsification).

Model-conditional diagnostic -- NOT used for inference:

    phi_floor = tau_m^2 / (tau_m^2 + c * sd_undiv^2),
    c = (nu_clean / (nu_clean - 2)) * exp(2 * tau_s^2)

the large-size limit of the within-year correlation between two syndicates, WITHIN
this model. It is not a result: the finite-variance conversion c is undefined on the
posterior draws with nu_clean <= 2 (the summaries below nanmean over them), and the
split is not identified against unmodelled shared-slip covariance. The manuscript
reports no floor decomposition; what it takes from this stage is that the model
containing the directional shock is predictively preferred and leaves k unchanged.
The phi_floor keys remain in the output for continuity, carrying this label.

Writes dispersion_calibration_systemic.json and dispersion_posterior_draws_systemic.npz.
Usage:  python src/calibrate_dispersion_systemic.py
"""
import io, json, sys
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
from adopted_model import scale_block
import arviz as az

SCRIPT_DIR = Path(__file__).resolve().parent.parent
RESULTS = SCRIPT_DIR / "model" / "exposure_results.json"
RITC = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
OUT = SCRIPT_DIR / "model" / "dispersion_calibration_systemic.json"
DRAWS = SCRIPT_DIR / "model" / "dispersion_posterior_draws_systemic.npz"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0
SEED = 42
RHO_SIZES = [50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0]
NU_VAR_EPS = 2.05  # draws with nu_clean <= this have (near-)undefined variance


def load_sample():
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    HHI = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    key = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    W = np.array([o["weights"] for o in recs], float)
    gpw = np.array([o.get("gpw_gbp_m") or 0.0 for o in recs], float)
    return S, R, HHI, yr, key, W, gpw


def ritc_flag(key):
    r = json.load(io.open(RITC, encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([k in occ for k in key])


def composition_loading(W, gpw, yidx, n_y):
    """c_it = cosine similarity of the syndicate's LoB weight vector to the
    premium-weighted market-mean vector of its reporting year."""
    c = np.zeros(len(W))
    for t in range(n_y):
        m = yidx == t
        wts = gpw[m]
        if wts.sum() <= 0:
            wts = np.ones(m.sum())
        wbar = (W[m] * wts[:, None]).sum(axis=0) / wts.sum()
        nb = np.linalg.norm(wbar)
        for i in np.where(m)[0]:
            ni = np.linalg.norm(W[i])
            c[i] = float(W[i] @ wbar / (ni * nb)) if ni > 0 and nb > 0 else 0.0
    return c


def build_and_fit(mode, S, logR, logH, yidx, n_y, ritc, *, tau_m_prior_sd=0.05,
                  c_load=None, seed=SEED, draws=1500, tune=1500):
    """mode in {'m0','m1','m2'}.  Returns idata with pointwise log-likelihood.
    The adopted model (scale_block) with, in m1/m2, a directional reporting-year
    shock in the location: the location is the only departure."""
    with pm.Model():
        b = scale_block(ritc=ritc, logR=logR, logH=logH, yidx=yidx, n_y=n_y,
                        record_shock=True)
        nu_obs, sigma = b["nu_obs"], b["sigma"]
        if mode == "m0":
            mu = 0.0
        else:
            tau_m = pm.HalfNormal("tau_m", tau_m_prior_sd)
            z_m = pm.Normal("z_m", 0.0, 1.0, shape=n_y)
            m_y = pm.Deterministic("m_y", tau_m * z_m)
            mu = m_y[yidx] if mode == "m1" else c_load * m_y[yidx]
        pm.StudentT("S_obs", nu=nu_obs, mu=mu, sigma=sigma, observed=S)
        idata = pm.sample(draws, tune=tune, chains=4, cores=1, target_accept=0.98,
                          random_seed=seed, progressbar=False,
                          idata_kwargs={"log_likelihood": True})
    return idata


def diag(idata, var_names):
    summ = az.summary(idata, var_names=var_names, hdi_prob=0.95)
    return summ, {
        "max_rhat": float(summ["r_hat"].max()),
        "min_ess_bulk": float(summ["ess_bulk"].min()),
        "divergences": int(idata.sample_stats["diverging"].sum()),
    }


def post_row(arr):
    a = np.asarray(arr, float)
    a = a[~np.isnan(a)]
    if a.size == 0:
        return {"mean": None, "sd": None, "hdi_2.5": None, "hdi_97.5": None}
    lo, hi = az.hdi(a, hdi_prob=0.95)
    return {"mean": float(a.mean()), "sd": float(a.std()),
            "hdi_2.5": float(lo), "hdi_97.5": float(hi)}


def derived(post):
    """Systemic-share quantities per posterior draw (NaN where variance undefined)."""
    nu, tau_s = post["nu_clean"], post["tau_s"]
    sd_u, sd_d, k = post["sd_undiv"], post["sd_div"], post["k"]
    tau_m = post["tau_m"]
    c = np.where(nu > NU_VAR_EPS, nu / (nu - 2.0) * np.exp(2.0 * tau_s ** 2), np.nan)
    out = {"frac_draws_nu_le_2": float((nu <= NU_VAR_EPS).mean()),
           "phi_floor": tau_m ** 2 / (tau_m ** 2 + c * sd_u ** 2)}
    for sz in RHO_SIZES:
        V = c * (sd_u ** 2 + sd_d ** 2 * (sz / REFERENCE_SIZE) ** (2.0 * (k - 1.0)))
        out[f"rho_Reff_{int(sz)}"] = tau_m ** 2 / (tau_m ** 2 + V)
    return out


def main():
    S, R, HHI, yr, key, W, gpw = load_sample()
    ritc = ritc_flag(key).astype(float)
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    n_y, n = len(years), len(S)
    logR = np.log(R / REFERENCE_SIZE)
    logH = np.log(HHI)
    c_load = composition_loading(W, gpw, yidx, n_y)
    print(f"n={n}  RITC={int(ritc.sum())}  years={n_y}  "
          f"c_load: mean={c_load.mean():.3f} min={c_load.min():.3f}")

    idatas, diags = {}, {}
    for mode in ["m0", "m1", "m2"]:
        print(f"\n=== fitting {mode.upper()} ===")
        idatas[mode] = build_and_fit(mode, S, logR, logH, yidx, n_y, ritc,
                                     c_load=c_load if mode == "m2" else None)
        vn = ["k", "gamma", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc",
              "tau_s", "sd_undiv", "sd_div", "f"]
        if mode != "m0":
            vn += ["tau_m"]
        summ, dg = diag(idatas[mode], vn)
        diags[mode] = dg
        print(summ[["mean", "sd", "hdi_2.5%", "hdi_97.5%", "r_hat", "ess_bulk"]])
        print(f"divergences={dg['divergences']}  maxRhat={dg['max_rhat']:.3f}")

    def rav(mode, p):
        return idatas[mode].posterior[p].values.reshape(-1, *idatas[mode].posterior[p].shape[2:])

    # ---- LOO comparisons ---------------------------------------------------
    def loo_pair(a, b):
        cmp_ = az.compare({a: idatas[a], b: idatas[b]}, ic="loo")
        top = cmp_.index[0]
        other = b if top == a else a
        sign = 1.0 if top == b else -1.0  # report as (b - a)
        return {
            f"elpd_diff_{b}_minus_{a}": float(sign * cmp_.loc[other, "elpd_diff"]),
            "dse": float(cmp_.loc[other, "dse"]),
            "preferred": str(top),
            "pareto_k_gt_0.7": {m: int((az.loo(idatas[m], pointwise=True)
                                        .pareto_k.values > 0.7).sum()) for m in (a, b)},
        }

    loo_m1_m0 = loo_pair("m0", "m1")
    loo_m2_m1 = loo_pair("m1", "m2")

    # ---- derived quantities (M1 headline, M2 secondary) ---------------------
    post1 = {p: rav("m1", p).ravel() if rav("m1", p).ndim == 1 or p != "m_y" else rav("m1", p)
             for p in ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "tau_s", "tau_m"]}
    der1 = derived(post1)
    post2 = {p: rav("m2", p).ravel()
             for p in ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "tau_s", "tau_m"]}
    der2 = derived(post2)

    m_y_draws = rav("m1", "m_y")            # (draws, n_y)
    s_y_draws = rav("m1", "s_y")
    tau_m1 = post1["tau_m"]
    phi1 = der1["phi_floor"]

    # ---- acceptance check 3: M0 refit vs archived calibration ---------------
    arch = json.load(io.open(SCRIPT_DIR / "model" / "dispersion_calibration_ritc.json",
                             encoding="utf-8"))
    repro = {}
    for p in ["k", "gamma", "sd_undiv"]:
        m0v = rav("m0", p).ravel()
        zdev = abs(m0v.mean() - arch["params"][p]["mean"]) / arch["params"][p]["sd"]
        repro[p] = {"refit_mean": float(m0v.mean()), "archived_mean":
                    arch["params"][p]["mean"], "abs_dev_in_posterior_sd": float(zdev),
                    "within_0.5_sd": bool(zdev < 0.5)}

    def params_block(mode, vn):
        summ = az.summary(idatas[mode], var_names=vn, hdi_prob=0.95)
        return {p: {"mean": float(summ.loc[p, "mean"]), "sd": float(summ.loc[p, "sd"]),
                    "hdi_2.5": float(summ.loc[p, "hdi_2.5%"]),
                    "hdi_97.5": float(summ.loc[p, "hdi_97.5%"])} for p in summ.index}

    vn1 = ["k", "gamma", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc",
           "tau_s", "sd_undiv", "sd_div", "f", "tau_m"]
    out = {
        "model": "systemic_location_year_effect_on_two_regime_ritc_model",
        "spec": ("M1: S ~ StudentT(nu_it, m_t, sigma_it); m_t = tau_m*z_t, "
                 "tau_m ~ HalfNormal(0.05); sigma as in RITC baseline. "
                 "M2: mu = cos_sim(w_it, wbar_t) * m_t. "
                 "phi_floor = tau_m^2/(tau_m^2 + c*sd_undiv^2), "
                 "c = nu/(nu-2)*exp(2 tau_s^2)"),
        "reference_size": REFERENCE_SIZE, "hhi_floor": HHI_FLOOR, "hhi_ceil": HHI_CEIL,
        "n": int(n), "n_ritc": int(ritc.sum()), "n_years": int(n_y),
        "years": [int(y) for y in years], "seed": SEED,
        "tau_m_prior_sd": 0.05,
        "params_m1": params_block("m1", vn1),
        "params_m2_tau_m": params_block("m2", ["tau_m"]),
        "tau_m": post_row(tau_m1),
        "m_t_by_year": {str(int(years[t])): post_row(m_y_draws[:, t])
                        for t in range(n_y)},
        "phi_floor": post_row(phi1),
        "rho_profile": {f"Reff_{int(sz)}": post_row(der1[f"rho_Reff_{int(sz)}"])
                        for sz in RHO_SIZES},
        "frac_draws_nu_le_2": der1["frac_draws_nu_le_2"],
        "phi_floor_m2": post_row(der2["phi_floor"]),
        "loo_compare": {"m1_vs_m0": loo_m1_m0, "m2_vs_m1": loo_m2_m1},
        "sd_undiv_migration": {"m0_mean": float(rav("m0", "sd_undiv").mean()),
                               "m1_mean": float(rav("m1", "sd_undiv").mean())},
        "posterior_prob": {
            "tau_m_gt_0.005": float((tau_m1 > 0.005).mean()),
            "phi_floor_gt_0.5": float(np.nanmean(phi1 > 0.5)),
        },
        "m0_reproduction_check": repro,
        "diagnostics": diags,
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    np.savez(DRAWS,
             **{p: rav("m1", p).ravel() for p in
                ["k", "gamma", "sd_undiv", "sd_div", "f", "nu_clean", "nu_ritc",
                 "lambda_ritc", "beta_ritc", "tau_s", "tau_m"]},
             m_y=m_y_draws, s_y=s_y_draws, phi_floor=phi1,
             years=years.astype(int),
             reference_size=np.array([REFERENCE_SIZE]),
             hhi_floor=np.array([HHI_FLOOR]), hhi_ceil=np.array([HHI_CEIL]))
    print(f"\nWrote {OUT}\nWrote {DRAWS} ({tau_m1.size} draws)")
    print(f"\n  tau_m     = {out['tau_m']['mean']:.4f} "
          f"[{out['tau_m']['hdi_2.5']:.4f},{out['tau_m']['hdi_97.5']:.4f}]"
          f"   P(tau_m>0.005)={out['posterior_prob']['tau_m_gt_0.005']:.3f}")
    print("  [model-conditional diagnostic; not used for inference]")
    print(f"  phi_floor = {out['phi_floor']['mean']:.3f} "
          f"[{out['phi_floor']['hdi_2.5']:.3f},{out['phi_floor']['hdi_97.5']:.3f}]"
          f"   P(phi>0.5)={out['posterior_prob']['phi_floor_gt_0.5']:.3f}"
          f"   (frac nu<=2: {out['frac_draws_nu_le_2']:.3f})")
    print(f"  sd_undiv  : M0 {out['sd_undiv_migration']['m0_mean']:.4f} -> "
          f"M1 {out['sd_undiv_migration']['m1_mean']:.4f}")
    print(f"  LOO M1-M0 : {loo_m1_m0}")
    print(f"  LOO M2-M1 : {loo_m2_m1}")


if __name__ == "__main__":
    sys.exit(main())
