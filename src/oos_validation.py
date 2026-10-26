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

Run: python src/oos_validation.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats
from scipy.special import logsumexp
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
from adopted_model import SAMPLE_CORES

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "oos_validation_results.json"
REF, HLO, HCE, SEED, K = 500.0, 0.01, 1.0, 42, 5


def load():
    with io.open(SD / "model" / "exposure_results.json", encoding="utf-8") as _fh:
        d = json.load(_fh)
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
        idata = pm.sample(1000, tune=1000, chains=4, cores=SAMPLE_CORES, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    out = {v: p[v].values.ravel() for v in p.data_vars if v in
           ("nu", "k", "gamma", "sd_undiv", "sd_div", "sigma0")}
    out["_divergences"] = int(idata.sample_stats["diverging"].sum())
    return out


def sigma_draws(R, H, dr):
    reff = (np.maximum(R, 1e-9) / REF)[:, None] * (1.0 / np.clip(H, HLO, HCE))[:, None] ** dr["gamma"][None, :]
    return np.sqrt(dr["sd_undiv"][None, :] ** 2 + dr["sd_div"][None, :] ** 2 * reff ** (2.0 * (dr["k"][None, :] - 1.0)))


def held_out_lppd(S_t, R_t, H_t, dr, kind, thin=800):
    idx = np.linspace(0, len(dr["nu"]) - 1, min(thin, len(dr["nu"]))).astype(int)
    nu = dr["nu"][idx]
    sig = sigma_draws(R_t, H_t, {k: v[idx] for k, v in dr.items() if not k.startswith("_")}) if kind == "model" \
        else np.broadcast_to(dr["sigma0"][idx][None, :], (len(S_t), len(idx)))
    lp = stats.t.logpdf(S_t[:, None], df=nu[None, :], scale=sig)          # (Ntest, D)
    return logsumexp(lp, axis=1) - np.log(lp.shape[1])                    # per-obs elpd


FOLD_MAP = SD / "data" / "fold_map.json"


def deal_positions(syndicates):
    """{syndicate: position}: the dealing rule, the sorted syndicates dealt out in turn (position i = rank, 0-based). It
    is the rule data/fold_map.json was dealt by, once, on the 643-record sample; nothing calls it to assign folds."""
    return {int(s): i for i, s in enumerate(sorted(set(int(x) for x in syndicates)))}


def load_fold_map(path=None):
    """{syndicate: position} from the frozen map (data/fold_map.json, dealt once on the 643-record sample's 118
    syndicates: the file states its rule and its sample)."""
    with io.open(str(path or FOLD_MAP), encoding="utf-8") as _fh:
        d = json.load(_fh)
    return {int(s): int(p) for s, p in d["position"].items()}


def fold_map_sha256(path=None):
    """SHA-256 of the frozen map's canonical JSON content (keys sorted, no whitespace), so the same map hashes the same
    whatever the line endings it was checked out with. Records that use the map carry it."""
    import hashlib
    with io.open(str(path or FOLD_MAP), encoding="utf-8") as _fh:
        d = json.load(_fh)
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def fold_assignment(syn, k=K, fold_map=None):
    """The fold of each observation: the frozen map's position of its syndicate, mod k, so that a whole syndicate's years
    are held out together and no syndicate moves when another leaves the sample. A syndicate that is not in the map is
    refused (ValueError); a sample with fewer syndicates than the map simply has fewer. `fold_map` stands in for the file
    (a test's, for synthetic syndicates). check_operator_backtest.py imports it to use the same folds (pinned in
    src/test_operator_backtest.py and src/test_fold_map.py)."""
    pos = load_fold_map() if fold_map is None else fold_map
    missing = sorted(set(int(s) for s in syn) - set(pos))
    if missing:
        raise ValueError("%d syndicate(s) are not in the frozen fold map (data/fold_map.json): %s"
                         % (len(missing), missing[:10]))
    return np.array([pos[int(s)] % k for s in syn])


def main():
    S, R, H, syn = load()
    uniq = np.array(sorted(set(syn)))
    fold = fold_assignment(syn)
    print(f"n={len(S)} syndicates={len(uniq)} folds={K}")

    elpd_m = np.full(len(S), np.nan); elpd_n = np.full(len(S), np.nan)
    divergences = {"model": [], "naive": []}
    covered = {q: 0 for q in (0.90, 0.95, 0.99)}; ntest_total = 0
    for f in range(K):
        te = fold == f; tr = ~te
        print(f"  fold {f}: train {tr.sum()} / test {te.sum()} ({te.sum()} obs, "
              f"{len(set(syn[te]))} held-out syndicates)")
        dm = fit(S[tr], R[tr], H[tr], "model")
        dn = fit(S[tr], R[tr], H[tr], "naive")
        divergences["model"].append(dm["_divergences"]); divergences["naive"].append(dn["_divergences"])
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
        "divergences_by_fold": divergences,
    }
    with io.open(OUT, "w", encoding="utf-8", newline="") as _fh:
        _fh.write(json.dumps(res, indent=2))
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
