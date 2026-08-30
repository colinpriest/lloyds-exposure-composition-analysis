#!/usr/bin/env python3
"""Is the size-correlation profile explained by a rising SYSTEMIC SHARE of variance?

The question. Larger syndicates co-move more (Figure 6). The manuscript has been
attributing that residual excess to pair-specific "shared slips", which the fitted models
cannot identify. There is a competing explanation that costs no new mechanism at all.

The adopted model already splits each syndicate's variance in two:

    Var(S_it) = sigma_undiv^2  +  sigma_div^2 * E_it^{2(k-1)}
                ^undiversifiable   ^diversifiable, decays with effective size E

so the UNDIVERSIFIABLE SHARE of variance,

    s_it = sigma_undiv^2 / Var(S_it),

necessarily rises with size: the diversifiable term decays for every k < 1 while the
floor does not. A large book is floor-dominated; a small one is noise-dominated.

Here is the point. The fitted model treats that floor as undiversifiable WITHIN a book
but INDEPENDENT ACROSS books -- the errors are iid, so conditional on the year it implies
zero cross-sectional correlation. If instead the undiversifiable component is SYSTEMIC,
i.e. one draw shared by the whole market in a year,

    S_it = sigma_undiv * Z_t  +  sigma_div * E_it^{k-1} * eps_it,

then the marginal variance is UNCHANGED -- every fitted parameter still applies -- but

    corr(S_it, S_jt) = sigma_undiv^2 / sqrt(Var_i * Var_j) = sqrt(s_i * s_j).

That is a prediction with NO FREE PARAMETERS. It is pinned entirely by sigma_undiv,
sigma_div, k and gamma, all already estimated from the marginal size ladder and none of
them fitted to any correlation. It says large pairs must co-move more, and it says by
exactly how much. So it can fail, which is what makes it worth running.

Three things are reported:

  1. the implied correlation profile by pair-size tercile against the observed one;
  2. whether the implied top-tercile value covers the observed excess that the
     independent-floor model misses;
  3. a falsification check -- the profile the same algebra predicts if the floor were
     NOT systemic, which is flat at zero.

Spearman against Pearson: the observed profile uses Spearman rho, so the implied Pearson
correlation is mapped through the elliptical relationship rho_S = (6/pi) arcsin(rho_P/2)
before comparison. The unmapped values are reported too, since the mapping is exact only
in the Gaussian case and the fitted tails are heavy.

Run:  python src/check_systemic_share.py
"""
import io
import json
import os
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from calibrate_dispersion_systemic import load_sample, ritc_flag        # noqa: E402
from systemic_correlation_check import PairEngine                       # noqa: E402

ROOT = os.path.dirname(HERE)
CALIB = os.path.join(ROOT, "model", "dispersion_calibration_ritc.json")
OUT = os.path.join(ROOT, "results", "check_systemic_share_results.json")
REFERENCE_SIZE, T_MIN, SEED = 500.0, 4, 42


def spearman_from_pearson(rp):
    """Elliptical-copula map. Exact for the Gaussian case."""
    return (6.0 / np.pi) * np.arcsin(np.clip(rp, -1.0, 1.0) / 2.0)


def main():
    S, R, HHI, yr, key, W, gpw = load_sample()
    ritc = ritc_flag(key)
    c = json.load(io.open(CALIB, encoding="utf-8"))
    k, gamma = c["k"], c["gamma"]
    su, sd = c["sd_undiv"], c["sd_div"]

    years = np.sort(np.unique(yr))
    n_y = len(years)
    yidx = np.searchsorted(years, yr)
    synd = np.array([int(str(s).split("_")[0]) for s in key])

    log_reff = np.log(R / REFERENCE_SIZE) - gamma * np.log(np.clip(HHI, 0.01, 1.0))
    var_div = sd ** 2 * np.exp(2.0 * (k - 1.0) * log_reff)
    var_tot = su ** 2 + var_div
    share = su ** 2 / var_tot                       # systemic share, if the floor is shared
    sigma_hat = np.sqrt(var_tot)

    # --- same pair/tercile construction as the Figure 6 profile ---------------
    clean = ritc < 0.5
    csynd, cy, cre = synd[clean], yidx[clean], np.exp(log_reff)[clean]
    synds = np.sort(np.unique(csynd))
    n_s = len(synds)
    sidx = np.searchsorted(synds, csynd)
    obs_mask = np.zeros((n_s, n_y), bool)
    obs_mask[sidx, cy] = True
    RE = np.full((n_s, n_y), np.nan)
    RE[sidx, cy] = cre
    SH = np.full((n_s, n_y), np.nan)
    SH[sidx, cy] = share[clean]

    eng = PairEngine(obs_mask, T_MIN)
    med_reff = np.nanmedian(RE, axis=1)
    med_share = np.nanmedian(SH, axis=1)
    pi = np.array([p[0] for p in eng.pairs])
    pj = np.array([p[1] for p in eng.pairs])
    pair_size = np.sqrt(med_reff[pi] * med_reff[pj]) * REFERENCE_SIZE

    order = np.argsort(pair_size)
    tercile = np.zeros(eng.n_pairs, int)
    for g, chunk in enumerate(np.array_split(order, 3)):
        tercile[chunk] = g

    # --- observed profile ------------------------------------------------------
    z = (S / sigma_hat)[clean]
    Z = np.full((n_s, n_y), np.nan)
    Z[sidx, cy] = z
    rho_obs = eng.rhos(Z)
    obs_bins = np.array([rho_obs[tercile == g].mean() for g in range(3)])

    # --- the prediction, with no free parameters -------------------------------
    rho_pred_p = np.sqrt(med_share[pi] * med_share[pj])
    rho_pred_s = spearman_from_pearson(rho_pred_p)
    pred_bins_p = np.array([rho_pred_p[tercile == g].mean() for g in range(3)])
    pred_bins_s = np.array([rho_pred_s[tercile == g].mean() for g in range(3)])

    size_bins = [float(np.exp(np.log(pair_size[tercile == g]).mean()))
                 for g in range(3)]
    share_bins = [float(np.sqrt(med_share[pi] * med_share[pj])[tercile == g].mean())
                  for g in range(3)]

    # rank agreement between predicted and observed, across all pairs
    tau = stats.kendalltau(rho_pred_p, rho_obs)
    # and the slope each implies across terciles
    D_obs = obs_bins[2] - obs_bins[0]
    D_pred = pred_bins_s[2] - pred_bins_s[0]

    print("systemic-share hypothesis: does a rising floor share explain the profile?\n")
    print("  fitted: k=%.3f  gamma=%.3f  sd_undiv=%.4f  sd_div=%.4f  (n=%d clean pairs "
          "from %d syndicates)" % (k, gamma, su, sd, eng.n_pairs, n_s))
    print("  NOTE: none of these was fitted to any correlation.\n")
    print("  tercile   pair size    implied     observed    implied rho_S")
    print("            (GBP m)      share       rho_S       (unmapped rho_P)")
    for g in range(3):
        print("  %-9s %9.1f   %8.3f    %+8.3f    %+8.3f  (%.3f)"
              % (("small", "mid", "large")[g], size_bins[g], share_bins[g] ** 2,
                 obs_bins[g], pred_bins_s[g], pred_bins_p[g]))
    print("\n  tercile spread (large - small): observed %+0.4f, implied %+0.4f"
          % (D_obs, D_pred))
    print("  rank agreement across all pairs: Kendall tau = %+0.3f (p = %.3g)"
          % (tau.statistic, tau.pvalue))
    print("\n  falsification: if the floor were NOT systemic (the fitted model's own\n"
          "  assumption, iid errors) the implied profile would be flat at 0.000.")

    covered = bool(pred_bins_s[2] >= obs_bins[2])
    print("\n  implied large-tercile correlation %s the observed %.3f"
          % ("COVERS" if covered else "does NOT cover", obs_bins[2]))

    # --- how much of the floor behaves as shared? ------------------------------
    # A wholly systemic floor over-predicts; a wholly idiosyncratic one predicts zero.
    # corr = phi * sqrt(s_i s_j) with phi the shared FRACTION of floor variance.
    # Regression through the origin, syndicate-block bootstrap: pairs sharing a
    # syndicate are not independent, so an iid bootstrap would understate the width.
    x, y = rho_pred_s, rho_obs
    phi_hat = float((x * y).sum() / (x * x).sum())
    rng = np.random.default_rng(SEED)
    boot = np.empty(4000)
    for b in range(boot.size):
        keep = rng.random(n_s) < 0.5
        m = keep[pi] & keep[pj]
        if m.sum() < 50:
            boot[b] = np.nan
            continue
        boot[b] = (x[m] * y[m]).sum() / (x[m] * x[m]).sum()
    boot = boot[np.isfinite(boot)]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    p_pos = float((boot > 0).mean())
    p_lt1 = float((boot < 1).mean())
    print("\n  shared fraction of floor variance: phi = %.2f [%.2f, %.2f]"
          % (phi_hat, lo, hi))
    print("     P(phi > 0) = %.3f   P(phi < 1) = %.3f" % (p_pos, p_lt1))
    print("     phi = 0 is the fitted model's iid floor; phi = 1 is a wholly systemic "
          "floor.")

    out = {
        "hypothesis": "the undiversifiable floor is a systemic (market-shared) "
                      "component, so the systemic variance share rises with size and "
                      "large pairs co-move more",
        "prediction": "corr(S_i,S_j) = sqrt(s_i*s_j), s = sd_undiv^2/Var; NO free "
                      "parameters -- pinned by the marginal size-ladder fit",
        "note": "sd_undiv, sd_div, k, gamma were estimated from marginal severities "
                "only; none was fitted to any correlation",
        "params": {"k": k, "gamma": gamma, "sd_undiv": su, "sd_div": sd},
        "n_pairs": int(eng.n_pairs), "n_syndicates": int(n_s), "t_min": T_MIN,
        "terciles": {
            "pair_size_gbp_m": size_bins,
            "implied_systemic_share": [float(x ** 2) for x in share_bins],
            "observed_spearman": [float(x) for x in obs_bins],
            "implied_spearman": [float(x) for x in pred_bins_s],
            "implied_pearson": [float(x) for x in pred_bins_p],
        },
        "tercile_spread": {"observed": float(D_obs), "implied": float(D_pred)},
        "rank_agreement": {"kendall_tau": float(tau.statistic),
                           "p_value": float(tau.pvalue)},
        "implied_covers_observed_large_tercile": covered,
        "shared_fraction_phi": {
            "estimate": phi_hat, "hdi_2.5": float(lo), "hdi_97.5": float(hi),
            "P_gt_0": p_pos, "P_lt_1": p_lt1,
            "interpretation": "fraction of the undiversifiable floor VARIANCE that "
                              "behaves as market-shared; phi=0 is the fitted model's "
                              "iid floor, phi=1 a wholly systemic one",
            "method": "regression through the origin of observed Spearman rho on "
                      "phi*sqrt(s_i s_j), syndicate-block bootstrap (pairs sharing a "
                      "syndicate are not independent)",
        },
        "falsification_note": "under the fitted model's own iid-error assumption the "
                              "implied profile is flat at zero, so this prediction "
                              "can fail",
    }
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, indent=2) + "\n")
    print("\nwrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
