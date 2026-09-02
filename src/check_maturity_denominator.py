"""Referee check: does the numerator/denominator maturity mismatch manufacture the size effect?

S = M/R has a MATURE numerator (u <= t-2) and a TOTAL-reserve denominator.  With
phi = R_mature / R_total (build_maturity_share.py),

    S = phi * (M / R_mature),

so a systematic relationship between phi and reserve size would put a mechanical size
gradient into S that the pooling exponent would absorb as diversification.

Three things are reported.

  (a) ASSOCIATION.  Spearman / Pearson correlation of phi with log R, for every run-off
      weighting delta.  If phi is unrelated to size there is no engine for the confound.

  (b) MATCHED REFIT.  Refit the headline two-regime model on a mature-matched reserve
      population:
        V2 "fully matched"  severity M/R_mat with size covariate R_mat = phi*R  (primary)
        V1 "severity only"  severity M/R_mat with size covariate R (secondary)
      A baseline refit on the SAME subsample with the original S isolates the denominator
      change from the change of sample.

  (c) STRATIFICATION.  Mean |z| under the headline scale by phi tercile, and a control
      regression |z| ~ log R + log phi, so the size coefficient is read with maturity held.

Writes check_maturity_denominator_results.json.
Usage:  python src/check_maturity_denominator.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

SD = Path(__file__).resolve().parent.parent
RESULTS = SD / "model" / "exposure_results.json"
RITC = SD / "pdf_extraction" / "ritc_scan.json"
MAT = SD / "model" / "maturity_share.json"
OUT = SD / "results" / "check_maturity_denominator_results.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42
PHI_MIN = 0.10                     # guard: S/phi explodes for a near-zero mature share


def load_sample():
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    key = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    return S, R, H, yr, key


def ritc_flag(key):
    r = json.load(io.open(RITC, encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([k in occ for k in key])


def fit(S, R, H, yidx, n_y, ritc, tag):
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
        pm.StudentT("S_obs", nu=nu_obs, mu=0.0, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    vn = ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "tau_s"]
    s = az.summary(idata, var_names=vn, hdi_prob=0.95)
    out = {v: {"mean": float(s.loc[v, "mean"]), "hdi_2.5": float(s.loc[v, "hdi_2.5%"]),
               "hdi_97.5": float(s.loc[v, "hdi_97.5%"])} for v in vn}
    out["_diag"] = {"max_rhat": float(s["r_hat"].max()),
                    "divergences": int(idata.sample_stats["diverging"].sum())}
    print(f"    {tag:34s} k={out['k']['mean']:.3f} "
          f"[{out['k']['hdi_2.5']:.3f},{out['k']['hdi_97.5']:.3f}]  "
          f"gamma={out['gamma']['mean']:.3f}  floor={out['sd_undiv']['mean']:.4f}  "
          f"div={out['_diag']['divergences']}")
    return out


def main():
    S, R, H, yr, key = load_sample()
    ritc_all = ritc_flag(key).astype(float)
    mat = json.load(io.open(MAT, encoding="utf-8"))["records"]

    tags = ["inf", "4", "2", "1"]
    have = np.array([k in mat for k in key])
    print(f"working sample n={len(S)}; matched to a usable triangle: {int(have.sum())} "
          f"({have.mean()*100:.1f}%)")

    phis = {t: np.array([mat[k][f"phi_delta_{t}"] if k in mat else np.nan for k in key])
            for t in tags}

    # ---------------- (a) association between maturity share and size ----------------
    assoc = {}
    logR = np.log(R)
    for t in tags:
        p = phis[t]
        ok = np.isfinite(p)
        sp = stats.spearmanr(p[ok], logR[ok])
        pe = stats.pearsonr(p[ok], np.log(R[ok]))
        # does maturity share predict dispersion directly?
        sp_abs = stats.spearmanr(p[ok], np.abs(S[ok]))
        assoc[t] = {
            "n": int(ok.sum()),
            "spearman_phi_vs_logR": {"rho": float(sp.statistic), "p": float(sp.pvalue)},
            "pearson_phi_vs_logR": {"r": float(pe[0]), "p": float(pe[1])},
            "spearman_phi_vs_absS": {"rho": float(sp_abs.statistic), "p": float(sp_abs.pvalue)},
            "phi_mean_by_size_tercile": None,
        }
        q = np.quantile(logR[ok], [1 / 3, 2 / 3])
        terc = np.digitize(logR[ok], q)
        assoc[t]["phi_mean_by_size_tercile"] = [float(p[ok][terc == i].mean()) for i in range(3)]
        print(f"  phi(delta={t:>3}) vs log R: Spearman {sp.statistic:+.3f} (p={sp.pvalue:.3f}); "
              f"tercile means {['%.3f' % v for v in assoc[t]['phi_mean_by_size_tercile']]}")

    # ---------------- (c) stratification on the headline scale ----------------
    cal = json.load(io.open(SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8"))
    k0, g0, su0, sd0 = cal["k"], cal["gamma"], cal["sd_undiv"], cal["sd_div"]
    reff = (R / REF) * (1.0 / H) ** g0
    sig0 = np.sqrt(su0 ** 2 + sd0 ** 2 * reff ** (2.0 * (k0 - 1.0)))
    z = S / sig0
    strat = {}
    for t in tags:
        p = phis[t]; ok = np.isfinite(p)
        q = np.quantile(p[ok], [1 / 3, 2 / 3])
        terc = np.digitize(p[ok], q)
        az_ = np.abs(z[ok])
        kw = stats.kruskal(*[az_[terc == i] for i in range(3)])
        X = np.column_stack([np.ones(ok.sum()), np.log(R[ok]), np.log(p[ok])])
        beta, *_ = np.linalg.lstsq(X, az_, rcond=None)
        resid = az_ - X @ beta
        dof = len(az_) - X.shape[1]
        cov = np.linalg.pinv(X.T @ X) * (resid @ resid) / dof
        se = np.sqrt(np.diag(cov))
        strat[t] = {
            "mean_abs_z_by_phi_tercile": [float(az_[terc == i].mean()) for i in range(3)],
            "kruskal": {"H": float(kw.statistic), "p": float(kw.pvalue)},
            "control_regression_abs_z": {
                "coef_logR": float(beta[1]), "t_logR": float(beta[1] / se[1]),
                "coef_logphi": float(beta[2]), "t_logphi": float(beta[2] / se[2])},
        }
        print(f"  |z| by phi tercile (delta={t:>3}): "
              f"{['%.3f' % v for v in strat[t]['mean_abs_z_by_phi_tercile']]}  "
              f"Kruskal p={kw.pvalue:.3f}; control coef_logR={beta[1]:+.3f} "
              f"(t={beta[1]/se[1]:+.2f}), coef_logphi={beta[2]:+.3f} (t={beta[2]/se[2]:+.2f})")

    # ---------------- (b) matched-denominator refits ----------------
    print("\nmatched-denominator refits (primary V2 = fully matched):")
    base_ok = np.isfinite(phis["2"]) & (phis["2"] >= PHI_MIN)
    for t in tags:
        base_ok &= np.isfinite(phis[t])
    sub = base_ok
    print(f"  refit subsample n={int(sub.sum())} "
          f"(dropped {int(have.sum() - sub.sum())} matched records with phi<{PHI_MIN})")
    years = np.sort(np.unique(yr[sub]))
    yidx = np.searchsorted(years, yr[sub]); n_y = len(years)
    fits = {}
    fits["baseline_same_subsample"] = fit(S[sub], R[sub], H[sub], yidx, n_y,
                                          ritc_all[sub], "baseline (original S, same n)")
    for t in tags:
        p = phis[t][sub]
        Smat = S[sub] / p
        Rmat = R[sub] * p
        fits[f"V2_fully_matched_delta_{t}"] = fit(
            Smat, Rmat, H[sub], yidx, n_y, ritc_all[sub],
            f"V2 fully matched (delta={t})")
    for t in ("inf", "2"):
        p = phis[t][sub]
        fits[f"V1_severity_only_delta_{t}"] = fit(
            S[sub] / p, R[sub], H[sub], yidx, n_y, ritc_all[sub],
            f"V1 severity only (delta={t})")

    res = {
        "n_working_sample": int(len(S)),
        "n_matched_to_triangle": int(have.sum()),
        "n_refit_subsample": int(sub.sum()),
        "phi_min_guard": PHI_MIN,
        "deltas": tags,
        "delta_meaning": ("phi(delta) = mature reserve share with unpaid weight "
                          "exp(-age/delta); delta=inf is the pure ultimate share"),
        "association_phi_vs_size": assoc,
        "stratification": strat,
        "refits": fits,
        "headline_reference": {"k": k0, "gamma": g0, "sd_undiv": su0, "sd_div": sd0},
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
