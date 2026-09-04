"""A3 + A4 proxy-error stress on the HEADLINE two-regime Bayesian model.

Replaces the fast-MLE reference in proxy_stress.py (which lands at a different point for the
weakly-identified gamma and drops the year shock, so its absolutes disagree with the headline).
This refits the exact calibrate_dispersion_ritc.py model (Student-t clean/RITC tail regime,
undiversifiable floor, reporting-year shock, mu=0) by NUTS on each perturbed HHI, at reduced
draws for tractability, and reports posterior-mean params + vignette VaRs so the reference row
reproduces its own reduced-draw reference row (gamma~0.260, nu_clean~2.40, floor~0.021,
V1 VaR99.5~0.392).  Those differ slightly from the manuscript's headline (gamma=0.243,
V1 VaR99.5=0.393) because this script samples at 500x2 rather than 1500x4 for tractability
across the sweep -- NOT because it fits a different model; it is two-regime throughout.
Compare against model/dispersion_calibration_ritc.json, or use
adopted_model.check_against_headline().

Run: python src/proxy_stress_bayes.py [B_A3]   (B_A3 replicates per rho; default 30)
"""
import io, json, sys
from pathlib import Path
import numpy as np
from scipy import stats
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
from adopted_model import scale_block

from dispersion_mle import sigma, deritc_z, HLO, HCE

SD = Path(__file__).resolve().parent.parent
REF = 500.0
SEED = 20240707
V1 = (500.0, 0.17)
B_A3 = int(sys.argv[1]) if len(sys.argv) > 1 else 30
DRAWS, TUNE, CHAINS = 500, 500, 2


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    rs = json.load(io.open(SD / "pdf_extraction" / "ritc_scan.json", encoding="utf-8"))
    occ = {k for k, v in rs.items() if v.get("ritc_occurred")}
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None and o.get("weights")]
    S = np.array([o["s_raw_a"] for o in recs]); R = np.array([o["opening_reserves_gbp_m"] for o in recs])
    H = np.clip(np.array([o["hhi"] for o in recs]), HLO, HCE)
    yr = np.array([o["year"] for o in recs]); W = np.array([o["weights"] for o in recs], float)
    ritc = np.array([f"{o['syndicate']}_{o['year']}" in occ for o in recs], float)
    t2 = json.load(io.open(SD / "vignettes/vignette-2/target_transition.json", encoding="utf-8"))
    v2o = (float(t2["old_reserve_size"]), float(t2["old_hhi"])); v2n = (float(t2["new_reserve_size"]), float(t2["new_hhi"]))
    return S, R, H, yr, W, ritc, v2o, v2n


def fit_bayes(S, R, H, yr, ritc):
    """The adopted model (scale_block) refitted on a perturbed concentration index:
    no departure in the model, only in the data it is given."""
    with pm.Model():
        b = scale_block(R, H, yr, ritc)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=1, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    m = lambda v: float(p[v].values.mean())
    nc = m("nu_clean"); lm = m("lambda_ritc")
    return {"k": m("k"), "gamma": m("gamma"), "sd_undiv": m("sd_undiv"), "sd_div": m("sd_div"),
            "nu_clean": nc, "nu_ritc": float(np.mean(p["nu_clean"].values * np.exp(-p["lambda_ritc"].values)))}


def vig(S, R, H, ritc, mp, tgt, alpha):
    sig_i = sigma(R, H, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    sig_q = sigma(tgt[0], tgt[1], mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    z = deritc_z(S / sig_i, ritc, mp["nu_clean"], mp["nu_ritc"])
    return float(np.percentile(z * sig_q, 100 * alpha, method="linear"))


def outputs(S, R, Hused, ritc, mp, v2o, v2n):
    return (vig(S, R, Hused, ritc, mp, V1, 0.99), vig(S, R, Hused, ritc, mp, V1, 0.995),
            vig(S, R, Hused, ritc, mp, v2n, 0.995) - vig(S, R, Hused, ritc, mp, v2o, 0.995))


def perturb_rank(H, rho, rng):
    n = len(H); r = stats.rankdata(H, method="ordinal")
    z2 = rho * stats.norm.ppf((r - 0.5) / n) + np.sqrt(1 - rho ** 2) * rng.standard_normal(n)
    return np.sort(H)[stats.rankdata(z2, method="ordinal").astype(int) - 1]


def summ(a):
    a = np.array(a, float); return [float(a.mean()), float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def main():
    S, R, H, yr, W, ritc, v2o, v2n = load()
    print(f"n={len(S)}  B_A3={B_A3}  draws={DRAWS}x{CHAINS}")
    p0 = fit_bayes(S, R, H, yr, ritc)
    ref = outputs(S, R, H, ritc, p0, v2o, v2n)
    # compare against the ADOPTED fit in model/dispersion_calibration_ritc.json, not
    # against remembered numbers: the line here used to print gamma=0.264 / V1=0.427
    # from a superseded run, and a stale benchmark is what lets a wrong fit look right
    print("REFERENCE (unperturbed; adopted headline gamma=0.243 nu_clean=2.43 "
          "floor=0.021 V1_99.5=0.393, at full draws):")
    print(f"  k={p0['k']:.3f} gamma={p0['gamma']:.3f} floor={p0['sd_undiv']:.4f} nu_clean={p0['nu_clean']:.2f} "
          f"nu_ritc={p0['nu_ritc']:.2f}  V1_99.5={ref[1]:.3f} V2_chg={ref[2]:+.3f}")

    res = {"meta": {"B_A3": B_A3, "draws": DRAWS, "chains": CHAINS, "seed": SEED, "n": len(S),
                    "scope": ("every refit is the ADOPTED specification (bracketed k, "
                              "positive floor, two-regime tail); the ranges are across "
                              "perturbation replicates of that one model. The stress "
                              "shows whether the fitted summaries and vignette points "
                              "move, CONDITIONAL on the specification -- the "
                              "floor-versus-no-floor and pooling-endpoint model "
                              "comparisons are not repeated under the perturbations "
                              "and cannot be re-adjudicated from these fits")},
           "reference": {**p0, "V1_VaR99": ref[0], "V1_VaR995": ref[1], "V2_change995": ref[2]}}

    print("\n=== A3 rank-correlation stress (Bayesian two-regime) ===")
    a3 = {}
    for rho in (0.9, 0.7, 0.5, 0.3):
        rng = np.random.default_rng(SEED + int(rho * 100))
        acc = {kk: [] for kk in ("k", "gamma", "sd_undiv", "nu_clean", "v1995", "v2", "sp")}
        for _ in range(B_A3):
            Ht = perturb_rank(H, rho, rng)
            acc["sp"].append(stats.spearmanr(H, Ht).statistic)
            m = fit_bayes(S, R, Ht, yr, ritc); o = outputs(S, R, Ht, ritc, m, v2o, v2n)
            for kk, vv in zip(("k", "gamma", "sd_undiv", "nu_clean"), (m["k"], m["gamma"], m["sd_undiv"], m["nu_clean"])):
                acc[kk].append(vv)
            acc["v1995"].append(o[1]); acc["v2"].append(o[2])
        a3[str(rho)] = {kk: summ(acc[kk]) for kk in acc}
        c = lambda x: f"{x[0]:.3f}[{x[1]:.2f},{x[2]:.2f}]"
        print(f"  rho={rho:.1f} (ach {np.mean(acc['sp']):.2f})  k={c(a3[str(rho)]['k'])}  gamma={c(a3[str(rho)]['gamma'])}  "
              f"floor={c(a3[str(rho)]['sd_undiv'])}  nu_clean={c(a3[str(rho)]['nu_clean'])}  "
              f"V1_99.5={c(a3[str(rho)]['v1995'])}  V2={c(a3[str(rho)]['v2'])}")

    print("\n=== A4 adversarial concentration (Bayesian two-regime) ===")
    a4 = {}
    emax = np.zeros_like(W); emax[np.arange(len(W)), W.argmax(axis=1)] = 1.0
    for alpha in (0.0, 0.25, 0.5, 0.75):
        Wa = (1 - alpha) * W + alpha * emax; Ha = np.clip((Wa ** 2).sum(axis=1), HLO, HCE)
        m = fit_bayes(S, R, Ha, yr, ritc); o = outputs(S, R, Ha, ritc, m, v2o, v2n)
        a4[str(alpha)] = {"med_hhi_shift": float(np.median(Ha - H)), "k": m["k"], "gamma": m["gamma"],
                          "sd_undiv": m["sd_undiv"], "nu_clean": m["nu_clean"], "V1_VaR995": o[1], "V2_change995": o[2]}
        print(f"  alpha={alpha:.2f} (dHHI {np.median(Ha-H):+.3f})  k={m['k']:.3f} gamma={m['gamma']:.3f} "
              f"floor={m['sd_undiv']:.4f} nu_clean={m['nu_clean']:.2f}  V1_99.5={o[1]:.3f} V2={o[2]:+.3f}")

    res["A3_rank_correlation"] = a3; res["A4_adversarial"] = a4
    (SD / "results" / "proxy_stress_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\nWrote proxy_stress_results.json (Bayesian two-regime)")


if __name__ == "__main__":
    main()
