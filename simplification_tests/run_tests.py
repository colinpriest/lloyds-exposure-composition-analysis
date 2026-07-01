"""
Empirical tests of four simplifications in the exposure-composition end model.

See docs/model-simplification-tests.md for the rationale, hypotheses, and
interpretation of results.  This script is deterministic (seed=42) and reads
only committed artefacts:

  - exposure_results.json           (the analysis bundle: observations, dispersion models)
  - pdf_extraction/syndicate_*.json  (raw extractions: claims triangles)

It writes simplification_tests/results.json and prints a summary.

Tests
  S2  age / maturity structure          -> is a triangle-derived maturity axis
                                           predictive of |PYD| after size+HHI?
  S3  vintage LoB mix vs current premix  -> how far does the current premium mix
                                           drift from the reserve-relevant mix,
                                           and does it move donor HHI / dispersion?
  S4  sequential vs simultaneous scaling -> is the joint (size,HHI) dispersion fit
                                           actually unstable, and is that driven by
                                           collinearity (as documented) or redundancy?
"""

import json
import glob
import math
import os
import sys
import collections

import numpy as np

np.random.seed(42)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, "exposure_results.json")
RAW_GLOB = os.path.join(ROOT, "pdf_extraction", "syndicate_*_*.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")

# Reuse the pipeline's own LoB mapping / projection so reconstructions stay faithful.
sys.path.insert(0, ROOT)
import run_analysis as ra          # noqa: E402
ra.log = lambda *a, **k: None      # silence pipeline logging on import/load

# long-tail (slow-developing) lines: Casualty, Professional Lines,
# Reinsurance-Casualty, Motor.  Used by S1 to test whether line *identity*
# predicts dispersion beyond the scalar HHI.
LONG_TAIL_IDX = [1, 9, 7, 4]

NORM = norm_cdf = lambda z: 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def cluster_ols(X, y, clusters):
    """OLS with cluster-robust (sandwich) SEs.  Returns beta, se, t, p, r2."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, k = X.shape
    XtX = X.T @ X
    XtX_inv = np.linalg.pinv(XtX)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta
    # cluster meat
    meat = np.zeros((k, k))
    G = 0
    for g in np.unique(clusters):
        m = clusters == g
        Xg = X[m]
        ug = resid[m]
        s = Xg.T @ ug
        meat += np.outer(s, s)
        G += 1
    dof = max(G - 1, 1)
    scale = (G / dof) * ((n - 1) / (n - k)) if n > k else 1.0
    V = scale * (XtX_inv @ meat @ XtX_inv)
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    t = np.divide(beta, se, out=np.zeros_like(beta), where=se > 0)
    p = np.array([2.0 * (1.0 - NORM(abs(tt))) for tt in t])
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    ss_res = float(np.sum(resid ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return dict(beta=beta.tolist(), se=se.tolist(), t=t.tolist(), p=p.tolist(),
                r2=r2, n=n, n_clusters=G)


def hellinger(p, q):
    p = np.asarray(p, float); q = np.asarray(q, float)
    return float(np.linalg.norm(np.sqrt(p) - np.sqrt(q)) / math.sqrt(2.0))


def winsorize(v, pct=95):
    cap = np.percentile(v, pct)
    return np.clip(v, None, cap)


def load_bundle():
    with open(BUNDLE, encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------------------
# S4 - sequential vs simultaneous dispersion scaling
# ----------------------------------------------------------------------------
def test_s4(bundle):
    obs = bundle["observations"]
    rows = [o for o in obs
            if o.get("s_raw_a") is not None
            and o.get("hhi") is not None
            and o.get("opening_reserves_gbp_m")
            and o["opening_reserves_gbp_m"] > 5.0]
    s = np.array([o["s_raw_a"] for o in rows], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in rows], float)
    H = np.array([o["hhi"] for o in rows], float)
    syn = np.array([o["syndicate"] for o in rows])
    logR = np.log(R)
    y = winsorize(s ** 2, 95)                      # same target family as the paper

    # (1) how associated are the two regressors, really?
    def pear(a, b):
        a = a - a.mean(); b = b - b.mean()
        return float((a @ b) / math.sqrt((a @ a) * (b @ b)))
    r_logR_H = pear(logR, H)
    r_logR_div = pear(logR, 1 - H)
    # rank corr
    def spear(a, b):
        ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
        return pear(ra.astype(float), rb.astype(float))
    rho = spear(logR, H)
    vif = 1.0 / (1.0 - r_logR_H ** 2)
    # design condition number for [1, logR, H] (standardised)
    Z = np.column_stack([(logR - logR.mean()) / logR.std(),
                         (H - H.mean()) / H.std()])
    cond = float(np.linalg.cond(np.column_stack([np.ones(len(Z)), Z])))

    # (2) linear joint vs single (cluster-robust), in-sample
    one = np.ones(len(y))
    m_size = cluster_ols(np.column_stack([one, logR]), y, syn)
    m_hhi = cluster_ols(np.column_stack([one, H]), y, syn)
    m_joint = cluster_ols(np.column_stack([one, logR, H]), y, syn)

    # (3) out-of-sample, syndicate-clustered 5-fold
    uniq = np.unique(syn)
    rng = np.random.RandomState(42)
    order = rng.permutation(uniq)
    folds = np.array_split(order, 5)

    def cv_r2(cols):
        num = den = 0.0
        for f in folds:
            te = np.isin(syn, f); tr = ~te
            Xtr = np.column_stack([c[tr] for c in cols]); Xte = np.column_stack([c[te] for c in cols])
            b = np.linalg.pinv(Xtr.T @ Xtr) @ (Xtr.T @ y[tr])
            pred = Xte @ b
            num += float(np.sum((y[te] - pred) ** 2))
            den += float(np.sum((y[te] - y[tr].mean()) ** 2))
        return 1.0 - num / den if den > 0 else float("nan")

    cv_size = cv_r2([one, logR])
    cv_hhi = cv_r2([one, H])
    cv_joint = cv_r2([one, logR, H])

    # (4) bootstrap stability of the joint linear coefficients (syndicate cluster)
    def boot(cols, B=400):
        ests = []
        for _ in range(B):
            pick = rng.choice(uniq, size=len(uniq), replace=True)
            idx = np.concatenate([np.where(syn == g)[0] for g in pick])
            Xb = np.column_stack([c[idx] for c in cols]); yb = y[idx]
            try:
                b = np.linalg.pinv(Xb.T @ Xb) @ (Xb.T @ yb)
                ests.append(b)
            except np.linalg.LinAlgError:
                pass
        ests = np.array(ests)
        return ests
    bj = boot([one, logR, H])
    # sign-stability of each joint slope across bootstrap (a separability symptom)
    frac_sign_logR = float(np.mean(np.sign(bj[:, 1]) == np.sign(m_joint["beta"][1])))
    frac_sign_H = float(np.mean(np.sign(bj[:, 2]) == np.sign(m_joint["beta"][2])))
    cv_slopes = {
        "logR_boot_cv_pct": float(100 * bj[:, 1].std() / abs(bj[:, 1].mean())) if bj[:, 1].mean() else None,
        "H_boot_cv_pct": float(100 * bj[:, 2].std() / abs(bj[:, 2].mean())) if bj[:, 2].mean() else None,
    }

    # (5) lift the delivered nonlinear joint fit + ordering from the bundle
    ec = bundle.get("exposure_composition", {}).get("dispersion_models", {})
    jc = bundle.get("joint_composition", {})
    delivered = {
        "joint_powerlaw": {k: ec.get("joint", {}).get(k) for k in
                           ("A", "p_A", "B1", "p_B1", "B2", "p_B2", "C1", "C2", "r_squared")},
        "stability_flags": ec.get("stability_flags"),
        "hhi_r_correlation": {k: jc.get("hhi_r_correlation", {}).get(k) for k in
                              ("pearson_r", "spearman_r", "p_pearson", "n")},
        "ordering_comparison": jc.get("ordering_comparison"),
        "variance_attribution": jc.get("variance_attribution"),
    }

    return {
        "n": len(y), "n_syndicates": int(len(uniq)),
        "regressor_association": {
            "pearson_logR_HHI": r_logR_H, "spearman_logR_HHI": rho,
            "pearson_logR_diversification": r_logR_div,
            "VIF": vif, "design_condition_number": cond,
        },
        "in_sample": {
            "size_only": {"beta_slope": m_size["beta"][1], "p_slope": m_size["p"][1], "r2": m_size["r2"]},
            "hhi_only": {"beta_slope": m_hhi["beta"][1], "p_slope": m_hhi["p"][1], "r2": m_hhi["r2"]},
            "joint": {"beta_logR": m_joint["beta"][1], "p_logR": m_joint["p"][1],
                      "beta_HHI": m_joint["beta"][2], "p_HHI": m_joint["p"][2], "r2": m_joint["r2"]},
        },
        "out_of_sample_cv_r2": {"size": cv_size, "hhi": cv_hhi, "joint": cv_joint,
                                "joint_gain_over_size_pp": 100 * (cv_joint - cv_size)},
        "joint_bootstrap": {"frac_sign_stable_logR": frac_sign_logR,
                            "frac_sign_stable_HHI": frac_sign_H, **cv_slopes},
        "delivered_model": delivered,
    }


# ----------------------------------------------------------------------------
# S3 - vintage LoB mix vs current premium-mix proxy
# ----------------------------------------------------------------------------
# generic "share of outstanding reserve by underwriting-year age" pattern used
# only to blend past mixes into a reserve-basis mix.  Results are reported both
# pattern-free (raw lag-k drift) and pattern-weighted.
VINTAGE_PATTERN = np.array([0.30, 0.25, 0.20, 0.13, 0.08, 0.04])


def test_s3(bundle):
    obs = [o for o in bundle["observations"] if o.get("weights") and o.get("year")]
    by_syn = collections.defaultdict(dict)     # syndicate -> {year: weight-vec}
    hhi_by = collections.defaultdict(dict)
    for o in obs:
        w = np.asarray(o["weights"], float)
        if w.sum() <= 0:
            continue
        w = w / w.sum()
        by_syn[o["syndicate"]][o["year"]] = w
        hhi_by[o["syndicate"]][o["year"]] = float(o.get("hhi") or (w ** 2).sum())

    # (a) pattern-free within-syndicate mix drift at lag k
    lag_dists = collections.defaultdict(list)
    for syn, yw in by_syn.items():
        yrs = sorted(yw)
        for i, t in enumerate(yrs):
            for k in range(1, 6):
                if t - k in yw:
                    lag_dists[k].append(hellinger(yw[t], yw[t - k]))
    lag_summary = {k: {"n": len(v), "median_hellinger": float(np.median(v)),
                       "p90_hellinger": float(np.percentile(v, 90))}
                   for k, v in sorted(lag_dists.items())}

    # (b) proxy error: current premium mix vs vintage-blended reserve mix
    proxy = []            # (syn, year, hellinger(premium, reserve-blend), dHHI, dispersion multiplier ratio)
    # combined dispersion V_HHI(HHI) from the bundle to translate dHHI into scale
    cm = bundle["joint_composition"]["combined_model"]["hhi"]
    A_h, B_h, C_h = cm["A"], cm["B"], cm["C"]
    v_hhi = lambda h: A_h + B_h * (max(h, 1e-6) ** C_h)
    for syn, yw in by_syn.items():
        yrs = sorted(yw)
        for t in yrs:
            past = [(t - k, yw[t - k]) for k in range(0, 6) if (t - k) in yw]
            if len(past) < 3:            # need enough history to form a vintage blend
                continue
            wts = VINTAGE_PATTERN[:len(past)].copy(); wts = wts / wts.sum()
            w_res = np.zeros(13)
            for (yr, wv), a in zip(past, wts):
                w_res += a * wv
            w_res /= w_res.sum()
            w_prem = yw[t]
            d = hellinger(w_prem, w_res)
            hhi_prem = float((w_prem ** 2).sum())
            hhi_res = float((w_res ** 2).sum())
            mult_ratio = math.sqrt(v_hhi(hhi_res) / v_hhi(hhi_prem)) if v_hhi(hhi_prem) > 0 else float("nan")
            proxy.append((syn, t, d, hhi_res - hhi_prem, mult_ratio))

    ds = np.array([p[2] for p in proxy]) if proxy else np.array([0.0])
    dhhi = np.array([p[3] for p in proxy]) if proxy else np.array([0.0])
    mult = np.array([p[4] for p in proxy]) if proxy else np.array([1.0])
    top = sorted(proxy, key=lambda p: -p[2])[:10]

    return {
        "panel_syndicates_used": len(by_syn),
        "lag_drift_pattern_free": lag_summary,
        "proxy_error": {
            "n": len(proxy),
            "median_hellinger_premium_vs_reserveblend": float(np.median(ds)),
            "p90_hellinger": float(np.percentile(ds, 90)),
            "median_abs_dHHI": float(np.median(np.abs(dhhi))),
            "p90_abs_dHHI": float(np.percentile(np.abs(dhhi), 90)),
            "median_dispersion_multiplier_ratio": float(np.median(mult)),
            "p90_dispersion_multiplier_ratio": float(np.percentile(mult, 90)),
            "pct_obs_multiplier_shift_gt_10pct": float(100 * np.mean(np.abs(mult - 1) > 0.10)),
        },
        "top_mix_shifters": [
            {"syndicate": int(s), "year": int(y), "hellinger": round(d, 3),
             "dHHI": round(dh, 3), "dispersion_mult_ratio": round(m, 3)}
            for (s, y, d, dh, m) in top
        ],
    }


# ----------------------------------------------------------------------------
# S2 - age / maturity structure from claims triangles
# ----------------------------------------------------------------------------
def _triangle_maturity(tri, report_year):
    """Reserve-weighted average development age from a runoff triangle.

    Orientation-robust: columns are aligned to underwriting_years; if the row
    count matches len(uw) instead, the matrix is transposed.  For each UW year
    we take its latest (most-developed) non-null incurred as the weight and
    age = report_year - uw_year.  Returns (maturity_years, young_share, n_uw)."""
    uw = tri.get("underwriting_years")
    rows = tri.get("development_rows")
    if not uw or not rows:
        return None
    # rows can be ragged -> pad to common width with NaN
    ncol = max(len(r) for r in rows)
    padded = []
    for r in rows:
        vals = [np.nan if v is None else float(v) for v in r]
        vals += [np.nan] * (ncol - len(vals))
        padded.append(vals)
    M = np.array(padded, float)
    if M.shape[1] != len(uw) and M.shape[0] == len(uw):
        M = M.T
    if M.shape[1] != len(uw):
        return None
    weights, ages = [], []
    for j, y in enumerate(uw):
        col = M[:, j]
        col = col[~np.isnan(col)]
        if col.size == 0:
            continue
        latest = col[-1]                 # last non-null down the column = most developed
        if latest <= 0:
            continue
        weights.append(latest)
        ages.append(report_year - int(y))
    if not weights:
        return None
    w = np.array(weights); a = np.array(ages, float)
    w = w / w.sum()
    maturity = float((w * a).sum())
    young_share = float(w[a <= 2].sum())
    return maturity, young_share, len(weights)


def test_s2(bundle):
    # index observations by (syn, year) for the response
    obs_ix = {(o["syndicate"], o["year"]): o for o in bundle["observations"]}
    recs = []
    for f in glob.glob(RAW_GLOB):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        models = d.get("models") or {}
        recset = list(models.values()) if isinstance(models, dict) else []
        # pull triangle (prefer _claims_triangle then _rag_triangle) + syn/year
        tri = None; syn = None; yr = None
        for r in recset + ([d] if not recset else []):
            if not isinstance(r, dict):
                continue
            syn = r.get("syndicate", syn); yr = r.get("year", yr)
            tri = tri or r.get("_claims_triangle") or r.get("_rag_triangle")
        if tri is None:
            # also look at file top level
            tri = d.get("_claims_triangle") or d.get("_rag_triangle")
            for r in recset:
                if isinstance(r, dict):
                    syn = syn or r.get("syndicate"); yr = yr or r.get("year")
        if tri is None or syn is None or yr is None:
            continue
        o = obs_ix.get((syn, yr))
        if not o or o.get("s_raw_a") is None or not o.get("opening_reserves_gbp_m"):
            continue
        mt = _triangle_maturity(tri, int(yr))
        if mt is None:
            continue
        maturity, young, n_uw = mt
        recs.append(dict(syn=syn, year=yr, maturity=maturity, young=young,
                         s=o["s_raw_a"], absS=abs(o["s_raw_a"]),
                         R=o["opening_reserves_gbp_m"], H=o.get("hhi") or 0.0))

    if len(recs) < 30:
        return {"status": "insufficient", "n": len(recs)}

    maturity = np.array([r["maturity"] for r in recs])
    absS = np.array([r["absS"] for r in recs])
    logR = np.log(np.array([r["R"] for r in recs]))
    H = np.array([r["H"] for r in recs])
    syn = np.array([r["syn"] for r in recs])
    one = np.ones(len(recs))

    # correlation and controlled regression of |PYD| on maturity
    def pear(a, b):
        a = a - a.mean(); b = b - b.mean()
        return float((a @ b) / math.sqrt((a @ a) * (b @ b)))
    r_absS_maturity = pear(absS, maturity)
    m_ctrl = cluster_ols(np.column_stack([one, maturity, logR, H]), absS, syn)
    m_sq = cluster_ols(np.column_stack([one, maturity, logR, H]), winsorize(absS ** 2, 95), syn)

    return {
        "status": "ok", "n": len(recs), "n_syndicates": int(len(np.unique(syn))),
        "maturity_summary": {"median_years": float(np.median(maturity)),
                             "p10": float(np.percentile(maturity, 10)),
                             "p90": float(np.percentile(maturity, 90))},
        "corr_absPYD_maturity": r_absS_maturity,
        "regression_absPYD": {  # y = |PYD ratio| ~ maturity + logR + HHI
            "maturity_coef": m_ctrl["beta"][1], "maturity_p": m_ctrl["p"][1],
            "logR_coef": m_ctrl["beta"][2], "logR_p": m_ctrl["p"][2],
            "HHI_coef": m_ctrl["beta"][3], "HHI_p": m_ctrl["p"][3],
            "r2": m_ctrl["r2"]},
        "regression_sqPYD": {
            "maturity_coef": m_sq["beta"][1], "maturity_p": m_sq["p"][1], "r2": m_sq["r2"]},
    }


def build_panel(records):
    """syndicate -> {year: 13-dim normalised weight vector} from pipeline records."""
    panel = collections.defaultdict(dict)
    for r in records:
        w = np.asarray(r.get("weights") or [], float)
        if w.size != 13 or w.sum() <= 0 or not r.get("year"):
            continue
        panel[r["syndicate"]][r["year"]] = w / w.sum()
    return panel


def reserve_blend(panel, syn, year, min_hist=3):
    """Vintage-blended reserve mix from a syndicate's own past premium mixes."""
    yw = panel.get(syn, {})
    past = [(year - k, yw[year - k]) for k in range(0, 6) if (year - k) in yw]
    if len(past) < min_hist:
        return None
    wts = VINTAGE_PATTERN[:len(past)].copy(); wts = wts / wts.sum()
    w_res = np.zeros(13)
    for (_, wv), a in zip(past, wts):
        w_res += a * wv
    return w_res / w_res.sum()


def reconstruct_movements(record):
    """Signed 13-dim LoB movement vector + observed-index set, faithful to the
    pipeline's mapping/sign logic (run_analysis.py lines ~536-573)."""
    M = np.zeros(13); observed = set()
    for mv in (record.get("lob_movements") or []):
        amt = ra.safe_float(mv.get("amount_gbp_m"))
        if amt is None:
            continue
        idx = ra.classify_lob(mv.get("line_of_business", ""))
        d = (mv.get("direction", "") or "").lower().strip()
        if d == "release" and amt > 0:
            amt = -amt
        elif d in ("strengthening", "adverse") and amt < 0:
            amt = -amt
        M[idx] += amt; observed.add(idx)
    return M, observed


def s_lob_under_weights(M, observed, R, w):
    """LoB severities for observed lines under a given donor weight vector."""
    s = np.zeros(13)
    for idx in observed:
        r_lob = R * max(w[idx], 0.01)
        if r_lob > 0:
            s[idx] = float(np.clip(M[idx] / r_lob, -5.0, 5.0))
    return s


# ----------------------------------------------------------------------------
# S1 - does specific LoB composition add dispersion info beyond (size, HHI)?
# ----------------------------------------------------------------------------
def test_s1(records):
    rows = [r for r in records
            if r.get("s_raw_a") is not None and r.get("hhi") is not None
            and r.get("opening_reserves_gbp_m") and r["opening_reserves_gbp_m"] > 5.0
            and r.get("weights") and sum(r["weights"]) > 0]
    s = np.array([r["s_raw_a"] for r in rows], float)
    R = np.array([r["opening_reserves_gbp_m"] for r in rows], float)
    H = np.array([r["hhi"] for r in rows], float)
    W = np.array([r["weights"] for r in rows], float)
    syn = np.array([r["syndicate"] for r in rows])
    logR = np.log(R)
    y = winsorize(s ** 2, 95)
    long_tail = W[:, LONG_TAIL_IDX].sum(axis=1)
    dominant = W.argmax(axis=1)
    one = np.ones(len(y))

    # (1) does line identity shift the MEAN of PYD? (pure-dispersion check)
    m_dir = cluster_ols(np.column_stack([one, long_tail]), s, syn)

    # (2) does it add to DISPERSION beyond size+HHI? long-tail-share coefficient
    base = cluster_ols(np.column_stack([one, logR, H]), y, syn)
    aug = cluster_ols(np.column_stack([one, logR, H, long_tail]), y, syn)

    # dominant-LoB fixed effects (group rare dominants into 'other')
    counts = collections.Counter(dominant.tolist())
    keep = [k for k, c in counts.items() if c >= 15]
    dum = np.column_stack([(dominant == k).astype(float) for k in keep]) if keep else np.zeros((len(y), 0))
    Xd = np.column_stack([one, logR, H, dum])
    aug_dom = cluster_ols(Xd, y, syn)

    # (3) out-of-sample, syndicate-clustered 5-fold
    uniq = np.unique(syn); rng = np.random.RandomState(42)
    folds = np.array_split(rng.permutation(uniq), 5)

    def cv_r2(X):
        num = den = 0.0
        for f in folds:
            te = np.isin(syn, f); tr = ~te
            b = np.linalg.pinv(X[tr].T @ X[tr]) @ (X[tr].T @ y[tr])
            num += float(np.sum((y[te] - X[te] @ b) ** 2))
            den += float(np.sum((y[te] - y[tr].mean()) ** 2))
        return 1.0 - num / den if den > 0 else float("nan")

    cv_base = cv_r2(np.column_stack([one, logR, H]))
    cv_lt = cv_r2(np.column_stack([one, logR, H, long_tail]))
    cv_dom = cv_r2(Xd)

    return {
        "n": len(y), "n_syndicates": int(len(uniq)),
        "long_tail_share_summary": {"median": float(np.median(long_tail)),
                                    "p90": float(np.percentile(long_tail, 90))},
        "mean_channel": {"long_tail_coef_on_signed_PYD": m_dir["beta"][1],
                         "p": m_dir["p"][1],
                         "note": "insignificant => line identity does not shift the mean (pure-dispersion holds)"},
        "dispersion_channel": {
            "base_r2": base["r2"],
            "long_tail_coef": aug["beta"][3], "long_tail_p": aug["p"][3],
            "delta_r2_add_long_tail": aug["r2"] - base["r2"],
            "dominant_fe_kept_lobs": [ra.LOB_NAMES[k] for k in keep],
            "delta_r2_add_dominant_fe": aug_dom["r2"] - base["r2"],
        },
        "out_of_sample_cv_r2": {"base_sizeHHI": cv_base,
                                "plus_long_tail": cv_lt, "plus_dominant_fe": cv_dom,
                                "long_tail_gain_pp": 100 * (cv_lt - cv_base),
                                "dominant_gain_pp": 100 * (cv_dom - cv_base)},
    }


# ----------------------------------------------------------------------------
# S3b - fuller materiality: VaR of mix-projected severity, current-premium mix
#       vs vintage-blended reserve mix, for each test portfolio.
# ----------------------------------------------------------------------------
def test_s3_materiality(records):
    panel = build_panel(records)
    donors = [r for r in records
              if r.get("lob_severity_computed") and r.get("opening_reserves_gbp_m")
              and r.get("s_raw_a") is not None
              and any(mv.get("amount_gbp_m") is not None for mv in (r.get("lob_movements") or []))]

    # dense market-average mix (equal-weighted, matches the spec reference mix) so
    # every donor's projection is non-zero and premix/reserveblend are comparable.
    allw = np.array([np.asarray(r["weights"], float) / sum(r["weights"])
                     for r in records if r.get("weights") and sum(r["weights"]) > 0])
    market_avg = allw.mean(axis=0)

    built = []          # (syn, s_prem, s_res)
    line_rel_changes = []   # projection-free: relative change of each observed-line severity
    for r in donors:
        w_res = reserve_blend(panel, r["syndicate"], r["year"])
        if w_res is None:
            continue
        w_prem = np.asarray(r["weights"], float); w_prem = w_prem / w_prem.sum()
        M, observed = reconstruct_movements(r)
        if not observed:
            continue
        R = r["opening_reserves_gbp_m"]
        s_prem = s_lob_under_weights(M, observed, R, w_prem)
        s_res = s_lob_under_weights(M, observed, R, w_res)
        for idx in observed:
            if abs(s_prem[idx]) > 1e-9:
                line_rel_changes.append(abs(s_res[idx] - s_prem[idx]) / abs(s_prem[idx]))
        built.append((r["syndicate"], s_prem, s_res))

    lrc = np.array(line_rel_changes) if line_rel_changes else np.array([0.0])

    def q(a, p):
        return float(np.percentile(a, p))

    def var_shift(wq, min_nonzero=1e-6):
        sp = np.array([float(np.dot(wq, sp_)) for _, sp_, _ in built])
        sr = np.array([float(np.dot(wq, sr_)) for _, _, sr_ in built])
        nz = np.abs(sp) > min_nonzero
        out = {"n_nonzero": int(nz.sum())}
        for lab, pct in [("Q75", 75), ("VaR90", 90), ("VaR95", 95), ("VaR99", 99)]:
            vp, vr = q(sp, pct), q(sr, pct)
            out[lab] = {"premix": round(vp, 4), "reserveblend": round(vr, 4),
                        "pct": round(100 * (vr - vp) / abs(vp), 1) if abs(vp) > min_nonzero else None}
        out["median_abs_rel_change_Smix"] = round(float(np.median(
            np.abs(sr[nz] - sp[nz]) / np.abs(sp[nz]))), 3) if nz.any() else None
        return out

    return {
        "n_donors_observed_amounts": len(donors),
        "n_donors_with_reserve_blend": len(built),
        "line_severity_distortion": {   # projection-free: how much each observed line's severity moves
            "n_line_cells": int(len(lrc)),
            "median_rel_change": float(np.median(lrc)),
            "p90_rel_change": float(np.percentile(lrc, 90)),
            "pct_cells_gt_25pct": float(100 * np.mean(lrc > 0.25)),
        },
        "market_average_projection": var_shift(market_avg),
        "test_portfolios": [{"portfolio": s["name"], **var_shift(np.asarray(ra.portfolio_weights_vector(s), float))}
                            for s in ra.TEST_PORTFOLIOS],
        "tail_support_note": "narrow test portfolios: only n_nonzero donors overlap the target lines; "
                             "market-average and line-level metrics are the reliable materiality signal",
    }


def load_records():
    out = ra.load_and_classify()
    return out[0] if isinstance(out, tuple) else out


def main():
    b = load_bundle()
    records = load_records()
    results = {
        "seed": 42,
        "S1_lob_agnostic_dispersion": test_s1(records),
        "S4_sequential_vs_simultaneous": test_s4(b),
        "S3_vintage_mix_vs_premium_proxy": test_s3(b),
        "S3b_vintage_mix_materiality": test_s3_materiality(records),
        "S2_age_maturity_structure": test_s2(b),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("wrote", OUT)
    # concise console summary
    s1 = results["S1_lob_agnostic_dispersion"]
    print("\n=== S1 LoB-agnostic dispersion ===")
    print("  mean channel: long_tail coef on signed PYD p=%.3f (want n.s.)" % s1["mean_channel"]["p"])
    print("  dispersion: long_tail p=%.3f dR2=%.4f | dominant-FE dR2=%.4f"
          % (s1["dispersion_channel"]["long_tail_p"], s1["dispersion_channel"]["delta_r2_add_long_tail"],
             s1["dispersion_channel"]["delta_r2_add_dominant_fe"]))
    print("  OOS gain (pp): long_tail=%.2f dominant=%.2f"
          % (s1["out_of_sample_cv_r2"]["long_tail_gain_pp"], s1["out_of_sample_cv_r2"]["dominant_gain_pp"]))
    s3m = results["S3b_vintage_mix_materiality"]
    print("\n=== S3b vintage-mix materiality ===")
    print("  donors: %d observed-amount (%d with reserve blend)"
          % (s3m["n_donors_observed_amounts"], s3m["n_donors_with_reserve_blend"]))
    lsd = s3m["line_severity_distortion"]
    print("  line-severity distortion: median=%.2f p90=%.2f  %.0f%% of lines move >25%%"
          % (lsd["median_rel_change"], lsd["p90_rel_change"], lsd["pct_cells_gt_25pct"]))
    ma = s3m["market_average_projection"]
    print("  market-avg S_mix VaR95 premix=%.3f reserveblend=%.3f (%s%%) | med|dSmix/Smix|=%s"
          % (ma["VaR95"]["premix"], ma["VaR95"]["reserveblend"], ma["VaR95"]["pct"], ma["median_abs_rel_change_Smix"]))
    s4 = results["S4_sequential_vs_simultaneous"]
    print("\n=== S4 sequential vs simultaneous ===")
    print("  regressor assoc:", {k: round(v, 3) for k, v in s4["regressor_association"].items()})
    print("  in-sample joint: p(logR)=%.3f p(HHI)=%.3f r2=%.3f"
          % (s4["in_sample"]["joint"]["p_logR"], s4["in_sample"]["joint"]["p_HHI"], s4["in_sample"]["joint"]["r2"]))
    print("  OOS cv r2:", {k: round(v, 4) for k, v in s4["out_of_sample_cv_r2"].items()})
    print("  ordering:", s4["delivered_model"]["ordering_comparison"].get("recommendation"),
          "| size-first %.1f%% hhi-first %.1f%%" % (
              s4["delivered_model"]["ordering_comparison"]["total_explained_size_first"],
              s4["delivered_model"]["ordering_comparison"]["total_explained_hhi_first"]))
    s3 = results["S3_vintage_mix_vs_premium_proxy"]
    print("\n=== S3 vintage mix vs premium proxy ===")
    print("  lag drift:", {k: round(v["median_hellinger"], 3) for k, v in s3["lag_drift_pattern_free"].items()})
    print("  proxy error:", {k: round(v, 3) for k, v in s3["proxy_error"].items() if isinstance(v, float)})
    s2 = results["S2_age_maturity_structure"]
    print("\n=== S2 age/maturity ===")
    if s2.get("status") == "ok":
        print("  n=%d corr(|PYD|,maturity)=%.3f  maturity_coef p=%.3f  r2=%.3f"
              % (s2["n"], s2["corr_absPYD_maturity"],
                 s2["regression_absPYD"]["maturity_p"], s2["regression_absPYD"]["r2"]))
    else:
        print("  ", s2)


if __name__ == "__main__":
    main()
