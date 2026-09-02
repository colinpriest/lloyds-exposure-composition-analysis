"""FX sensitivity: converted-GBP baseline vs as-reported (nominal) currency.

Since the FX conversion (docs/fx-conversion.md), exposure_results.json is a
single-currency GBP dataset: USD-presented reports are converted at the
reporting-date H.10 spot rate inside run_analysis.py. This script quantifies what
the conversion changes: it refits the adopted two-regime Bayesian model on
(a) the converted baseline as in the bundle and (b) the nominal (as-reported)
sizes reconstructed by multiplying USD observations back by the same year-end
rates, and compares k / gamma / floor / nu_clean and the vignette VaRs.

BOTH fits use the adopted implementation (adopted_model.scale_block) on the
adopted n=790 sample and the ADOPTED sampling configuration -- 4 chains x 1500
draws after 1500 tuning, target_accept 0.98, seed 42: calibrate_dispersion_ritc.py's
call, verbatim -- so the converted fit is the adopted posterior re-drawn, not an
approximation to it. A previous version imported the reduced-draw (2 x 500)
refitter from proxy_stress_bayes.py for tractability and stored point estimates
only; the manuscript then printed that reduced-draw baseline (k=0.608,
gamma=0.260, floor=0.0206, nu_clean=2.40) labelled as the adopted fit. Review
caught it. This version:

  * checks the converted fit against the published calibration with
    adopted_model.check_against_headline (tolerance 0.5 posterior SD) and
    REFUSES to write results if it disagrees;
  * persists posterior mean, SD, 95% HDI and sampling diagnostics (max R-hat,
    min bulk ESS, divergence count) for BOTH fits;
  * persists the DESCRIPTIVE point sensitivities (change and percent change for
    the floor and the Vignette 1 VaR) and, under each fit, CONDITIONAL fit
    summaries: the fit's own-posterior tail-regime ordering, and its floor and k
    HDIs as conditional parameter summaries. The floor-versus-no-floor and
    pooling-endpoint model comparisons are NOT repeated under the nominal
    treatment; the bracketed, floored fit cannot re-establish them, and nothing
    here claims otherwise.

NO between-treatment interval is estimated. A previous version stored
"interval_checks" asking whether the nominal fit's points fell inside the
converted fit's marginal intervals; review was right that containment of one
specification's point in another specification's marginal interval is not an
interval for the between-treatment difference, and says nothing about whether
that difference is small or resolved. Constructing such an interval would need
a declared joint sensitivity analysis over both currency treatments; pairing
separately fitted chains by draw index or a shared seed is not a joint
posterior. The comparison here is therefore explicitly descriptive.

Severity S=PYD/reserves and HHI are within-filing ratios (currency-neutral), so
only the SIZE variable R differs between the two fits.

Run: python src/fx_sensitivity.py
"""
import io, json
from pathlib import Path

import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from adopted_model import load_sample, scale_block, check_against_headline, report, TOL_SD
from proxy_stress_bayes import outputs

SD = Path(__file__).resolve().parent.parent

# The ADOPTED sampling configuration -- calibrate_dispersion_ritc.py's pm.sample
# call, verbatim. src/test_fx_sensitivity.py reads that script's AST and fails if
# these ever drift from it.
DRAWS, TUNE, CHAINS, TARGET_ACCEPT, SEED = 1500, 1500, 4, 0.98, 42

PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")


def fx_map():
    """(is_usd, rate) per observation key from the converted bundle."""
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    m = {}
    for o in d["observations"]:
        k = f"{o['syndicate']}_{o['year']}"
        m[k] = (bool(o.get("fx_applied")), o.get("fx_rate_usd_per_gbp"))
    return m


def fit_adopted_config(S, R, H, yr, ritc):
    """One fit of the adopted model at the adopted sampling configuration."""
    with pm.Model():
        b = scale_block(R, H, yr, ritc)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=1,
                          target_accept=TARGET_ACCEPT, random_seed=SEED,
                          progressbar=False)
    summ = az.summary(idata, var_names=list(PARAMS), hdi_prob=0.95, round_to=6)
    post = idata.posterior
    params = {}
    for p in PARAMS:
        a = post[p].values.ravel()
        params[p] = {"mean": float(a.mean()), "sd": float(a.std(ddof=1)),
                     "hdi_2.5": float(summ.loc[p, "hdi_2.5%"]),
                     "hdi_97.5": float(summ.loc[p, "hdi_97.5%"])}
    diag = {"max_rhat": float(summ["r_hat"].max()),
            "min_ess_bulk": float(summ["ess_bulk"].min()),
            "divergences": int(idata.sample_stats["diverging"].values.sum())}
    means = {p: params[p]["mean"] for p in PARAMS}
    draws = {p: post[p].values.ravel() for p in PARAMS}
    # CONDITIONAL summaries of THIS fit, within the adopted specification. The
    # tail-regime ordering is re-established on this fit's own posterior. The
    # floor and k rows are conditional parameter summaries ONLY: the fitted model
    # excludes the no-floor alternative and brackets k in (0.5, 1), so they
    # cannot re-establish the floor-versus-no-floor or pooling-endpoint model
    # comparisons, which are not repeated under this treatment. (A previous
    # version called this block "qualitative" with a floor_hdi95_positive
    # Boolean, presenting conditional summaries as re-established conclusions;
    # review was right to object.)
    cond = {
        "note": ("conditional summaries within the adopted specification. "
                 "P_nu_ritc_lt_nu_clean is this fit's own-posterior tail-regime "
                 "ordering; floor_hdi95 and k_hdi95 are conditional parameter "
                 "summaries only -- the floor-versus-no-floor and "
                 "pooling-endpoint model comparisons were NOT repeated under "
                 "this treatment, and the bracketed fit cannot re-establish "
                 "them"),
        "P_nu_ritc_lt_nu_clean": float((post["nu_ritc"].values
                                        < post["nu_clean"].values).mean()),
        "floor_hdi95": [params["sd_undiv"]["hdi_2.5"],
                        params["sd_undiv"]["hdi_97.5"]],
        "k_hdi95": [params["k"]["hdi_2.5"], params["k"]["hdi_97.5"]],
    }
    return means, params, diag, draws, cond


def main():
    S, R, H, yr, syn, ritc = load_sample()   # the adopted n=790 sample
    keys = ["%s_%s" % (s, y) for s, y in zip(syn, yr)]
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    t2 = json.load(io.open(SD / "vignettes" / "vignette-2" / "target_transition.json",
                           encoding="utf-8"))
    v2o = (float(t2["old_reserve_size"]), float(t2["old_hhi"]))
    v2n = (float(t2["new_reserve_size"]), float(t2["new_hhi"]))

    fx = fx_map()
    is_usd = np.array([fx.get(k, (False, None))[0] for k in keys])
    rate = np.array([fx.get(k, (False, None))[1] or 1.0 for k in keys])
    R_nominal = np.where(is_usd, R * rate, R)   # undo conversion (as-reported USD)
    rates_used = d["fx_conversion"]["year_end_rates_used"]
    print(f"n={len(S)}  USD={int(is_usd.sum())} ({100*is_usd.mean():.0f}%)  "
          f"mean USD reserve shrink x{np.mean(1/rate[is_usd]):.2f}  "
          f"sampling {CHAINS}x{DRAWS} (tune {TUNE}, target_accept {TARGET_ACCEPT}), "
          f"the adopted configuration")

    out, agreement = {}, None
    for label, Rx in [("FX-converted to GBP (baseline)", R),
                      ("nominal (as-reported)", R_nominal)]:
        means, params, diag, draws, cond = fit_adopted_config(S, Rx, H, yr, ritc)
        o = outputs(S, Rx, H, ritc, means, v2o, v2n)
        out[label] = {**means, "V1_VaR99": o[0], "V1_VaR995": o[1],
                      "V2_change995": o[2], "params": params, "diagnostics": diag,
                      "conditional_fit_summaries": cond}
        print(f"  {label:<32} k={means['k']:.3f} gamma={means['gamma']:.3f} "
              f"floor={means['sd_undiv']:.4f} nu_clean={means['nu_clean']:.2f}  "
              f"V1_99.5={o[1]:.3f}  V2={o[2]:+.3f}  rhat<={diag['max_rhat']:.3f} "
              f"ess>={diag['min_ess_bulk']:.0f} div={diag['divergences']}")
        if label.startswith("FX-converted"):
            ok, rows = check_against_headline(draws)
            report(rows, ok, "FX converted baseline")
            agreement = {"ok": bool(ok), "tolerance_sd": TOL_SD, "rows": rows}
            if not ok:
                raise SystemExit("the converted refit disagrees with the published "
                                 "adopted calibration; refusing to write results")

    conv = out["FX-converted to GBP (baseline)"]
    nom = out["nominal (as-reported)"]
    point_sensitivities = {
        "note": ("point sensitivities of two SEPARATELY fitted posteriors; no "
                 "posterior interval for the between-treatment difference is "
                 "estimated (that would require a declared joint analysis over "
                 "both currency treatments -- pairing separately fitted chains by "
                 "seed or draw index is not a joint posterior). Each fit's own "
                 "parameter HDIs, diagnostics and conditional summaries are under "
                 "fits/<label>"),
        "floor": {"converted": conv["sd_undiv"], "nominal": nom["sd_undiv"],
                  "change": nom["sd_undiv"] - conv["sd_undiv"],
                  "pct_change": 100.0 * (nom["sd_undiv"] / conv["sd_undiv"] - 1.0)},
        "V1_VaR995": {"converted": conv["V1_VaR995"], "nominal": nom["V1_VaR995"],
                      "change": nom["V1_VaR995"] - conv["V1_VaR995"],
                      "pct_change": 100.0 * (nom["V1_VaR995"]
                                             / conv["V1_VaR995"] - 1.0)},
    }
    (SD / "results" / "fx_sensitivity_results.json").write_text(
        json.dumps({"n": int(len(S)), "n_usd": int(is_usd.sum()),
                    "rates": {y: r["usd_per_gbp"] for y, r in rates_used.items()},
                    "rate_source": "Fed H.10 year-end spot (fx_rates_h10.json)",
                    "sampling": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS,
                                 "target_accept": TARGET_ACCEPT, "seed": SEED,
                                 "same_as": "calibrate_dispersion_ritc.py"},
                    "adopted_agreement": agreement,
                    "point_sensitivities": point_sensitivities,
                    "fits": out}, indent=2), encoding="utf-8")
    print("Wrote fx_sensitivity_results.json")


if __name__ == "__main__":
    main()
