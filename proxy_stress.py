"""A3 + A4: premium-HHI proxy-error stress tests (FAST MLE scan — qualitative only).

NOTE: the fast Nelder-Mead MLE finds a different point for the weakly-identified gamma and drops
the year shock, so its ABSOLUTE reference (gamma~0.12, nu~2.29, V1~0.44) does not match the
headline Bayesian fit. Use proxy_stress_bayes.py for headline-consistent absolutes (it writes
proxy_stress_results.json). This script writes proxy_stress_mle_results.json and is kept only as
a fast qualitative cross-check of the relative pattern.


Premium HHI is an observable proxy for the unavailable reserve HHI. Two tests that the core
conclusions do NOT depend on the proxy being perfect:

A3  Rank-correlation stress. Perturb HHI (Gaussian-copula rank noise onto the *empirical* HHI
    marginal) to target Spearman(H_prem, H_tilde) in {0.9,0.7,0.5,0.3}; B replicates each;
    refit (fast MLE) and re-transfer. No arbitrary duration multipliers.

A4  Adversarial concentration. w^alpha = (1-alpha) w_prem + alpha e_max forces reserve
    concentration progressively above premium concentration (alpha in {0.25,0.5,0.75}); refit
    and re-transfer.

Outputs per level: k, gamma, sd_undiv, nu_clean, Vignette-1 VaR99/VaR99.5, Vignette-2 paired
VaR99.5 change. Reference row = unperturbed MLE (rho=1 / alpha=0).

Run: python proxy_stress.py [B]
"""
import io, json, sys
from pathlib import Path
import numpy as np
from scipy import stats

from dispersion_mle import fit_mle, transfer_var, HLO, HCE

SD = Path(__file__).resolve().parent
B = int(sys.argv[1]) if len(sys.argv) > 1 else 250
SEED = 20240707
V1 = (500.0, 0.17)


def load():
    d = json.load(io.open(SD / "exposure_results.json", encoding="utf-8"))
    rs = json.load(io.open(SD / "pdf_extraction" / "ritc_scan.json", encoding="utf-8"))
    occ = {k for k, v in rs.items() if v.get("ritc_occurred")}
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None and o.get("weights")]
    S = np.array([o["s_raw_a"] for o in recs]); R = np.array([o["opening_reserves_gbp_m"] for o in recs])
    H = np.clip(np.array([o["hhi"] for o in recs]), HLO, HCE)
    W = np.array([o["weights"] for o in recs], float)
    ritc = np.array([f"{o['syndicate']}_{o['year']}" in occ for o in recs], float)
    t2 = json.load(io.open(SD / "vignettes/vignette-2/target_transition.json", encoding="utf-8"))
    v2o = (float(t2["old_reserve_size"]), float(t2["old_hhi"])); v2n = (float(t2["new_reserve_size"]), float(t2["new_hhi"]))
    return S, R, H, W, ritc, v2o, v2n


def outputs(S, R, Hused, ritc, mp, v2o, v2n):
    """Vignette VaRs at these params/HHI."""
    v1_99 = transfer_var(S, R, Hused, ritc, V1, mp, 0.99)
    v1_995 = transfer_var(S, R, Hused, ritc, V1, mp, 0.995)
    v2 = transfer_var(S, R, Hused, ritc, v2n, mp, 0.995) - transfer_var(S, R, Hused, ritc, v2o, mp, 0.995)
    return v1_99, v1_995, v2


def perturb_rank(H, rho, rng):
    n = len(H); r = stats.rankdata(H, method="ordinal")
    z1 = stats.norm.ppf((r - 0.5) / n)
    z2 = rho * z1 + np.sqrt(1 - rho ** 2) * rng.standard_normal(n)
    r2 = stats.rankdata(z2, method="ordinal").astype(int) - 1
    Hs = np.sort(H)
    return Hs[r2]


def summ(a):
    a = np.array(a, float)
    return [float(np.mean(a)), float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def main():
    S, R, H, W, ritc, v2o, v2n = load()
    p0 = fit_mle(S, R, H, ritc)
    print(f"n={len(S)}  baseline MLE k={p0['k']:.3f} gamma={p0['gamma']:.3f} floor={p0['sd_undiv']:.4f} "
          f"nu_clean={p0['nu_clean']:.2f}  B={B}")
    init = np.array([np.log((p0['k'] - 0.5) / (1 - p0['k'] + 1e-9)) if p0['k'] < 1 else 3.0,
                     np.log(max(p0['gamma'], 1e-3)), np.log(p0['sd_undiv']), np.log(p0['sd_div']),
                     np.log(p0['nu_clean']), p0['lambda_ritc']])
    ref = outputs(S, R, H, ritc, p0, v2o, v2n)
    result = {"meta": {"B": B, "seed": SEED, "n": len(S)},
              "reference_unperturbed": {"k": p0["k"], "gamma": p0["gamma"], "sd_undiv": p0["sd_undiv"],
                                        "nu_clean": p0["nu_clean"], "V1_VaR99": ref[0], "V1_VaR995": ref[1],
                                        "V2_change995": ref[2]}}

    # ---- A3 rank-correlation stress ----
    print("\n=== A3 rank-correlation stress ===")
    print(f"{'rho':>5}{'ach.rho':>9}  {'k':>18}{'gamma':>18}{'floor':>18}{'nu_clean':>16}{'V1_99.5':>16}{'V2_chg':>16}")
    a3 = {}
    for rho in (0.9, 0.7, 0.5, 0.3):
        rng = np.random.default_rng(SEED + int(rho * 100))
        acc = {kk: [] for kk in ("k", "gamma", "sd_undiv", "nu_clean", "v199", "v1995", "v2", "sp")}
        for _ in range(B):
            Ht = perturb_rank(H, rho, rng)
            acc["sp"].append(stats.spearmanr(H, Ht).statistic)
            m = fit_mle(S, R, Ht, ritc, p0=init)
            o = outputs(S, R, Ht, ritc, m, v2o, v2n)
            for kk, vv in zip(("k", "gamma", "sd_undiv", "nu_clean"), (m["k"], m["gamma"], m["sd_undiv"], m["nu_clean"])):
                acc[kk].append(vv)
            acc["v199"].append(o[0]); acc["v1995"].append(o[1]); acc["v2"].append(o[2])
        a3[rho] = {kk: summ(acc[kk]) for kk in acc}
        def c(x): return f"{x[0]:.3f}[{x[1]:.2f},{x[2]:.2f}]"
        print(f"{rho:>5.1f}{np.mean(acc['sp']):>9.2f}  {c(a3[rho]['k']):>18}{c(a3[rho]['gamma']):>18}"
              f"{c(a3[rho]['sd_undiv']):>18}{c(a3[rho]['nu_clean']):>16}{c(a3[rho]['v1995']):>16}{c(a3[rho]['v2']):>16}")

    # ---- A4 adversarial concentration ----
    print("\n=== A4 adversarial concentration (reserve mix more concentrated) ===")
    print(f"{'alpha':>6}{'medHHIshift':>13}  {'k':>8}{'gamma':>8}{'floor':>9}{'nu_clean':>10}{'V1_99.5':>10}{'V2_chg':>10}")
    a4 = {}
    emax = np.zeros_like(W); emax[np.arange(len(W)), W.argmax(axis=1)] = 1.0
    for alpha in (0.0, 0.25, 0.5, 0.75):
        Wa = (1 - alpha) * W + alpha * emax
        Ha = np.clip((Wa ** 2).sum(axis=1), HLO, HCE)
        m = fit_mle(S, R, Ha, ritc, p0=init)
        o = outputs(S, R, Ha, ritc, m, v2o, v2n)
        shift = float(np.median(Ha - H))
        a4[alpha] = {"med_hhi_shift": shift, "k": m["k"], "gamma": m["gamma"], "sd_undiv": m["sd_undiv"],
                     "nu_clean": m["nu_clean"], "V1_VaR995": o[1], "V2_change995": o[2]}
        print(f"{alpha:>6.2f}{shift:>13.3f}  {m['k']:>8.3f}{m['gamma']:>8.3f}{m['sd_undiv']:>9.4f}"
              f"{m['nu_clean']:>10.2f}{o[1]:>10.3f}{o[2]:>+10.3f}")

    result["A3_rank_correlation"] = {str(k): v for k, v in a3.items()}
    result["A4_adversarial"] = {str(k): v for k, v in a4.items()}
    (SD / "proxy_stress_mle_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\nWrote proxy_stress_mle_results.json (fast MLE scan; see proxy_stress_bayes.py for headline-consistent absolutes)")


if __name__ == "__main__":
    main()
