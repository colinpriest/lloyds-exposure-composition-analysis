"""Appendix C: pooling-form comparison by PSIS-LOO (blended free-k vs independent k=0.5).

Two candidate pooling laws for the diversifiable dispersion, BOTH with the undiversifiable
floor and the effective size E = R*(1/H)^gamma:

  M1 - blended exponent:   sigma = sqrt( sd_undiv^2 + sd_div^2 * [E/ref]^{2(k-1)} ),  k in [0.5,1] free
  M2 - independent sqrt(N): as M1 but k fixed at 0.5 (pure independence; all non-independent
                            behaviour carried by the systematic floor)

Robust (Student-t) likelihood, mu=0, reporting-year shared shock, uniform undiversifiable
variance-share prior - identical to calibrate_dispersion.py (the single-nu baseline), so the
comparison isolates the pooling FORM. Reports per-model elpd_loo, the M1-M2 difference, its SE,
PSIS-LOO stacking weights, and each model's k / sd_undiv posterior.

Run: python pooling_compare.py
"""
import io, json
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

SCRIPT_DIR = Path(__file__).resolve().parent.parent
OUT = SCRIPT_DIR / "results" / "pooling_compare_results.json"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0
SEED = 42


def load_sample():
    d = json.load(io.open(SCRIPT_DIR / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    HHI = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    return S, R, HHI, yr


def fit(S, R, HHI, yr, free_k):
    years = np.sort(np.unique(yr)); yidx = np.searchsorted(years, yr)
    n_y, n = len(years), len(S)
    logR = np.log(R / REFERENCE_SIZE); logH = np.log(HHI)
    with pm.Model():
        if free_k:
            theta = pm.Normal("theta", 0.0, 1.5)
            k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        else:
            k = pm.Deterministic("k", pm.math.constant(0.5))
        gamma = pm.HalfNormal("gamma", 1.0)
        log_tot = pm.Normal("log_tot", np.log(0.05), 1.0); tot_sd = pm.math.exp(log_tot)
        f = pm.Beta("f", 1.0, 1.0)
        sd_undiv = pm.Deterministic("sd_undiv", tot_sd * pm.math.sqrt(f))
        sd_div = pm.Deterministic("sd_div", tot_sd * pm.math.sqrt(1.0 - f))
        tau_s = pm.HalfNormal("tau_s", 0.5)
        z_s = pm.Normal("z_s", 0.0, 1.0, shape=n_y); s_y = tau_s * z_s
        log_reff = logR - gamma * logH
        var = sd_undiv ** 2 + sd_div ** 2 * pm.math.exp(2.0 * (k - 1.0) * log_reff)
        sigma = pm.math.exp(s_y[yidx]) * pm.math.sqrt(var)
        nu = pm.Gamma("nu", 2.0, 0.1)
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False, idata_kwargs={"log_likelihood": True})
    return idata


def summ(idata, name, free_k):
    vn = ["k", "gamma", "nu", "sd_undiv", "sd_div"] if free_k else ["gamma", "nu", "sd_undiv", "sd_div"]
    s = az.summary(idata, var_names=vn, hdi_prob=0.95)
    post = idata.posterior
    kf = post["k"].values.ravel()
    out = {"name": name, "free_k": free_k,
           "k_mean": float(kf.mean()),
           "k_hdi": [float(np.percentile(kf, 2.5)), float(np.percentile(kf, 97.5))],
           "P_k_gt_0.5": float((kf > 0.5001).mean()) if free_k else 0.0,
           "sd_undiv_mean": float(post["sd_undiv"].values.ravel().mean()),
           "sd_undiv_hdi": [float(s.loc["sd_undiv", "hdi_2.5%"]), float(s.loc["sd_undiv", "hdi_97.5%"])],
           "gamma_mean": float(post["gamma"].values.ravel().mean()),
           "nu_mean": float(post["nu"].values.ravel().mean()),
           "max_rhat": float(s["r_hat"].max()),
           "divergences": int(idata.sample_stats["diverging"].sum())}
    return out


def main():
    S, R, HHI, yr = load_sample()
    print(f"n={len(S)}  years={len(np.unique(yr))}")
    print("fitting M1 (blended, k free)..."); id1 = fit(S, R, HHI, yr, True)
    print("fitting M2 (independent, k=0.5)..."); id2 = fit(S, R, HHI, yr, False)

    loo1 = az.loo(id1); loo2 = az.loo(id2)
    cmp = az.compare({"M1_blended": id1, "M2_independent": id2}, ic="loo")
    # difference M1 - M2
    d_elpd = float(loo1.elpd_loo - loo2.elpd_loo)
    # SE of the difference from pointwise elpd
    e1 = id1.log_likelihood["S_obs"]  # placeholder to ensure loo used pointwise
    dse = float(cmp["dse"].max()) if "dse" in cmp else None

    res = {
        "n": int(len(S)), "n_years": int(len(np.unique(yr))), "seed": SEED,
        "spec": "Student-t, mu=0, floor (uniform var-share), year shock; M2 = M1 with k fixed 0.5",
        "M1_blended": {**summ(id1, "M1_blended", True),
                       "elpd_loo": float(loo1.elpd_loo), "p_loo": float(loo1.p_loo), "se": float(loo1.se)},
        "M2_independent": {**summ(id2, "M2_independent", False),
                           "elpd_loo": float(loo2.elpd_loo), "p_loo": float(loo2.p_loo), "se": float(loo2.se)},
        "delta_elpd_M1_minus_M2": d_elpd,
        "delta_se": dse,
        "loo_weights": {str(i): float(w) for i, w in zip(cmp.index, cmp["weight"])},
        "compare_table": cmp.reset_index().to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 64)
    print(f"{'model':<18}{'elpd_loo':>10}{'p_loo':>8}{'k':>18}{'sd_undiv':>12}")
    for m in ("M1_blended", "M2_independent"):
        r = res[m]
        kdesc = f"{r['k_mean']:.3f}[{r['k_hdi'][0]:.2f},{r['k_hdi'][1]:.2f}]" if r["free_k"] else "0.5 (fixed)"
        print(f"{m:<18}{r['elpd_loo']:>10.2f}{r['p_loo']:>8.1f}{kdesc:>18}{r['sd_undiv_mean']:>12.4f}")
    print(f"\nDelta elpd (M1-M2) = {d_elpd:+.2f}   Delta SE = {dse}")
    print(f"LOO stacking weights: {res['loo_weights']}")
    print(f"M1 P(k>0.5) = {res['M1_blended']['P_k_gt_0.5']:.3f}   "
          f"max Rhat M1/M2 = {res['M1_blended']['max_rhat']:.2f}/{res['M2_independent']['max_rhat']:.2f}   "
          f"div M1/M2 = {res['M1_blended']['divergences']}/{res['M2_independent']['divergences']}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
