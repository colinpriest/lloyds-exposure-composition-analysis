"""Check 3 (referee): M1 (free k) vs M2 (k=0.5, sqrt-N + floor) under BY-SYNDICATE 5-fold CV.

Appendix 3.1 adjudicates M1 vs M2 on observation-level PSIS-LOO (optimistic under
clustering). This re-runs the comparison on the identical five-fold by-syndicate folds used
by the headline OOS check (oos_validation.py), scoring held-out ELPD. Reports
Delta ELPD(M1 - M2), its SE, and the fraction of held-out syndicate-years where M1 has
higher predictive density. Both models carry the undiversifiable floor and drop the year
shock (as in oos_validation), so the comparison isolates the pooling FORM.

Writes check_pooling_cv_results.json.
Usage:  python check_pooling_cv.py
"""
import io, json, sys
from pathlib import Path
import numpy as np
from scipy import stats
from scipy.special import logsumexp
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm

from oos_validation import load, sigma_draws, held_out_lppd, REF, HLO, HCE, SEED, K

SD = Path(__file__).resolve().parent
OUT = SD / "check_pooling_cv_results.json"


def fit_pooling(S, R, H, free_k):
    logR = np.log(R / REF); logH = np.log(H)
    with pm.Model():
        nu = pm.Gamma("nu", 2.0, 0.1)
        if free_k:
            theta = pm.Normal("theta", 0.0, 1.5)
            k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
        else:
            k = pm.Deterministic("k", pm.math.constant(0.5))
        gamma = pm.HalfNormal("gamma", 1.0)
        log_tot = pm.Normal("log_tot", np.log(0.05), 1.0); tot = pm.math.exp(log_tot)
        f = pm.Beta("f", 1.0, 1.0)
        su = pm.Deterministic("sd_undiv", tot * pm.math.sqrt(f))
        sd = pm.Deterministic("sd_div", tot * pm.math.sqrt(1.0 - f))
        var = su ** 2 + sd ** 2 * pm.math.exp(2.0 * (k - 1.0) * (logR - gamma * logH))
        pm.StudentT("S_obs", nu=nu, mu=0.0, sigma=pm.math.sqrt(var), observed=S)
        idata = pm.sample(1000, tune=1000, chains=4, cores=1, target_accept=0.95,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    return {v: p[v].values.ravel() for v in ("nu", "k", "gamma", "sd_undiv", "sd_div")}


def main():
    S, R, H, syn = load()
    uniq = np.array(sorted(set(syn)))
    fold_of = {s: i % K for i, s in enumerate(uniq)}
    fold = np.array([fold_of[s] for s in syn])
    print(f"n={len(S)} syndicates={len(uniq)} folds={K}")

    elpd_m1 = np.full(len(S), np.nan); elpd_m2 = np.full(len(S), np.nan)
    for fdx in range(K):
        te = fold == fdx; tr = ~te
        print(f"  fold {fdx}: train {tr.sum()} / test {te.sum()}")
        d1 = fit_pooling(S[tr], R[tr], H[tr], free_k=True)
        d2 = fit_pooling(S[tr], R[tr], H[tr], free_k=False)
        elpd_m1[te] = held_out_lppd(S[te], R[te], H[te], d1, "model")
        elpd_m2[te] = held_out_lppd(S[te], R[te], H[te], d2, "model")

    diff = elpd_m1 - elpd_m2
    E1, E2 = float(np.nansum(elpd_m1)), float(np.nansum(elpd_m2))
    dE = float(np.nansum(diff)); se = float(np.sqrt(len(diff)) * np.nanstd(diff))
    res = {
        "n": int(len(S)), "n_syndicates": int(len(uniq)), "folds": K, "seed": SEED,
        "criterion": "5-fold by-syndicate held-out ELPD (matches Section 4.6 OOS)",
        "held_out_ELPD_M1_free_k": E1, "held_out_ELPD_M2_sqrtN_floor": E2,
        "delta_ELPD_M1_minus_M2": dE, "delta_SE": se, "z": dE / se if se else None,
        "pct_held_out_M1_higher_density": float(np.mean(diff > 0) * 100),
        "note_psis_loo_appendix31": "PSIS-LOO gave M1-M2 ~+1 (approx 1 SE); this is the "
                                    "conservative by-syndicate CV counterpart",
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"by-syndicate CV held-out ELPD:  M1(free k) = {E1:.2f}   M2(sqrtN+floor) = {E2:.2f}")
    print(f"Delta(M1 - M2) = {dE:+.2f}   SE = {se:.2f}   z = {res['z']:+.2f}")
    print(f"M1 higher density on {res['pct_held_out_M1_higher_density']:.0f}% of held-out syndicate-years")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
