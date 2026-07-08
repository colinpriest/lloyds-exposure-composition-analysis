"""Out-of-sample held-out-syndicate validation vs naive pooling.

Does the composition dispersion model predict the severity of *unseen syndicates* better than
naively pooling the market? We use 5-fold cross-validation BY SYNDICATE (a whole syndicate's
years are held out together, so no syndicate leaks between train and test), and score the
held-out log pointwise predictive density (lppd) of two models fitted on the training fold:

  MODEL  S ~ t(nu, 0, sigma(R,H)),  sigma = sqrt(sd_undiv^2 + sd_div^2 [E/ref]^{2(k-1)}),
         E = R (1/H)^gamma           (size + concentration + undiversifiable floor)
  NAIVE  S ~ t(nu0, 0, sigma0)       (one market-wide dispersion; ignores size/concentration)

Both are robust (Student-t, mu=0); the year shock is dropped so the comparison isolates the
composition covariates. Report per-model held-out ELPD, the paired difference (MODEL - NAIVE)
with its standard error, and held-out tail calibration (nominal vs empirical exceedance).

Run: python oos_validation.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats
from scipy.special import logsumexp
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm

SD = Path(__file__).resolve().parent
OUT = SD / "oos_validation_results.json"
REF, HLO, HCE, SEED, K = 500.0, 0.01, 1.0, 42, 5


def load():
    d = json.load(io.open(SD / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    syn = np.array([o["syndicate"] for o in recs])
    return S, R, H, syn


def fit(S, R, H, kind):
    logR = np.log(R / REF); logH = np.log(H)
    with pm.Model():
        nu = pm.Gamma("nu", 2.0, 0.1)
        if kind == "model":
            theta = pm.Normal("theta", 0.0, 1.5)
            k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
            gamma = pm.HalfNormal("gamma", 1.0)
            log_tot = pm.Normal("log_tot", np.log(0.05), 1.0); tot = pm.math.exp(log_tot)
            f = pm.Beta("f", 1.0, 1.0)
            su = pm.Deterministic("sd_undiv", tot * pm.math.sqrt(f))
            sd = pm.Deterministic("sd_div", tot * pm.math.sqrt(1.0 - f))
            var = su ** 2 + sd ** 2 * pm.math.exp(2.0 * (k - 1.0) * (logR - gamma * logH))
            sigma = pm.math.sqrt(var)
        else:
            log_s0 = pm.Normal("log_s0", np.log(0.08), 1.0)
            sigma = pm.Deterministic("sigma0", pm.math.exp(log_s0))
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=sigma, observed=S)
        idata = pm.sample(1000, tune=1000, chains=4, cores=1, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    out = {v: p[v].values.ravel() for v in p.data_vars if v in
           ("nu", "k", "gamma", "sd_undiv", "sd_div", "sigma0")}
    return out


def sigma_draws(R, H, dr):
    reff = (np.maximum(R, 1e-9) / REF)[:, None] * (1.0 / np.clip(H, HLO, HCE))[:, None] ** dr["gamma"][None, :]
    return np.sqrt(dr["sd_undiv"][None, :] ** 2 + dr["sd_div"][None, :] ** 2 * reff ** (2.0 * (dr["k"][None, :] - 1.0)))


def held_out_lppd(S_t, R_t, H_t, dr, kind, thin=800):
    idx = np.linspace(0, len(dr["nu"]) - 1, min(thin, len(dr["nu"]))).astype(int)
    nu = dr["nu"][idx]
    sig = sigma_draws(R_t, H_t, {k: v[idx] for k, v in dr.items()}) if kind == "model" \
        else np.broadcast_to(dr["sigma0"][idx][None, :], (len(S_t), len(idx)))
    lp = stats.t.logpdf(S_t[:, None], df=nu[None, :], scale=sig)          # (Ntest, D)
    return logsumexp(lp, axis=1) - np.log(lp.shape[1])                    # per-obs elpd


def main():
    S, R, H, syn = load()
    uniq = np.array(sorted(set(syn)))
    fold_of = {s: i % K for i, s in enumerate(uniq)}          # deterministic syndicate->fold
    fold = np.array([fold_of[s] for s in syn])
    print(f"n={len(S)} syndicates={len(uniq)} folds={K}")

    elpd_m = np.full(len(S), np.nan); elpd_n = np.full(len(S), np.nan)
    covered = {q: 0 for q in (0.90, 0.95, 0.99)}; ntest_total = 0
    for f in range(K):
        te = fold == f; tr = ~te
        print(f"  fold {f}: train {tr.sum()} / test {te.sum()} ({te.sum()} obs, "
              f"{len(set(syn[te]))} held-out syndicates)")
        dm = fit(S[tr], R[tr], H[tr], "model")
        dn = fit(S[tr], R[tr], H[tr], "naive")
        elpd_m[te] = held_out_lppd(S[te], R[te], H[te], dm, "model")
        elpd_n[te] = held_out_lppd(S[te], R[te], H[te], dn, "naive")
        # tail calibration under MODEL posterior-mean predictive
        sig_mean = sigma_draws(R[te], H[te], dm).mean(axis=1); nu_mean = dm["nu"].mean()
        for q in covered:
            hi = stats.t.ppf(0.5 + q / 2, df=nu_mean, scale=sig_mean)
            covered[q] += int(np.sum(np.abs(S[te]) <= hi))
        ntest_total += te.sum()

    diff = elpd_m - elpd_n
    ELPD_m, ELPD_n = float(np.nansum(elpd_m)), float(np.nansum(elpd_n))
    dELPD = float(np.nansum(diff)); se = float(np.sqrt(len(diff)) * np.nanstd(diff))
    res = {
        "n": int(len(S)), "n_syndicates": int(len(uniq)), "folds": K, "seed": SEED,
        "held_out_ELPD_model": ELPD_m, "held_out_ELPD_naive": ELPD_n,
        "delta_ELPD_model_minus_naive": dELPD, "delta_SE": se, "z": dELPD / se if se else None,
        "per_obs": {"model": ELPD_m / len(S), "naive": ELPD_n / len(S), "delta": dELPD / len(S),
                    "pct_obs_model_better": float(np.mean(diff > 0) * 100)},
        "tail_calibration": {f"{int(q*100)}%": {"nominal": q, "empirical": covered[q] / ntest_total}
                             for q in covered},
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"held-out ELPD  model = {ELPD_m:8.2f}   naive = {ELPD_n:8.2f}")
    print(f"Delta ELPD (model - naive) = {dELPD:+.2f}   SE = {se:.2f}   z = {dELPD/se:+.2f}")
    print(f"per-obs delta = {dELPD/len(S):+.4f}   model better on {res['per_obs']['pct_obs_model_better']:.0f}% of held-out obs")
    print("tail calibration (held-out, MODEL):")
    for q, v in res["tail_calibration"].items():
        print(f"  {q} interval: nominal {v['nominal']:.3f}  empirical coverage {v['empirical']:.3f}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
