"""Does external RITC break the operator's invariance assumptions?

The transfer operator assumes the severity  s = signed_pyd / opening_reserves  is a
*scale family with location 0*:

    location = 0                      (mean-zero, fixed)
    scale    = sigma(R, HHI)          (the fitted pooling/concentration/floor model)
    SHAPE    = invariant              (same standardised distribution everywhere)

RITC (reinsurance-to-close of another syndicate's account) injects a lumpy step change
into PYD that is NOT a function of (R, HHI).  It could therefore break invariance in two
distinct ways, and we test each separately:

  (A) SCALE invariance under the operator.  z = s / sigma(R,HHI).  If RITC years have a
      larger spread in z than clean years, the (R,HHI) model under-scales them -- RITC
      carries extra variance the operator cannot see.  (Robust: Fligner-Killeen + a
      cluster-bootstrap IQR ratio.)

  (B) SHAPE invariance.  Remove location AND scale (each group standardised by its own
      median / IQR) and compare the残 standardised SHAPE (Bowley skew, tail-skew ratio,
      Moors kurtosis, k-sample Anderson-Darling).  If RITC has a different standardised
      shape, transporting an RITC donor's shape to a clean target is unjustified even
      after correct scaling.

  (C) OMNIBUS.  k-sample Anderson-Darling on the operator-standardised z itself (clean vs
      RITC) -- the joint scale+shape test of "is the operator-standardised residual the
      same distribution regardless of RITC?".

All p-values use a CLUSTER bootstrap resampling *syndicates*.  Shape stats reuse
test_shape_invariance.py so the methodology is identical to the size/HHI axes.

Run:  python ritc_shape_invariance.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats

import run_analysis as ra
from test_shape_invariance import (
    build_population, select, bowley_skew, tail_skew_ratio, moors_kurt,
    robust_scale, anderson_ksample_shape, cluster_bootstrap_diff, _q,
)

SCRIPT_DIR = Path(__file__).resolve().parent
CAL = SCRIPT_DIR / "dispersion_calibration.json"
RITC = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
OUT = SCRIPT_DIR / "ritc_shape_invariance_results.json"
SEED = 12345
N_BOOT = 4000
SHAPE_STATS = {"Bowley skew": bowley_skew, "Tail skew ratio": tail_skew_ratio,
               "Moors kurtosis": moors_kurt}


def sigma_op(R, HHI, cal):
    """Operator dispersion sigma(R,HHI) at the posterior-mean parameters (no year shock)."""
    ref = cal["reference_size"]; k = cal["k"]; g = cal["gamma"]
    su = cal["sd_undiv"]; sd = cal["sd_div"]
    hh = np.clip(HHI, cal.get("hhi_floor", 0.01), cal.get("hhi_ceil", 1.0))
    log_reff = np.log(R / ref) - g * np.log(hh)
    return np.sqrt(su ** 2 + sd ** 2 * np.exp(2.0 * (k - 1.0) * log_reff))


def mad(a):
    return float(np.median(np.abs(a - np.median(a))))


def cluster_bootstrap_ratio(vals, cluster, group, scale_fn, g_num, g_den, rng, n=N_BOOT):
    """Cluster-bootstrap CI for scale_fn(group==g_num) / scale_fn(group==g_den)."""
    clusters = np.unique(cluster)
    idx = {c: np.where(cluster == c)[0] for c in clusters}
    out = []
    for _ in range(n):
        pick = rng.choice(clusters, size=len(clusters), replace=True)
        rows = np.concatenate([idx[c] for c in pick])
        vg, gg = vals[rows], group[rows]
        a, b = vg[gg == g_num], vg[gg == g_den]
        if len(a) < 8 or len(b) < 8:
            continue
        da, db = scale_fn(a), scale_fn(b)
        if db > 0:
            out.append(da / db)
    out = np.array([x for x in out if np.isfinite(x)])
    if len(out) < n * 0.5:
        return None
    lo, hi = np.percentile(out, [2.5, 97.5])
    p = 2.0 * min((out <= 1.0).mean(), (out >= 1.0).mean())
    return {"ratio": float(np.median(out)), "ci": (float(lo), float(hi)),
            "p": float(min(p, 1.0)), "n_boot": len(out)}


def load_calib_population():
    """The exact population calibrate_dispersion.py fits on (n=790), with syndicate+key."""
    d = json.load(io.open(SCRIPT_DIR / "exposure_results.json", encoding="utf-8"))
    rows = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    return rows


def analyse(label, rows, strong, weak, cal, rng, out_store):
    s = np.array([x["s_raw_a"] for x in rows], float)
    R = np.array([x["opening_reserves_gbp_m"] for x in rows], float)
    HHI = np.array([x["hhi"] for x in rows], float)
    cluster = np.array([x["syndicate"] for x in rows])
    key = np.array([f"{x['syndicate']}_{x['year']}" for x in rows])
    isS = np.array([k in strong for k in key])
    isW = np.array([k in weak for k in key])
    ritc = isS | isW
    z = s / sigma_op(R, HHI, cal)   # operator-standardised residual

    g3 = np.where(isS, 2, np.where(isW, 1, 0))
    gb = ritc.astype(int)
    n_syn = len(np.unique(cluster))
    print(f"\n{'#'*74}\n#  POPULATION: {label}   n={len(s)}  syndicates={n_syn}  "
          f"clean={int((~ritc).sum())}  weak={int(isW.sum())}  strong={int(isS.sum())}\n{'#'*74}")

    # ── descriptive table ────────────────────────────────────────────────────
    def desc(name, m):
        a, zz = s[m], z[m]
        print(f"  {name:<10}{m.sum():>5}  s_med={_q(a,50):+.4f}  IQR(s)={robust_scale(a):.4f}  "
              f"z_med={_q(zz,50):+.3f}  IQR(z)={robust_scale(zz):.3f}  MAD(z)={mad(zz):.3f}  "
              f"sd(z)={zz.std():.3f}  |  Bowley={bowley_skew(a):+.3f}  tailR={tail_skew_ratio(a):.2f}  "
              f"Moors={moors_kurt(a):.3f}")
    print("  DESCRIPTIVE (z = s / sigma_operator):")
    desc("clean", ~ritc); desc("weak", isW); desc("strong", isS)
    desc("all RITC", ritc); desc("ALL", np.ones(len(s), bool))

    res = {"meta": {"n": int(len(s)), "n_syndicates": int(n_syn),
                    "clean": int((~ritc).sum()), "weak": int(isW.sum()), "strong": int(isS.sum()),
                    "operator": {kk: cal[kk] for kk in ("k", "gamma", "sd_undiv", "sd_div", "reference_size")},
                    "seed": SEED, "n_boot": N_BOOT}}

    # ── (A) SCALE invariance under the operator ──────────────────────────────
    print(f"\n{'='*74}\n  (A) SCALE INVARIANCE under the operator:  spread of z = s/sigma(R,HHI)\n{'='*74}")
    fk = stats.fligner(z[~ritc], z[ritc])
    lev = stats.levene(z[~ritc], z[ritc], center="median")
    print(f"  Fligner-Killeen (clean vs RITC equal scale?):  chi2={fk.statistic:.2f}  p={fk.pvalue:.3f}")
    print(f"  Brown-Forsythe Levene (median-centred):        W={lev.statistic:.2f}  p={lev.pvalue:.3f}")
    res["scale"] = {"fligner_p": float(fk.pvalue), "levene_p": float(lev.pvalue), "ratios": {}}
    for lab, fn in [("IQR(z)", robust_scale), ("MAD(z)", mad), ("SD(z)", lambda a: float(np.std(a)))]:
        rr = cluster_bootstrap_ratio(z, cluster, gb, fn, 1, 0, rng)
        if rr:
            sig = "  *** " if rr["p"] < 0.05 else "      "
            print(f"    {lab:<8} RITC/clean ratio = {rr['ratio']:.3f}  "
                  f"95% CI [{rr['ci'][0]:.3f}, {rr['ci'][1]:.3f}]  p={rr['p']:.3f}{sig}")
            res["scale"]["ratios"][lab] = rr
    for gname, code in [("strong", 2), ("weak", 1)]:
        gg = np.where(g3 == code, 1, np.where(g3 == 0, 0, -1))
        keep = gg >= 0
        rr = cluster_bootstrap_ratio(z[keep], cluster[keep], gg[keep], robust_scale, 1, 0, rng)
        if rr:
            print(f"      IQR(z) {gname:<6}/clean ratio = {rr['ratio']:.3f}  "
                  f"95% CI [{rr['ci'][0]:.3f}, {rr['ci'][1]:.3f}]  p={rr['p']:.3f}")
            res["scale"]["ratios"][f"IQR_{gname}"] = rr

    # ── (B) SHAPE invariance (location+scale removed) ────────────────────────
    print(f"\n{'='*74}\n  (B) SHAPE INVARIANCE:  standardised skew / kurtosis / tail asymmetry\n{'='*74}")
    ad_shape = anderson_ksample_shape(s, gb)
    verdict = "SHAPE DIFFERS" if ad_shape["p"] < 0.05 else "no shape difference"
    print(f"  Anderson-Darling k-sample (group-standardised, clean vs RITC): "
          f"A2k={ad_shape['stat']:.2f}  p={ad_shape['p']:.3f}  -> {verdict}")
    ad_shape3 = anderson_ksample_shape(s, g3)
    print(f"  Anderson-Darling k-sample (clean vs weak vs strong):           "
          f"A2k={ad_shape3['stat']:.2f}  p={ad_shape3['p']:.3f}")
    res["shape"] = {"ad_clean_vs_ritc": ad_shape, "ad_three_way": ad_shape3, "diffs": {}}
    print(f"\n  RITC - clean standardised-shape difference (cluster bootstrap):")
    for lab, fn in SHAPE_STATS.items():
        rr = cluster_bootstrap_diff(s, cluster, gb, fn, 1, 0, rng, n=N_BOOT)
        if rr:
            sig = "  *** " if rr["p"] < 0.05 else "      "
            print(f"    {lab:<16} diff={rr['point']:+.3f}  "
                  f"95% CI [{rr['ci'][0]:+.3f}, {rr['ci'][1]:+.3f}]  p={rr['p']:.3f}{sig}")
            res["shape"]["diffs"][lab] = rr

    # ── (C) OMNIBUS on operator-standardised z ───────────────────────────────
    print(f"\n{'='*74}\n  (C) OMNIBUS:  is operator-standardised z the same distribution?  (scale+shape)\n{'='*74}")
    with np.errstate(all="ignore"):
        adz = stats.anderson_ksamp([z[~ritc], z[ritc]])
    pz = getattr(adz, "pvalue", None) or adz.significance_level
    print(f"  Anderson-Darling k-sample on z (clean vs RITC, NOT re-scaled): "
          f"A2k={adz.statistic:.2f}  p={float(pz):.3f}  -> "
          f"{'DIFFERS' if pz < 0.05 else 'consistent'}")
    ks = stats.ks_2samp(z[~ritc], z[ritc])
    print(f"  KS 2-sample on z (clean vs RITC):  D={ks.statistic:.3f}  p={ks.pvalue:.3f}")
    res["omnibus_z"] = {"ad_stat": float(adz.statistic), "ad_p": float(pz),
                        "ks_stat": float(ks.statistic), "ks_p": float(ks.pvalue)}

    # ── (D) TAIL over-representation: does RITC inject the standardised tail? ─
    print(f"\n{'='*74}\n  (D) TAIL: are RITC obs over-represented in the extreme |z| tail?\n{'='*74}")
    az_ = np.abs(z); base = ritc.mean()
    res["tail"] = {"base_rate_ritc": float(base), "levels": {}}
    for q in (90, 95):
        thr = np.percentile(az_, q)
        intail = az_ > thr
        # 2x2: RITC x in-tail  -> Fisher exact odds ratio
        a11 = int((ritc & intail).sum()); a10 = int((ritc & ~intail).sum())
        a01 = int((~ritc & intail).sum()); a00 = int((~ritc & ~intail).sum())
        orr, pf = stats.fisher_exact([[a11, a10], [a01, a00]])
        frac = a11 / max(intail.sum(), 1)
        print(f"    top {100-q:>2}% |z| (thr={thr:.2f}, {int(intail.sum())} obs):  RITC frac={frac:.2f} "
              f"(base {base:.2f})  odds ratio={orr:.2f}  Fisher p={pf:.3f}"
              f"{'  *** ' if pf < 0.05 else ''}")
        res["tail"]["levels"][f"top_{100-q}pct"] = {
            "threshold": float(thr), "n_in_tail": int(intail.sum()),
            "ritc_frac_in_tail": float(frac), "odds_ratio": float(orr), "fisher_p": float(pf)}

    out_store[label] = res


def main():
    rng = np.random.default_rng(SEED)
    cal = json.load(io.open(CAL, encoding="utf-8"))
    r = json.load(io.open(RITC, encoding="utf-8"))
    strong = {k for k, v in r.items() if v.get("ritc_occurred") and v.get("confidence") == "strong"}
    weak = {k for k, v in r.items() if v.get("ritc_occurred") and v.get("confidence") == "weak"}

    print("RITC shape/scale-invariance tests")
    print(f"(cluster bootstrap: {N_BOOT} resamples of syndicates; seed={SEED})")
    print(f"operator: k={cal['k']:.4f} gamma={cal['gamma']:.4f} "
          f"sd_undiv={cal['sd_undiv']:.4f} sd_div={cal['sd_div']:.4f}")

    store = {}
    # PRIMARY: the full calibration population (n=790) -> matches the nu result & max power
    analyse("CALIB (n=790)", load_calib_population(), strong, weak, cal, rng, store)
    # SENSITIVITY: the strict N5 rescaling population
    records = build_population()
    analyse("N5 (rescaling pop)", select(records, "N5"), strong, weak, cal, rng, store)

    OUT.write_text(json.dumps(store, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")
    print("\nRead-out:  (A) scale ratio CI excluding 1 => operator under-scales RITC.")
    print("           (B) AD p<0.05 or shape-diff CI excluding 0 => RITC has a different standardised SHAPE.")
    print("           (C) omnibus: is the operator-standardised residual the same law regardless of RITC?")
    print("           (D) Fisher OR>1 => RITC over-represented in the standardised tail (the nu channel).")


if __name__ == "__main__":
    main()
