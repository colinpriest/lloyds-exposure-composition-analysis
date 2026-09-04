"""Referee check: selection weighting and a worst-case bound for the 24% of filings not observed.

missingness_check.py shows (i) extraction failure IS size-biased and (ii) among syndicates
observed at least once, a failure-prone indicator adds nothing to dispersion given size.
Test (ii) cannot establish missing-at-random, and says nothing at all about the orphan
syndicates that are never observed.  Two sensitivity analyses are added here.

  A. SELECTION WEIGHTING (IPW).  Fit a response propensity
        logit P(extraction succeeds) ~ log R + reporting year
     over filings whose syndicate has at least one successful year (so a size proxy
     exists), then refit the headline dispersion model weighting each observation by
     1/p_hat, which up-weights the under-represented small syndicates.  If the structural
     parameters are unmoved, the size bias documented in missingness_check.py does not
     propagate into the fitted scale.

  B. WORST-CASE ORPHAN BOUND.  The orphan filings are never observed, so no test can
     recover them; instead we ask how extreme they would have to be to matter.  Pseudo-
     observations are appended at small sizes, with severity set to equally spaced
     quantiles of the fitted Student-t inflated by a factor c, and the model refit for
     c = 1, 1.5, 2, 3, 5.  We report the c at which each headline conclusion would flip.
     Deterministic quantile placement (not random draws) keeps this reproducible.

Writes check_missingness_sensitivity_results.json.
Usage:  python src/check_missingness_sensitivity.py
"""
import io, json, glob
from pathlib import Path
import numpy as np
from scipy import stats
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
from adopted_model import scale_block
import arviz as az

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_missingness_sensitivity_results.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42
C_GRID = [1.0, 1.5, 2.0, 3.0, 5.0]


def load_sample():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    key = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    syn = np.array([o["syndicate"] for o in recs])
    return S, R, H, yr, key, syn


def ritc_flag(key):
    r = json.load(io.open(SD / "pdf_extraction" / "ritc_scan.json", encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([k in occ for k in key])


def scan_filings():
    """(syndicate, year, reserves_gbp_m or None) for every retrieved filing."""
    cs = json.load(io.open(SD / "pdf_extraction" / "currency_scan.json", encoding="utf-8"))
    fx = json.load(io.open(SD / "model" / "fx_rates_h10.json", encoding="utf-8"))
    cur = {k: v["currency"] for k, v in cs["reports"].items()}
    rates = {int(y): r["usd_per_gbp"] for y, r in fx["year_end_rates"].items()}
    rows = []
    for f in glob.glob(str(SD / "pdf_extraction" / "syndicate_*_*.json")):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
            md = d.get("models", {})
            res = None
            for mk in ("gemini-2.5-flash", "gpt-5-mini"):
                v = md.get(mk, {}).get("opening_reserves_gbp_m")
                if v is not None and v > 0:
                    res = float(v); break
            base = f.split("syndicate_")[1].replace(".json", "")
            s, y = base.rsplit("_", 1)
            if res is not None and cur.get(base) == "USD":
                res = res / rates[int(y)]
            rows.append((int(s), int(y), res))
        except Exception:
            pass
    return rows


def fit(S, R, H, yidx, n_y, ritc, tag, w=None):
    """The adopted model (scale_block); the only departure is an optional
    observation weight on the likelihood."""
    logR = np.log(R / REF); logH = np.log(H)
    with pm.Model():
        b = scale_block(ritc=ritc, logR=logR, logH=logH, yidx=yidx, n_y=n_y)
        nu_obs, sigma = b["nu_obs"], b["sigma"]
        dist = pm.StudentT.dist(nu=nu_obs, mu=0.0, sigma=sigma)
        if w is None:
            pm.StudentT("S_obs", nu=nu_obs, mu=0.0, sigma=sigma, observed=S)
        else:
            pm.Potential("S_obs_w", (pm.logp(dist, S) * w).sum())
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    vn = ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "tau_s"]
    s = az.summary(idata, var_names=vn, hdi_prob=0.95)
    kf = idata.posterior["k"].values.ravel()
    out = {v: {"mean": float(s.loc[v, "mean"]), "hdi_2.5": float(s.loc[v, "hdi_2.5%"]),
               "hdi_97.5": float(s.loc[v, "hdi_97.5%"])} for v in vn}
    # (a P_k_lt_1 key computed at 0.999 was removed here: under the bracketed
    # transform P(k<1) is identically 1 by construction, and a proximity value
    # wearing the endpoint label reads as evidence it is not)
    out["_diag"] = {"max_rhat": float(s["r_hat"].max()),
                    "divergences": int(idata.sample_stats["diverging"].sum())}
    print(f"    {tag:32s} k={out['k']['mean']:.3f} "
          f"[{out['k']['hdi_2.5']:.3f},{out['k']['hdi_97.5']:.3f}]  "
          f"gamma={out['gamma']['mean']:.3f}  floor={out['sd_undiv']['mean']:.4f}  "
          f"nu={out['nu_clean']['mean']:.2f}  div={out['_diag']['divergences']}")
    return out


def main():
    S, R, H, yr, key, syn = load_sample()
    ritc = ritc_flag(key).astype(float)
    years = np.sort(np.unique(yr)); yidx = np.searchsorted(years, yr); n_y = len(years)

    rows = scan_filings()
    ok_syn = {s for s, y, r in rows if r is not None}
    orphan_rows = [(s, y) for s, y, r in rows if r is None and s not in ok_syn]
    orphan_syn = sorted({s for s, y in orphan_rows})
    print(f"filings={len(rows)}  failed={sum(1 for _,_,r in rows if r is None)}  "
          f"orphan filings={len(orphan_rows)}  distinct orphan syndicates={len(orphan_syn)}")

    # ---------------- A. selection weighting ----------------
    syn_size = {}
    for s, y, r in rows:
        if r is not None:
            syn_size.setdefault(s, []).append(r)
    syn_med = {s: float(np.median(v)) for s, v in syn_size.items()}
    Xr, Xy, Yv = [], [], []
    for s, y, r in rows:
        if s in syn_med:
            Xr.append(np.log(syn_med[s])); Xy.append(y); Yv.append(1 if r is not None else 0)
    Xr = np.array(Xr); Xy = np.array(Xy); Yv = np.array(Yv)
    yrs = np.sort(np.unique(Xy))
    D = np.column_stack([np.ones(len(Xr)), Xr] +
                        [(Xy == u).astype(float) for u in yrs[1:]])
    beta = np.zeros(D.shape[1])
    for _ in range(60):                                   # Newton-Raphson logistic
        p = 1.0 / (1.0 + np.exp(-D @ beta))
        Wd = p * (1 - p) + 1e-9
        beta += np.linalg.pinv((D * Wd[:, None]).T @ D) @ (D.T @ (Yv - p))
    Dw = np.column_stack([np.ones(len(S)), np.log([syn_med.get(s, np.median(R)) for s in syn])] +
                         [(yr == u).astype(float) for u in yrs[1:]])
    phat = 1.0 / (1.0 + np.exp(-Dw @ beta))
    w = 1.0 / np.clip(phat, 0.15, 1.0)
    w = w / w.mean() * 1.0                                # mean-1 weights: n is preserved
    print(f"  propensity: coef(log R) = {beta[1]:+.3f}; "
          f"p_hat range [{phat.min():.3f},{phat.max():.3f}]; "
          f"weight range [{w.min():.2f},{w.max():.2f}]")

    print("\nrefits:")
    res = {"n": int(len(S)),
           "n_filings": len(rows),
           "n_failed": int(sum(1 for _, _, r in rows if r is None)),
           "n_orphan_filings": len(orphan_rows),
           "n_orphan_syndicates": len(orphan_syn),
           "seed": SEED,
           "propensity_model": {"coef_logR": float(beta[1]),
                                "p_hat_min": float(phat.min()),
                                "p_hat_max": float(phat.max()),
                                "weight_min": float(w.min()),
                                "weight_max": float(w.max())},
           "fits": {}}
    res["fits"]["unweighted"] = fit(S, R, H, yidx, n_y, ritc, "unweighted [headline]")
    res["fits"]["ipw_selection_weighted"] = fit(S, R, H, yidx, n_y, ritc,
                                                "IPW selection-weighted", w=w)

    # ---------------- B. worst-case orphan bound ----------------
    cal = json.load(io.open(SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8"))
    k0, g0, su0, sd0, nu0 = cal["k"], cal["gamma"], cal["sd_undiv"], cal["sd_div"], cal["nu_clean"]
    fail_syn = sorted({s for s, y, r in rows if r is None and s in syn_med})
    fail_sizes = np.array([syn_med[s] for s in fail_syn])
    m = len(orphan_rows)
    q = (np.arange(m) + 0.5) / m
    R_orph = np.quantile(fail_sizes, np.linspace(0.05, 0.95, m))
    H_orph = np.full(m, float(np.median(H)))
    yr_orph = np.array([y for _, y in orphan_rows])
    reff = (R_orph / REF) * (1.0 / H_orph) ** g0
    sig_orph = np.sqrt(su0 ** 2 + sd0 ** 2 * reff ** (2.0 * (k0 - 1.0)))
    base_t = stats.t.ppf(q, df=nu0)
    print(f"\n  worst-case orphans: m={m} pseudo-records, sizes "
          f"{R_orph.min():.0f}m-{R_orph.max():.0f}m (median {np.median(R_orph):.0f}m)")
    res["worst_case"] = {
        "n_pseudo": m,
        "orphan_size_grid_m": {"min": float(R_orph.min()), "max": float(R_orph.max()),
                               "median": float(np.median(R_orph))},
        "placement": "equally spaced Student-t quantiles scaled by c*sigma(R,H); deterministic",
        "by_c": {}}
    for c in C_GRID:
        S_aug = np.concatenate([S, c * sig_orph * base_t])
        R_aug = np.concatenate([R, R_orph]); H_aug = np.concatenate([H, H_orph])
        yr_aug = np.concatenate([yr, yr_orph])
        ritc_aug = np.concatenate([ritc, np.zeros(m)])
        ya = np.sort(np.unique(yr_aug)); yia = np.searchsorted(ya, yr_aug)
        res["worst_case"]["by_c"][str(c)] = fit(S_aug, R_aug, H_aug, yia, len(ya),
                                                ritc_aug, f"orphans inflated x{c}")

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
