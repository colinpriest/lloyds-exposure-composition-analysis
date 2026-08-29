"""Referee check: by-syndicate predictive comparison of the pooling FORM and the FLOOR.

check_pooling_cv.py compares only M1 (free k) against M2 (k=1/2).  Two referee points
need more:

  (1) the pooling exponent: compare EXPLICIT k=1/2, free k, and k=1 (comonotonic), plus
      an unconstrained-support free k, on by-syndicate held-out prediction;
  (2) the floor: the paper calls the undiversifiable floor "real", but the reported
      comparison held a floor in BOTH candidates.  A no-floor model must be scored
      head-to-head, and its behaviour over the OBSERVED size range displayed.

Models (all Student-t, mu=0; year shock dropped, as in oos_validation.py, so the
comparison isolates the scale form):

  M1  free k in (0.5,1) via logistic     + floor      [adopted]
  M2  k = 1/2 fixed                      + floor      [independent sqrt-N pooling]
  M5  k = 1   fixed                      + floor      [comonotonic, no diversification]
  M6  k ~ Normal(0.5,0.5), unconstrained + floor      [free k, honest support]
  M7  free k in (0.5,1) via logistic     + NO floor   [pure power law]

Scored by 5-fold cross-validation BY SYNDICATE on the same folds as oos_validation.py.
Also refits M1 and M7 on the FULL sample and tabulates the fitted scale sigma(R) across
the observed size range and beyond it, so the floor's effect is visible where the data
actually are rather than only in the 100bn extrapolation.

Writes check_pooling_cv_extended_results.json.
Usage:  python check_pooling_cv_extended.py
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

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_pooling_cv_extended_results.json"

MODELS = {
    "M1_free_k_floor":      dict(k="logistic", floor=True,
                                 label="free k in (0.5,1), floor [adopted]"),
    "M2_k0.5_floor":        dict(k=0.5, floor=True,
                                 label="k = 1/2 fixed, floor [independent sqrt-N]"),
    "M5_k1_floor":          dict(k=1.0, floor=True,
                                 label="k = 1 fixed, floor [comonotonic]"),
    "M6_k_unconstrained_floor": dict(k="normal", floor=True,
                                 label="k ~ Normal(0.5,0.5) unconstrained, floor"),
    "M7_free_k_nofloor":    dict(k="logistic", floor=False,
                                 label="free k in (0.5,1), NO floor [pure power law]"),
}


def build(S, R, H, cfg):
    logR = np.log(R / REF); logH = np.log(H)
    with pm.Model() as m:
        nu = pm.Gamma("nu", 2.0, 0.1)
        kc = cfg["k"]
        if kc == "logistic":
            theta = pm.Normal("theta", 0.0, 1.5)
            k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        elif kc == "normal":
            k = pm.Normal("k", 0.5, 0.5)
        else:
            k = pm.Deterministic("k", pm.math.constant(float(kc)))
        gamma = pm.HalfNormal("gamma", 1.0)
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
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=pm.math.sqrt(var), observed=S)
    return m


def fit(S, R, H, cfg, draws=1000, tune=1000):
    with build(S, R, H, cfg):
        idata = pm.sample(draws, tune=tune, chains=4, cores=1, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    dr = {v: p[v].values.ravel() for v in ("nu", "k", "gamma", "sd_undiv", "sd_div")}
    dr["_divergences"] = int(idata.sample_stats["diverging"].sum())
    return dr


def sigma_draws(R, H, dr):
    reff = (np.maximum(R, 1e-9) / REF)[:, None] * \
           (1.0 / np.clip(H, HLO, HCE))[:, None] ** dr["gamma"][None, :]
    return np.sqrt(dr["sd_undiv"][None, :] ** 2 +
                   dr["sd_div"][None, :] ** 2 * reff ** (2.0 * (dr["k"][None, :] - 1.0)))


def held_out_lppd(S_t, R_t, H_t, dr, thin=800):
    n = len(dr["nu"])
    idx = np.linspace(0, n - 1, min(thin, n)).astype(int)
    sub = {k: v[idx] for k, v in dr.items() if not k.startswith("_")}
    sig = sigma_draws(R_t, H_t, sub)
    lp = stats.t.logpdf(S_t[:, None], df=sub["nu"][None, :], scale=sig)
    return logsumexp(lp, axis=1) - np.log(lp.shape[1])


def main():
    S, R, H, syn = load()
    uniq = np.array(sorted(set(syn)))
    fold_of = {s: i % K for i, s in enumerate(uniq)}
    fold = np.array([fold_of[s] for s in syn])
    print(f"n={len(S)} syndicates={len(uniq)} folds={K}")
    print(f"observed reserve size range: {R.min():.1f}m to {R.max():.1f}m "
          f"(median {np.median(R):.1f}m, p95 {np.percentile(R,95):.1f}m)")

    elpd = {name: np.full(len(S), np.nan) for name in MODELS}
    for fdx in range(K):
        te = fold == fdx; tr = ~te
        print(f"  fold {fdx}: train {tr.sum()} / test {te.sum()}")
        for name, cfg in MODELS.items():
            dr = fit(S[tr], R[tr], H[tr], cfg)
            elpd[name][te] = held_out_lppd(S[te], R[te], H[te], dr)
            print(f"      {name:28s} div={dr['_divergences']}")

    totals = {n: float(np.nansum(v)) for n, v in elpd.items()}
    pairs = {}
    for a, b in itertools.combinations(MODELS, 2):
        d = elpd[a] - elpd[b]
        dE = float(np.nansum(d)); se = float(np.sqrt(len(d)) * np.nanstd(d))
        pairs[f"{a}__minus__{b}"] = {
            "delta_ELPD": dE, "SE": se, "z": (dE / se) if se else None,
            "pct_first_higher_density": float(np.mean(d > 0) * 100)}

    # Full-sample floor vs no-floor: behaviour across the OBSERVED size range.
    print("\nfull-sample fits for the size-range comparison ...")
    full = {}
    for name in ("M1_free_k_floor", "M7_free_k_nofloor"):
        dr = fit(S, R, H, MODELS[name], draws=1500, tune=1500)
        full[name] = {v: [float(dr[v].mean()),
                          float(np.percentile(dr[v], 2.5)),
                          float(np.percentile(dr[v], 97.5))]
                      for v in ("k", "gamma", "sd_undiv", "sd_div", "nu")}
        full[name]["_draws"] = dr
    Hbar = float(np.median(H))
    grid = [25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2000.0, 5000.0,
            float(np.max(R)), 10000.0, 100000.0]
    sigma_tab = []
    for r in grid:
        row = {"R_m": r, "in_observed_range": bool(r <= R.max())}
        for name in ("M1_free_k_floor", "M7_free_k_nofloor"):
            s = sigma_draws(np.array([r]), np.array([Hbar]), full[name]["_draws"])[0]
            row[name] = {"mean": float(s.mean()),
                         "lo": float(np.percentile(s, 2.5)),
                         "hi": float(np.percentile(s, 97.5))}
        row["ratio_nofloor_over_floor"] = (row["M7_free_k_nofloor"]["mean"] /
                                           row["M1_free_k_floor"]["mean"])
        sigma_tab.append(row)
    for name in full:
        full[name].pop("_draws")

    res = {
        "n": int(len(S)), "n_syndicates": int(len(uniq)), "folds": K, "seed": SEED,
        "criterion": "5-fold by-syndicate held-out ELPD (same folds as oos_validation.py)",
        "models": {n: MODELS[n]["label"] for n in MODELS},
        "held_out_ELPD": totals,
        "pairwise": pairs,
        "observed_size_range_m": {"min": float(R.min()), "max": float(R.max()),
                                  "median": float(np.median(R)),
                                  "p95": float(np.percentile(R, 95))},
        "full_sample_params": full,
        "sigma_over_size_range": {"H_at_median": Hbar, "rows": sigma_tab},
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")

    print("\n" + "=" * 74)
    print("by-syndicate held-out ELPD:")
    for n, v in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"  {n:28s} {v:9.2f}   {MODELS[n]['label']}")
    print("\nkey pairwise contrasts (delta, SE, z):")
    for key in ("M1_free_k_floor__minus__M2_k0.5_floor",
                "M1_free_k_floor__minus__M5_k1_floor",
                "M1_free_k_floor__minus__M6_k_unconstrained_floor",
                "M1_free_k_floor__minus__M7_free_k_nofloor"):
        p = pairs[key]
        z = p["z"]
        print(f"  {key:52s} {p['delta_ELPD']:+8.2f} +- {p['SE']:5.2f}  z={z:+.2f}")
    print("\nsigma(R) at median H, floor vs no floor:")
    for row in sigma_tab:
        tag = "" if row["in_observed_range"] else "  (extrapolation)"
        print(f"  R={row['R_m']:9.0f}m  floor {row['M1_free_k_floor']['mean']:.4f}   "
              f"no-floor {row['M7_free_k_nofloor']['mean']:.4f}   "
              f"ratio {row['ratio_nofloor_over_floor']:.3f}{tag}")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
