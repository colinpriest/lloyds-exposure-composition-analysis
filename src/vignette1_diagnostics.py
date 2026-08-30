"""C: Vignette-1 tail-support and VaR diagnostics (make the 1-in-200 auditable).

C2 top-10 adverse transferred donors (with posterior interval on the transferred severity)
C3 tail-order influence (remove largest 1/2; leave-one-top-10-donor-out; leave-one-top-synd-out)
C4 VaR curve raw vs transferred at {0.95,0.975,0.99,0.9925,0.995}
C5 TVaR99 and TVaR97.5 (expected shortfall) raw vs transferred
C6 GPD/EVT cross-check across thresholds {q90,q92.5,q95} for raw / de-RITC / clean-only pools

De-RITC operator at posterior mean; C2 intervals propagate posterior draws. Donor pool =
distortion_tool.html embedded pool (789). Run: python vignette1_diagnostics.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats

from vignette_uncertainty import load_pool, load_draws, load_ritc, load_targets
from dispersion_mle import sigma, deritc_z

SD = Path(__file__).resolve().parent.parent
V1 = (500.0, 0.17)
Q = "linear"


def transferred(S, R, H, ritc, mp, tgt, deritc=True):
    sig_i = sigma(R, H, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    sig_q = sigma(tgt[0], tgt[1], mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    z = S / sig_i
    if deritc:
        z = deritc_z(z, ritc.astype(float), mp["nu_clean"], mp["nu_ritc"])
    return z * sig_q, sig_q / sig_i


def var(a, p):
    return float(np.percentile(a, 100 * p, method=Q))


def tvar(a, p):
    v = var(a, p); tail = a[a >= v]
    return float(tail.mean()) if len(tail) else float("nan")


def gpd_var(sample, uq, p):
    u = np.percentile(sample, uq, method=Q); exc = sample[sample > u] - u
    N, Nu = len(sample), len(exc)
    if Nu < 10:
        return None
    xi, _, sc = stats.genpareto.fit(exc, floc=0.0)
    if sc <= 0 or not np.isfinite(xi):
        return None
    def vq(pp):
        a = (N / Nu) * (1 - pp)
        return u - sc * np.log(a) if abs(xi) < 1e-6 else u + (sc / xi) * (a ** (-xi) - 1)
    return {"u": float(u), "Nu": int(Nu), "xi": float(xi), "scale": float(sc),
            "var99": float(vq(0.99)), "var995": float(vq(0.995))}


def main():
    S, R, H, synd, year = load_pool()
    ritc = load_ritc(synd, year)
    draws, ref, hlo, hce = load_draws()
    mp = {k: float(draws[k].mean()) for k in draws}
    cal = json.load(io.open(SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8"))
    mp = {**mp, "k": cal["k"], "gamma": cal["gamma"], "sd_undiv": cal["sd_undiv"],
          "sd_div": cal["sd_div"], "nu_clean": cal["nu_clean"], "nu_ritc": cal["nu_ritc"]}

    Sadj, lam = transferred(S, R, H, ritc, mp, V1)
    out = {"V1_target": V1, "n_donors": int(len(S))}

    # ---- C2 top-10 adverse transferred donors ----
    order = np.argsort(-Sadj)[:10]
    # posterior interval on each donor's transferred severity
    D = min(2000, len(draws["k"]))
    idx = np.linspace(0, len(draws["k"]) - 1, D).astype(int)
    print("=== C2  Top-10 adverse transferred donors (Vignette 1) ===")
    print(f"{'#':>2}{'synd':>7}{'yr':>6}{'RITC':>5}{'S_raw':>9}{'R_i':>9}{'H_i':>7}{'lambda':>8}{'S_adj':>9}{'  [95% CI]':>16}")
    c2 = []
    for rk, i in enumerate(order, 1):
        # posterior draws of this donor's transferred severity
        sig_i = sigma(R[i], H[i], draws["k"][idx], draws["gamma"][idx], draws["sd_undiv"][idx], draws["sd_div"][idx])
        sig_q = sigma(V1[0], V1[1], draws["k"][idx], draws["gamma"][idx], draws["sd_undiv"][idx], draws["sd_div"][idx])
        zi = S[i] / sig_i
        if ritc[i]:
            u = np.clip(stats.t.cdf(zi, df=draws["nu_ritc"][idx]), 1e-12, 1 - 1e-12)
            zi = stats.t.ppf(u, df=draws["nu_clean"][idx])
        sd_draws = zi * sig_q
        lo, hi = np.percentile(sd_draws, [2.5, 97.5])
        print(f"{rk:>2}{synd[i]:>7}{year[i]:>6}{('Y' if ritc[i] else '-'):>5}{S[i]:>9.3f}"
              f"{R[i]:>9.1f}{H[i]:>7.3f}{lam[i]:>8.3f}{Sadj[i]:>9.3f}   [{lo:.3f},{hi:.3f}]")
        c2.append({"rank": rk, "syndicate": int(synd[i]), "year": int(year[i]), "ritc": int(ritc[i]),
                   "S_raw": float(S[i]), "R_i": float(R[i]), "H_i": float(H[i]), "lambda": float(lam[i]),
                   "S_adj": float(Sadj[i]), "S_adj_lo": float(lo), "S_adj_hi": float(hi)})
    out["C2_top10"] = c2

    # ---- C3 tail-order influence ----
    base = var(Sadj, 0.995)
    srt = np.argsort(-Sadj)
    rm1 = var(np.delete(Sadj, srt[0]), 0.995)
    rm2 = var(np.delete(Sadj, srt[:2]), 0.995)
    loo = [var(np.delete(Sadj, srt[j]), 0.995) for j in range(10)]  # remove each top-10 donor alone
    # leave-one-top-syndicate-out (syndicates appearing in top-10)
    top_syn = list(dict.fromkeys(synd[srt[:10]]))
    los = [var(Sadj[synd != s], 0.995) for s in top_syn]
    c3 = {"all": base, "remove_largest": rm1, "remove_largest2": rm2,
          "loo_top10_min": min(loo), "loo_top10_max": max(loo),
          "loo_top_synd_min": min(los), "loo_top_synd_max": max(los)}
    print("\n=== C3  Tail-order influence (VaR99.5) ===")
    for lbl, v in [("All donors", base), ("Remove largest donor", rm1), ("Remove largest two", rm2),
                   ("LOO top-10 donor: min", min(loo)), ("LOO top-10 donor: max", max(loo)),
                   ("LOO top-syndicate: min", min(los)), ("LOO top-syndicate: max", max(los))]:
        print(f"  {lbl:<26}{v:>7.3f}   ({100*(v-base)/base:+.1f}%)")
    out["C3_influence"] = c3

    # ---- C4 VaR curve raw vs transferred ----
    print("\n=== C4  VaR curve (raw vs transferred) ===")
    c4 = []
    for p in (0.95, 0.975, 0.99, 0.9925, 0.995):
        vr, vt = var(S, p), var(Sadj, p)
        print(f"  {p*100:>6.2f}%  raw {vr:>7.3f}  transferred {vt:>7.3f}  ({100*(vt-vr)/abs(vr):+.0f}%)")
        c4.append({"p": p, "raw": vr, "transferred": vt})
    out["C4_var_curve"] = c4

    # ---- C5 TVaR ----
    print("\n=== C5  TVaR / expected shortfall ===")
    c5 = {}
    for lbl, p in [("VaR99", None), ("TVaR97.5", 0.975), ("TVaR99", 0.99), ("VaR99.5", None)]:
        pass
    tab = [("VaR99", var(S, 0.99), var(Sadj, 0.99)), ("TVaR97.5", tvar(S, 0.975), tvar(Sadj, 0.975)),
           ("TVaR99", tvar(S, 0.99), tvar(Sadj, 0.99)), ("VaR99.5", var(S, 0.995), var(Sadj, 0.995))]
    for lbl, vr, vt in tab:
        print(f"  {lbl:<10} raw {vr:>7.3f}  transferred {vt:>7.3f}  ({100*(vt-vr)/abs(vr):+.0f}%)")
        c5[lbl] = {"raw": vr, "transferred": vt}
    out["C5_tvar"] = c5

    # ---- C6 GPD/EVT cross-check ----
    print("\n=== C6  GPD/EVT cross-check ===")
    clean = ~ritc.astype(bool)
    Sadj_clean, _ = transferred(S[clean], R[clean], H[clean], ritc[clean], mp, V1)
    # the pure-rescale comparator: scale-only transfer RETAINING the RITC donors'
    # tails (deritc=False). This is the "before" population for the manuscript's
    # de-RITC tail-lightening claim; review found it quoted (~0.50) but never
    # committed, so it is generated here alongside the other three pools.
    Sadj_pure, _ = transferred(S, R, H, ritc, mp, V1, deritc=False)
    pools = {"Raw": S, "Transferred (pure rescale)": Sadj_pure,
             "Transferred (de-RITC)": Sadj, "Clean-only": Sadj_clean}
    c6 = []
    print(f"  {'Pool':<22}{'thr':>6}{'Nexc':>6}{'xi':>8}{'scale':>8}{'GPD_V99':>9}{'GPD_V995':>10}")
    for name, pool in pools.items():
        for uq in (90.0, 92.5, 95.0):
            g = gpd_var(pool, uq, None)
            if g:
                print(f"  {name:<22}{uq:>6.1f}{g['Nu']:>6}{g['xi']:>+8.2f}{g['scale']:>8.3f}{g['var99']:>9.3f}{g['var995']:>10.3f}")
                c6.append({"pool": name, "threshold_pct": uq, **g})
    out["C6_gpd"] = c6

    (SD / "results" / "vignette1_diagnostics_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nWrote vignette1_diagnostics_results.json")


if __name__ == "__main__":
    main()
