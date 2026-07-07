"""Does RITC change the TAIL SHAPE of the operator-standardised residual?

Correction to ritc_shape_invariance.py: the robust shape statistics there (Bowley
skew, Moors kurtosis, tail-skew ratio) are built from quantiles at/inside the 10th-90th
percentiles, and KS is body-dominated -- all three are BLIND to the extreme tail.  So
their "no shape difference" verdict only covers the central shape.  The tail is part of
the shape, and the nu robustness fit (nu 2.14 -> 2.43 when RITC is dropped) says it moves.

This script tests the tail shape of z = s / sigma(R,HHI) directly, clean vs RITC, with
tail-SENSITIVE estimators and a cluster (by-syndicate) bootstrap:

  * Student-t degrees of freedom nu (MLE) fit to z per group  -> lower nu = heavier tail
  * GPD tail index xi on |z| exceedances over a common high threshold
  * Hill tail index on the top order statistics of |z|
  * far-tail quantile ratios q95, q99 of |z|  (RITC / clean)
  * far-tail spread ratio (q99 - q50)/(q90 - q50)  -- shape beyond p90 the robust
    statistics could not see

Run:  python ritc_tail_shape.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats

import run_analysis as ra
from test_shape_invariance import build_population, select, _q
from ritc_shape_invariance import sigma_op, load_calib_population

SCRIPT_DIR = Path(__file__).resolve().parent
CAL = SCRIPT_DIR / "dispersion_calibration.json"
RITC = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
OUT = SCRIPT_DIR / "ritc_tail_shape_results.json"
SEED = 12345
N_BOOT = 4000
THR_Q = 90.0     # common threshold percentile (of pooled |z|) for GPD/Hill exceedances


# ── tail-shape estimators (all defined on a 1-D array of z) ──────────────────
def t_nu(z):
    """Student-t MLE degrees of freedom (free loc/scale). Clipped to [1,50]."""
    try:
        df, _, _ = stats.t.fit(z)
    except Exception:
        return np.nan
    return float(np.clip(df, 1.0, 50.0))


def gpd_xi(z, thr):
    az = np.abs(z); exc = az[az > thr] - thr
    if len(exc) < 12:
        return np.nan
    try:
        xi, _, sc = stats.genpareto.fit(exc, floc=0.0)
    except Exception:
        return np.nan
    return float(xi) if (sc > 0 and np.isfinite(xi)) else np.nan


def hill_xi(z, k_frac=0.15):
    """Hill tail index xi = 1/alpha on the top k order statistics of |z|."""
    az = np.sort(np.abs(z))[::-1]
    k = max(int(k_frac * len(az)), 8)
    if k + 1 >= len(az) or az[k] <= 0:
        return np.nan
    logs = np.log(az[:k]) - np.log(az[k])
    m = logs.mean()
    return float(m) if m > 0 else np.nan     # Hill xi (=1/alpha)


def q_ratio_stat(z, p):
    return _q(np.abs(z), p)


def far_spread(z):
    """(q99 - q50)/(q90 - q50) of |z| -- upper-tail stretch beyond p90."""
    az = np.abs(z); q50, q90, q99 = _q(az, 50), _q(az, 90), _q(az, 99)
    d = q90 - q50
    return (q99 - q50) / d if d > 0 else np.nan


# ── cluster bootstrap of a per-group statistic and its clean/RITC contrast ───
def cluster_contrast(z, cluster, ritc, stat_fn, kind, rng, thr=None, n=N_BOOT):
    """Bootstrap point + CI for stat(RITC) vs stat(clean).

    kind='diff'  -> stat(RITC) - stat(clean),   H0: 0
    kind='ratio' -> stat(RITC) / stat(clean),   H0: 1
    """
    clusters = np.unique(cluster)
    idx = {c: np.where(cluster == c)[0] for c in clusters}
    call = (lambda a: stat_fn(a, thr)) if thr is not None else stat_fn
    obs = (call(z[ritc]), call(z[~ritc]))
    obs_val = (obs[0] - obs[1]) if kind == "diff" else (obs[0] / obs[1] if obs[1] else np.nan)
    vals = []
    for _ in range(n):
        pick = rng.choice(clusters, size=len(clusters), replace=True)
        rows = np.concatenate([idx[c] for c in pick])
        zr, rr = z[rows], ritc[rows]
        if rr.sum() < 12 or (~rr).sum() < 12:
            continue
        a, b = call(zr[rr]), call(zr[~rr])
        if not (np.isfinite(a) and np.isfinite(b)):
            continue
        vals.append((a - b) if kind == "diff" else (a / b if b else np.nan))
    vals = np.array([v for v in vals if np.isfinite(v)])
    if len(vals) < n * 0.4:
        return {"ritc": _f(obs[0]), "clean": _f(obs[1]), "obs": _f(obs_val), "ci": None, "p": None, "n_boot": int(len(vals))}
    lo, hi = np.percentile(vals, [2.5, 97.5])
    null = 0.0 if kind == "diff" else 1.0
    p = 2.0 * min((vals <= null).mean(), (vals >= null).mean())
    return {"ritc": _f(obs[0]), "clean": _f(obs[1]), "obs": _f(obs_val),
            "ci": (float(lo), float(hi)), "p": float(min(p, 1.0)), "n_boot": int(len(vals))}


def _f(x):
    return float(x) if np.isfinite(x) else None


def run(label, rows, strong, weak, cal, rng, store):
    s = np.array([x["s_raw_a"] for x in rows], float)
    R = np.array([x["opening_reserves_gbp_m"] for x in rows], float)
    HHI = np.array([x["hhi"] for x in rows], float)
    cluster = np.array([x["syndicate"] for x in rows])
    key = np.array([f"{x['syndicate']}_{x['year']}" for x in rows])
    ritc = np.array([(k in strong) or (k in weak) for k in key])
    z = s / sigma_op(R, HHI, cal)
    thr = float(np.percentile(np.abs(z), THR_Q))

    print(f"\n{'#'*74}\n#  {label}:  n={len(z)}  clean={int((~ritc).sum())}  RITC={int(ritc.sum())}"
          f"  |z| threshold(p{THR_Q:.0f})={thr:.2f}\n{'#'*74}")

    tests = [
        ("Student-t nu (MLE)",        t_nu,       "diff",  None, "lower nu = heavier"),
        ("GPD xi (|z| exceedances)",  gpd_xi,     "diff",  thr,  "higher xi = heavier"),
        ("Hill xi (top 15% |z|)",     hill_xi,    "diff",  None, "higher xi = heavier"),
        ("q95(|z|) ratio",            lambda a, p=95: q_ratio_stat(a, p), "ratio", None, ">1 = RITC bigger"),
        ("q99(|z|) ratio",            lambda a, p=99: q_ratio_stat(a, p), "ratio", None, ">1 = RITC bigger"),
        ("far spread (q99-q50)/(q90-q50)", far_spread, "diff", None, "upper-tail stretch >p90"),
    ]
    res = {"meta": {"n": len(z), "clean": int((~ritc).sum()), "ritc": int(ritc.sum()),
                    "thr_p90_absz": thr, "seed": SEED, "n_boot": N_BOOT}, "tests": {}}
    print(f"  {'statistic':<34}{'clean':>9}{'RITC':>9}{'contrast':>11}{'95% CI':>22}{'p':>8}")
    print("  " + "-" * 92)
    for name, fn, kind, th, note in tests:
        r = cluster_contrast(z, cluster, ritc, fn, kind, rng, thr=th)
        ci = f"[{r['ci'][0]:+.2f}, {r['ci'][1]:+.2f}]" if r["ci"] else "     n/a"
        pv = f"{r['p']:.3f}" if r["p"] is not None else "  n/a"
        sig = " ***" if (r["p"] is not None and r["p"] < 0.05) else ""
        cl = f"{r['clean']:.2f}" if r["clean"] is not None else "n/a"
        ri = f"{r['ritc']:.2f}" if r["ritc"] is not None else "n/a"
        ob = f"{r['obs']:+.2f}" if r["obs"] is not None else "n/a"
        print(f"  {name:<34}{cl:>9}{ri:>9}{ob:>11}{ci:>22}{pv:>8}{sig}   ({note})")
        res["tests"][name] = r
    store[label] = res


def main():
    rng = np.random.default_rng(SEED)
    cal = json.load(io.open(CAL, encoding="utf-8"))
    r = json.load(io.open(RITC, encoding="utf-8"))
    strong = {k for k, v in r.items() if v.get("ritc_occurred") and v.get("confidence") == "strong"}
    weak = {k for k, v in r.items() if v.get("ritc_occurred") and v.get("confidence") == "weak"}
    print("RITC TAIL-SHAPE comparison of operator-standardised z = s/sigma(R,HHI)")
    print(f"(cluster bootstrap {N_BOOT} resamples of syndicates; seed={SEED})")
    print(f"operator: k={cal['k']:.4f} gamma={cal['gamma']:.4f} sd_undiv={cal['sd_undiv']:.4f} sd_div={cal['sd_div']:.4f}")
    store = {}
    run("CALIB (n=790)", load_calib_population(), strong, weak, cal, rng, store)
    run("N5 (rescaling pop)", select(build_population(), "N5"), strong, weak, cal, rng, store)
    OUT.write_text(json.dumps(store, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")
    print("\nA heavier RITC tail shows as: nu(RITC) < nu(clean) (negative nu contrast),")
    print("xi(RITC) > xi(clean) (positive), and q95/q99/far-spread ratios > 1.")


if __name__ == "__main__":
    main()
