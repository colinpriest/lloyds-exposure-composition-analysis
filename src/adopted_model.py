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

where 1[RITC] marks the assumed-business regime: an accepted reinsurance to close or a
confirmed inward transfer (assumed_business.py, PLAN R195),
with mu_it = 0 in the headline. Callers supply their own mu, which is the only thing
they are allowed to vary; everything else comes from scale_block().

The headline fits it with the concentration exponent gamma FIXED AT 0 in the likelihood (the author's
decision of 10 October 2026, option B): sigma_it does not depend on H, and the headline transfer operator
(size-only) is this fit's own posterior, a refit and not a zeroing of another fit's draws. The same
specification with gamma ~ HalfNormal(1) is the gamma-free fit (calibrate_dispersion_ritc_gamma_free.py,
GAMMA_FREE_JSON and GAMMA_FREE_DRAWS below): the concentration overlay's only source, a labelled
sensitivity. scale_block()'s default is the headline's gamma_prior="fixed_0"; a script that fits the
gamma-free model says so with gamma_prior="halfnormal".

Two guards come with it:

  headline()          - the published posterior, read from the calibration JSON
  check_against_headline() - compares a refit's shared parameters with it (or, with
                        reference=GAMMA_FREE_JSON, with the gamma-free fit) and returns
                        the discrepancies, so "I fitted the adopted model" is a
                        checkable claim rather than a comment.

Import this; do not copy the block.

Current status, so that "defined once" is a fact and not an aspiration:
every fitting script builds from scale_block(). The headline calibration calls it
with (R, H, yr, ritc) and nothing else; each sensitivity script departs from the
adopted model only through the block's keyword options (the support of k, a fitted
gamma, a loading on the scale shock, an extra log-scale term) or through its own likelihood (a
location term, observation weights, a random intercept). test_model_variants.py
enumerates every random variable each script creates and fails on any that is not
its declared departure; paper/audit_numbers.py lists every fitting script on each
build and FAILS the build for one that claims the adopted model without building
from this block.
"""
import io
import os
import json
from pathlib import Path

import numpy as np
import pymc as pm
import assumed_business

SD = Path(__file__).resolve().parent.parent
RESULTS = SD / "model" / "exposure_results.json"
RITC_SCAN = SD / "pdf_extraction" / "ritc_scan.json"
#: the headline fit, gamma = 0 in the likelihood (calibrate_dispersion_ritc.py)
HEADLINE_JSON = SD / "model" / "dispersion_calibration_ritc.json"
HEADLINE_DRAWS = SD / "model" / "dispersion_posterior_draws_ritc.npz"
#: the gamma-free fit, gamma ~ HalfNormal(1) (calibrate_dispersion_ritc_gamma_free.py): the overlay's source
GAMMA_FREE_JSON = SD / "model" / "dispersion_calibration_ritc_gamma_free.json"
GAMMA_FREE_DRAWS = SD / "model" / "dispersion_posterior_draws_ritc_gamma_free.npz"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0

# Shared parameters a location variant must not move by more than this, in units of
# the reference posterior SD. A refit that shifts k or the floor by more than half a
# posterior standard deviation is fitting something else.
TOL_SD = 0.5


#: how many chains sample in parallel, one setting for every fit. The outputs do not
#: depend on it (round 53 compared a parallel and a sequential run of the manifest:
#: identical), but on Windows each chain is a spawned process whose cost is paid per
#: fit, and the manifest is mostly many short fits, so the default is sequential;
#: PYMC_CORES=4 parallelises the chains (see "Reproducing the paper's results" in
#: the README). Replicate-level parallelism (PROXY_WORKERS) is where the time goes.
SAMPLE_CORES = int(os.environ.get("PYMC_CORES", "1"))

def load_sample():
    """The gross-basis working sample (its size is whatever the loader retains; read it
    from exposure_results.json, never from prose), with syndicate
    identifiers and the assumed-business flag: RITC or a confirmed inward transfer
    (assumed_business.py, PLAN R195)."""
    with io.open(RESULTS, encoding="utf-8") as _fh:
        d = json.load(_fh)
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    syn = np.array([o["syndicate"] for o in recs])
    key = np.array(["%s_%s" % (o["syndicate"], o["year"]) for o in recs])
    occ = assumed_business.keys()
    ritc = np.array([k in occ for k in key]).astype(float)
    return S, R, H, yr, syn, ritc


#: the support of k. "logistic" is the adopted prior, k = 1/2 + 1/2 logistic(theta), theta ~ N(0, 1.5);
#: "fixed_0.5" fixes k at the bracket's lower end; "logistic_0.25" and "logistic_0" widen the support to
#: k = k_lo + (1 - k_lo) logistic(theta) with k_lo = 0.25 and 0 (the same theta prior and free variables), so
#: that check_k_support.py can measure what the data say about k below 1/2.
K_PRIORS = ("logistic", "fixed_0.5", "logistic_0.25", "logistic_0")
#: the lower end of the support of k under each logistic prior
K_LOWER = {"logistic": 0.5, "logistic_0.25": 0.25, "logistic_0": 0.0}
GAMMA_PRIORS = ("halfnormal", "fixed_0")
SIGMA_UNDERFLOW_FLOOR = 1e-12


def scale_block(R=None, H=None, yr=None, ritc=None, *, logR=None, logH=None,
                yidx=None, n_y=None, k_prior="logistic", gamma_prior="fixed_0", record_shock=False,
                shock_loading=None, extra_log_scale=None):
    """Create the adopted scale and tail inside the caller's active pm.Model().

    Returns a dict with `sigma` and `nu_obs` for the likelihood, plus the named
    parameters so a caller can record them for the consistency check, and the
    building blocks (`var`, `log_reff`, `s_y`, `yidx`, `n_y`) a variant composes.

    Called with (R, H, yr, ritc) it is the adopted model exactly; the keyword
    options are the ONLY ways a sensitivity script may depart from it, each one
    the declared dimension of a variant:
      logR/logH/yidx/n_y  the same inputs already transformed (no departure);
      k_prior             k on the bracket [1/2, 1], the adopted prior's support ("logistic",
                          the adopted prior; the bracket is a modelling choice from the
                          finite-variance benchmarks, not a universal bound), fixed at the
                          bracket's lower end ("fixed_0.5", the
                          sensitivity of check_k_half_sensitivity), or on a wider support
                          k = k_lo + (1 - k_lo) logistic(theta), theta ~ N(0, 1.5), with k_lo
                          0.25 or 0 ("logistic_0.25", "logistic_0": check_k_support);
      gamma_prior         the concentration exponent as the constant 0 in the likelihood
                          ("fixed_0", the headline since 10 October 2026: no gamma random
                          variable, log_reff = logR; the returned `gamma` is 0.0) or fitted,
                          gamma ~ HalfNormal(1) ("halfnormal", the gamma-free fit that is the
                          concentration overlay's source and the subject of
                          check_gamma_free_fit);
      record_shock       register s_y as a Deterministic for posterior checks;
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

    # k = 1/2 is finite-variance independent sqrt-N pooling and k = 1 is comonotonic pooling. The adopted prior
    # restricts k to [1/2, 1] by its support: a modelling choice based on those finite-variance benchmarks, not a
    # universal bound (heavier-tailed, infinite-variance blocks can decline outside it). The fixed option sits at
    # the bracket's lower end.
    if k_prior == "logistic":
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", 0.5 + 0.5 * pm.math.sigmoid(theta))
    elif k_prior == "fixed_0.5":
        k = 0.5
    elif k_prior in K_LOWER:
        k_lo = K_LOWER[k_prior]
        theta = pm.Normal("theta", 0.0, 1.5)
        k = pm.Deterministic("k", k_lo + (1.0 - k_lo) * pm.math.sigmoid(theta))
    else:
        raise ValueError("k_prior must be one of %s" % (K_PRIORS,))
    if gamma_prior == "halfnormal":
        gamma = pm.HalfNormal("gamma", 1.0)
    elif gamma_prior == "fixed_0":
        gamma = 0.0
    else:
        raise ValueError("gamma_prior must be one of %s" % (GAMMA_PRIORS,))
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


def sigma_numeric(R, H, ritc, params=None, *, s_y=None, yidx=None):
    """The adopted model's conditional scale as NUMBERS, at fixed parameter values.

    The same algebra as scale_block's `sigma`, for a diagnostic that needs sigma_it outside a
    pm.Model(): a residual is only a residual of THIS model if it is divided by this. The two are
    held in step by src/test_serial_dependence_claims.py (TestTheNumericScaleIsTheModelsOwn), which
    evaluates the symbolic block at the same parameter values and compares, so this is not a second
    definition of the scale. (Until the review of 29 September 2026 this docstring named a test
    file that did not exist; src/test_docstring_references.py now resolves every test file a
    source names.)

        sigma_it = exp(s_t + beta_ritc 1[RITC])
                   * sqrt(sd_undiv^2 + sd_div^2 [(R/500)(1/H)^gamma]^{2(k-1)})

    `params` defaults to the published posterior means. The headline fit has no gamma (it is 0 in the
    likelihood), so a mapping without one is read at gamma = 0. The reporting-year shock s_t is a random
    effect the calibration does not persist per year, so it is left out unless the caller supplies
    `s_y` and `yidx`; a diagnostic that must condition on the year states how it did so.
    """
    p = params if params is not None else {n: v["mean"] for n, v in headline().items()}
    R = np.asarray(R, dtype=float)
    H = np.clip(np.asarray(H, dtype=float), HHI_FLOOR, HHI_CEIL)
    ritc = np.asarray(ritc, dtype=float)
    log_reff = np.log(R / REFERENCE_SIZE) - p.get("gamma", 0.0) * np.log(H)
    var = p["sd_undiv"] ** 2 + p["sd_div"] ** 2 * np.exp(2.0 * (p["k"] - 1.0) * log_reff)
    log_scale = p["beta_ritc"] * ritc
    if s_y is not None or yidx is not None:
        if s_y is None or yidx is None:
            raise ValueError("a year shock needs both s_y and yidx")
        log_scale = log_scale + np.asarray(s_y, dtype=float)[np.asarray(yidx)]
    return np.exp(log_scale) * np.sqrt(var)


# every scale and tail parameter the published fit reports (round 56: sd_div, lambda_ritc
# and tau_s were not compared, so a refit could move sd_div a posterior SD and still pass). gamma left the
# list with option B (10 October 2026): the headline fixes it at 0, so it is not a fitted parameter to compare;
# the gamma-free fit's gamma is compared where that fit is the reference (GAMMA_FREE_SHARED).
SHARED = ["k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s"]
#: the parameters a refit of the gamma-free model is compared on, against GAMMA_FREE_JSON
GAMMA_FREE_SHARED = ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s"]


def headline(reference=HEADLINE_JSON):
    """The published adopted-model posterior (the gamma = 0 headline), or with `reference` another calibration's."""
    with io.open(reference, encoding="utf-8") as _fh:
        d = json.load(_fh)
    return d["params"]


def posterior_draws(idata, names):
    """{name: the posterior draws, flattened} for `names`, with gamma as exact zeros when the fit has none (the
    headline fixes it at 0 in the likelihood, so the posterior carries no gamma variable)."""
    post = idata.posterior
    out = {}
    for n in names:
        if n == "gamma" and "gamma" not in post:
            out[n] = np.zeros(post["lambda_ritc"].values.size)
        else:
            out[n] = post[n].values.ravel()
    return out


def check_against_headline(post, tol_sd=TOL_SD, reference=HEADLINE_JSON):
    """Compare a refit's shared parameters with the published adopted-model fit.

    `post` maps parameter name -> posterior draws. Returns (ok, rows) where each row
    records the refit mean, the reference mean and the gap in reference posterior SDs.
    A location term should barely move these; a different likelihood moves them a lot.
    The reference is the gamma = 0 headline (SHARED); with reference=GAMMA_FREE_JSON a refit of the
    gamma-free model is compared with that fit, gamma included (GAMMA_FREE_SHARED). A parameter whose
    reference posterior SD is 0 passes only at the reference value exactly: a gap from a point mass is
    infinitely many SDs, not none (until 10 October 2026 any gap there read as 0).
    """
    h = headline(reference)
    names = GAMMA_FREE_SHARED if os.path.abspath(str(reference)) == os.path.abspath(str(GAMMA_FREE_JSON)) else SHARED
    rows, ok = [], True
    for p in names:
        if p not in post or p not in h:
            continue
        m = float(np.asarray(post[p]).ravel().mean())
        hm, hsd = float(h[p]["mean"]), float(h[p]["sd"])
        if hsd > 0:
            z = abs(m - hm) / hsd
        else:
            z = 0.0 if m == hm else float("inf")
        rows.append({"param": p, "refit": m, "headline": hm, "gap_in_sd": z})
        if z > tol_sd:
            ok = False
    return ok, rows


def report(rows, ok, label=""):
    print("  shared parameters vs the published fit%s:"
          % ((" (%s)" % label) if label else ""))
    for r in rows:
        flag = "" if r["gap_in_sd"] <= TOL_SD else "   <-- DIFFERENT MODEL?"
        print("    %-11s refit %8.4f   headline %8.4f   gap %.2f sd%s"
              % (r["param"], r["refit"], r["headline"], r["gap_in_sd"], flag))
    print("  consistent with the adopted model: %s" % ("yes" if ok else "NO"))
