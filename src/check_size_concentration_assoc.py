"""Association and redundancy/separability between SIZE and CONCENTRATION metrics
at the syndicate-year unit (n=790 fit sample).

Why it matters: the operator's effective size is log R_eff = log R - gamma*log H, so the
pooling exponent k (on size) and the concentration exponent gamma are separately identified
only if log R and log H are not collinear. If size and concentration were redundant, k and
gamma could not be told apart.

Reports:
  (a) Association: Pearson/Spearman between log R (size) and HHI, log(1/H) (effective line
      count), and diversification 1-H; both raw and after partialling out the reporting year.
  (b) Redundancy: variance inflation factors (VIF) of log R and log(1/H) with year fixed
      effects; condition number of the standardised [log R, log H] design; R^2 of HHI ~ log R
      (share of concentration explained by size).
  (c) Separability: HHI spread (IQR, range) within size deciles — does concentration vary at
      fixed size? — plus a chi-square test of independence on the size x concentration
      tercile grid.

Writes check_size_concentration_assoc_results.json.
Usage:  python src/check_size_concentration_assoc.py
"""
import io, json, sys
from pathlib import Path
import numpy as np
from scipy import stats

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_size_concentration_assoc_results.json"
HLO, HCE = 0.01, 1.0


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    return R, H, yr


def residualise_by_year(x, yr):
    """Return x with per-year means removed (partial out reporting-year fixed effects)."""
    r = x.astype(float).copy()
    for y in np.unique(yr):
        m = yr == y
        r[m] = r[m] - r[m].mean()
    return r


def vif(target, others):
    """VIF = 1/(1-R^2) from OLS of target on others (with intercept)."""
    X = np.column_stack([np.ones_like(target)] + others)
    beta, *_ = np.linalg.lstsq(X, target, rcond=None)
    resid = target - X @ beta
    ss_tot = ((target - target.mean()) ** 2).sum()
    r2 = 1.0 - (resid @ resid) / ss_tot if ss_tot > 0 else 0.0
    return float(1.0 / (1.0 - r2)) if r2 < 1 else np.inf, float(r2)


def year_dummies(yr):
    ys = np.unique(yr)[1:]  # drop one for identifiability
    return [(yr == y).astype(float) for y in ys]


def main():
    R, H, yr = load()
    logR = np.log(R)
    logH = np.log(H)
    inv_line = 1.0 / H          # effective line count n_eff = 1/H
    div = 1.0 - H               # diversification
    n = len(R)
    print(f"n={n} syndicate-years")

    # (a) association
    def assoc(a, b):
        return {"pearson": float(stats.pearsonr(a, b)[0]),
                "pearson_p": float(stats.pearsonr(a, b)[1]),
                "spearman": float(stats.spearmanr(a, b)[0]),
                "spearman_p": float(stats.spearmanr(a, b)[1])}
    raw = {"logR_vs_HHI": assoc(logR, H),
           "logR_vs_log_inv_line": assoc(logR, np.log(inv_line)),
           "logR_vs_diversification": assoc(logR, div)}
    # partial out year
    lr_c, h_c, li_c = (residualise_by_year(x, yr) for x in (logR, H, np.log(inv_line)))
    partial = {"logR_vs_HHI_within_year": assoc(lr_c, h_c),
               "logR_vs_log_inv_line_within_year": assoc(lr_c, li_c)}

    # (b) redundancy
    yd = year_dummies(yr)
    vif_logR, r2_logR = vif(logR, [np.log(inv_line)] + yd)
    vif_line, r2_line = vif(np.log(inv_line), [logR] + yd)
    # condition number of standardised [logR, logH]
    Z = np.column_stack([(logR - logR.mean()) / logR.std(),
                         (logH - logH.mean()) / logH.std()])
    sv = np.linalg.svd(Z, compute_uv=False)
    cond = float(sv[0] / sv[-1])
    # HHI explained by size
    _, r2_hhi_on_size = vif(H, [logR])
    redundancy = {
        "vif_logR_given_line_and_year": vif_logR,
        "vif_log_inv_line_given_size_and_year": vif_line,
        "condition_number_logR_logH": cond,
        "r2_HHI_on_logR": r2_hhi_on_size,
        "note": "VIF<2.5 and condition number<~10 => size and concentration are not "
                "collinear; k and gamma separately identified.",
    }

    # (c) separability: HHI spread within size deciles
    dec = np.clip((stats.rankdata(logR) / (n + 1) * 10).astype(int), 0, 9)
    within = []
    for d in range(10):
        hh = H[dec == d]
        within.append({"size_decile": d + 1, "n": int(len(hh)),
                       "median_logR": float(np.median(logR[dec == d])),
                       "HHI_median": float(np.median(hh)),
                       "HHI_iqr": [float(np.percentile(hh, 25)), float(np.percentile(hh, 75))],
                       "HHI_range": [float(hh.min()), float(hh.max())]})
    # chi-square independence on 3x3 tercile grid
    def terc(x):
        return np.clip((stats.rankdata(x) / (n + 1) * 3).astype(int), 0, 2)
    grid = np.zeros((3, 3), int)
    tr, th = terc(logR), terc(H)
    for i in range(n):
        grid[tr[i], th[i]] += 1
    chi2, chi_p, dof, _ = stats.chi2_contingency(grid)
    cramers_v = float(np.sqrt(chi2 / (n * 2)))
    separability = {"hhi_within_size_deciles": within,
                    "chi2_size_x_conc_tercile": {"chi2": float(chi2), "p": float(chi_p),
                                                 "dof": int(dof), "cramers_v": cramers_v,
                                                 "grid": grid.tolist()},
                    "median_HHI_iqr_width_within_decile":
                        float(np.median([w["HHI_iqr"][1] - w["HHI_iqr"][0] for w in within]))}

    out = {"n": n, "unit": "syndicate-year",
           "a_association_raw": raw, "a_association_within_year": partial,
           "b_redundancy": redundancy, "c_separability": separability}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print("(a) log R vs HHI: Pearson %.3f (p=%.3g), Spearman %.3f; within-year Spearman %.3f"
          % (raw["logR_vs_HHI"]["pearson"], raw["logR_vs_HHI"]["pearson_p"],
             raw["logR_vs_HHI"]["spearman"], partial["logR_vs_HHI_within_year"]["spearman"]))
    print("    log R vs log(1/H): Pearson %.3f, Spearman %.3f"
          % (raw["logR_vs_log_inv_line"]["pearson"], raw["logR_vs_log_inv_line"]["spearman"]))
    print("(b) VIF logR=%.2f, VIF log(1/H)=%.2f, condition#(logR,logH)=%.2f, R^2(HHI~logR)=%.3f"
          % (vif_logR, vif_line, cond, r2_hhi_on_size))
    print("(c) chi2 size x conc terciles: chi2=%.1f p=%.3g Cramer's V=%.3f; "
          "median within-decile HHI IQR width=%.3f"
          % (chi2, chi_p, cramers_v, separability["median_HHI_iqr_width_within_decile"]))


if __name__ == "__main__":
    sys.exit(main())
