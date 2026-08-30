#!/usr/bin/env python3
"""The correlation-by-size profile, residualised on the fitted year factor.

CORRECTION -- read this before the numbers. The first version of this check estimated a
"shared fraction of floor variance" phi = 0.50 from the raw correlation-by-size profile
and reported that the independent floor was "rejected". Review found the analysis
invalid, for a reason that generalises:

    ITS NULL WAS NOT THE FITTED MODEL. The adopted analysis already fits a common
    directional year factor m_t (tau_m ~ 2.2% of reserves, credibly non-zero). ANY
    common additive component induces a rising correlation-by-size profile, because
    large syndicates' diversifiable noise is smaller, so the common part is a larger
    share of their standardised severity. The raw profile against a flat-zero null
    therefore re-measures m_t and mislabels it as a shared floor.

Residualising on the fitted m_t confirms it: the profile collapses (raw tercile means
about +0.02/+0.06/+0.08 become about -0.01/-0.01/-0.00) and the regression diagnostic
falls from +0.50 to about -0.06. There is NO residual shared-floor signal beyond the
year factor already in the model.

The second defect was labelling: the old output called a syndicate-subsampling interval
an "hdi" and its resampling frequencies "P(...)", which are posterior-language labels
for frequentist quantities. This version writes no posterior-language KEY NAMES: it is a
DIAGNOSTIC. Its range is the 5th-95th percentile range induced by posterior draws of
m_t with all other fitted quantities held fixed -- a PARTIAL POSTERIOR-SENSITIVITY
range, not a joint posterior interval for a separately fitted coefficient, and not a
data-resampling interval either. Its single free coefficient is an OLS-through-origin
regression diagnostic.

What remains true and useful:

  * the raw profile is the EXPECTED signature of the fitted year factor -- a systemic
    component whose variance share rises with size as diversifiable noise shrinks;
  * after removing that factor, these data show no additional market-shared floor;
  * pair-specific (shared-slip) dependence is not fitted anywhere and stays open;
  * nothing here bears on the floor, which remains a structural extrapolation choice.

The reserve-weighted working-sample aggregate is reported as DESCRIPTIVE volatility
only. It covers the 790-observation modelling sample (76% of active syndicate-years,
57-80 records per year), embeds the year factor and composition changes, and a scale
interval can never contain zero -- so it cannot evidence a floor and is not offered as
evidence of one.

Run:  python src/check_systemic_share.py
"""
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from calibrate_dispersion_systemic import load_sample, ritc_flag        # noqa: E402
from systemic_correlation_check import PairEngine                       # noqa: E402

ROOT = os.path.dirname(HERE)
CALIB = os.path.join(ROOT, "model", "dispersion_calibration_ritc.json")
DRAWS = os.path.join(ROOT, "model", "dispersion_posterior_draws_systemic.npz")
OUT = os.path.join(ROOT, "results", "check_systemic_share_results.json")
REFERENCE_SIZE, T_MIN, SEED, N_DRAWS = 500.0, 4, 42, 500


def spearman_from_pearson(rp):
    """Elliptical-copula map; exact in the Gaussian case."""
    return (6.0 / np.pi) * np.arcsin(np.clip(rp, -1.0, 1.0) / 2.0)


def build_design(S, R, HHI, yr, key, ritc, params=None):
    """Pair engine, terciles and the share predictor for the clean sub-panel.

    `params` overrides the calibration file (used by the synthetic self-test)."""
    c = params or json.load(io.open(CALIB, encoding="utf-8"))
    k, gamma, su, sd = c["k"], c["gamma"], c["sd_undiv"], c["sd_div"]
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    synd = np.array([int(str(s).split("_")[0]) for s in key])
    log_reff = np.log(R / REFERENCE_SIZE) - gamma * np.log(np.clip(HHI, 0.01, 1.0))
    var_tot = su ** 2 + sd ** 2 * np.exp(2.0 * (k - 1.0) * log_reff)
    D = {"params": {"k": k, "gamma": gamma, "sd_undiv": su, "sd_div": sd},
         "years": years, "yidx": yidx,
         "sigma_hat": np.sqrt(var_tot),
         "share": su ** 2 / var_tot}
    clean = ritc < 0.5
    csynd, cy = synd[clean], yidx[clean]
    synds = np.sort(np.unique(csynd))
    n_s = len(synds)
    sidx = np.searchsorted(synds, csynd)
    obs_mask = np.zeros((n_s, len(years)), bool)
    obs_mask[sidx, cy] = True
    RE = np.full(obs_mask.shape, np.nan)
    RE[sidx, cy] = np.exp(log_reff)[clean]
    SH = np.full(obs_mask.shape, np.nan)
    SH[sidx, cy] = D["share"][clean]
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
    x = spearman_from_pearson(np.sqrt(med_share[pi] * med_share[pj]))
    D.update(clean=clean, sidx=sidx, cy=cy, n_s=n_s, eng=eng,
             tercile=tercile, pair_size=pair_size, x=x)
    return D


def profile(D, severities):
    """Tercile means of pairwise Spearman rho, plus the OLS-through-origin
    coefficient of rho on the share predictor. The coefficient is a regression
    DIAGNOSTIC of profile height, not a posterior quantity."""
    z = (severities / D["sigma_hat"])[D["clean"]]
    Z = np.full((D["n_s"], len(D["years"])), np.nan)
    Z[D["sidx"], D["cy"]] = z
    rho = D["eng"].rhos(Z)
    bins = np.array([rho[D["tercile"] == g].mean() for g in range(3)])
    x = D["x"]
    coef = float((x * rho).sum() / (x * x).sum())
    return bins, coef


def main():
    S, R, HHI, yr, key, W, gpw = load_sample()
    ritc = ritc_flag(key)
    D = build_design(S, R, HHI, yr, key, ritc)
    yidx = D["yidx"]

    dz = np.load(DRAWS)
    m_draws = dz["m_y"]                              # (n_draws, n_years)
    m_mean = m_draws.mean(axis=0)

    bins_raw, coef_raw = profile(D, S)
    bins_res, coef_res = profile(D, S - m_mean[yidx])

    # propagate m_t's posterior uncertainty INTO THE DIAGNOSTIC: one residualised
    # profile per posterior draw of m_t. This is a range across draws of a fitted
    # nuisance, not a posterior distribution for any new parameter.
    rng = np.random.default_rng(SEED)
    pick = rng.choice(m_draws.shape[0], min(N_DRAWS, m_draws.shape[0]), replace=False)
    coefs = np.empty(len(pick))
    top = np.empty(len(pick))
    for i, dr in enumerate(pick):
        b, cf = profile(D, S - m_draws[dr][yidx])
        coefs[i] = cf
        top[i] = b[2]
    lo, hi = np.percentile(coefs, [5, 95])

    print("correlation-by-size profile, against the FITTED model rather than zero\n")
    print("  the adopted analysis fits a common directional year factor m_t; any such")
    print("  factor produces a rising profile, so the raw profile is not evidence of")
    print("  a shared floor. residualising on the fitted m_t:\n")
    print("  tercile means               small     mid    large")
    print("  raw (embeds m_t)          %+7.3f %+7.3f %+7.3f" % tuple(bins_raw))
    print("  minus posterior-mean m_t  %+7.3f %+7.3f %+7.3f" % tuple(bins_res))
    print("\n  regression diagnostic (rho on share predictor, through origin):")
    print("  raw %+0.3f  ->  residualised %+0.3f, range [%+0.3f, %+0.3f] across %d"
          % (coef_raw, coef_res, lo, hi, len(pick)))
    print("  posterior draws of m_t: a partial posterior-sensitivity range (other fitted")
    print("  quantities held fixed), not a joint posterior interval")
    print("\n  conclusion: the raw profile is the expected signature of the fitted")
    print("  year factor; residualised on it there is no residual shared-floor")
    print("  signal. nothing here bears on the floor, which stays a structural")
    print("  choice.")

    # descriptive working-sample aggregate -- explicitly not evidence
    M_obs = S * R
    years = D["years"]
    mkt = np.array([M_obs[yr == y].sum() / R[yr == y].sum() for y in years])
    n_per = [int((yr == y).sum()) for y in years]
    print("\n  descriptive only: reserve-weighted WORKING-SAMPLE aggregate severity")
    print("  (76%% of active syndicate-years; %d-%d records/yr; embeds m_t and"
          % (min(n_per), max(n_per)))
    print("  composition changes; a scale interval cannot contain zero, so this")
    print("  cannot evidence a floor):  year-to-year SD = %.4f"
          % float(mkt.std(ddof=1)))

    out = {
        "correction": "the first version estimated phi=0.50 against a flat-zero null "
                      "and reported the independent floor rejected. That null was "
                      "false: the fitted model already contains a common directional "
                      "year factor m_t, and any common additive component produces a "
                      "rising correlation-by-size profile. Residualised on the fitted "
                      "m_t the profile collapses. The phi estimate, its rejection "
                      "language, and the market-aggregate floor-existence argument "
                      "are withdrawn.",
        "labels": "the coefficient is an OLS-through-origin regression diagnostic. "
                  "The range is the 5th-95th percentile range induced by 500 "
                  "posterior draws of the fitted m_t with all other fitted "
                  "quantities held fixed: a partial posterior-sensitivity range, "
                  "not a joint posterior interval for a separately fitted "
                  "coefficient, and not a data-resampling interval.",
        "params": D["params"],
        "n_pairs": int(D["eng"].n_pairs), "n_syndicates": int(D["n_s"]),
        "t_min": T_MIN, "n_mt_draws": int(len(pick)), "seed": SEED,
        "tercile_means": {
            "raw_embeds_year_factor": [float(v) for v in bins_raw],
            "residualised_posterior_mean_mt": [float(v) for v in bins_res],
            "residualised_large_tercile_range_5_95_across_mt_draws":
                [float(np.percentile(top, 5)), float(np.percentile(top, 95))],
        },
        "regression_diagnostic": {
            "raw": float(coef_raw),
            "residualised": float(coef_res),
            "range_5_95_across_mt_draws": [float(lo), float(hi)],
        },
        "conclusion": "the correlation-by-size profile is the expected signature of "
                      "the fitted directional year factor; residualised on it there "
                      "is no residual signal for a market-shared floor. Pair-specific "
                      "(shared-slip) dependence remains unmodelled. Nothing here "
                      "bears on the floor, which remains a structural extrapolation "
                      "choice.",
        "working_sample_aggregate_descriptive_only": {
            "note": "reserve-weighted severity of the 790-record modelling sample "
                    "(76% of active syndicate-years, unbalanced membership), NOT the "
                    "whole market; embeds the year factor and composition changes; a "
                    "scale interval cannot contain zero, so this is not evidence "
                    "about the floor and is recorded only as descriptive volatility",
            "n_records_per_year": n_per,
            "by_year": [float(v) for v in mkt],
            "sd": float(mkt.std(ddof=1)),
        },
    }
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, indent=2) + "\n")
    print("\nwrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
