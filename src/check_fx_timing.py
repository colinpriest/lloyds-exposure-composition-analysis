"""Does converting the OPENING balance at the CLOSING rate matter?

The manuscript said the one-year offset is "immaterial because R enters only through
the sub-linear ratio R/R_ref". Two things were wrong with that. R/R_ref is linear --
it is the exponent k-1 that attenuates it -- and the sensitivity actually run
(check_currency_entanglement.py) compares sterling-converted against unconverted
NOMINAL figures. That is a different question: it asks whether conversion matters at
all, not whether the DATE of conversion matters. The claim was asserted, not tested.

This tests it. R_{i,t} is the opening reserve of reporting year t, i.e. the position at
31 December of year t-1, but the pipeline converts it at year t's closing rate. So
refit the adopted model with every USD filing's opening balance converted at the
PRIOR year-end rate instead, and compare:

  - the shared parameters against the published posterior;
  - the Vignette 1 stress the paper reports.

Both conversions are defensible -- the closing rate is what the accounts themselves
use, and a reader can check the difference here rather than take "immaterial" on
trust.

Run: python src/check_fx_timing.py
"""
import io
import json

import numpy as np
import pytensor

pytensor.config.mode = "NUMBA"
import arviz as az
import pymc as pm

from adopted_model import (SD, REFERENCE_SIZE, RITC_SCAN, scale_block,
                           check_against_headline, report)
from dispersion_mle import deritc_z, sigma

OUT = SD / "results" / "check_fx_timing_results.json"
FX = SD / "model" / "fx_rates_h10.json"
TARGET = (500.0, 0.17)
SEED = 42
HHI_FLOOR, HHI_CEIL = 0.01, 1.0


def hdi95(x):
    a = np.asarray(x, float).ravel()
    return [float(v) for v in az.hdi(a, hdi_prob=0.95)]


def load():
    """The working sample, plus each filing's currency and applied rate."""
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    rate = np.array([o.get("fx_rate_usd_per_gbp") or 1.0 for o in recs], float)
    usd = np.array([bool(o.get("fx_applied")) for o in recs])
    key = np.array(["%s_%s" % (o["syndicate"], o["year"]) for o in recs])
    occ = {k for k, v in json.load(io.open(RITC_SCAN, encoding="utf-8")).items()
           if v.get("ritc_occurred")}
    ritc = np.array([k in occ for k in key]).astype(float)
    return S, R, H, yr, rate, usd, ritc


def retime(R, yr, rate, usd):
    """Reconvert USD openings at the PRIOR year-end rate.

    The pipeline stores GBP = USD / rate_t. Undo that and redivide by rate_{t-1}: the
    rate in force at the date the opening balance was actually struck.
    """
    ye = json.load(io.open(FX, encoding="utf-8"))["year_end_rates"]
    prior = np.array([ye.get(str(int(y) - 1), {}).get("usd_per_gbp", np.nan)
                      for y in yr], float)
    out = R.copy()
    m = usd & np.isfinite(prior)
    out[m] = (R[m] * rate[m]) / prior[m]
    return out, int(m.sum()), int((usd & ~np.isfinite(prior)).sum())


def fit(S, R, H, yr, ritc):
    with pm.Model():
        b = scale_block(R, H, yr, ritc)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    p = idata.posterior
    names = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "beta_ritc")
    draws = {n: p[n].values.ravel() for n in names}
    s = az.summary(idata, var_names=list(names), hdi_prob=0.95)
    return draws, {"max_rhat": float(s["r_hat"].max()),
                   "divergences": int(idata.sample_stats["diverging"].sum())}


def v1_stress(S, R, H, ritc, d):
    mp = {n: float(np.mean(d[n])) for n in
          ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")}
    sig_i = sigma(R, H, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    sig_q = sigma(np.array([TARGET[0]]), np.array([TARGET[1]]),
                  mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])[0]
    z = deritc_z(S / sig_i, ritc, mp["nu_clean"], mp["nu_ritc"])
    return float(np.percentile(z * sig_q, 99.5, method="linear"))


def main():
    S, R, H, yr, rate, usd, ritc = load()
    R2, n_retimed, n_missing = retime(R, yr, rate, usd)
    moved = np.abs(R2 - R) / R
    print("n=%d  USD filings=%d  re-timed=%d  (no prior-year rate: %d)"
          % (len(S), int(usd.sum()), n_retimed, n_missing))
    print("opening balance moves by %.1f%% on average across re-timed filings, "
          "max %.1f%%" % (100 * moved[moved > 0].mean(), 100 * moved.max()))

    base, dg_b = fit(S, R, H, yr, ritc)
    alt, dg_a = fit(S, R2, H, yr, ritc)

    ok_b, rows_b = check_against_headline(base)
    ok_a, rows_a = check_against_headline(alt)
    print("\nreporting-date conversion (as published):")
    report(rows_b, ok_b)
    print("\nopening-date conversion:")
    report(rows_a, ok_a)

    res = {"n": int(len(S)), "n_usd": int(usd.sum()), "n_retimed": n_retimed,
           "seed": SEED,
           "question": ("does applying the reporting-year CLOSING rate to an OPENING "
                        "balance change the fit? Refits with USD openings converted at "
                        "the prior year-end rate instead."),
           "mean_abs_relative_change_in_R": float(moved[moved > 0].mean()),
           "max_abs_relative_change_in_R": float(moved.max()),
           "reporting_date": {"params": {n: {"mean": float(v.mean()),
                                             "hdi": hdi95(v)}
                                         for n, v in base.items()},
                              "vs_headline": rows_b,
                              "adopted_model_consistent": bool(ok_b),
                              "diagnostics": dg_b},
           "opening_date": {"params": {n: {"mean": float(v.mean()), "hdi": hdi95(v)}
                                       for n, v in alt.items()},
                            "vs_headline": rows_a,
                            "adopted_model_consistent": bool(ok_a),
                            "diagnostics": dg_a}}

    v1b = v1_stress(S, R, H, ritc, base)
    v1a = v1_stress(S, R2, H, ritc, alt)
    res["V1_VaR995"] = {"reporting_date": v1b, "opening_date": v1a,
                        "absolute_change": v1a - v1b,
                        "relative_change": (v1a - v1b) / v1b}

    print("\nparameter                reporting-date     opening-date")
    for n in ("k", "gamma", "sd_undiv", "nu_clean"):
        print("  %-22s %8.4f          %8.4f"
              % (n, base[n].mean(), alt[n].mean()))
    print("  %-22s %8.4f          %8.4f   (%+.1f%%)"
          % ("V1 VaR99.5", v1b, v1a, 100 * res["V1_VaR995"]["relative_change"]))

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\nwritten to", OUT)


if __name__ == "__main__":
    main()
