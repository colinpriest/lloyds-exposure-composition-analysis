"""Recompute every by-syndicate CV comparison with SYNDICATE-CLUSTERED standard errors.

oos_validation.py and check_pooling_cv_extended.py hold out whole syndicates, which
correctly prevents train/test leakage. But they then compute the standard error of the
paired ELPD difference as sqrt(n) * sd(d_i) over all 790 pointwise differences, which
treats repeated years from the same syndicate as independent observations. The
standard errors, and every z quoted from them, are therefore not cluster-robust.

This re-runs the same folds and models, keeps the per-observation held-out log
predictive densities, and reports each pairwise contrast under BOTH conventions:

  plain      SE = sqrt(n) * sd(d_i)                 over n observations
  clustered  SE = sqrt(m) * sd(D_j), D_j = sum of d_i within syndicate j, over m
             syndicates -- cluster-robust, but a normal approximation

and, as the headline, a BAYESIAN BOOTSTRAP over syndicates, which is what actually
belongs in a Bayesian paper: draw w ~ Dirichlet(1,...,1) over the m syndicate
totals D_j and form m * sum_j w_j D_j.  This is the posterior for the population
ELPD difference under a non-parametric Dirichlet prior on the syndicate population.
It respects the clustering, makes no normal approximation (the pointwise
differences are heavy-tailed), and reports P(model A predicts better) and a
credible interval rather than a z-score.

Models (Student-t, mu=0, no year shock, matching oos_validation.py):
  composition  size + concentration + floor, free k        [the paper's headline]
  size_only    size + floor, no concentration
  naive        one market-wide scale
  k0.5         k fixed at 1/2, floor
  k1           k fixed at 1 (algebraically the naive pool)
  nofloor      free k, no floor

Writes check_cv_clustered_se_results.json.
Usage:  python src/check_cv_clustered_se.py
"""
import io, json, itertools
from pathlib import Path
import numpy as np
from scipy import stats
from scipy.special import logsumexp
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm

from oos_validation import load, REF, HLO, HCE, SEED, K

BB = 20000   # Bayesian-bootstrap draws

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_cv_clustered_se_results.json"

MODELS = {
    "composition": dict(k="logistic", floor=True, conc=True, naive=False),
    "size_only":   dict(k="logistic", floor=True, conc=False, naive=False),
    "naive":       dict(naive=True),
    "k0.5":        dict(k=0.5, floor=True, conc=True, naive=False),
    "k1":          dict(k=1.0, floor=True, conc=True, naive=False),
    "nofloor":     dict(k="logistic", floor=False, conc=True, naive=False),
}
PAIRS = [("composition", "naive"), ("composition", "size_only"),
         ("composition", "k0.5"), ("composition", "k1"),
         ("composition", "nofloor"), ("size_only", "naive")]


def fit(S, R, H, cfg):
    logR = np.log(R / REF); logH = np.log(H)
    with pm.Model():
        nu = pm.Gamma("nu", 2.0, 0.1)
        if cfg.get("naive"):
            log_s0 = pm.Normal("log_s0", np.log(0.08), 1.0)
            sigma = pm.Deterministic("sigma0", pm.math.exp(log_s0))
        else:
            kc = cfg["k"]
            if kc == "logistic":
                theta = pm.Normal("theta", 0.0, 1.5)
                k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
            else:
                k = pm.Deterministic("k", pm.math.constant(float(kc)))
            gamma = (pm.HalfNormal("gamma", 1.0) if cfg["conc"]
                     else pm.Deterministic("gamma", pm.math.constant(0.0)))
            log_tot = pm.Normal("log_tot", np.log(0.05), 1.0)
            tot = pm.math.exp(log_tot)
            if cfg["floor"]:
                f = pm.Beta("f", 1.0, 1.0)
                su = pm.Deterministic("sd_undiv", tot * pm.math.sqrt(f))
                sd = pm.Deterministic("sd_div", tot * pm.math.sqrt(1.0 - f))
            else:
                su = pm.Deterministic("sd_undiv", pm.math.constant(0.0))
                sd = pm.Deterministic("sd_div", tot)
            var = su ** 2 + sd ** 2 * pm.math.exp(2.0 * (k - 1.0) * (logR - gamma * logH))
            sigma = pm.math.sqrt(var)
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=sigma, observed=S)
        idata = pm.sample(1000, tune=1000, chains=4, cores=1, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    keep = [v for v in ("nu", "k", "gamma", "sd_undiv", "sd_div", "sigma0")
            if v in p.data_vars]
    return {v: p[v].values.ravel() for v in keep}


def lppd(S_t, R_t, H_t, dr, thin=800):
    n = len(dr["nu"])
    idx = np.linspace(0, n - 1, min(thin, n)).astype(int)
    nu = dr["nu"][idx]
    if "sigma0" in dr:
        sig = np.broadcast_to(dr["sigma0"][idx][None, :], (len(S_t), len(idx)))
    else:
        reff = (np.maximum(R_t, 1e-9) / REF)[:, None] * \
               (1.0 / np.clip(H_t, HLO, HCE))[:, None] ** dr["gamma"][idx][None, :]
        sig = np.sqrt(dr["sd_undiv"][idx][None, :] ** 2 +
                      dr["sd_div"][idx][None, :] ** 2 *
                      reff ** (2.0 * (dr["k"][idx][None, :] - 1.0)))
    lp = stats.t.logpdf(S_t[:, None], df=nu[None, :], scale=sig)
    return logsumexp(lp, axis=1) - np.log(lp.shape[1])


def main():
    S, R, H, syn = load()
    uniq = np.array(sorted(set(syn)))
    fold_of = {s: i % K for i, s in enumerate(uniq)}
    fold = np.array([fold_of[s] for s in syn])
    print(f"n={len(S)}  syndicates={len(uniq)}  folds={K}")

    e = {m: np.full(len(S), np.nan) for m in MODELS}
    for f in range(K):
        te = fold == f; tr = ~te
        print(f"  fold {f}: train {tr.sum()} / test {te.sum()}")
        for m, cfg in MODELS.items():
            e[m][te] = lppd(S[te], R[te], H[te], fit(S[tr], R[tr], H[tr], cfg))

    res = {"n": int(len(S)), "n_syndicates": int(len(uniq)), "folds": K, "seed": SEED,
           "issue": ("plain SE treats repeated years from one syndicate as independent; "
                     "clustered SE aggregates the paired differences within syndicate "
                     "and takes the spread across syndicate totals"),
           "held_out_ELPD": {m: float(np.nansum(v)) for m, v in e.items()},
           "contrasts": {}}

    print("\n" + "=" * 84)
    print(f"{'contrast':<26}{'dELPD':>8}{'SEpl':>7}{'SEcl':>7}"
          f"{'BB 95% credible':>24}{'P(A>B)':>9}")
    for a, b in PAIRS:
        d = e[a] - e[b]
        ok = np.isfinite(d)
        dE = float(d[ok].sum())
        se_p = float(np.sqrt(ok.sum()) * d[ok].std(ddof=1))
        tot = {}
        for di, sj in zip(d[ok], syn[ok]):
            tot[sj] = tot.get(sj, 0.0) + di
        v = np.array(list(tot.values()), float)
        se_c = float(np.sqrt(len(v)) * v.std(ddof=1))
        # Bayesian bootstrap over syndicates (Dirichlet weights on cluster totals)
        rng = np.random.default_rng(SEED)
        W = rng.dirichlet(np.ones(len(v)), size=BB)
        draws = len(v) * (W @ v)
        rec = {"delta_ELPD": dE,
               "SE_plain": se_p, "z_plain": dE / se_p if se_p else None,
               "SE_clustered": se_c, "z_clustered": dE / se_c if se_c else None,
               "SE_inflation": se_c / se_p if se_p else None,
               "bb_mean": float(draws.mean()),
               "bb_sd": float(draws.std(ddof=1)),
               "bb_2.5": float(np.percentile(draws, 2.5)),
               "bb_97.5": float(np.percentile(draws, 97.5)),
               "P_first_better": float((draws > 0).mean()),
               "n_clusters": int(len(v)),
               "pct_obs_first_better": float((d[ok] > 0).mean() * 100),
               "pct_syndicates_first_better": float((v > 0).mean() * 100)}
        res["contrasts"][f"{a}__vs__{b}"] = rec
        print(f"{a+' vs '+b:<26}{dE:>8.2f}{se_p:>7.2f}{se_c:>7.2f}"
              f"{('[%+.2f, %+.2f]' % (rec['bb_2.5'], rec['bb_97.5'])):>24}"
              f"{rec['P_first_better']:>9.3f}")

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
