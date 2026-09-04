"""Check 4 (referee): size-maturity partial confound (within data limits).

Worry: larger books are more mature / vintage-diversified, so part of the size effect is
maturity. Build the weak proxies public data allow and test whether k survives them:
  (a) age-in-window = t - first_observed_year(i)  (left-censored at 2014)
  (b) reserve-to-GWP ratio R/GWP  (crude duration proxy)
Add each proxy to the LOG-SCALE of the dispersion model (log sigma gets + delta*proxy) and
refit k; separately run the control regression |z| ~ log R + proxy. Report k to 3 dp with
and without each proxy, and the proxy coefficient.

Writes check_size_maturity_results.json.
Usage:  python src/check_size_maturity.py
"""
import io, json, sys
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
from adopted_model import scale_block
import arviz as az

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_size_maturity_results.json"
RITC = SD / "pdf_extraction" / "ritc_scan.json"
CALIB = SD / "model" / "dispersion_calibration_ritc.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None and o.get("gpw_gbp_m")]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    syn = np.array([o["syndicate"] for o in recs])
    gpw = np.array([o["gpw_gbp_m"] for o in recs], float)
    key = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    return S, R, H, yr, syn, gpw, key


def ritc_flag(key):
    r = json.load(io.open(RITC, encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([k in occ for k in key], float)


def fit(S, R, H, yr, ritc, proxy=None):
    """The adopted model (scale_block); if proxy is given, the only departure is
    an extra log-scale term delta * proxy_std."""
    with pm.Model():
        extra = None
        if proxy is not None:
            delta = pm.Normal("delta_proxy", 0.0, 0.5)
            extra = delta * proxy
        b = scale_block(R, H, yr, ritc, extra_log_scale=extra)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    res = {"k": float(p["k"].values.mean()),
           "k_hdi": [float(x) for x in az.hdi(p["k"].values.ravel(), hdi_prob=0.95)],
           "gamma": float(p["gamma"].values.mean()),
           "sd_undiv": float(p["sd_undiv"].values.mean())}
    if proxy is not None:
        dd = p["delta_proxy"].values.ravel()
        res["delta_proxy"] = {"mean": float(dd.mean()),
                              "hdi": [float(x) for x in az.hdi(dd, hdi_prob=0.95)]}
    return res


def control_regression(S, R, H, proxy):
    """|z| ~ log R + proxy, z = S/sigma_hat(M0). OLS coefficients + t-stats."""
    c = json.load(io.open(CALIB, encoding="utf-8"))
    log_reff = np.log(np.maximum(R, 1e-9) / c["reference_size"]) - c["gamma"] * np.log(H)
    sigma_hat = np.sqrt(c["sd_undiv"] ** 2 + c["sd_div"] ** 2
                        * np.exp(2.0 * (c["k"] - 1.0) * log_reff))
    y = np.abs(S / sigma_hat)
    X = np.column_stack([np.ones_like(y), np.log(R / REF), proxy])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = len(y) - X.shape[1]
    s2 = (resid @ resid) / dof
    cov = s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    return {"coef_logR": float(beta[1]), "t_logR": float(beta[1] / se[1]),
            "coef_proxy": float(beta[2]), "t_proxy": float(beta[2] / se[2])}


def main():
    S, R, H, yr, syn, gpw, key = load()
    ritc = ritc_flag(key)
    first_year = {s: yr[syn == s].min() for s in set(syn)}
    age = np.array([yr[i] - first_year[syn[i]] for i in range(len(S))], float)   # censored at 2014
    r_gwp = R / np.maximum(gpw, 1e-6)
    def std(x): return (x - x.mean()) / x.std()
    age_s, rgwp_s = std(age), std(np.log(r_gwp))
    print(f"n={len(S)}  age range {age.min():.0f}-{age.max():.0f}  "
          f"R/GWP median {np.median(r_gwp):.2f}")

    base = fit(S, R, H, yr, ritc)
    print(f"  base            k={base['k']:.3f}")
    age_fit = fit(S, R, H, yr, ritc, proxy=age_s)
    print(f"  + age           k={age_fit['k']:.3f}  delta={age_fit['delta_proxy']['mean']:+.3f} {age_fit['delta_proxy']['hdi']}")
    rgwp_fit = fit(S, R, H, yr, ritc, proxy=rgwp_s)
    print(f"  + log(R/GWP)    k={rgwp_fit['k']:.3f}  delta={rgwp_fit['delta_proxy']['mean']:+.3f} {rgwp_fit['delta_proxy']['hdi']}")

    ctrl_age = control_regression(S, R, H, age_s)
    ctrl_rgwp = control_regression(S, R, H, rgwp_s)

    out = {"n": int(len(S)), "seed": SEED,
           "proxies": {"age_in_window": "t - first_observed_year(i), left-censored at 2014",
                       "log_reserve_to_gwp": "log(R / gross_premiums_written)"},
           "k_base": base, "k_plus_age": age_fit, "k_plus_log_r_gwp": rgwp_fit,
           "control_regression_absz": {"plus_age": ctrl_age, "plus_log_r_gwp": ctrl_rgwp}}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")
    print(f"  k: base {base['k']:.3f} | +age {age_fit['k']:.3f} | +log(R/GWP) {rgwp_fit['k']:.3f}")
    print(f"  |z| control: age coef {ctrl_age['coef_proxy']:+.3f} (t={ctrl_age['t_proxy']:+.2f}); "
          f"log(R/GWP) coef {ctrl_rgwp['coef_proxy']:+.3f} (t={ctrl_rgwp['t_proxy']:+.2f})")


if __name__ == "__main__":
    sys.exit(main())
