"""Compare clean and assumed-business observations after base-scale standardisation.

Severity s = signed_pyd / reserve base is divided by the posterior-mean size,
concentration and floor scale from model/dispersion_calibration.json: the older
single-regime, gamma-free calibration, not the adopted two-regime headline fit.
Neither a reporting-year multiplier nor a separate assumed-business multiplier is
divided out, so both can remain in z. RITC is the historical shorthand here for the
broader assumed-business flag, including confirmed inward transfers and take-ons.

RITC (reinsurance-to-close of another syndicate's account) can introduce a step in
observed PYD or change the cohort mix and subsequent development. It could break invariance in two
distinct ways, and we test each separately:

  (A) SPREAD of z = s / sigma(R,HHI). The group contrast describes spread after
      this standardisation; retained year and regime effects prevent attributing it
      uniquely to the fitted base scale. (Fligner-Killeen + cluster-bootstrap IQR ratio.)

  (B) SHAPE invariance.  Remove location AND scale (each group standardised by its own
      median / IQR) and compare the standardised SHAPE (Bowley skew, tail-skew ratio,
      Moors kurtosis, k-sample Anderson-Darling).  If RITC has a different standardised
      shape, a common standardised-shape assumption would be challenged.

  (C) OMNIBUS.  k-sample Anderson-Darling on the base-standardised z itself (clean vs
      RITC) -- a joint scale+shape comparison of "is the base-standardised residual the
      same distribution regardless of RITC?".

Calibration, stated exactly because it differs between the numbers printed here.
The ratio and shape-difference intervals use a CLUSTER bootstrap resampling syndicates,
preserving their within-syndicate rows. The legacy p fields are twice the smaller
observed-bootstrap sign fraction without null centering, not established as
null-calibrated p-values. The Fligner-Killeen, Levene,
k-sample Anderson-Darling, KS and Fisher exact figures are ordinary library tests on
rows: they assume independent observations, which this panel does not satisfy, so they
may be miscalibrated or anti-conservative here and are descriptive rather than calibrated.
Shape stats reuse test_shape_invariance.py so the methodology is identical to the
size/HHI axes.

Run:  python src/ritc_shape_invariance.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats

import run_analysis as ra
from test_shape_invariance import (
    build_population, select, bowley_skew, tail_skew_ratio, moors_kurt,
    robust_scale, anderson_ksample_shape, cluster_bootstrap_diff, _q,
    ROW_TEST_NOTE, BOOTSTRAP_SIGN_NOTE,
)
import assumed_business

SCRIPT_DIR = Path(__file__).resolve().parent.parent
CAL = SCRIPT_DIR / "model" / "dispersion_calibration.json"
CALIBRATION_SOURCE = "model/dispersion_calibration.json (single-regime, gamma-free)"
STANDARDISATION_NOTE = "single-regime base scale only; reporting-year and assumed-business scale effects remain in z"
RITC = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
OUT = SCRIPT_DIR / "results" / "ritc_shape_invariance_results.json"
SEED = 12345
N_BOOT = 4000
SHAPE_STATS = {"Bowley skew": bowley_skew, "Tail skew ratio": tail_skew_ratio,
               "Moors kurtosis": moors_kurt}


def sigma_op(R, HHI, cal):
    """Single-regime base dispersion at posterior means; no year or regime multiplier."""
    ref = cal["reference_size"]; k = cal["k"]; g = cal["gamma"]
    su = cal["sd_undiv"]; sd = cal["sd_div"]
    hh = np.clip(HHI, cal.get("hhi_floor", 0.01), cal.get("hhi_ceil", 1.0))
    log_reff = np.log(R / ref) - g * np.log(hh)
    return np.sqrt(su ** 2 + sd ** 2 * np.exp(2.0 * (k - 1.0) * log_reff))


def mad(a):
    return float(np.median(np.abs(a - np.median(a))))


def spread_direction(lo, hi):
    """Describe the interval's direction without attributing it to a model scale."""
    return ("RITC spread wider after base standardisation (interval above 1)" if lo > 1
            else "RITC spread narrower after base standardisation (interval below 1)" if hi < 1
            else "unresolved (interval straddles 1)")


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
    """The exact population calibrate_dispersion.py fits on (the working sample), with syndicate+key."""
    with io.open(SCRIPT_DIR / "model" / "exposure_results.json", encoding="utf-8") as _fh:
        d = json.load(_fh)
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
    z = s / sigma_op(R, HHI, cal)   # single-regime base-standardised residual

    g3 = np.where(isS, 2, np.where(isW, 1, 0))
    gb = ritc.astype(int)
    n_syn = len(np.unique(cluster))
    print(f"\n{'#'*74}\n#  POPULATION: {label}   n={len(s)}  syndicates={n_syn}  "
          f"clean={int((~ritc).sum())}  weak={int(isW.sum())}  strong={int(isS.sum())}\n{'#'*74}")

    # ── descriptive table ────────────────────────────────────────────────────
    def desc(name, m):
        a, zz = s[m], z[m]
        if len(a) == 0:
            # the rebuilt scanner (round 54) assigns no weak-confidence flags: every
            # flag rests on an explicit acceptance construction
            print(f"  {name:<10}{0:>5}  (no observations in this group)")
            return
        print(f"  {name:<10}{m.sum():>5}  s_med={_q(a,50):+.4f}  IQR(s)={robust_scale(a):.4f}  "
              f"z_med={_q(zz,50):+.3f}  IQR(z)={robust_scale(zz):.3f}  MAD(z)={mad(zz):.3f}  "
              f"sd(z)={zz.std():.3f}  |  Bowley={bowley_skew(a):+.3f}  tailR={tail_skew_ratio(a):.2f}  "
              f"Moors={moors_kurt(a):.3f}")
    print("  DESCRIPTIVE (z = s / single-regime base sigma):")
    desc("clean", ~ritc); desc("weak", isW); desc("strong", isS)
    desc("all RITC", ritc); desc("ALL", np.ones(len(s), bool))

    res = {"meta": {"n": int(len(s)), "n_syndicates": int(n_syn),
                    "clean": int((~ritc).sum()), "weak": int(isW.sum()), "strong": int(isS.sum()),
                    "operator": {kk: cal[kk] for kk in ("k", "gamma", "sd_undiv", "sd_div", "reference_size")},
                    "calibration_source": CALIBRATION_SOURCE,
                    "standardisation": STANDARDISATION_NOTE,
                    "row_test_note": ROW_TEST_NOTE, "bootstrap_sign_note": BOOTSTRAP_SIGN_NOTE,
                    "seed": SEED, "n_boot": N_BOOT}}

    print("  Row-level test p-values are descriptive: within-syndicate dependence may miscalibrate them.")
    print("  sign2 is twice the smaller observed-bootstrap sign fraction, not an established null-calibrated p-value.")

    # ── (A) Spread after single-regime base-scale standardisation ────────────
    print(f"\n{'='*74}\n  (A) SPREAD after base standardisation: z = s/sigma(R,HHI)\n{'='*74}")
    fk = stats.fligner(z[~ritc], z[ritc])
    lev = stats.levene(z[~ritc], z[ritc], center="median")
    print(f"  Fligner-Killeen (clean vs RITC equal scale?):  chi2={fk.statistic:.2f}  p={fk.pvalue:.3f}")
    print(f"  Brown-Forsythe Levene (median-centred):        W={lev.statistic:.2f}  p={lev.pvalue:.3f}")
    res["scale"] = {"fligner_p": float(fk.pvalue), "levene_p": float(lev.pvalue), "ratios": {}}
    for lab, fn in [("IQR(z)", robust_scale), ("MAD(z)", mad), ("SD(z)", lambda a: float(np.std(a)))]:
        rr = cluster_bootstrap_ratio(z, cluster, gb, fn, 1, 0, rng)
        if rr:
            # The side of one describes the spread contrast; retained effects
            # prevent attribution of that contrast solely to the base scale.
            lo, hi = rr["ci"]
            rr["direction"] = spread_direction(lo, hi)
            print(f"    {lab:<8} RITC/clean ratio = {rr['ratio']:.3f}  "
                  f"95% CI [{rr['ci'][0]:.3f}, {rr['ci'][1]:.3f}]  sign2={rr['p']:.3f}")
            res["scale"]["ratios"][lab] = rr
    for gname, code in [("strong", 2), ("weak", 1)]:
        if int((g3 == code).sum()) == 0:
            continue
        gg = np.where(g3 == code, 1, np.where(g3 == 0, 0, -1))
        keep = gg >= 0
        rr = cluster_bootstrap_ratio(z[keep], cluster[keep], gg[keep], robust_scale, 1, 0, rng)
        if rr:
            print(f"      IQR(z) {gname:<6}/clean ratio = {rr['ratio']:.3f}  "
                  f"95% CI [{rr['ci'][0]:.3f}, {rr['ci'][1]:.3f}]  sign2={rr['p']:.3f}")
            res["scale"]["ratios"][f"IQR_{gname}"] = rr

    # ── (B) SHAPE invariance (location+scale removed) ────────────────────────
    print(f"\n{'='*74}\n  (B) SHAPE INVARIANCE:  standardised skew / kurtosis / tail asymmetry\n{'='*74}")
    ad_shape = anderson_ksample_shape(s, gb)
    print(f"  Anderson-Darling k-sample (group-standardised, clean vs RITC): "
          f"A2k={ad_shape['stat']:.2f}  p={ad_shape['p']:.3f}  (row-level descriptive)")
    ad_shape3 = anderson_ksample_shape(s, g3)
    print(f"  Anderson-Darling k-sample (clean vs weak vs strong):           "
          f"A2k={ad_shape3['stat']:.2f}  p={ad_shape3['p']:.3f}")
    res["shape"] = {"ad_clean_vs_ritc": ad_shape, "ad_three_way": ad_shape3, "diffs": {}}
    print(f"\n  RITC - clean standardised-shape difference (cluster bootstrap):")
    for lab, fn in SHAPE_STATS.items():
        rr = cluster_bootstrap_diff(s, cluster, gb, fn, 1, 0, rng, n=N_BOOT)
        if rr:
            print(f"    {lab:<16} diff={rr['point']:+.3f}  "
                  f"95% CI [{rr['ci'][0]:+.3f}, {rr['ci'][1]:+.3f}]  sign2={rr['p']:.3f}")
            res["shape"]["diffs"][lab] = rr

    # ── (C) OMNIBUS on base-standardised z ───────────────────────────────────
    print(f"\n{'='*74}\n  (C) OMNIBUS:  is base-standardised z the same distribution?  (scale+shape)\n{'='*74}")
    with np.errstate(all="ignore"):
        adz = stats.anderson_ksamp([z[~ritc], z[ritc]])
    pz = getattr(adz, "pvalue", None) or adz.significance_level
    print(f"  Anderson-Darling k-sample on z (clean vs RITC, NOT re-scaled): "
          f"A2k={adz.statistic:.2f}  p={float(pz):.3f}  (row-level descriptive)")
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
    with io.open(CAL, encoding="utf-8") as _fh:
        cal = json.load(_fh)
    strong, weak = assumed_business.strong_weak()

    print("RITC shape/scale-invariance tests")
    print(f"(cluster bootstrap: {N_BOOT} resamples of syndicates; seed={SEED})")
    print(f"single-regime base scale: k={cal['k']:.4f} gamma={cal['gamma']:.4f} "
          f"sd_undiv={cal['sd_undiv']:.4f} sd_div={cal['sd_div']:.4f}")

    store = {}
    # PRIMARY: the full calibration population (the working sample) -> matches the nu result & max power
    analyse("CALIB (working sample)", load_calib_population(), strong, weak, cal, rng, store)
    # SENSITIVITY: the strict N5 rescaling population
    records = build_population()
    analyse("N5 (rescaling pop)", select(records, "N5"), strong, weak, cal, rng, store)

    with io.open(OUT, "w", encoding="utf-8", newline="") as _fh:
        _fh.write(json.dumps(store, indent=2))
    print(f"\nWrote {OUT}")
    print("\nRead-out:  (A) a scale ratio interval is read by WHICH SIDE of one it lies:")
    print("               entirely ABOVE 1 => RITC residuals have the wider spread;")
    print("               entirely BELOW 1 => RITC residuals have the narrower spread;")
    print("               retained year and regime effects preclude attributing this solely to base scale;")
    print("               STRADDLING 1 => the comparison is unresolved at this resolution.")
    print("               Each population's own direction is printed with its ratio above")
    print("               and recorded in the result file; these intervals are the")
    print("               cluster-bootstrapped ones.")
    print("           (B) Shape intervals describe uncertainty; row-level AD p-values may be miscalibrated.")
    print("           (C) The omnibus compares base-standardised residuals on a row-level basis.")
    print("           (D) Fisher odds ratios describe tail representation; row-level p-values may be miscalibrated.")


if __name__ == "__main__":
    main()
