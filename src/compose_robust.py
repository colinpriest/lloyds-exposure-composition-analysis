"""Appendix C.2: composition robustness by PSIS-LOO (dominant LoB + long-tail share).

Tests whether line-of-business composition improves the dispersion model beyond size, HHI
and the year shock. Three nested models on log-sigma, single-t floor baseline (RITC regime
orthogonal), refitted on n=790:

  base   : log sigma = base dispersion (k, gamma, floor, year shock)   [= calibrate_dispersion]
  +LT    : base + beta_LT * long_tail_share
  +domLoB: base + delta_g[dominant group],  delta_g ~ N(0, tau_L)
           groups = {Aggregate, Property, Casualty, Aviation, Other}

Reports per-model elpd_loo, Delta-elpd (vs base) and its SE, beta_LT posterior, tau_L and the
per-group dispersion multipliers exp(delta_g). Long-tail lines = {Casualty, Professional Lines,
Reinsurance-Casualty, Motor} (LONG_TAIL_IDX in simplification_tests).

Run: python compose_robust.py
"""
import io, json
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

def hdi95(x):
    """95% highest-density interval of a posterior sample.

    Not equal-tailed percentiles: the manuscript's stated convention is that every
    interval on a fitted parameter is an HDI, and percentile endpoints silently
    violated it while being stored under a key named "hdi".
    """
    a = np.asarray(x, float).ravel()
    if a.min() == a.max():
        return [float(a[0]), float(a[0])]
    return [float(v) for v in az.hdi(a, hdi_prob=0.95)]


SCRIPT_DIR = Path(__file__).resolve().parent.parent
OUT = SCRIPT_DIR / "results" / "compose_robust_results.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42
LONG_TAIL_IDX = [1, 9, 7, 4]  # Casualty, Professional Lines, Reinsurance-Casualty, Motor
DOM_MAP = {12: "Aggregate", 0: "Property", 1: "Casualty", 5: "Aviation"}  # else -> Other


def load():
    d = json.load(io.open(SCRIPT_DIR / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None and o.get("weights")]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    W = np.array([o["weights"] for o in recs], float)
    lt = W[:, LONG_TAIL_IDX].sum(axis=1)
    dom = W.argmax(axis=1)
    groups = ["Aggregate", "Property", "Casualty", "Aviation", "Other"]
    gidx = np.array([groups.index(DOM_MAP.get(int(dm), "Other")) for dm in dom])
    return S, R, H, yr, lt, gidx, groups


def base_pieces(model, R, H, yr):
    logR = np.log(R / REF); logH = np.log(H)
    years = np.sort(np.unique(yr)); yidx = np.searchsorted(years, yr); n_y = len(years)
    theta = pm.Normal("theta", 0.0, 1.5)
    k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
    gamma = pm.HalfNormal("gamma", 1.0)
    log_tot = pm.Normal("log_tot", np.log(0.05), 1.0); tot = pm.math.exp(log_tot)
    f = pm.Beta("f", 1.0, 1.0)
    su = pm.Deterministic("sd_undiv", tot * pm.math.sqrt(f))
    sd = pm.Deterministic("sd_div", tot * pm.math.sqrt(1.0 - f))
    tau_s = pm.HalfNormal("tau_s", 0.5); z_s = pm.Normal("z_s", 0.0, 1.0, shape=n_y)
    s_y = tau_s * z_s
    log_reff = logR - gamma * logH
    var = su ** 2 + sd ** 2 * pm.math.exp(2.0 * (k - 1.0) * log_reff)
    nu = pm.Gamma("nu", 2.0, 0.1)
    return var, s_y[yidx], nu


def fit(kind, S, R, H, yr, lt, gidx, groups):
    with pm.Model() as m:
        var, s_y, nu = base_pieces(m, R, H, yr)
        add = 0.0
        if kind == "lt":
            b = pm.Normal("beta_LT", 0.0, 1.0); add = b * lt
        elif kind == "dom":
            tau_L = pm.HalfNormal("tau_L", 0.5)
            zL = pm.Normal("zL", 0.0, 1.0, shape=len(groups))
            delta = pm.Deterministic("delta", tau_L * zL)
            add = delta[gidx]
        sigma = pm.math.exp(s_y + add) * pm.math.sqrt(var)
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=sigma, observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False, idata_kwargs={"log_likelihood": True})
    return idata


def main():
    S, R, H, yr, lt, gidx, groups = load()
    print(f"n={len(S)}  long_tail_share median={np.median(lt):.3f}  groups={ {g:int((gidx==i).sum()) for i,g in enumerate(groups)} }")
    ids = {}
    for kind, name in [("base", "base"), ("lt", "+long_tail"), ("dom", "+dominant_LoB")]:
        print(f"fitting {name}..."); ids[name] = fit(kind, S, R, H, yr, lt, gidx, groups)
    loos = {n: az.loo(i) for n, i in ids.items()}
    cmp = az.compare(ids, ic="loo")

    res = {"n": int(len(S)), "seed": SEED,
           "long_tail_lines": ["Casualty", "Professional Lines", "Reinsurance-Casualty", "Motor"],
           "dominant_groups": groups,
           "models": {}, "compare_table": cmp.reset_index().to_dict(orient="records")}
    base_elpd = float(loos["base"].elpd_loo)
    for n, l in loos.items():
        res["models"][n] = {"elpd_loo": float(l.elpd_loo), "p_loo": float(l.p_loo),
                            "se": float(l.se), "delta_elpd_vs_base": float(l.elpd_loo - base_elpd)}
    # extra params
    plt_ = ids["+long_tail"].posterior["beta_LT"].values.ravel()
    res["beta_LT"] = {"mean": float(plt_.mean()), "hdi": hdi95(plt_),
                      "P_gt_0": float((plt_ > 0).mean()),
                      "multiplier_full_range": float(np.exp(plt_.mean() * (lt.max() - lt.min())))}
    pd = ids["+dominant_LoB"].posterior
    tauL = pd["tau_L"].values.ravel()
    res["tau_L"] = {"mean": float(tauL.mean()), "hdi": hdi95(tauL)}
    dl = pd["delta"].values.reshape(-1, len(groups))
    res["dominant_multipliers"] = {groups[i]: {"mult_mean": float(np.exp(dl[:, i]).mean()),
                                               "hdi": hdi95(np.exp(dl[:, i]))}
                                   for i in range(len(groups))}
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 60)
    for n in ("base", "+long_tail", "+dominant_LoB"):
        r = res["models"][n]
        print(f"  {n:<16} elpd={r['elpd_loo']:8.2f}  Delta_vs_base={r['delta_elpd_vs_base']:+6.2f}  SE={r['se']:.2f}")
    b = res["beta_LT"]; print(f"\n  beta_LT = {b['mean']:+.3f} {b['hdi']}  P(>0)={b['P_gt_0']:.2f}  range-multiplier={b['multiplier_full_range']:.2f}")
    print(f"  tau_L   = {res['tau_L']['mean']:.3f} {res['tau_L']['hdi']}")
    for g, v in res["dominant_multipliers"].items():
        print(f"    {g:<10} mult={v['mult_mean']:.2f} [{v['hdi'][0]:.2f},{v['hdi'][1]:.2f}]")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
