"""OOS #5: size-only-with-floor model held-out ELPD (third row for the out-of-sample table).

Same 5-fold-by-syndicate scheme, seed and held-out lppd as oos_validation.py, but the model
drops the concentration channel:  sigma = sqrt(sd_undiv^2 + sd_div^2 (R/ref)^{2(k-1)})  (no gamma,
no HHI). Compare its held-out ELPD with the full composition model (598.66) and the naive
market pool (530.71) to see whether concentration adds out-of-sample predictive value.

Run: python src/oos_size_only.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats
from scipy.special import logsumexp
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm

SD = Path(__file__).resolve().parent.parent
REF, HLO, HCE, SEED, K = 500.0, 0.01, 1.0, 42, 5


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs]); R = np.array([o["opening_reserves_gbp_m"] for o in recs])
    syn = np.array([o["syndicate"] for o in recs])
    return S, R, syn


def fit(S, R):
    logR = np.log(R / REF)
    with pm.Model():
        nu = pm.Gamma("nu", 2.0, 0.1)
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        log_tot = pm.Normal("log_tot", np.log(0.05), 1.0); tot = pm.math.exp(log_tot)
        f = pm.Beta("f", 1.0, 1.0)
        su = pm.Deterministic("sd_undiv", tot * pm.math.sqrt(f))
        sd = pm.Deterministic("sd_div", tot * pm.math.sqrt(1.0 - f))
        var = su ** 2 + sd ** 2 * pm.math.exp(2.0 * (k - 1.0) * logR)   # size only, no gamma/HHI
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=pm.math.sqrt(var), observed=S)
        idata = pm.sample(1000, tune=1000, chains=4, cores=1, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    return {v: p[v].values.ravel() for v in ("nu", "k", "sd_undiv", "sd_div")}


def sigma_draws(R, dr):
    reff = (np.maximum(R, 1e-9) / REF)[:, None] ** 1.0
    return np.sqrt(dr["sd_undiv"][None, :] ** 2 + dr["sd_div"][None, :] ** 2 *
                   (np.maximum(R, 1e-9) / REF)[:, None] ** (2.0 * (dr["k"][None, :] - 1.0)))


def lppd(S_t, R_t, dr, thin=800):
    idx = np.linspace(0, len(dr["nu"]) - 1, min(thin, len(dr["nu"]))).astype(int)
    sig = sigma_draws(R_t, {k: v[idx] for k, v in dr.items()})
    lp = stats.t.logpdf(S_t[:, None], df=dr["nu"][idx][None, :], scale=sig)
    return logsumexp(lp, axis=1) - np.log(lp.shape[1])


def main():
    S, R, syn = load()
    uniq = np.array(sorted(set(syn))); fold = np.array([{s: i % K for i, s in enumerate(uniq)}[s] for s in syn])
    elpd = np.full(len(S), np.nan)
    for f in range(K):
        te = fold == f
        print(f"  fold {f}: train {(~te).sum()} / test {te.sum()}")
        dr = fit(S[~te], R[~te]); elpd[te] = lppd(S[te], R[te], dr)
    E = float(np.nansum(elpd))
    out = {"model": "size_only_with_floor", "held_out_ELPD": E, "per_obs": E / len(S),
           "vs_full_598.66": E - 598.66, "vs_naive_530.71": E - 530.71}
    (SD / "results" / "oos_size_only_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nsize-only held-out ELPD = {E:.2f}  (full 598.66, naive 530.71)")
    print(f"  vs full = {E-598.66:+.2f}   vs naive = {E-530.71:+.2f}")
    print(f"Wrote oos_size_only_results.json")


if __name__ == "__main__":
    main()
