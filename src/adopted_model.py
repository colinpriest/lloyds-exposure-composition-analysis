"""The adopted dispersion model, defined once so that no script can fit a different one.

Every "the adopted model, plus X" analysis in this repository used to retype the
likelihood from whichever calibrate_*.py its author happened to open. That is how
check_mean_concentration_bayes came to be built on calibrate_dispersion.py -- the
older SINGLE-REGIME fit, with one common nu and no RITC scale term -- while
describing itself, and being described in the manuscript, as the adopted model. The
error was visible in its own output (gamma = 0.310 against the adopted 0.243) and
still went unnoticed, because nothing compared the two.

The adopted specification is the two-regime fit of calibrate_dispersion_ritc.py:

    S_it     ~ StudentT(nu_it, mu_it, sigma_it)
    nu_it    = nu_clean * exp(-lambda_ritc * 1[RITC])
    sigma_it = exp(s_t + beta_ritc * 1[RITC])
               * sqrt(sd_undiv^2 + sd_div^2 * [(R/500)(1/H)^gamma]^{2(k-1)})
    s_t      ~ Normal(0, tau_s)

with mu_it = 0 in the headline. Callers supply their own mu, which is the only thing
they are allowed to vary; everything else comes from scale_block().

Two guards come with it:

  headline()          - the published posterior, read from the calibration JSON
  check_against_headline() - compares a refit's shared parameters with it and returns
                        the discrepancies, so "I fitted the adopted model" is a
                        checkable claim rather than a comment.

Import this; do not copy the block.

Current status, so that "defined once" is a fact and not an aspiration:
every fitting script builds from scale_block(). The headline calibration calls it
with (R, H, yr, ritc) and nothing else; each sensitivity script departs from the
adopted model only through the block's keyword options (the support of k, a loading
on the scale shock, an extra log-scale term) or through its own likelihood (a
location term, observation weights, a random intercept). test_model_variants.py
enumerates every random variable each script creates and fails on any that is not
its declared departure; paper/audit_numbers.py lists every fitting script on each
build and FAILS the build for one that claims the adopted model without building
from this block.
"""
import io
import json
from pathlib import Path

import numpy as np
import pymc as pm

SD = Path(__file__).resolve().parent.parent
RESULTS = SD / "model" / "exposure_results.json"
RITC_SCAN = SD / "pdf_extraction" / "ritc_scan.json"
HEADLINE_JSON = SD / "model" / "dispersion_calibration_ritc.json"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0

# Shared parameters a location variant must not move by more than this, in units of
# the headline posterior SD. A refit that shifts gamma or k by more than half a
# posterior standard deviation is fitting something else.
TOL_SD = 0.5


def load_sample():
    """The n=790 working sample, with syndicate identifiers and the RITC flag."""
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    syn = np.array([o["syndicate"] for o in recs])
    key = np.array(["%s_%s" % (o["syndicate"], o["year"]) for o in recs])
    occ = {k for k, v in json.load(io.open(RITC_SCAN, encoding="utf-8")).items()
           if v.get("ritc_occurred")}
    ritc = np.array([k in occ for k in key]).astype(float)
    return S, R, H, yr, syn, ritc


K_PRIORS = ("logistic", "normal_0.5", "normal_0.75", "uniform")
SIGMA_UNDERFLOW_FLOOR = 1e-12


def scale_block(R=None, H=None, yr=None, ritc=None, *, logR=None, logH=None,
                yidx=None, n_y=None, k_prior="logistic", record_shock=False,
                shock_loading=None, extra_log_scale=None):
    """Create the adopted scale and tail inside the caller's active pm.Model().

    Returns a dict with `sigma` and `nu_obs` for the likelihood, plus the named
    parameters so a caller can record them for the consistency check, and the
    building blocks (`var`, `log_reff`, `s_y`, `yidx`, `n_y`) a variant composes.

    Called with (R, H, yr, ritc) it is the adopted model exactly; the keyword
    options are the ONLY ways a sensitivity script may depart from it, each one
    the declared dimension of a variant:
      logR/logH/yidx/n_y  the same inputs already transformed (no departure);
      k_prior             the support of k: "logistic" (the adopted bracket) or
                          the unconstrained priors of check_k_unconstrained;
      record_shock        register s_y as a Deterministic for posterior checks;
      shock_loading       callable(log_reff) -> multiplier on the reporting-year
                          scale shock (the size-loaded scale shock);
      extra_log_scale     a tensor added to the log-scale (a proxy covariate).
    Every other departure (a location term, weights, a random intercept) lives in
    the caller's likelihood, outside this block.
    """
    if logR is None:
        years = np.sort(np.unique(yr))
        yidx = np.searchsorted(years, yr)
        n_y = len(years)
        logR = np.log(R / REFERENCE_SIZE)
        logH = np.log(H)

    if k_prior == "logistic":
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
    elif k_prior == "normal_0.5":
        k = pm.Normal("k", 0.5, 0.5)
    elif k_prior == "normal_0.75":
        k = pm.Normal("k", 0.75, 0.5)
    elif k_prior == "uniform":
        k = pm.Uniform("k", -0.5, 2.0)
    else:
        raise ValueError("k_prior must be one of %s" % (K_PRIORS,))
    gamma = pm.HalfNormal("gamma", 1.0)
    log_tot = pm.Normal("log_tot", np.log(0.05), 1.0)
    tot_sd = pm.math.exp(log_tot)
    f = pm.Beta("f", 1.0, 1.0)
    sd_undiv = pm.Deterministic("sd_undiv", tot_sd * pm.math.sqrt(f))
    sd_div = pm.Deterministic("sd_div", tot_sd * pm.math.sqrt(1.0 - f))
    tau_s = pm.HalfNormal("tau_s", 0.5)
    z_s = pm.Normal("z_s", 0.0, 1.0, shape=n_y)
    s_y = tau_s * z_s
    if record_shock:
        s_y = pm.Deterministic("s_y", s_y)

    nu_clean = pm.Gamma("nu_clean", 2.0, 0.1)
    lam = pm.Normal("lambda_ritc", 0.0, 0.7)
    nu_ritc = pm.Deterministic("nu_ritc", nu_clean * pm.math.exp(-lam))
    nu_obs = nu_clean * pm.math.exp(-lam * ritc)
    beta_ritc = pm.Normal("beta_ritc", 0.0, 0.5)

    log_reff = logR - gamma * logH
    var = sd_undiv ** 2 + sd_div ** 2 * pm.math.exp(2.0 * (k - 1.0) * log_reff)
    shock = s_y[yidx]
    if shock_loading is not None:
        shock = shock_loading(log_reff) * shock
    log_scale = shock + beta_ritc * ritc
    if extra_log_scale is not None:
        log_scale = log_scale + extra_log_scale
    sigma = pm.math.exp(log_scale) * pm.math.sqrt(var)
    # An extreme NUTS proposal can drive exp(log_scale) below the smallest
    # double, and the NUMBA backend then raises ZeroDivisionError from the
    # Student-t density instead of returning -inf (a divergent transition). The
    # floor is 1e-12, ten orders of magnitude below any fitted scale, so it never
    # binds in the posterior and leaves every value and gradient there unchanged.
    sigma = pm.math.maximum(sigma, SIGMA_UNDERFLOW_FLOOR)

    return {"sigma": sigma, "nu_obs": nu_obs, "k": k, "gamma": gamma,
            "sd_undiv": sd_undiv, "sd_div": sd_div, "nu_clean": nu_clean,
            "nu_ritc": nu_ritc, "lambda_ritc": lam, "beta_ritc": beta_ritc,
            "tau_s": tau_s, "var": var, "log_reff": log_reff, "s_y": s_y,
            "yidx": yidx, "n_y": n_y}


SHARED = ["k", "gamma", "sd_undiv", "nu_clean", "nu_ritc", "beta_ritc"]


def headline():
    """The published adopted-model posterior."""
    d = json.load(io.open(HEADLINE_JSON, encoding="utf-8"))
    return d["params"]


def check_against_headline(post, tol_sd=TOL_SD):
    """Compare a refit's shared parameters with the published adopted-model fit.

    `post` maps parameter name -> posterior draws. Returns (ok, rows) where each row
    records the refit mean, the headline mean and the gap in headline posterior SDs.
    A location term should barely move these; a different likelihood moves them a lot.
    """
    h = headline()
    rows, ok = [], True
    for p in SHARED:
        if p not in post or p not in h:
            continue
        m = float(np.asarray(post[p]).ravel().mean())
        hm, hsd = float(h[p]["mean"]), float(h[p]["sd"])
        z = abs(m - hm) / hsd if hsd > 0 else 0.0
        rows.append({"param": p, "refit": m, "headline": hm, "gap_in_sd": z})
        if z > tol_sd:
            ok = False
    return ok, rows


def report(rows, ok, label=""):
    print("  shared parameters vs the published adopted fit%s:"
          % ((" (%s)" % label) if label else ""))
    for r in rows:
        flag = "" if r["gap_in_sd"] <= TOL_SD else "   <-- DIFFERENT MODEL?"
        print("    %-11s refit %8.4f   headline %8.4f   gap %.2f sd%s"
              % (r["param"], r["refit"], r["headline"], r["gap_in_sd"], flag))
    print("  consistent with the adopted model: %s" % ("yes" if ok else "NO"))
