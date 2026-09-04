"""#2 top-10 donor table (full columns + clean-only status) and #4 weak-flag evidence pull.

#2: the top-10 adverse transferred (de-RITC) Vignette-1 donors with rank, syndicate, year,
    RITC confidence (strong/weak/clean), raw severity, donor R and H, transfer factor lambda,
    transferred S^(q) with 95% credible interval, and whether the donor is retained in the clean-only
    pool and where it ranks there.
#4: for every RITC-flagged donor among the TOP-20 adverse transferred scenarios AND every
    RITC-flagged donor whose transferred severity sits near the VaR99/VaR99.5 thresholds, pull
    the dual-LLM evidence phrase / section / page for manual adjudication.

Run: python src/donor_review.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats

from vignette_uncertainty import load_pool, load_draws, load_ritc, load_targets
from dispersion_mle import sigma, deritc_z

SD = Path(__file__).resolve().parent.parent
V1 = (500.0, 0.17)


def main():
    S, R, H, synd, year = load_pool()
    ritc = load_ritc(synd, year)
    draws, ref, hlo, hce = load_draws()
    cal = json.load(io.open(SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8"))
    mp = {"k": cal["k"], "gamma": cal["gamma"], "sd_undiv": cal["sd_undiv"], "sd_div": cal["sd_div"],
          "nu_clean": cal["nu_clean"], "nu_ritc": cal["nu_ritc"]}
    rs = json.load(io.open(SD / "pdf_extraction" / "ritc_scan.json", encoding="utf-8"))
    conf = {}
    for k, v in rs.items():
        if v.get("ritc_occurred"):
            conf[k] = v

    def transfer(Sx, Rx, Hx, rx):
        sig_i = sigma(Rx, Hx, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
        sig_q = sigma(V1[0], V1[1], mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
        z = deritc_z(Sx / sig_i, rx.astype(float), mp["nu_clean"], mp["nu_ritc"])
        return z * sig_q, sig_q / sig_i

    Sadj, lam = transfer(S, R, H, ritc)
    # clean-only pool ranking
    cl = ~ritc.astype(bool)
    Sadj_cl, _ = transfer(S[cl], R[cl], H[cl], ritc[cl])
    clean_order = np.argsort(-Sadj_cl)
    clean_key_rank = {f"{synd[cl][i]}_{year[cl][i]}": r + 1 for r, i in enumerate(clean_order)}

    def cflag(s, y):
        c = conf.get(f"{s}_{y}")
        return "clean" if c is None else c.get("confidence", "?")

    order = np.argsort(-Sadj)
    D = min(2000, len(draws["k"])); idx = np.linspace(0, len(draws["k"]) - 1, D).astype(int)

    print("=== #2  Top-10 adverse transferred donors (Vignette 1, de-RITC) ===")
    print(f"{'#':>2}{'synd':>7}{'yr':>6}{'flag':>7}{'S_raw':>8}{'R_i':>9}{'H_i':>7}{'lambda':>8}"
          f"{'S_adj':>8}{'  95% CrI':>16}{'  clean-only':>16}")
    rows2 = []
    for rk, i in enumerate(order[:10], 1):
        sig_i = sigma(R[i], H[i], draws["k"][idx], draws["gamma"][idx], draws["sd_undiv"][idx], draws["sd_div"][idx])
        sig_q = sigma(V1[0], V1[1], draws["k"][idx], draws["gamma"][idx], draws["sd_undiv"][idx], draws["sd_div"][idx])
        zi = S[i] / sig_i
        if ritc[i]:
            u = np.clip(stats.t.cdf(zi, df=draws["nu_ritc"][idx]), 1e-12, 1 - 1e-12)
            zi = stats.t.ppf(u, df=draws["nu_clean"][idx])
        sd_draws = zi * sig_q; lo, hi = np.percentile(sd_draws, [2.5, 97.5])
        fl = cflag(synd[i], year[i]); key = f"{synd[i]}_{year[i]}"
        if ritc[i]:
            costat = "excluded"
        else:
            costat = f"kept (#{clean_key_rank.get(key, '?')})"
        print(f"{rk:>2}{synd[i]:>7}{year[i]:>6}{fl:>7}{S[i]:>8.3f}{R[i]:>9.1f}{H[i]:>7.3f}"
              f"{lam[i]:>8.3f}{Sadj[i]:>8.3f}   [{lo:.3f},{hi:.3f}]{costat:>16}")
        rows2.append({"rank": rk, "syndicate": int(synd[i]), "year": int(year[i]), "ritc_flag": fl,
                      "S_raw": float(S[i]), "R_i": float(R[i]), "H_i": float(H[i]), "lambda": float(lam[i]),
                      "S_adj": float(Sadj[i]), "S_adj_lo": float(lo), "S_adj_hi": float(hi),
                      "clean_only": costat})

    # ---- #4 weak/strong evidence in the tail ----
    v99 = np.percentile(Sadj, 99, method="linear"); v995 = np.percentile(Sadj, 99.5, method="linear")
    top20 = set(order[:20])
    near_thr = set(np.where((Sadj >= 0.90 * v99))[0])   # at/near VaR99 and above
    flagged_tail = sorted(top20 | near_thr, key=lambda i: -Sadj[i])
    print("\n=== #4  RITC-flagged donors in the tail (top-20 adverse and/or near VaR99/99.5) — for manual review ===")
    print(f"(VaR99={v99:.3f}, VaR99.5={v995:.3f})\n")
    rows4 = []
    for i in flagged_tail:
        if not ritc[i]:
            continue
        c = conf.get(f"{synd[i]}_{year[i]}", {})
        rank = int(np.where(order == i)[0][0]) + 1
        ev = (c.get("evidence", "") or "").strip().replace("\n", " ")
        print(f"  synd {synd[i]} {year[i]}  [{c.get('confidence','?')}]  adverse-rank {rank}  "
              f"S_adj={Sadj[i]:.3f}  (>=VaR99: {Sadj[i]>=v99}, >=VaR99.5: {Sadj[i]>=v995})")
        print(f"    section: {c.get('section','?')}  page: {c.get('page','?')}  n_strong_hits: {c.get('n_strong_hits','?')}")
        print(f"    evidence: \"{ev[:280]}\"\n")
        rows4.append({"syndicate": int(synd[i]), "year": int(year[i]), "confidence": c.get("confidence"),
                      "adverse_rank": rank, "S_adj": float(Sadj[i]), "ge_var99": bool(Sadj[i] >= v99),
                      "ge_var995": bool(Sadj[i] >= v995), "section": c.get("section"), "page": c.get("page"),
                      "n_strong_hits": c.get("n_strong_hits"), "evidence": ev})

    # Dropping only the weak-confidence flags from the donor pool, parameters
    # unchanged: the transferred pool minus those donors, re-read at the same
    # quantile rule. This is a pool exclusion, not a refit.
    weak = np.array([cflag(s, y) == "weak" for s, y in zip(synd, year)])
    keep = ~weak
    drop_weak = {"n_weak_dropped": int(weak.sum()), "n_donors": int(keep.sum()),
                 "VaR99": float(np.percentile(Sadj[keep], 99.0)),
                 "VaR995": float(np.percentile(Sadj[keep], 99.5))}
    # The manual-review set of the supplement, with each member's current rank.
    rank_of = {f"{synd[i]}_{year[i]}": r + 1 for r, i in enumerate(order)}
    review_set = ["2008_2019", "1861_2020", "2008_2016", "1209_2017", "1274_2018", "2003_2015"]
    review_ranks = {k: {"adverse_rank": rank_of.get(k), "confidence": cflag(*k.split("_")),
                        "in_pool": k in rank_of} for k in review_set}
    (SD / "results" / "donor_review_results.json").write_text(json.dumps(
        {"V1_target": V1, "top10": rows2, "tail_ritc_evidence": rows4,
         "VaR99": float(v99), "VaR995": float(v995),
         "drop_weak_only": drop_weak, "manual_review_ranks": review_ranks}, indent=2), encoding="utf-8")
    print("Wrote donor_review_results.json")


if __name__ == "__main__":
    main()
