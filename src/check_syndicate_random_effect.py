"""Does a persistent syndicate intercept change the scale fit, or the transfer?

The paper bounds persistent syndicate heterogeneity indirectly (about 8% of
sufficiently observed syndicates carry a credibly non-zero mean) and shows that
de-meaned lag-1 correlation is null.  But de-meaning removes exactly the intercept
whose relevance is at issue, so it cannot show that persistent heterogeneity is
immaterial to the SCALE fit.  The direct test is to put the intercept in the model:

    S_it = alpha_i + sigma_it * eps_it,      alpha_i ~ Normal(0, tau_alpha^2)

fitted with partial pooling (non-centred), alongside the adopted mu=0 model on the
same data.  We then ask whether k, the floor, gamma and the tail move.

Two further quantities matter for the operator.  First, tau_alpha itself: how large
is persistent reserving bias relative to the dispersion scale?  Second, the
consequence for transfer.  Equation (7) rescales the RAW severity, so for a donor
with intercept alpha_i the transferred value is lambda*alpha_i + lambda*sigma*eps:
the donor's own bias is carried across, scaled, rather than removed.  We therefore
also report what the shrunken alpha_hat_i imply for the donor pool, and what
subtracting them would do to the Vignette 1 tail.

Writes check_syndicate_random_effect_results.json.
Usage:  python check_syndicate_random_effect.py
"""
import io, json
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

SD = Path(__file__).resolve().parent.parent
RESULTS = SD / "model" / "exposure_results.json"
RITC = SD / "pdf_extraction" / "ritc_scan.json"
OUT = SD / "results" / "check_syndicate_random_effect_results.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42


def load_sample():
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    syn = np.array([o["syndicate"] for o in recs])
    key = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    return S, R, H, yr, syn, key


def ritc_flag(key):
    r = json.load(io.open(RITC, encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([k in occ for k in key])


def fit(S, R, H, yidx, n_y, ritc, sidx, n_s, random_intercept, tag):
    logR = np.log(R / REF); logH = np.log(H)
    with pm.Model():
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        gamma = pm.HalfNormal("gamma", 1.0)
        log_tot = pm.Normal("log_tot", np.log(0.05), 1.0)
        tot = pm.math.exp(log_tot)
        f = pm.Beta("f", 1.0, 1.0)
        su = pm.Deterministic("sd_undiv", tot * pm.math.sqrt(f))
        sd = pm.Deterministic("sd_div", tot * pm.math.sqrt(1.0 - f))
        tau_s = pm.HalfNormal("tau_s", 0.5)
        z_s = pm.Normal("z_s", 0.0, 1.0, shape=n_y)
        nu_clean = pm.Gamma("nu_clean", 2.0, 0.1)
        lam = pm.Normal("lambda_ritc", 0.0, 0.7)
        pm.Deterministic("nu_ritc", nu_clean * pm.math.exp(-lam))
        nu_obs = nu_clean * pm.math.exp(-lam * ritc)
        beta_ritc = pm.Normal("beta_ritc", 0.0, 0.5)
        var = su ** 2 + sd ** 2 * pm.math.exp(2.0 * (k - 1.0) * (logR - gamma * logH))
        sigma = pm.math.exp((tau_s * z_s)[yidx] + beta_ritc * ritc) * pm.math.sqrt(var)
        if random_intercept:
            tau_a = pm.HalfNormal("tau_alpha", 0.05)
            z_a = pm.Normal("z_alpha", 0.0, 1.0, shape=n_s)
            alpha = pm.Deterministic("alpha", tau_a * z_a)
            mu = alpha[sidx]
        else:
            mu = 0.0
        pm.StudentT("S_obs", nu=nu_obs, mu=mu, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    vn = ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "tau_s"]
    if random_intercept:
        vn.append("tau_alpha")
    s = az.summary(idata, var_names=vn, hdi_prob=0.95)
    out = {v: {"mean": float(s.loc[v, "mean"]), "hdi_2.5": float(s.loc[v, "hdi_2.5%"]),
               "hdi_97.5": float(s.loc[v, "hdi_97.5%"])} for v in vn}
    out["_diag"] = {"max_rhat": float(s["r_hat"].max()),
                    "divergences": int(idata.sample_stats["diverging"].sum())}
    if random_intercept:
        a = idata.posterior["alpha"].values.reshape(-1, n_s)
        out["_alpha_mean"] = a.mean(axis=0).tolist()
    print(f"  {tag:32s} k={out['k']['mean']:.3f} "
          f"[{out['k']['hdi_2.5']:.3f},{out['k']['hdi_97.5']:.3f}]  "
          f"gamma={out['gamma']['mean']:.3f}  floor={out['sd_undiv']['mean']:.4f}  "
          f"nu={out['nu_clean']['mean']:.2f}  div={out['_diag']['divergences']}")
    return out


def main():
    S, R, H, yr, syn, key = load_sample()
    ritc = ritc_flag(key).astype(float)
    years = np.sort(np.unique(yr)); yidx = np.searchsorted(years, yr)
    sids = np.sort(np.unique(syn)); sidx = np.searchsorted(sids, syn)
    print(f"n={len(S)}  syndicates={len(sids)}  years={len(years)}")

    res = {"n": int(len(S)), "n_syndicates": int(len(sids)), "seed": SEED,
           "model": "S_it = alpha_i + sigma_it eps_it, alpha_i ~ N(0, tau_alpha^2)",
           "fits": {}}
    print("\nfits:")
    res["fits"]["mu0_adopted"] = fit(S, R, H, yidx, len(years), ritc, sidx, len(sids),
                                     False, "mu = 0 (adopted)")
    ri = fit(S, R, H, yidx, len(years), ritc, sidx, len(sids), True,
             "syndicate random intercept")
    alpha = np.array(ri.pop("_alpha_mean"))
    res["fits"]["random_intercept"] = ri

    ta = ri["tau_alpha"]
    ref_scale = res["fits"]["mu0_adopted"]["sd_div"]["mean"]
    res["tau_alpha_vs_scale"] = {
        "tau_alpha": ta["mean"], "tau_alpha_hdi": [ta["hdi_2.5"], ta["hdi_97.5"]],
        "sd_div_at_reference": ref_scale,
        "ratio_tau_alpha_over_sd_div": ta["mean"] / ref_scale}
    res["shrunken_alpha"] = {
        "mean_abs": float(np.abs(alpha).mean()),
        "max_abs": float(np.abs(alpha).max()),
        "p90_abs": float(np.percentile(np.abs(alpha), 90)),
        "n_abs_gt_0.02": int((np.abs(alpha) > 0.02).sum()),
        "note": ("partial-pooled posterior-mean intercepts; Equation (7) rescales raw "
                 "S so these transfer, scaled by the size ratio, rather than cancel")}
    print(f"\ntau_alpha = {ta['mean']:.4f} [{ta['hdi_2.5']:.4f}, {ta['hdi_97.5']:.4f}]"
          f"   vs sd_div {ref_scale:.4f}  -> ratio {ta['mean']/ref_scale:.2f}")
    print(f"shrunken |alpha|: mean {np.abs(alpha).mean():.4f}, p90 "
          f"{np.percentile(np.abs(alpha),90):.4f}, max {np.abs(alpha).max():.4f}; "
          f"{int((np.abs(alpha)>0.02).sum())} syndicates with |alpha|>0.02")

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
