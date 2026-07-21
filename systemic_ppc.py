"""Stage 2 of specifications/systemic-analysis.md -- posterior predictive check
and sensitivities for the systemic location year effect (M1).

  A. PPC: 500 M1 posterior draws -> replicated severities on the observed panel
     design -> exact Stage-0 pipeline (same plug-in sigma_hat, same pair set) ->
     compare observed D / tau_trend / per-bin mean rho to replicate bands.
  B. Leave-one-year-out: refit M1 dropping each reporting year; flag if any single
     year moves the tau_m posterior mean by more than 50%.
  C. Prior sensitivity: tau_m ~ HalfNormal(0.025 / 0.05 / 0.10).
  D. RITC treatment: refit M1 on clean observations only.

Writes systemic_ppc_results.json and systemic_correlation_profile.png.
Usage:  python systemic_ppc.py
"""
import io, json, sys, time
from pathlib import Path
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from calibrate_dispersion_systemic import (load_sample, ritc_flag, build_and_fit,
                                           derived, post_row, diag,
                                           REFERENCE_SIZE, NU_VAR_EPS)
from systemic_correlation_check import PairEngine, T_MIN

SCRIPT_DIR = Path(__file__).resolve().parent
CALIB_M0 = SCRIPT_DIR / "model" / "dispersion_calibration_ritc.json"
CALIB_M1 = SCRIPT_DIR / "model" / "dispersion_calibration_systemic.json"
DRAWS_M1 = SCRIPT_DIR / "model" / "dispersion_posterior_draws_systemic.npz"
OUT = SCRIPT_DIR / "results" / "systemic_ppc_results.json"
FIG = SCRIPT_DIR / "figures" / "systemic_correlation_profile.png"
SEED = 42
N_REPS = 500


def main():
    t0 = time.time()
    S, R, HHI, yr, key, W, gpw = load_sample()
    ritc = ritc_flag(key).astype(float)
    synd = np.array([k.split("_")[0] for k in key])
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    n_y, n = len(years), len(S)
    logR = np.log(R / REFERENCE_SIZE)
    logH = np.log(HHI)

    # ---- Stage-0 pipeline objects (clean subset, fixed pair set) -------------
    c0 = json.load(io.open(CALIB_M0, encoding="utf-8"))
    log_reff0 = logR - c0["gamma"] * logH
    sigma_hat = np.sqrt(c0["sd_undiv"] ** 2
                        + c0["sd_div"] ** 2 * np.exp(2.0 * (c0["k"] - 1.0) * log_reff0))
    reff0 = np.exp(log_reff0)
    clean = ritc < 0.5
    csynd, cy, cre = synd[clean], yidx[clean], reff0[clean]
    synds = np.sort(np.unique(csynd))
    n_s = len(synds)
    sidx = np.searchsorted(synds, csynd)
    obs_mask = np.zeros((n_s, n_y), bool)
    obs_mask[sidx, cy] = True
    RE = np.full((n_s, n_y), np.nan)
    RE[sidx, cy] = cre
    eng = PairEngine(obs_mask, T_MIN)
    med_reff = np.nanmedian(RE, axis=1)
    pi = np.array([p[0] for p in eng.pairs])
    pj = np.array([p[1] for p in eng.pairs])
    pair_size = np.sqrt(med_reff[pi] * med_reff[pj]) * REFERENCE_SIZE  # GBP m
    order = np.argsort(pair_size)
    tercile = np.zeros(eng.n_pairs, int)
    for g, chunk in enumerate(np.array_split(order, 3)):
        tercile[chunk] = g

    def profile(S_vec):
        """Stage-0 statistics for a full-sample severity vector."""
        z = (S_vec / sigma_hat)[clean]
        Z = np.full((n_s, n_y), np.nan)
        Z[sidx, cy] = z
        rho = eng.rhos(Z)
        bins = np.array([rho[tercile == g].mean() for g in range(3)])
        D = bins[2] - bins[0]
        tau = stats.kendalltau(np.log(pair_size), rho).statistic
        return bins, D, tau

    bins_obs, D_obs, tau_obs = profile(S)
    print(f"observed: bins={np.round(bins_obs,4)}  D={D_obs:+.4f}  tau={tau_obs:+.4f}")

    # ---- A. PPC --------------------------------------------------------------
    dz = np.load(DRAWS_M1)
    n_draws = dz["tau_m"].size
    rng = np.random.default_rng(SEED)
    pick = rng.choice(n_draws, N_REPS, replace=False)
    bins_rep = np.empty((N_REPS, 3))
    D_rep = np.empty(N_REPS)
    tau_rep = np.empty(N_REPS)
    for r, d in enumerate(pick):
        lr = logR - dz["gamma"][d] * logH
        var = dz["sd_undiv"][d] ** 2 + dz["sd_div"][d] ** 2 * np.exp(
            2.0 * (dz["k"][d] - 1.0) * lr)
        sig = np.exp(dz["s_y"][d][yidx] + dz["beta_ritc"][d] * ritc) * np.sqrt(var)
        nu = dz["nu_clean"][d] * np.exp(-dz["lambda_ritc"][d] * ritc)
        S_rep = dz["m_y"][d][yidx] + sig * rng.standard_t(nu)
        bins_rep[r], D_rep[r], tau_rep[r] = profile(S_rep)
    p_D = float((1 + (D_rep >= D_obs).sum()) / (N_REPS + 1))
    p_tau = float((1 + (tau_rep >= tau_obs).sum()) / (N_REPS + 1))
    band = np.percentile(bins_rep, [5, 95], axis=0)
    inside = [bool(band[0, g] <= bins_obs[g] <= band[1, g]) for g in range(3)]
    ppc_pass = bool(all(inside) and 0.05 <= p_D <= 0.95 and 0.05 <= p_tau <= 0.95)
    print(f"PPC: p(D)={p_D:.3f}  p(tau)={p_tau:.3f}  inside={inside}  pass={ppc_pass}"
          f"  ({time.time()-t0:.0f}s)")

    # ---- figure --------------------------------------------------------------
    m1 = json.load(io.open(CALIB_M1, encoding="utf-8"))
    grid = np.logspace(np.log10(20), np.log10(4000), 60)
    nu_d, ts_d = dz["nu_clean"], dz["tau_s"]
    cfac = np.where(nu_d > NU_VAR_EPS, nu_d / (nu_d - 2.0) * np.exp(2 * ts_d ** 2), np.nan)
    curve = np.empty_like(grid)
    for i, sz in enumerate(grid):
        V = cfac * (dz["sd_undiv"] ** 2 + dz["sd_div"] ** 2
                    * (sz / REFERENCE_SIZE) ** (2.0 * (dz["k"] - 1.0)))
        curve[i] = np.nanmean(dz["tau_m"] ** 2 / (dz["tau_m"] ** 2 + V))
    xbin = [float(np.exp(np.log(pair_size[tercile == g]).mean())) for g in range(3)]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.fill_between(xbin, band[0], band[1], color="#9aa5b1", alpha=0.30, lw=0,
                    label="PPC 5-95% band (M1 replicates)")
    ax.plot(xbin, bins_obs, "o-", color="#2166ac", lw=2, markersize=8, zorder=3,
            label="Observed mean pairwise Spearman rho")
    ax.plot(grid, curve, "--", color="#b2182b", lw=2,
            label="M1 implied rho(Reff), equal-size pairs")
    ax.set_xscale("log")
    ax.set_xlabel("Pair effective size Reff (m, geometric mean)")
    ax.set_ylabel("Within-pair correlation of PYD severity")
    ax.set_title("Correlation-vs-size profile: observed vs M1 posterior predictive")
    ax.grid(True, alpha=0.25)
    ax.axhline(0, color="0.5", lw=0.8, alpha=0.5)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG, dpi=150)
    plt.close(fig)
    print(f"wrote {FIG}")

    # ---- B/C/D refits ---------------------------------------------------------
    def fit_summary(tag, **kw):
        t1 = time.time()
        idata = build_and_fit("m1", **kw)
        post = idata.posterior
        p = {q: post[q].values.ravel() for q in
             ["tau_m", "nu_clean", "tau_s", "sd_undiv", "sd_div", "k", "gamma"]}
        der = derived(p)
        _, dg = diag(idata, ["k", "gamma", "nu_clean", "tau_s", "sd_undiv", "tau_m"])
        res = {"tau_m_mean": float(p["tau_m"].mean()),
               "tau_m": post_row(p["tau_m"]),
               "phi_floor_mean": float(np.nanmean(der["phi_floor"])),
               "phi_floor": post_row(der["phi_floor"]),
               "frac_draws_nu_le_2": der["frac_draws_nu_le_2"],
               "diagnostics": dg}
        print(f"  {tag}: tau_m={res['tau_m_mean']:.4f}  "
              f"phi_floor={res['phi_floor_mean']:.3f}  div={dg['divergences']}  "
              f"rhat={dg['max_rhat']:.3f}  ({time.time()-t1:.0f}s)")
        return res

    full_tau_m = float(dz["tau_m"].mean())
    full_phi = float(np.nanmean(dz["phi_floor"]))

    print("\n=== B. leave-one-year-out ===")
    loyo = {}
    for t, y in enumerate(years):
        m = yr != y
        yl = np.searchsorted(np.sort(np.unique(yr[m])), yr[m])
        loyo[str(int(y))] = fit_summary(
            f"drop {y}", S=S[m], logR=logR[m], logH=logH[m], yidx=yl,
            n_y=len(np.unique(yr[m])), ritc=ritc[m])
    shifts = {y: abs(v["tau_m_mean"] - full_tau_m) / full_tau_m
              for y, v in loyo.items()}
    worst = max(shifts, key=shifts.get)
    loyo_flag = {"full_tau_m_mean": full_tau_m,
                 "max_rel_shift": float(shifts[worst]), "worst_year": worst,
                 "exceeds_50pct": bool(shifts[worst] > 0.5)}
    print(f"LOYO worst: drop {worst} -> rel shift {shifts[worst]:.2f} "
          f"(flag={loyo_flag['exceeds_50pct']})")

    print("\n=== C. prior sensitivity ===")
    prior_sens = {"0.05": {"tau_m_mean": full_tau_m, "phi_floor_mean": full_phi,
                           "source": "stage-1 fit"}}
    for psd in [0.025, 0.10]:
        prior_sens[str(psd)] = fit_summary(
            f"HalfNormal({psd})", S=S, logR=logR, logH=logH, yidx=yidx,
            n_y=n_y, ritc=ritc, tau_m_prior_sd=psd)

    print("\n=== D. RITC exclusion ===")
    m = ritc < 0.5
    yl = np.searchsorted(np.sort(np.unique(yr[m])), yr[m])
    ritc_ex = fit_summary("clean only", S=S[m], logR=logR[m], logH=logH[m],
                          yidx=yl, n_y=len(np.unique(yr[m])),
                          ritc=np.zeros(int(m.sum())))
    ritc_ex["rel_shift_tau_m_vs_default"] = float(
        abs(ritc_ex["tau_m_mean"] - full_tau_m) / full_tau_m)

    out = {
        "seed": SEED, "n_reps": N_REPS, "n": int(n), "n_years": int(n_y),
        "n_pairs": int(eng.n_pairs),
        "sources": {"m0": str(CALIB_M0.name), "m1_draws": str(DRAWS_M1.name)},
        "ppc": {
            "D": {"observed": float(D_obs), "band_5_95":
                  [float(np.percentile(D_rep, 5)), float(np.percentile(D_rep, 95))],
                  "p_ppc": p_D},
            "tau_trend": {"observed": float(tau_obs), "band_5_95":
                          [float(np.percentile(tau_rep, 5)),
                           float(np.percentile(tau_rep, 95))],
                          "p_ppc": p_tau},
            "bins": [{"bin": ["small", "mid", "large"][g],
                      "observed_mean_rho": float(bins_obs[g]),
                      "band_5": float(band[0, g]), "band_95": float(band[1, g]),
                      "inside": inside[g]} for g in range(3)],
            "pass": ppc_pass,
        },
        "loyo": loyo, "loyo_flag": loyo_flag,
        "prior_sensitivity": prior_sens,
        "ritc_exclusion": ritc_ex,
        "figure": str(FIG.name),
        "runtime_seconds": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}  ({out['runtime_seconds']:.0f}s total)")


if __name__ == "__main__":
    sys.exit(main())
