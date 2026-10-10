"""B: four RITC treatments — does RITC create the structural result, or only shape the far tail?

T1 Preferred de-RITC : all donors, clean/RITC tail regimes, rank-map RITC onto clean tail.
T2 Pure rescale      : all donors, NO de-RITC (RITC carried as ordinary development).
T3 Clean-only        : exclude all RITC syndicate-years; fit & transfer clean donors only.
T4 Strong-only excl  : exclude strong-confidence RITC only (weak retained as clean); sensitivity.

Structural params (k, gamma, floor, nu) are the published Bayesian fits. Each row is computed
through the matching operator on the donor pool under the paper's headline size-only transfer
operator, from a fit with gamma fixed at 0 in the likelihood (option B, 10 October 2026:
transfer_operator.py): T1/T2 the headline calibration (dispersion_calibration_ritc.json), T3 and
T4 ritc_robustness's gamma = 0 refits of EXCL_ALL and EXCL_STRONG (`fits_gamma_fixed_0`). The
concentration overlay, the labelled sensitivity, is reported beside T1 and T2 only, from the
full-sample gamma-free calibration, with its parameters; T3 and T4 are refits on subsamples and carry
no overlay leg (the decisions of 10 October 2026: the overlay is reported on the full-sample gamma-free
fit only).

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
NO_OVERLAY_NOTE = ("no overlay leg: this treatment's fit is a refit on a subsample with gamma fixed at 0 in the "
                   "likelihood (the headline's construction since option B, 10 October 2026); the overlay is "
                   "reported on the full-sample gamma-free fit only (T1 and T2)")


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

    rob_all = json.load(io.open(SD / "results" / "ritc_robustness_results.json", encoding="utf-8"))
    rob, rob_g0 = rob_all["fits"], rob_all["fits_gamma_fixed_0"]

    def P(fit):  # pull single-nu robustness params; a gamma = 0 fit has no gamma in its params
        p = fit["params"]
        return {"k": p["k"]["mean"], "gamma": p["gamma"]["mean"] if "gamma" in p else 0.0,
                "sd_undiv": p["sd_undiv"]["mean"],
                "sd_div": p["sd_div"]["mean"], "nu_clean": p["nu"]["mean"], "nu_ritc": p["nu"]["mean"]}

    def regime(mode):  # the two-regime calibration of the operator's own fit
        cal = transfer_operator.load_calibration(mode)
        return {"k": cal["k"], "gamma": cal["gamma"], "sd_undiv": cal["sd_undiv"], "sd_div": cal["sd_div"],
                "nu_clean": cal["nu_clean"], "nu_ritc": cal["nu_ritc"]}

    reg_h, reg_o = regime(transfer_operator.HEADLINE), regime(transfer_operator.SENSITIVITY)

    all_rows, clean, strong_out = np.ones(len(S), bool), ~ritc, ~isS
    specs = [  # (name, donor mask, headline fit's means, overlay fit's means, tail label, de-RITC)
        ("T1 Preferred de-RITC", all_rows, reg_h, reg_o, "clean/RITC regimes", True),
        ("T2 Pure rescale", all_rows, reg_h, reg_o, "RITC carried", False),
        ("T3 Clean-only exclusion", clean, P(rob_g0["EXCL_ALL"]), None, "clean only", False),
        ("T4 Strong-only exclusion", strong_out, P(rob_g0["EXCL_STRONG"]), None, "sensitivity", False),
    ]

    print(f"{'Treatment':<26}{'n':>5}{'k':>8}{'gamma':>8}{'floor':>9}{'nu':>16}{'V1_995':>9}{'V2_chg':>9}"
          f"{'  overlay V1':>12}")
    print("-" * 102)
    out = {"V1_target": V1, **transfer_operator.stamp(transfer_operator.HEADLINE),
           "vignettes": ("V1_VaR995 and V2_change995 are under the headline size-only operator, from each "
                         "treatment's fit with gamma fixed at 0 in the likelihood (k, gamma, sd_undiv and nu are "
                         "that fit's); the overlay_sensitivity block of T1 and T2 is the concentration overlay "
                         "from the full-sample gamma-free calibration, whose parameters it records; T3 and T4, "
                         "refits on subsamples, carry no overlay leg"),
           "treatments": []}
    for name, m, p, po, tail, der in specs:
        v1, v2 = v995_and_v2(S[m], R[m], H[m], ritc[m], p, v2o, v2n, deritc=der)
        o1, o2 = (v995_and_v2(S[m], R[m], H[m], ritc[m], po, v2o, v2n, deritc=der,
                              mode=transfer_operator.SENSITIVITY) if po is not None else (float("nan"), None))
        n = int(m.sum())
        nu = f"{p['nu_clean']:.2f}/{p['nu_ritc']:.2f}" if p["nu_clean"] != p["nu_ritc"] else f"{p['nu_clean']:.2f}"
        print(f"{name:<26}{n:>5}{p['k']:>8.3f}{p['gamma']:>8.3f}{p['sd_undiv']:>9.4f}{nu:>16}{v1:>9.3f}{v2:>+9.3f}"
              f"{o1:>12.3f}")
        out["treatments"].append({"treatment": name, "n_donors": n, "k": p["k"], "gamma": p["gamma"],
                                  "sd_undiv": p["sd_undiv"], "nu": tail, "nu_clean": p["nu_clean"],
                                  "nu_ritc": p["nu_ritc"], "V1_VaR995": v1, "V2_change995": v2,
                                  **({"overlay_sensitivity": {
                                      **transfer_operator.stamp(transfer_operator.SENSITIVITY),
                                      "k": po["k"], "gamma": po["gamma"], "sd_undiv": po["sd_undiv"],
                                      "nu_clean": po["nu_clean"], "nu_ritc": po["nu_ritc"],
                                      "V1_VaR995": o1, "V2_change995": o2}}
                                     if po is not None else {"overlay_sensitivity_note": NO_OVERLAY_NOTE})})
    (SD / "results" / "ritc_treatments_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nWrote ritc_treatments_results.json")


if __name__ == "__main__":
    main()
