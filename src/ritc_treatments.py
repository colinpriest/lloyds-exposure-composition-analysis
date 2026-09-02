"""B: four RITC treatments — does RITC create the structural result, or only shape the far tail?

T1 Preferred de-RITC : all donors, clean/RITC tail regimes, rank-map RITC onto clean tail.
T2 Pure rescale      : all donors, NO de-RITC (RITC carried as ordinary development).
T3 Clean-only        : exclude all RITC syndicate-years; fit & transfer clean donors only.
T4 Strong-only excl  : exclude strong-confidence RITC only (weak retained as clean); sensitivity.

Structural params (k, gamma, floor, nu) are the published Bayesian fits: T1/T2 from
dispersion_calibration_ritc.json; T3 from ritc_robustness EXCL_ALL; T4 from EXCL_STRONG.
Vignette VaRs are computed through the matching operator on the donor pool.

Run: python src/ritc_treatments.py
"""
import io, json
from pathlib import Path
import numpy as np

from dispersion_mle import sigma, deritc_z
from vignette_uncertainty import load_pool, load_ritc, load_targets

SD = Path(__file__).resolve().parent.parent
V1 = (500.0, 0.17)


def strong_weak(synd, year):
    rs = json.load(io.open(SD / "pdf_extraction" / "ritc_scan.json", encoding="utf-8"))
    strong = {k for k, v in rs.items() if v.get("ritc_occurred") and v.get("confidence") == "strong"}
    weak = {k for k, v in rs.items() if v.get("ritc_occurred") and v.get("confidence") == "weak"}
    isS = np.array([f"{s}_{y}" in strong for s, y in zip(synd, year)])
    isW = np.array([f"{s}_{y}" in weak for s, y in zip(synd, year)])
    return isS, isW


def var(S, R, H, ritc, tgt, mp, alpha, deritc):
    sig_i = sigma(R, H, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    sig_q = sigma(tgt[0], tgt[1], mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    z = S / sig_i
    if deritc:
        z = deritc_z(z, ritc.astype(float), mp["nu_clean"], mp["nu_ritc"])
    return float(np.percentile(z * sig_q, 100 * alpha, method="linear"))


def v995_and_v2(S, R, H, ritc, mp, v2o, v2n, deritc):
    v1 = var(S, R, H, ritc, V1, mp, 0.995, deritc)
    v2 = var(S, R, H, ritc, v2n, mp, 0.995, deritc) - var(S, R, H, ritc, v2o, mp, 0.995, deritc)
    return v1, v2


def main():
    S, R, H, synd, year = load_pool()
    ritc = load_ritc(synd, year)
    isS, isW = strong_weak(synd, year)
    v1t, v2o, v2n = load_targets()

    cal = json.load(io.open(SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8"))
    rob = json.load(io.open(SD / "results" / "ritc_robustness_results.json", encoding="utf-8"))["fits"]

    def P(fit):  # pull single-nu robustness params
        p = fit["params"]
        return {"k": p["k"]["mean"], "gamma": p["gamma"]["mean"], "sd_undiv": p["sd_undiv"]["mean"],
                "sd_div": p["sd_div"]["mean"], "nu_clean": p["nu"]["mean"], "nu_ritc": p["nu"]["mean"]}

    regime = {"k": cal["k"], "gamma": cal["gamma"], "sd_undiv": cal["sd_undiv"], "sd_div": cal["sd_div"],
              "nu_clean": cal["nu_clean"], "nu_ritc": cal["nu_ritc"]}
    p_excl_all = P(rob["EXCL_ALL"]); p_excl_strong = P(rob["EXCL_STRONG"])

    rows = []
    # T1 preferred de-RITC (all donors)
    v1, v2 = v995_and_v2(S, R, H, ritc, regime, v2o, v2n, deritc=True)
    rows.append(("T1 Preferred de-RITC", int(len(S)), regime, "clean/RITC regimes", v1, v2))
    # T2 pure rescale (all donors, no de-RITC)
    v1, v2 = v995_and_v2(S, R, H, ritc, regime, v2o, v2n, deritc=False)
    rows.append(("T2 Pure rescale", int(len(S)), regime, "RITC carried", v1, v2))
    # T3 clean-only (exclude all RITC donors, single-nu EXCL_ALL params)
    m = ~ritc
    v1, v2 = v995_and_v2(S[m], R[m], H[m], ritc[m], p_excl_all, v2o, v2n, deritc=False)
    rows.append(("T3 Clean-only exclusion", int(m.sum()), p_excl_all, "clean only", v1, v2))
    # T4 strong-only exclusion (exclude strong donors, EXCL_STRONG params)
    m = ~isS
    v1, v2 = v995_and_v2(S[m], R[m], H[m], ritc[m], p_excl_strong, v2o, v2n, deritc=False)
    rows.append(("T4 Strong-only exclusion", int(m.sum()), p_excl_strong, "sensitivity", v1, v2))

    print(f"{'Treatment':<26}{'n':>5}{'k':>8}{'gamma':>8}{'floor':>9}{'nu':>16}{'V1_995':>9}{'V2_chg':>9}")
    print("-" * 90)
    out = {"V1_target": V1, "treatments": []}
    for name, n, p, tail, v1, v2 in rows:
        nu = f"{p['nu_clean']:.2f}/{p['nu_ritc']:.2f}" if p["nu_clean"] != p["nu_ritc"] else f"{p['nu_clean']:.2f}"
        print(f"{name:<26}{n:>5}{p['k']:>8.3f}{p['gamma']:>8.3f}{p['sd_undiv']:>9.4f}{nu:>16}{v1:>9.3f}{v2:>+9.3f}")
        out["treatments"].append({"treatment": name, "n_donors": n, "k": p["k"], "gamma": p["gamma"],
                                  "sd_undiv": p["sd_undiv"], "nu": tail, "nu_clean": p["nu_clean"],
                                  "nu_ritc": p["nu_ritc"], "V1_VaR995": v1, "V2_change995": v2})
    (SD / "results" / "ritc_treatments_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nWrote ritc_treatments_results.json")


if __name__ == "__main__":
    main()
