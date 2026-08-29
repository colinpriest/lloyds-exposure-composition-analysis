"""Referee/author check: is the undiversifiable floor supported WHERE IT BITES?

check_pooling_cv_extended.py compared the floor and no-floor models on POOLED
held-out ELPD across all 790 syndicate-years and found them indistinguishable
(+1.5 +- 1.2 in the no-floor model's favour).  That test has almost no power for
the floor: the two fitted scales agree to within ~3% from 50m to 1bn of reserves,
so the ~750 small and mid-sized observations contribute near-zero signal and simply
add noise, while the handful of very large syndicates that the floor actually
affects are swamped.

This re-runs the same by-syndicate 5-fold cross-validation but RETAINS the
per-observation held-out ELPD, then decomposes the floor-vs-no-floor difference by
reserve size.  The question is whether the floor model predicts LARGE held-out
syndicates better, which is the comparison that bears on the claim.

Reported per stratum: paired Delta ELPD (floor minus no-floor), a plain SE, a
syndicate-clustered SE (the honest one, since a large syndicate contributes several
years), per-observation mean gain, and the win rate.

Writes check_floor_large_syndicates_results.json.
Usage:  python check_floor_large_syndicates.py
"""
import io, json
from pathlib import Path
import numpy as np
from scipy import stats
from scipy.special import logsumexp
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm

from oos_validation import load, REF, HLO, HCE, SEED, K
from check_pooling_cv_extended import MODELS, fit, sigma_draws, held_out_lppd

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_floor_large_syndicates_results.json"

# Size strata (GBP m).  The floor/no-floor scales diverge above roughly 2bn.
STRATA = [("all", 0.0, np.inf),
          ("lt_100m", 0.0, 100.0),
          ("100m_500m", 100.0, 500.0),
          ("500m_2bn", 500.0, 2000.0),
          ("gt_2bn", 2000.0, np.inf),
          ("gt_5bn", 5000.0, np.inf),
          ("gt_10bn", 10000.0, np.inf)]


BB = 20000   # Bayesian-bootstrap draws


def cluster_se(diff, syn):
    """SE of the summed paired difference, clustering by syndicate."""
    tot = {}
    for d, s in zip(diff, syn):
        tot[s] = tot.get(s, 0.0) + d
    v = np.array(list(tot.values()), float)
    m = len(v)
    if m < 2:
        return float("nan")
    return float(np.sqrt(m) * v.std(ddof=1))


def bayes_boot(diff, syn):
    """Posterior for the stratum ELPD difference: Dirichlet weights on syndicate totals."""
    tot = {}
    for d, s in zip(diff, syn):
        tot[s] = tot.get(s, 0.0) + d
    v = np.array(list(tot.values()), float)
    if len(v) < 2:
        return None
    rng = np.random.default_rng(SEED)
    W = rng.dirichlet(np.ones(len(v)), size=BB)
    draws = len(v) * (W @ v)
    return {"bb_mean": float(draws.mean()),
            "bb_2.5": float(np.percentile(draws, 2.5)),
            "bb_97.5": float(np.percentile(draws, 97.5)),
            "P_floor_better": float((draws > 0).mean())}


def main():
    S, R, H, syn = load()
    uniq = np.array(sorted(set(syn)))
    fold_of = {s: i % K for i, s in enumerate(uniq)}
    fold = np.array([fold_of[s] for s in syn])
    print(f"n={len(S)} syndicates={len(uniq)} folds={K}")
    for lo, hi in [(2000.0, np.inf), (5000.0, np.inf), (10000.0, np.inf)]:
        m = (R >= lo) & (R < hi)
        print(f"  R in [{lo:.0f}, {hi}): {m.sum()} obs, {len(set(syn[m]))} syndicates")

    e_floor = np.full(len(S), np.nan)
    e_nofloor = np.full(len(S), np.nan)
    for fdx in range(K):
        te = fold == fdx; tr = ~te
        print(f"  fold {fdx}: train {tr.sum()} / test {te.sum()}")
        d1 = fit(S[tr], R[tr], H[tr], MODELS["M1_free_k_floor"], draws=1000, tune=1000)
        d7 = fit(S[tr], R[tr], H[tr], MODELS["M7_free_k_nofloor"], draws=1000, tune=1000)
        e_floor[te] = held_out_lppd(S[te], R[te], H[te], d1)
        e_nofloor[te] = held_out_lppd(S[te], R[te], H[te], d7)

    diff = e_floor - e_nofloor            # positive => floor model predicts better
    res = {"n": int(len(S)), "n_syndicates": int(len(uniq)), "folds": K, "seed": SEED,
           "sign_convention": "Delta = ELPD(floor) - ELPD(no floor); positive favours the floor",
           "strata": {}}
    print("\n" + "=" * 86)
    print(f"{'stratum':<12}{'n':>5}{'syn':>5}{'dELPD':>10}{'SE':>8}{'clSE':>8}"
          f"{'z_cl':>7}{'per-obs':>10}{'win%':>7}")
    for name, lo, hi in STRATA:
        m = (R >= lo) & (R < hi) & np.isfinite(diff)
        n = int(m.sum())
        if n == 0:
            continue
        d = diff[m]
        tot = float(d.sum())
        se = float(np.sqrt(n) * d.std(ddof=1)) if n > 1 else float("nan")
        cse = cluster_se(d, syn[m])
        z = tot / cse if cse and np.isfinite(cse) and cse > 0 else float("nan")
        rec = {"n_obs": n, "n_syndicates": int(len(set(syn[m]))),
               "delta_ELPD_floor_minus_nofloor": tot,
               "SE_plain": se, "SE_clustered_by_syndicate": cse,
               "z_clustered": z, "per_obs_mean": tot / n,
               "pct_obs_floor_better": float((d > 0).mean() * 100),
               "bayes_bootstrap": bayes_boot(d, syn[m]),
               "elpd_floor": float(e_floor[m].sum()),
               "elpd_nofloor": float(e_nofloor[m].sum())}
        res["strata"][name] = rec
        print(f"{name:<12}{n:>5}{rec['n_syndicates']:>5}{tot:>10.2f}{se:>8.2f}"
              f"{cse:>8.2f}{z:>7.2f}{rec['per_obs_mean']:>10.4f}"
              f"{rec['pct_obs_floor_better']:>7.0f}")

    # Which individual large syndicate-years drive it?
    big = np.where(R >= 2000.0)[0]
    order = big[np.argsort(-np.abs(diff[big]))][:12]
    res["largest_contributors"] = [
        {"syndicate": int(syn[i]), "R_m": float(R[i]), "S": float(S[i]),
         "elpd_floor": float(e_floor[i]), "elpd_nofloor": float(e_nofloor[i]),
         "delta": float(diff[i])} for i in order]
    print("\ntop |contributions| among R >= 2bn (positive favours the floor):")
    for r in res["largest_contributors"]:
        print(f"   syn {r['syndicate']:>5}  R={r['R_m']:>8.0f}m  S={r['S']:+.3f}  "
              f"delta={r['delta']:+.3f}")

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
