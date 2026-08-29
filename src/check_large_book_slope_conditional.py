"""The large-book slope as a CONDITIONAL derivative, compared draw-by-draw.

check_large_book_slope_bayes.py regressed log|S| on log R with only a syndicate
intercept. That estimates a *marginal* large-book association: it does not hold
concentration, reporting year or the RITC regime fixed, so it is not the conditional
derivative d log sigma / d log R that the principal scale model implies, and
comparing it to k-1 was tighter than the fitted models warrant.

This refits it with the controls the scale model actually uses:

    log|S_it| = a + b logR_it + c logH_it + d 1[RITC] + year_t + alpha_i + eps_it
    alpha_i ~ N(0, tau_alpha^2),  year_t ~ N(0, tau_year^2),  eps ~ StudentT(nu)

so b is the partial slope with concentration, regime and period held. Both the
marginal and conditional versions are reported, because the gap between them is
itself informative about how entangled size is with the other covariates.

The comparison with the floorless law is also made properly Bayesian. The previous
version tested against a FIXED -0.342, ignoring that k in the no-floor model has its
own posterior. Here the no-floor scale model is refit on the full sample, its k draws
retained, and the two posteriors compared draw by draw:

    P(b < k_nofloor - 1)      is the large-book decline steeper than the floorless law?
    P(b > (k_nofloor - 1)/2)  is it at most half that rate, i.e. materially flattened?

Writes check_large_book_slope_conditional_results.json.
Usage:  python check_large_book_slope_conditional.py
"""
import io, json
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from oos_validation import load, REF, HLO, HCE, SEED

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_large_book_slope_conditional_results.json"
RITC = SD / "pdf_extraction" / "ritc_scan.json"
RESULTS = SD / "model" / "exposure_results.json"
ZERO = 1e-6
THRESHOLDS = [("above_500m", 500.0), ("above_1bn", 1000.0), ("above_2bn", 2000.0)]


def meta():
    """year and RITC flag aligned to the oos_validation sample."""
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    yr = np.array([o["year"] for o in recs])
    key = [f"{o['syndicate']}_{o['year']}" for o in recs]
    r = json.load(io.open(RITC, encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return yr, np.array([k in occ for k in key], float)


def fit_nofloor_k(S, R, H):
    """Full-sample no-floor scale model; keep the k draws."""
    logR = np.log(R / REF); logH = np.log(np.clip(H, HLO, HCE))
    with pm.Model():
        nu = pm.Gamma("nu", 2.0, 0.1)
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        gamma = pm.HalfNormal("gamma", 1.0)
        log_tot = pm.Normal("log_tot", np.log(0.05), 1.0)
        sd = pm.math.exp(log_tot)
        var = sd ** 2 * pm.math.exp(2.0 * (k - 1.0) * (logR - gamma * logH))
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=pm.math.sqrt(var), observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    return idata.posterior["k"].values.ravel()


def fit_slope(logR, logH, ritc, yidx, n_y, sidx, n_s, logA, conditional):
    with pm.Model():
        a = pm.Normal("a", 0.0, 5.0)
        b = pm.Normal("b", 0.0, 1.0)
        tau_a = pm.HalfNormal("tau_alpha", 1.0)
        z_a = pm.Normal("z_alpha", 0.0, 1.0, shape=n_s)
        mu = a + b * logR + (tau_a * z_a)[sidx]
        if conditional:
            c = pm.Normal("c", 0.0, 1.0)
            d = pm.Normal("d", 0.0, 1.0)
            tau_y = pm.HalfNormal("tau_year", 1.0)
            z_y = pm.Normal("z_year", 0.0, 1.0, shape=n_y)
            mu = mu + c * logH + d * ritc + (tau_y * z_y)[yidx]
        sigma = pm.HalfNormal("sigma", 2.0)
        nu = pm.Gamma("nu", 2.0, 0.1)
        pm.StudentT("y", nu=nu, mu=mu, sigma=sigma, observed=logA)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    return idata


def summarise(idata, kdraws, conditional):
    b = idata.posterior["b"].values.ravel()
    vn = ["b", "tau_alpha", "sigma", "nu"] + (["c", "d", "tau_year"] if conditional else [])
    s = az.summary(idata, var_names=vn, hdi_prob=0.95)
    # draw-by-draw against the no-floor law's own posterior slope k-1
    n = min(len(b), len(kdraws))
    rng = np.random.default_rng(SEED)
    bb = rng.choice(b, n, replace=False)
    kk = rng.choice(kdraws, n, replace=False) - 1.0
    rec = {"b_mean": float(b.mean()),
           "b_hdi_2.5": float(s.loc["b", "hdi_2.5%"]),
           "b_hdi_97.5": float(s.loc["b", "hdi_97.5%"]),
           "P_b_lt_0": float((b < 0).mean()),
           "P_b_steeper_than_nofloor": float((bb < kk).mean()),
           "P_b_at_most_half_nofloor": float((bb > kk / 2).mean()),
           "tau_alpha_mean": float(s.loc["tau_alpha", "mean"]),
           "nu_mean": float(s.loc["nu", "mean"]),
           "max_rhat": float(s["r_hat"].max()),
           "divergences": int(idata.sample_stats["diverging"].sum())}
    if conditional:
        rec["c_logH_mean"] = float(s.loc["c", "mean"])
        rec["d_ritc_mean"] = float(s.loc["d", "mean"])
        rec["tau_year_mean"] = float(s.loc["tau_year", "mean"])
    return rec


def main():
    S, R, H, syn = load()
    yr, ritc_all = meta()
    assert len(yr) == len(S)
    print("fitting the no-floor scale model for its k posterior ...")
    kdraws = fit_nofloor_k(S, R, H)
    print(f"  k_nofloor = {kdraws.mean():.3f}  ->  implied slope "
          f"{kdraws.mean()-1:.3f}  (95% [{np.percentile(kdraws-1,2.5):.3f}, "
          f"{np.percentile(kdraws-1,97.5):.3f}])")

    res = {"seed": SEED,
           "k_nofloor_mean": float(kdraws.mean()),
           "nofloor_slope_mean": float(kdraws.mean() - 1.0),
           "nofloor_slope_hdi": [float(np.percentile(kdraws - 1, 2.5)),
                                 float(np.percentile(kdraws - 1, 97.5))],
           "note": ("marginal = size only with a syndicate intercept; conditional "
                    "adds log H, the RITC indicator and a reporting-year effect, so b "
                    "is the partial slope the scale model implies. Comparisons with "
                    "the floorless law are draw-by-draw against its own k posterior."),
           "thresholds": {}}

    for name, T in THRESHOLDS:
        m = (R >= T) & (np.abs(S) > ZERO)
        lr = np.log(R[m]); lh = np.log(np.clip(H[m], HLO, HCE))
        la = np.log(np.abs(S[m])); rc = ritc_all[m]
        ids = np.sort(np.unique(syn[m])); sidx = np.searchsorted(ids, syn[m])
        yrs = np.sort(np.unique(yr[m])); yidx = np.searchsorted(yrs, yr[m])
        print(f"\n{name}: n={m.sum()} obs, {len(ids)} syndicates, {len(yrs)} years")
        out = {"n": int(m.sum()), "n_syndicates": int(len(ids))}
        for tag, cond in (("marginal", False), ("conditional", True)):
            idata = fit_slope(lr, lh, rc, yidx, len(yrs), sidx, len(ids), la, cond)
            rec = summarise(idata, kdraws, cond)
            out[tag] = rec
            print(f"   {tag:12s} b = {rec['b_mean']:+.3f} "
                  f"[{rec['b_hdi_2.5']:+.3f}, {rec['b_hdi_97.5']:+.3f}]   "
                  f"P(b<0)={rec['P_b_lt_0']:.3f}   "
                  f"P(steeper than no-floor)={rec['P_b_steeper_than_nofloor']:.3f}   "
                  f"P(<=half)={rec['P_b_at_most_half_nofloor']:.3f}   "
                  f"div={rec['divergences']}")
        res["thresholds"][name] = out

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
