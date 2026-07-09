"""Stage 0 of specifications/systemic-correlation-analysis.md.

Descriptive gate for the systemic-vs-non-systemic question: does the within-year
correlation of signed PYD severities rise with syndicate size?  Rank-based, no MCMC.

Method (spec section 3):
  1. Standardise severities with the archived M0 posterior means (no exp(s_t) term --
     per-year scale shocks are not persisted; harmless for signed rank stats, see spec).
  2. Drop RITC observations.
  3. Pairwise Spearman correlations over >=6 common reporting years, binned by pair
     effective size terciles; trend stats D (top-bottom mean rho) and Kendall tau.
  4. Year-median co-movement matrix m_gt across within-year size terciles.
  5. Within-syndicate year-permutation null (B=2000) for one-sided p-values.

Gate: proceed to Stage 1 iff p_perm(D) < 0.20 or p_perm(tau_trend) < 0.20.

Writes systemic_correlation_check_results.json.
Usage:  python systemic_correlation_check.py
"""
import io, json, sys, time
from pathlib import Path
import numpy as np
from scipy import stats

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS = SCRIPT_DIR / "exposure_results.json"
CALIB = SCRIPT_DIR / "dispersion_calibration_ritc.json"
RITC = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
OUT = SCRIPT_DIR / "systemic_correlation_check_results.json"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0
T_MIN = 6
B = 2000
SEED = 42


def load_sample():
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    HHI = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    synd = np.array([str(o["syndicate"]) for o in recs])
    key = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    return S, R, HHI, yr, synd, key


def ritc_flag(key):
    r = json.load(io.open(RITC, encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([k in occ for k in key])


def rank_rows(a):
    """Rank each row (no ties expected: continuous data)."""
    order = np.argsort(a, axis=1)
    ranks = np.empty_like(order)
    rows = np.arange(a.shape[0])[:, None]
    ranks[rows, order] = np.arange(a.shape[1])[None, :]
    return ranks.astype(float)


class PairEngine:
    """Precomputed pair/mask structure; evaluates all pairwise Spearman rhos for a
    given syndicate-by-year residual matrix Z (NaN = missing)."""

    def __init__(self, obs_mask, t_min):
        n_s, n_y = obs_mask.shape
        self.pairs = []          # (i, j)
        masks = {}               # maskbits -> group dict
        for i in range(n_s):
            for j in range(i + 1, n_s):
                m = obs_mask[i] & obs_mask[j]
                if m.sum() < t_min:
                    continue
                bits = int(np.packbits(m, bitorder="little")[:2].view(np.uint16)[0])
                g = masks.setdefault(bits, {"cols": np.where(m)[0], "members": []})
                g["members"].append((len(self.pairs), i, j))
                self.pairs.append((i, j))
        self.groups = []
        for g in masks.values():
            synds = sorted({i for _, i, j in g["members"]} | {j for _, i, j in g["members"]})
            smap = {s: r for r, s in enumerate(synds)}
            idx = np.array([p for p, _, _ in g["members"]])
            gi = np.array([smap[i] for _, i, _ in g["members"]])
            gj = np.array([smap[j] for _, _, j in g["members"]])
            self.groups.append((np.array(synds), g["cols"], idx, gi, gj))
        self.n_pairs = len(self.pairs)

    def rhos(self, Z):
        rho = np.empty(self.n_pairs)
        for synds, cols, idx, gi, gj in self.groups:
            sub = Z[np.ix_(synds, cols)]
            rk = rank_rows(sub)
            rk -= rk.mean(axis=1, keepdims=True)
            rk /= np.sqrt((rk ** 2).sum(axis=1, keepdims=True))
            rho[idx] = (rk[gi] * rk[gj]).sum(axis=1)
        return rho


def year_medians(Z, tercile_of, n_y):
    """m_gt matrix (3 x n_y): median residual per within-year size tercile."""
    m = np.full((3, n_y), np.nan)
    for t in range(n_y):
        for g in range(3):
            v = Z[:, t][tercile_of[:, t] == g]
            v = v[~np.isnan(v)]
            if v.size:
                m[g, t] = np.median(v)
    return m


def spearman(a, b):
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < 3:
        return np.nan
    return stats.spearmanr(a[ok], b[ok]).statistic


def main():
    t0 = time.time()
    S, R, HHI, yr, synd, key = load_sample()
    ritc = ritc_flag(key)
    n_dropped = int(ritc.sum())
    keep = ~ritc
    S, R, HHI, yr, synd = S[keep], R[keep], HHI[keep], yr[keep], synd[keep]

    c = json.load(io.open(CALIB, encoding="utf-8"))
    k_hat, g_hat = c["k"], c["gamma"]
    sd_u, sd_d = c["sd_undiv"], c["sd_div"]
    log_reff = np.log(R / REFERENCE_SIZE) - g_hat * np.log(HHI)
    sigma_hat = np.sqrt(sd_u ** 2 + sd_d ** 2 * np.exp(2.0 * (k_hat - 1.0) * log_reff))
    z = S / sigma_hat
    reff = np.exp(log_reff)

    years = np.sort(np.unique(yr))
    synds = np.sort(np.unique(synd))
    n_y, n_s = len(years), len(synds)
    yidx = np.searchsorted(years, yr)
    sidx = np.searchsorted(synds, synd)

    Z = np.full((n_s, n_y), np.nan)
    RE = np.full((n_s, n_y), np.nan)
    Z[sidx, yidx] = z
    RE[sidx, yidx] = reff
    obs_mask = ~np.isnan(Z)
    print(f"n={len(z)} (dropped {n_dropped} RITC)  syndicates={n_s}  years={n_y}")

    # ---- pairwise structure ------------------------------------------------
    eng = PairEngine(obs_mask, T_MIN)
    print(f"pairs with >= {T_MIN} common years: {eng.n_pairs}")
    med_reff = np.array([np.nanmedian(RE[i]) for i in range(n_s)])
    pair_i = np.array([p[0] for p in eng.pairs])
    pair_j = np.array([p[1] for p in eng.pairs])
    pair_size = np.sqrt(med_reff[pair_i] * med_reff[pair_j]) * REFERENCE_SIZE  # GBP m
    pair_common = np.array([(obs_mask[i] & obs_mask[j]).sum() for i, j in eng.pairs])
    order = np.argsort(pair_size)
    tercile = np.zeros(eng.n_pairs, int)
    for g, chunk in enumerate(np.array_split(order, 3)):
        tercile[chunk] = g

    # within-year size terciles for the year-median matrix
    tercile_of = np.full((n_s, n_y), -1)
    for t in range(n_y):
        rows = np.where(obs_mask[:, t])[0]
        o = rows[np.argsort(RE[rows, t])]
        for g, chunk in enumerate(np.array_split(o, 3)):
            tercile_of[chunk, t] = g

    def all_stats(Zm):
        rho = eng.rhos(Zm)
        D = rho[tercile == 2].mean() - rho[tercile == 0].mean()
        tau = stats.kendalltau(np.log(pair_size), rho).statistic
        m_gt = year_medians(Zm, tercile_of, n_y)
        xs = {"small_mid": spearman(m_gt[0], m_gt[1]),
              "small_large": spearman(m_gt[0], m_gt[2]),
              "mid_large": spearman(m_gt[1], m_gt[2])}
        return rho, D, tau, m_gt, xs

    rho_obs, D_obs, tau_obs, m_gt_obs, xs_obs = all_stats(Z)

    # ---- permutation null --------------------------------------------------
    rng = np.random.default_rng(SEED)
    row_pos = [np.where(obs_mask[i])[0] for i in range(n_s)]
    ge_D = ge_tau = 0
    ge_xs = {kk: 0 for kk in xs_obs}
    for b in range(B):
        Zp = np.full_like(Z, np.nan)
        for i in range(n_s):
            pos = row_pos[i]
            Zp[i, pos] = Z[i, pos[rng.permutation(len(pos))]]
        _, D_p, tau_p, _, xs_p = all_stats(Zp)
        ge_D += D_p >= D_obs
        ge_tau += tau_p >= tau_obs
        for kk in ge_xs:
            if not np.isnan(xs_p[kk]) and xs_p[kk] >= xs_obs[kk]:
                ge_xs[kk] += 1
    p_D = (1 + ge_D) / (B + 1)
    p_tau = (1 + ge_tau) / (B + 1)
    p_xs = {kk: (1 + v) / (B + 1) for kk, v in ge_xs.items()}

    gate = bool(p_D < 0.20 or p_tau < 0.20)

    bins = []
    for g, name in enumerate(["small", "mid", "large"]):
        m = tercile == g
        bins.append({
            "bin": name, "n_pairs": int(m.sum()),
            "mean_rho": float(rho_obs[m].mean()),
            "median_rho": float(np.median(rho_obs[m])),
            "mean_common_years": float(pair_common[m].mean()),
            "reff_range": [float(pair_size[m].min()), float(pair_size[m].max())],
        })

    out = {
        "n_obs": int(len(z)), "n_dropped_ritc": n_dropped,
        "n_syndicates": int(n_s), "n_years": int(n_y),
        "n_pairs": int(eng.n_pairs), "t_min": T_MIN, "b_permutations": B, "seed": SEED,
        "m0_source": "dispersion_calibration_ritc.json",
        "note_sigma_hat": "per-year exp(s_t) omitted (not persisted in M0 outputs); "
                          "rank-preserving under the null, see spec section 3.1",
        "pair_bins": bins,
        "trend": {"D": float(D_obs), "p_perm_D": float(p_D),
                  "tau_trend": float(tau_obs), "p_perm_tau": float(p_tau)},
        "year_median_matrix": {
            "years": [int(y) for y in years],
            "terciles": ["small", "mid", "large"],
            "m_gt": [[None if np.isnan(v) else round(float(v), 4) for v in row]
                     for row in m_gt_obs],
            "cross_tercile_spearman": {kk: {"rho": float(v), "p_perm": float(p_xs[kk])}
                                       for kk, v in xs_obs.items()},
            "sd_by_tercile": {name: float(np.nanstd(m_gt_obs[g]))
                              for g, name in enumerate(["small", "mid", "large"])},
        },
        "gate_passed": gate,
        "runtime_seconds": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}  ({out['runtime_seconds']}s)")
    for bn in bins:
        print(f"  {bn['bin']:>5}: n={bn['n_pairs']:4d}  mean rho={bn['mean_rho']:+.4f}"
              f"  median rho={bn['median_rho']:+.4f}")
    print(f"  D = {D_obs:+.4f}  (p_perm={p_D:.4f})")
    print(f"  tau_trend = {tau_obs:+.4f}  (p_perm={p_tau:.4f})")
    for kk, v in xs_obs.items():
        print(f"  year-median corr {kk}: {v:+.3f} (p_perm={p_xs[kk]:.4f})")
    print(f"  GATE {'PASSED' if gate else 'FAILED'} -> "
          f"{'proceed to Stage 1' if gate else 'stop (record negative result)'}")


if __name__ == "__main__":
    sys.exit(main())
