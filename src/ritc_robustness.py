"""RITC robustness: does external RITC drive the heavy tail / move the operator?

External RITC (reinsurance-to-close of another syndicate's account) injects large,
lumpy step-changes into prior-year development that are NOT a portfolio-composition
effect. If those observations are inflating the heavy tail (nu) or distorting the
pooling operator (k, gamma, floor), that matters for how we treat RITC flags.

We re-fit the *identical* calibration model (calibrate_dispersion.py) on three nested
samples, keyed to the dual-LLM RITC scan (pdf_extraction/ritc_scan.json), which flags
each syndicate-year as ritc_occurred with confidence strong/weak:

  (1) ALL            - full sample (baseline, = dispersion_calibration.json)
  (2) EXCL_STRONG    - drop only the strong-confidence RITC years, keep weak + clean
  (3) EXCL_ALL       - drop all RITC (strong + weak), clean only

and compare k, gamma, nu (tail index), the undiversifiable floor, and P(nu<2).

Run:  python ritc_robustness.py
"""
import json, io
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

SCRIPT_DIR = Path(__file__).resolve().parent.parent
RESULTS = SCRIPT_DIR / "model" / "exposure_results.json"
RITC = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
OUT = SCRIPT_DIR / "results" / "ritc_robustness_results.json"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0
SEED = 42


def load_sample():
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    HHI = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    keys = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    return S, R, HHI, yr, keys


def ritc_sets():
    r = json.load(io.open(RITC, encoding="utf-8"))
    strong = {k for k, v in r.items() if v.get("ritc_occurred") and v.get("confidence") == "strong"}
    weak = {k for k, v in r.items() if v.get("ritc_occurred") and v.get("confidence") == "weak"}
    return strong, weak


def fit(S, R, HHI, yr):
    """Identical spec to calibrate_dispersion.py, returned as a summary dict."""
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    n_y, n = len(years), len(S)
    logR = np.log(R / REFERENCE_SIZE)
    logH = np.log(HHI)
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
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    summ = az.summary(idata, var_names=["k", "gamma", "nu", "tau_s", "sd_undiv", "sd_div", "f"], hdi_prob=0.95)
    post = idata.posterior
    kf = post["k"].values.ravel(); gf = post["gamma"].values.ravel(); nuf = post["nu"].values.ravel()
    suf = post["sd_undiv"].values.ravel(); ff = post["f"].values.ravel()

    def hdi(p):
        r = summ.loc[p]
        return {"mean": float(r["mean"]), "sd": float(r["sd"]),
                "hdi_2.5": float(r["hdi_2.5%"]), "hdi_97.5": float(r["hdi_97.5%"])}

    return {
        "n": int(n), "n_years": int(n_y),
        "params": {p: hdi(p) for p in ["k", "gamma", "nu", "tau_s", "sd_undiv", "sd_div", "f"]},
        # (P_k_lt_1 / P_k_gt_0.5 keys computed at 0.999 / 0.5001 were removed:
        # both are guaranteed by the bracketed support, and endpoint labels on
        # interior thresholds misstate what was computed)
        "P_nu_lt_2": float((nuf < 2.0).mean()),
        "P_nu_lt_3": float((nuf < 3.0).mean()),
        "P_undiv_share_gt_0.05": float((ff > 0.05).mean()),
        "max_rhat": float(summ["r_hat"].max()),
        "min_ess": float(summ["ess_bulk"].min()),
        "divergences": int(idata.sample_stats["diverging"].sum()),
    }


def main():
    S, R, HHI, yr, keys = load_sample()
    strong, weak = ritc_sets()
    is_strong = np.array([k in strong for k in keys])
    is_weak = np.array([k in weak for k in keys])
    masks = {
        "ALL":         np.ones(len(S), bool),
        "EXCL_STRONG": ~is_strong,
        "EXCL_ALL":    ~(is_strong | is_weak),
    }
    counts = {"n_total": int(len(S)), "n_strong": int(is_strong.sum()),
              "n_weak": int(is_weak.sum()), "n_clean": int((~(is_strong | is_weak)).sum())}
    print(f"sample n={counts['n_total']}  strong={counts['n_strong']}  "
          f"weak={counts['n_weak']}  clean={counts['n_clean']}\n")

    res = {}
    for name, m in masks.items():
        print(f"--- fitting {name} (n={int(m.sum())}) ---")
        res[name] = fit(S[m], R[m], HHI[m], yr[m])

    out = {"meta": {"seed": SEED, "reference_size": REFERENCE_SIZE,
                    "ritc_scan": "pdf_extraction/ritc_scan.json (dual-LLM, ritc_occurred + confidence)",
                    "counts": counts,
                    "spec": "identical to calibrate_dispersion.py (Student-t, k in [.5,1], gamma>=0, uniform undiv variance share, year shock)"},
           "fits": res}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    def g(r, p, f="{:.3f}"):
        v = r["params"][p]
        return f"{f.format(v['mean'])} [{f.format(v['hdi_2.5'])},{f.format(v['hdi_97.5'])}]"
    hdr = f"\n{'model':<12}{'n':>5}  {'k':<20}{'gamma':<20}{'nu':<20}{'P(nu<2)':>8}{'P(nu<3)':>9}  {'sd_undiv':<18}"
    print(hdr); print("-" * len(hdr))
    for name, r in res.items():
        print(f"{name:<12}{r['n']:>5}  {g(r,'k'):<20}{g(r,'gamma'):<20}{g(r,'nu'):<20}"
              f"{r['P_nu_lt_2']:>8.2f}{r['P_nu_lt_3']:>9.2f}  {g(r,'sd_undiv','{:.4f}'):<18}")
    print(f"\ndivergences/maxRhat: " +
          "  ".join(f"{n}={r['divergences']}/{r['max_rhat']:.2f}" for n, r in res.items()))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
