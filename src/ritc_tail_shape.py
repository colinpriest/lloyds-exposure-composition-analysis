"""Compare the TAIL SHAPE of the single-regime base-standardised residual.

Correction to ritc_shape_invariance.py: the robust shape statistics there (Bowley
skew, Moors kurtosis, tail-skew ratio) are built from quantiles at/inside the 10th-90th
percentiles, and KS is body-dominated -- all three have limited sensitivity to the
extreme tail. A failure to detect central shape differences does not settle tail shape.
The current robustness fits give similar point estimates with and without the
assumed-business records; their point difference does not establish a tail-shape change.

This script compares tail behaviour of z = s / sigma(R,HHI), clean vs RITC, with
tail-sensitive statistics and a cluster (by-syndicate) bootstrap:

  * Student-t degrees of freedom nu (MLE) fit to z per group  -> lower nu = heavier tail
  * GPD tail index xi on |z| exceedances over a common high threshold
  * Hill tail index on the top order statistics of |z|
  * far-tail quantile ratios q95, q99 of |z|  (RITC / clean)
  * far-tail spread ratio (q99 - q50)/(q90 - q50)  -- shape beyond p90 the robust
    statistics could not see

What each statistic measures (frozen review of 21 September 2026, M05).  z divides by the
single-regime calibration's sigma at its posterior-mean parameters, with no year shock and no
RITC scale term, so each regime's own scale and each year's effect stay in z.  The q95 and q99
ratios of |z| are therefore MAGNITUDE statistics: multiplying one group's z by a constant moves
them without changing that group's tail shape, and a ratio describes the relative residual
magnitudes at that quantile, not whether their tail is thinner or heavier.  The
Student-t nu (fitted with a free scale), the Hill index and the far-spread ratio do not
move under that rescaling. The GPD shape estimate uses a fixed pooled threshold: scaling
one group changes its exceedances and can move the estimate; scaling the threshold with
the group restores scale equivariance. Each result records its measurement scope.
The bootstrap's legacy `p` is twice the smaller fraction of resampled contrasts on either
side of zero (or one for a ratio), without null centering; it is not established as a
null-calibrated p-value.

The Student-t nu is an MLE CLIPPED to NU_CLIP = [1, 50]. A clipped value is a boundary, not an
estimate: in the 29 September 2026 review, the then-current strict rescaling population had 16
RITC residuals whose fit returned exactly 1.00, the lower clip, and a review note quoted it as
a "direct MLE" (A-6). Each
Student-t row therefore records whether either group's value sits on a clip bound
(`ritc_at_bound`, `clean_at_bound`: "lower", "upper" or null) and how many bootstrap replicates
had a group on a bound (`n_boot_at_bound`), so the contrast's interval is read knowing it is
built partly from clipped draws.

Run:  python src/ritc_tail_shape.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats

import run_analysis as ra
from test_shape_invariance import build_population, select, _q
from ritc_shape_invariance import sigma_op, load_calib_population, CALIBRATION_SOURCE, STANDARDISATION_NOTE
import assumed_business

SCRIPT_DIR = Path(__file__).resolve().parent.parent
CAL = SCRIPT_DIR / "model" / "dispersion_calibration.json"
RITC = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
OUT = SCRIPT_DIR / "results" / "ritc_tail_shape_results.json"
SEED = 12345
N_BOOT = 4000
THR_Q = 90.0     # common pooled |z| threshold for GPD; Hill uses each group's top 15%
# The GPD's fixed pooled threshold can change its selected tail under group rescaling.
MEASURES = {
    "Student-t nu (MLE)": "shape",
    "GPD xi (|z| exceedances)": "threshold-dependent shape",
    "Hill xi (top 15% |z|)": "shape",
    "q95(|z|) ratio": "magnitude",
    "q99(|z|) ratio": "magnitude",
    "far spread (q99-q50)/(q90-q50)": "shape",
}
BOOTSTRAP_P_NOTE = ("legacy p is twice the smaller observed-bootstrap fraction on either side of the null; "
                    "without null centering it is not established as a null-calibrated p-value")


# ── tail-shape estimators (all defined on a 1-D array of z) ──────────────────
#: the Student-t MLE's clip: below 1 the t has no mean, above 50 it is Gaussian for this purpose
NU_CLIP = (1.0, 50.0)


def t_nu(z):
    """Student-t MLE degrees of freedom (free loc/scale), clipped to NU_CLIP; nu_bound() says
    whether the returned value is the clip rather than an interior estimate."""
    try:
        df, _, _ = stats.t.fit(z)
    except Exception:
        return np.nan
    return float(np.clip(df, *NU_CLIP))


def nu_bound(value):
    """"lower" or "upper" when a clipped nu sits on NU_CLIP, else None (an interior estimate)."""
    if value is None or not np.isfinite(value):
        return None
    if value <= NU_CLIP[0]:
        return "lower"
    if value >= NU_CLIP[1]:
        return "upper"
    return None


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
def cluster_contrast(z, cluster, ritc, stat_fn, kind, rng, thr=None, n=N_BOOT, bound_fn=None):
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
    n_at_bound = 0
    for _ in range(n):
        pick = rng.choice(clusters, size=len(clusters), replace=True)
        rows = np.concatenate([idx[c] for c in pick])
        zr, rr = z[rows], ritc[rows]
        if rr.sum() < 12 or (~rr).sum() < 12:
            continue
        a, b = call(zr[rr]), call(zr[~rr])
        if not (np.isfinite(a) and np.isfinite(b)):
            continue
        if bound_fn is not None and (bound_fn(a) or bound_fn(b)):
            n_at_bound += 1
        vals.append((a - b) if kind == "diff" else (a / b if b else np.nan))
    vals = np.array([v for v in vals if np.isfinite(v)])
    bounds = ({"ritc_at_bound": bound_fn(obs[0]), "clean_at_bound": bound_fn(obs[1]),
               "n_boot_at_bound": int(n_at_bound)} if bound_fn is not None else {})
    if len(vals) < n * 0.4:
        return {"ritc": _f(obs[0]), "clean": _f(obs[1]), "obs": _f(obs_val), "ci": None, "p": None,
                "n_boot": int(len(vals)), **bounds}
    lo, hi = np.percentile(vals, [2.5, 97.5])
    null = 0.0 if kind == "diff" else 1.0
    p = 2.0 * min((vals <= null).mean(), (vals >= null).mean())
    return {"ritc": _f(obs[0]), "clean": _f(obs[1]), "obs": _f(obs_val),
            "ci": (float(lo), float(hi)), "p": float(min(p, 1.0)), "n_boot": int(len(vals)), **bounds}


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
        ("GPD xi (|z| exceedances)",  gpd_xi,     "diff",  thr,  "pooled threshold; scale-sensitive"),
        ("Hill xi (top 15% |z|)",     hill_xi,    "diff",  None, "higher xi = heavier"),
        ("q95(|z|) ratio",            lambda a, p=95: q_ratio_stat(a, p), "ratio", None, ">1 = RITC bigger"),
        ("q99(|z|) ratio",            lambda a, p=99: q_ratio_stat(a, p), "ratio", None, ">1 = RITC bigger"),
        ("far spread (q99-q50)/(q90-q50)", far_spread, "diff", None, "upper-tail stretch >p90"),
    ]
    res = {"meta": {"n": len(z), "clean": int((~ritc).sum()), "ritc": int(ritc.sum()),
                    "calibration_source": CALIBRATION_SOURCE, "standardisation": STANDARDISATION_NOTE,
                    "bootstrap_p_note": BOOTSTRAP_P_NOTE,
                    "thr_p90_absz": thr, "seed": SEED, "n_boot": N_BOOT}, "tests": {}}
    print("  sign2 is twice the smaller observed-bootstrap sign fraction, not an established null-calibrated p-value")
    print(f"  {'statistic':<34}{'clean':>9}{'RITC':>9}{'contrast':>11}{'95% CI':>22}{'sign2':>8}")
    print("  " + "-" * 92)
    for name, fn, kind, th, note in tests:
        r = cluster_contrast(z, cluster, ritc, fn, kind, rng, thr=th,
                             bound_fn=nu_bound if fn is t_nu else None)
        ci = f"[{r['ci'][0]:+.2f}, {r['ci'][1]:+.2f}]" if r["ci"] else "     n/a"
        pv = f"{r['p']:.3f}" if r["p"] is not None else "  n/a"
        cl = f"{r['clean']:.2f}" if r["clean"] is not None else "n/a"
        ri = f"{r['ritc']:.2f}" if r["ritc"] is not None else "n/a"
        ob = f"{r['obs']:+.2f}" if r["obs"] is not None else "n/a"
        print(f"  {name:<34}{cl:>9}{ri:>9}{ob:>11}{ci:>22}{pv:>8}   ({note})")
        r["measures"] = MEASURES[name]
        if fn is t_nu:
            r["clip"] = list(NU_CLIP)
            for grp in ("ritc", "clean"):
                if r[grp + "_at_bound"]:
                    print("      %s group's nu is the %s CLIP bound %.0f, not an interior MLE"
                          % (grp, r[grp + "_at_bound"], r[grp]))
        res["tests"][name] = r
    store[label] = res


def main():
    rng = np.random.default_rng(SEED)
    with io.open(CAL, encoding="utf-8") as _fh:
        cal = json.load(_fh)
    strong, weak = assumed_business.strong_weak()
    print("RITC TAIL-SHAPE comparison of single-regime base-standardised z = s/sigma(R,HHI)")
    print(f"(cluster bootstrap {N_BOOT} resamples of syndicates; seed={SEED})")
    print(f"single-regime base scale: k={cal['k']:.4f} gamma={cal['gamma']:.4f} sd_undiv={cal['sd_undiv']:.4f} sd_div={cal['sd_div']:.4f}")
    store = {}
    run("CALIB (working sample)", load_calib_population(), strong, weak, cal, rng, store)
    run("N5 (rescaling pop)", select(build_population(), "N5"), strong, weak, cal, rng, store)
    with io.open(OUT, "w", encoding="utf-8", newline="") as _fh:
        _fh.write(json.dumps(store, indent=2))
    print(f"\nWrote {OUT}")
    print("\nStudent-t nu, the Hill index and far-spread ratio describe tail shape; read contrasts")
    print("with their intervals and any nu clipping. GPD xi uses a fixed pooled threshold and")
    print("can change under group rescaling, so its contrast alone does not establish a shape change.")
    print("q95/q99 ratios describe magnitudes and can change under rescaling alone.")


if __name__ == "__main__":
    main()
