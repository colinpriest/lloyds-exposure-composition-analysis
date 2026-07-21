"""Fast maximum-likelihood fit of the dispersion model (shared by the stress-test scripts).

Same structural form as calibrate_dispersion_ritc.py but fitted by L-BFGS instead of NUTS, so
it can be re-run thousands of times (proxy-error stress, adversarial concentration). No year
shock (dropped for speed / identifiability under perturbation). Recovers the Bayesian posterior
means closely on the unperturbed data.

  S ~ StudentT(nu_it, 0, sigma_it)
  sigma = sqrt( sd_undiv^2 + sd_div^2 * [ (R/ref)(1/H)^gamma ]^{2(k-1)} )
  nu_it = nu_clean            (clean)
        = nu_clean*exp(-lam)  (RITC)
"""
import numpy as np
from scipy import stats
from scipy.optimize import minimize

REF, HLO, HCE = 500.0, 0.01, 1.0


def _unpack(p):
    k = 0.5 + 0.5 / (1.0 + np.exp(-p[0]))
    gamma = np.exp(p[1]); su = np.exp(p[2]); sd = np.exp(p[3])
    nuc = np.exp(p[4]); lam = p[5]
    return k, gamma, su, sd, nuc, lam


def sigma(R, H, k, gamma, su, sd):
    reff = (np.maximum(R, 1e-9) / REF) * (1.0 / np.clip(H, HLO, HCE)) ** gamma
    return np.sqrt(su ** 2 + sd ** 2 * reff ** (2.0 * (k - 1.0)))


def _negll(p, S, R, H, ritc):
    k, gamma, su, sd, nuc, lam = _unpack(p)
    if not (np.isfinite(gamma) and su > 0 and sd > 0 and 1e-3 < nuc < 200):
        return 1e12
    sig = sigma(R, H, k, gamma, su, sd)
    nu = nuc * np.exp(-lam * ritc)
    ll = stats.t.logpdf(S, df=nu, loc=0.0, scale=sig)
    if not np.all(np.isfinite(ll)):
        return 1e12
    return -ll.sum()


def fit_mle(S, R, H, ritc, p0=None):
    """Returns dict with k, gamma, sd_undiv, sd_div, nu_clean, nu_ritc, lambda_ritc, success."""
    if p0 is None:
        p0 = np.array([0.5, np.log(0.3), np.log(0.022), np.log(0.06), np.log(2.4), 0.45])
    res = minimize(_negll, p0, args=(S, R, H, ritc), method="Nelder-Mead",
                   options={"maxiter": 4000, "xatol": 1e-6, "fatol": 1e-6})
    k, gamma, su, sd, nuc, lam = _unpack(res.x)
    return {"k": float(k), "gamma": float(gamma), "sd_undiv": float(su), "sd_div": float(sd),
            "nu_clean": float(nuc), "nu_ritc": float(nuc * np.exp(-lam)), "lambda_ritc": float(lam),
            "negll": float(res.fun), "success": bool(res.success)}


def deritc_z(z, ritc, nu_clean, nu_ritc):
    """Map RITC standardised residuals from the RITC tail to the clean tail (quantile transform)."""
    z = np.array(z, float, copy=True)
    m = ritc.astype(bool)
    if m.any():
        u = np.clip(stats.t.cdf(z[m], df=nu_ritc), 1e-12, 1 - 1e-12)
        z[m] = stats.t.ppf(u, df=nu_clean)
    return z


def transfer_var(S, R, H, ritc, tgt, mp, alpha, deritc=True):
    """VaR_alpha of donor severities transferred to target tgt=(Rq,Hq) under params mp."""
    Rq, Hq = tgt
    sig_i = sigma(R, H, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    sig_q = sigma(Rq, Hq, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    z = S / sig_i
    if deritc:
        z = deritc_z(z, ritc, mp["nu_clean"], mp["nu_ritc"])
    S_adj = z * sig_q
    return float(np.percentile(S_adj, 100.0 * alpha, method="linear"))


if __name__ == "__main__":
    import io, json
    from pathlib import Path
    SD = Path(__file__).resolve().parent.parent
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    rs = json.load(io.open(SD / "pdf_extraction" / "ritc_scan.json", encoding="utf-8"))
    occ = {k for k, v in rs.items() if v.get("ritc_occurred")}
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs]); R = np.array([o["opening_reserves_gbp_m"] for o in recs])
    H = np.clip(np.array([o["hhi"] for o in recs]), HLO, HCE)
    ritc = np.array([f"{o['syndicate']}_{o['year']}" in occ for o in recs], float)
    m = fit_mle(S, R, H, ritc)
    print("MLE baseline recovery (cf. Bayesian k=0.611 g=0.264 floor=0.022 nu_clean=2.40 nu_ritc=1.54):")
    print(f"  k={m['k']:.3f} gamma={m['gamma']:.3f} floor={m['sd_undiv']:.4f} sd_div={m['sd_div']:.4f} "
          f"nu_clean={m['nu_clean']:.2f} nu_ritc={m['nu_ritc']:.2f}  success={m['success']}")
    print(f"  V1 VaR99.5={transfer_var(S,R,H,ritc,(500.,0.17),m,0.995):.3f}  (cf 0.427)")
