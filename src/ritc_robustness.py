"""RITC robustness: does external RITC drive the heavy tail / move the operator?

External RITC (reinsurance-to-close of another syndicate's account) injects large,
lumpy step-changes into prior-year development that are NOT a portfolio-composition
effect. If those observations are inflating the heavy tail (nu) or distorting the
pooling operator (k, gamma, floor), that matters for how we treat RITC flags.

We re-fit the *identical* calibration model (calibrate_dispersion.py) on three nested
samples, keyed to the deterministic RITC scan (pdf_extraction/ritc_scan.json), which flags
each syndicate-year as ritc_occurred with confidence strong/weak:

  (1) ALL            - full sample (baseline, = dispersion_calibration.json)
  (2) EXCL_STRONG    - drop only the strong-confidence RITC years, keep weak + clean
  (3) EXCL_ALL       - drop all RITC (strong + weak), clean only

and compare k, gamma, nu (tail index), the undiversifiable floor, and P(nu<2).

The two exclusion samples are fitted a second time with gamma FIXED AT 0 in the likelihood (`fits_gamma_fixed_0`,
the same model otherwise): ritc_treatments.py's T3 and T4 then build their headline size-only rows the way the
headline does since option B (the author's decision of 10 October 2026), from a gamma = 0 fit and not by
zeroing gamma in a fit that estimates it. The gamma-fitted `fits` stay the comparison of gamma (and k, nu and the
floor) across the three samples; T3 and T4, refits on subsamples, carry no overlay leg.

Run:  python src/ritc_robustness.py
"""
import json, io
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
from adopted_model import SAMPLE_CORES
import arviz as az
import assumed_business

SCRIPT_DIR = Path(__file__).resolve().parent.parent
RESULTS = SCRIPT_DIR / "model" / "exposure_results.json"
RITC = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
OUT = SCRIPT_DIR / "results" / "ritc_robustness_results.json"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0
SEED = 42
#: the samples fitted a second time with gamma = 0 in the likelihood (ritc_treatments.py's T3 and T4)
GAMMA_FIXED_0_FITS = ("EXCL_STRONG", "EXCL_ALL")


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
    """(strong, weak): strong RITC flags with the confirmed inward transfers, and the
    weak RITC flags (assumed_business.py, PLAN R195)."""
    return assumed_business.strong_weak()


def fit(S, R, HHI, yr, gamma_prior="halfnormal"):
    """Identical spec to calibrate_dispersion.py, returned as a summary dict; gamma_prior="fixed_0" fixes gamma at 0
    in the likelihood (no gamma variable), the construction of the headline since option B."""
    if gamma_prior not in ("halfnormal", "fixed_0"):
        raise ValueError("gamma_prior must be 'halfnormal' or 'fixed_0'")
    fitted_gamma = gamma_prior == "halfnormal"
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    n_y, n = len(years), len(S)
    logR = np.log(R / REFERENCE_SIZE)
    logH = np.log(HHI)
    with pm.Model():
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        gamma = pm.HalfNormal("gamma", 1.0) if fitted_gamma else 0.0
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
        idata = pm.sample(1500, tune=1500, chains=4, cores=SAMPLE_CORES, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    names = ["k", "gamma", "nu", "tau_s", "sd_undiv", "sd_div", "f"]
    if not fitted_gamma:
        names.remove("gamma")
    summ = az.summary(idata, var_names=names, hdi_prob=0.95)
    post = idata.posterior
    kf = post["k"].values.ravel(); nuf = post["nu"].values.ravel()
    suf = post["sd_undiv"].values.ravel(); ff = post["f"].values.ravel()

    def hdi(p):
        r = summ.loc[p]
        return {"mean": float(r["mean"]), "sd": float(r["sd"]),
                "hdi_2.5": float(r["hdi_2.5%"]), "hdi_97.5": float(r["hdi_97.5%"])}

    return {
        "n": int(n), "n_years": int(n_y),
        **({} if fitted_gamma else {"gamma_prior": "fixed_0", "gamma": 0.0}),
        "params": {p: hdi(p) for p in names},
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
    # the exclusion samples again with gamma = 0 in the likelihood: ritc_treatments.py's T3/T4 headline rows
    res_g0 = {}
    for name in GAMMA_FIXED_0_FITS:
        m = masks[name]
        print(f"--- fitting {name} with gamma = 0 (n={int(m.sum())}) ---")
        res_g0[name] = fit(S[m], R[m], HHI[m], yr[m], gamma_prior="fixed_0")

    out = {"meta": {"seed": SEED, "reference_size": REFERENCE_SIZE,
                    "ritc_scan": "pdf_extraction/ritc_scan.json (deterministic sentence classifier, ritc_occurred + confidence), with the confirmed inward transfers of pdf_extraction/audit/portfolio_transfer_adjudication.json counted as strong (assumed_business.py)",
                    "counts": counts,
                    "spec": "identical to calibrate_dispersion.py (Student-t, k in [.5,1], gamma>=0, uniform undiv variance share, year shock)",
                    "spec_gamma_fixed_0": ("the same with gamma = 0 in the likelihood (no concentration term), for "
                                           "ritc_treatments.py's T3/T4 headline rows")},
           "fits": res,
           "fits_gamma_fixed_0": res_g0}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    def g(r, p, f="{:.3f}"):
        v = r["params"][p]
        return f"{f.format(v['mean'])} [{f.format(v['hdi_2.5'])},{f.format(v['hdi_97.5'])}]"
    hdr = f"\n{'model':<12}{'n':>5}  {'k':<20}{'gamma':<20}{'nu':<20}{'P(nu<2)':>8}{'P(nu<3)':>9}  {'sd_undiv':<18}"
    print(hdr); print("-" * len(hdr))
    for name, r in res.items():
        print(f"{name:<12}{r['n']:>5}  {g(r,'k'):<20}{g(r,'gamma'):<20}{g(r,'nu'):<20}"
              f"{r['P_nu_lt_2']:>8.2f}{r['P_nu_lt_3']:>9.2f}  {g(r,'sd_undiv','{:.4f}'):<18}")
    for name, r in res_g0.items():
        print(f"{name + ' g=0':<12}{r['n']:>5}  {g(r,'k'):<20}{'0 (fixed)':<20}{g(r,'nu'):<20}"
              f"{r['P_nu_lt_2']:>8.2f}{r['P_nu_lt_3']:>9.2f}  {g(r,'sd_undiv','{:.4f}'):<18}")
    print(f"\ndivergences/maxRhat: " +
          "  ".join(f"{n}={r['divergences']}/{r['max_rhat']:.2f}" for n, r in res.items())
          + "  " + "  ".join(f"{n} g=0={r['divergences']}/{r['max_rhat']:.2f}" for n, r in res_g0.items()))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
