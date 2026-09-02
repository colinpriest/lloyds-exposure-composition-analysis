"""Check 2 (referee): currency / year-effect entanglement.

USD share trends 6%->43% and conversion uses the year-end rate, so the sterling
adjustment is itself time-correlated and could alias the reserve cycle m_t.

(a) Refit the directional-shock model (systemic M1: mu=m_t) on STERLING (converted) and on
    NOMINAL (as-reported) sizes; report m_t and tau_m both ways, and
    m_t^sterling - m_t^nominal against USD-share_t and the year-end rate_t.
(b) Add USD-share_t as a year-level covariate to the mean (mu_it = beta*usdshare_t + m_t) on
    the sterling data; report whether m_t stays credible and whether tau_m moves.

Writes check_currency_entanglement_results.json.
Usage:  python src/check_currency_entanglement.py
"""
import io, json, sys
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_currency_entanglement_results.json"
RITC = SD / "pdf_extraction" / "ritc_scan.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)   # sterling (converted)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    fxr = np.array([o.get("fx_rate_usd_per_gbp") or 1.0 for o in recs], float)
    usd = np.array([bool(o.get("fx_applied")) for o in recs])
    R_nom = np.where(usd, R * fxr, R)   # undo conversion -> as-reported
    key = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    return S, R, R_nom, H, yr, usd, key


def ritc_flag(key):
    r = json.load(io.open(RITC, encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([k in occ for k in key], float)


def fit_m1(S, R, H, yr, ritc, usd_share_year=None):
    years = np.sort(np.unique(yr)); yidx = np.searchsorted(years, yr); n_y = len(years)
    logR = np.log(R / REF); logH = np.log(H)
    with pm.Model():
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        gamma = pm.HalfNormal("gamma", 1.0)
        log_tot = pm.Normal("log_tot", np.log(0.05), 1.0); tot = pm.math.exp(log_tot)
        f = pm.Beta("f", 1.0, 1.0)
        su = pm.Deterministic("sd_undiv", tot * pm.math.sqrt(f))
        sd = pm.Deterministic("sd_div", tot * pm.math.sqrt(1.0 - f))
        tau_s = pm.HalfNormal("tau_s", 0.5)
        z_s = pm.Normal("z_s", 0.0, 1.0, shape=n_y); s_y = tau_s * z_s
        nu_clean = pm.Gamma("nu_clean", 2.0, 0.1)
        lam = pm.Normal("lambda_ritc", 0.0, 0.7)
        nu_obs = nu_clean * pm.math.exp(-lam * ritc)
        beta_ritc = pm.Normal("beta_ritc", 0.0, 0.5)
        var = su ** 2 + sd ** 2 * pm.math.exp(2.0 * (k - 1.0) * (logR - gamma * logH))
        sigma = pm.math.exp(s_y[yidx] + beta_ritc * ritc) * pm.math.sqrt(var)
        tau_m = pm.HalfNormal("tau_m", 0.05)
        z_m = pm.Normal("z_m", 0.0, 1.0, shape=n_y)
        m_y = pm.Deterministic("m_y", tau_m * z_m)
        mu = m_y[yidx]
        if usd_share_year is not None:
            beta_share = pm.Normal("beta_share", 0.0, 0.1)
            usd_c = usd_share_year - usd_share_year.mean()
            mu = mu + beta_share * usd_c[yidx]
        pm.StudentT("S_obs", nu=nu_obs, mu=mu, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    return idata, years


def summ(idata, years):
    p = idata.posterior
    tau_m = float(p["tau_m"].values.mean())
    my = p["m_y"].values.reshape(-1, len(years))
    m_t = {int(years[t]): float(my[:, t].mean()) for t in range(len(years))}
    extra = {}
    if "beta_share" in p:
        b = p["beta_share"].values.ravel()
        extra["beta_share"] = {"mean": float(b.mean()),
                               "hdi": [float(x) for x in az.hdi(b, hdi_prob=0.95)]}
    k = float(p["k"].values.mean()); g = float(p["gamma"].values.mean())
    su = float(p["sd_undiv"].values.mean())
    return {"tau_m": tau_m, "m_t": m_t, "k": k, "gamma": g, "sd_undiv": su, **extra}


def main():
    S, R_st, R_nom, H, yr, usd, key = load()
    ritc = ritc_flag(key)
    years = np.sort(np.unique(yr))
    usd_share = np.array([usd[yr == y].mean() for y in years])
    fxr_year = {}
    fx = json.load(io.open(SD / "model" / "fx_rates_h10.json", encoding="utf-8"))
    rate_year = np.array([fx["year_end_rates"][str(int(y))]["usd_per_gbp"] for y in years])
    print("USD share by year:", dict(zip([int(y) for y in years], np.round(usd_share, 2))))

    print("=== (a) sterling (converted) ===")
    ist, _ = fit_m1(S, R_st, H, yr, ritc)
    st = summ(ist, years)
    print(f"  tau_m={st['tau_m']:.4f}  k={st['k']:.3f}")
    print("=== (a) nominal (as-reported) ===")
    inom, _ = fit_m1(S, R_nom, H, yr, ritc)
    nom = summ(inom, years)
    print(f"  tau_m={nom['tau_m']:.4f}  k={nom['k']:.3f}")

    diff = np.array([st["m_t"][int(y)] - nom["m_t"][int(y)] for y in years])
    corr_share = float(np.corrcoef(diff, usd_share)[0, 1])
    corr_rate = float(np.corrcoef(diff, rate_year)[0, 1])

    print("=== (b) sterling + USD-share year covariate ===")
    icov, _ = fit_m1(S, R_st, H, yr, ritc, usd_share_year=usd_share)
    cov = summ(icov, years)
    print(f"  tau_m={cov['tau_m']:.4f}  beta_share={cov['beta_share']['mean']:+.4f} "
          f"{cov['beta_share']['hdi']}")

    out = {
        "usd_share_by_year": {int(y): float(s) for y, s in zip(years, usd_share)},
        "year_end_rate": {int(y): float(r) for y, r in zip(years, rate_year)},
        "a_sterling": st, "a_nominal": nom,
        "m_t_diff_sterling_minus_nominal": {int(y): float(diff[i]) for i, y in enumerate(years)},
        "corr_mt_diff_vs_usd_share": corr_share,
        "corr_mt_diff_vs_year_end_rate": corr_rate,
        "b_with_usd_share_covariate": cov,
        "seed": SEED,
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")
    print(f"  tau_m: sterling {st['tau_m']:.4f} | nominal {nom['tau_m']:.4f} | +USDshare cov {cov['tau_m']:.4f}")
    print(f"  corr(m_t^st - m_t^nom, USD-share) = {corr_share:+.3f}; vs year-end rate = {corr_rate:+.3f}")
    print(f"  beta_share = {cov['beta_share']['mean']:+.4f} {cov['beta_share']['hdi']} "
          f"({'excludes' if cov['beta_share']['hdi'][0]*cov['beta_share']['hdi'][1]>0 else 'includes'} 0)")


if __name__ == "__main__":
    sys.exit(main())
