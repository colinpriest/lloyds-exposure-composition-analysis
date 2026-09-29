"""B: four RITC treatments — does RITC create the structural result, or only shape the far tail?

T1 Preferred de-RITC : all donors, clean/RITC tail regimes, rank-map RITC onto clean tail.
T2 Pure rescale      : all donors, NO de-RITC (RITC carried as ordinary development).
T3 Clean-only        : exclude all RITC syndicate-years; fit & transfer clean donors only.
T4 Strong-only excl  : exclude strong-confidence RITC only (weak retained as clean); sensitivity.

Structural params (k, gamma, floor, nu) are the published Bayesian fits: T1/T2 from
dispersion_calibration_ritc.json; T3 from ritc_robustness EXCL_ALL; T4 from EXCL_STRONG.
Vignette VaRs are computed through the matching operator on the donor pool, under the paper's
headline size-only transfer operator (gamma zeroed in each fit's means, not a refit:
transfer_operator.py), with the fitted concentration overlay beside each row as the labelled
sensitivity.

Run: python src/ritc_treatments.py
"""
import io, json
from pathlib import Path
import numpy as np
from pool_quantile import var_q

from dispersion_mle import sigma, deritc_z
from vignette_uncertainty import load_pool, load_ritc, load_targets
import assumed_business
import transfer_operator

SD = Path(__file__).resolve().parent.parent
V1 = (500.0, 0.17)


def strong_weak(synd, year):
    strong, weak = assumed_business.strong_weak()
    isS = np.array([f"{s}_{y}" in strong for s, y in zip(synd, year)])
    isW = np.array([f"{s}_{y}" in weak for s, y in zip(synd, year)])
    return isS, isW


def var(S, R, H, ritc, tgt, mp, alpha, deritc):
    sig_i = sigma(R, H, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    sig_q = sigma(tgt[0], tgt[1], mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    z = S / sig_i
    if deritc:
        z = deritc_z(z, ritc.astype(float), mp["nu_clean"], mp["nu_ritc"])
    return var_q(z * sig_q, alpha)


def v995_and_v2(S, R, H, ritc, mp, v2o, v2n, deritc, mode=transfer_operator.HEADLINE):
    """V1 VaR99.5 and the V2 change at the fitted means `mp`, under the transfer operator `mode`."""
    mp = transfer_operator.params(mp, mode)
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

    all_rows, clean, strong_out = np.ones(len(S), bool), ~ritc, ~isS
    specs = [  # (name, donor mask, fitted means, tail label, de-RITC)
        ("T1 Preferred de-RITC", all_rows, regime, "clean/RITC regimes", True),
        ("T2 Pure rescale", all_rows, regime, "RITC carried", False),
        ("T3 Clean-only exclusion", clean, p_excl_all, "clean only", False),
        ("T4 Strong-only exclusion", strong_out, p_excl_strong, "sensitivity", False),
    ]

    print(f"{'Treatment':<26}{'n':>5}{'k':>8}{'gamma':>8}{'floor':>9}{'nu':>16}{'V1_995':>9}{'V2_chg':>9}"
          f"{'  overlay V1':>12}")
    print("-" * 102)
    out = {"V1_target": V1, **transfer_operator.stamp(transfer_operator.HEADLINE),
           "vignettes": ("V1_VaR995 and V2_change995 are under the headline size-only operator (gamma zeroed in "
                         "each treatment's fitted means, not a refit); the overlay_sensitivity block of each row "
                         "is the fitted concentration overlay; gamma is each fit's fitted value"),
           "treatments": []}
    for name, m, p, tail, der in specs:
        v1, v2 = v995_and_v2(S[m], R[m], H[m], ritc[m], p, v2o, v2n, deritc=der)
        o1, o2 = v995_and_v2(S[m], R[m], H[m], ritc[m], p, v2o, v2n, deritc=der,
                             mode=transfer_operator.SENSITIVITY)
        n = int(m.sum())
        nu = f"{p['nu_clean']:.2f}/{p['nu_ritc']:.2f}" if p["nu_clean"] != p["nu_ritc"] else f"{p['nu_clean']:.2f}"
        print(f"{name:<26}{n:>5}{p['k']:>8.3f}{p['gamma']:>8.3f}{p['sd_undiv']:>9.4f}{nu:>16}{v1:>9.3f}{v2:>+9.3f}"
              f"{o1:>12.3f}")
        out["treatments"].append({"treatment": name, "n_donors": n, "k": p["k"], "gamma": p["gamma"],
                                  "sd_undiv": p["sd_undiv"], "nu": tail, "nu_clean": p["nu_clean"],
                                  "nu_ritc": p["nu_ritc"], "V1_VaR995": v1, "V2_change995": v2,
                                  "overlay_sensitivity": {**transfer_operator.stamp(transfer_operator.SENSITIVITY),
                                                          "V1_VaR995": o1, "V2_change995": o2}})
    (SD / "results" / "ritc_treatments_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nWrote ritc_treatments_results.json")


if __name__ == "__main__":
    main()
